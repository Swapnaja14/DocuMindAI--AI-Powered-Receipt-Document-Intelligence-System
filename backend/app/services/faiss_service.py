import json
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from datetime import datetime, timezone

import faiss
import numpy as np

logger = logging.getLogger(__name__)


class FAISSService:
    """
    Manages the FAISS vector index and the mapping between
    FAISS integer IDs and MongoDB chunk IDs.
    
    Implements crash-safe persistence:
    - Writes new index, mapping, and manifest to temporary files first.
    - Validates both files (structural integrity & count matching) before publishing.
    - Atomically replaces active files and keeps previous valid snapshots (.bak).
    - Automatically detects index/mapping corruption or mismatch on load and recovers safely from backup.
    """

    def __init__(
        self,
        index_path: str = "storage/faiss/chunks.index",
        mapping_path: str = "storage/faiss/chunk_mapping.json",
        manifest_path: Optional[str] = None,
    ):
        self.index_path = Path(index_path)
        self.mapping_path = Path(mapping_path)
        if manifest_path:
            self.manifest_path = Path(manifest_path)
        else:
            self.manifest_path = self.index_path.parent / "manifest.json"

        self.backup_index_path = self.index_path.with_name(f"{self.index_path.name}.bak")
        self.backup_mapping_path = self.mapping_path.with_name(f"{self.mapping_path.name}.bak")
        self.backup_manifest_path = self.manifest_path.with_name(f"{self.manifest_path.name}.bak")

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.index = None
        self.id_to_chunk_id: Dict[str, str] = {}
        self.chunk_id_to_id: Dict[str, int] = {}

        self._load()

    def _validate_pair(
        self,
        idx_path: Path,
        map_path: Path,
        man_path: Optional[Path] = None,
    ) -> Tuple[Optional[Any], Optional[Dict[str, str]]]:
        """
        Validate that index file and mapping file exist, are non-corrupt,
        and have matching vector and chunk mapping counts.
        """
        if not idx_path.exists() or not map_path.exists():
            return None, None

        try:
            loaded_index = faiss.read_index(str(idx_path))
        except Exception as err:
            logger.warning("Failed to read FAISS index at %s: %s", idx_path, err)
            return None, None

        try:
            with open(map_path, "r", encoding="utf-8") as f:
                loaded_mapping = json.load(f)
        except Exception as err:
            logger.warning("Failed to read mapping file at %s: %s", map_path, err)
            return None, None

        if not isinstance(loaded_mapping, dict):
            logger.warning("Mapping at %s is not a dictionary", map_path)
            return None, None

        if loaded_index.ntotal != len(loaded_mapping):
            logger.warning(
                "Count mismatch between index (%d vectors) and mapping (%d entries) at %s",
                loaded_index.ntotal,
                len(loaded_mapping),
                idx_path,
            )
            return None, None

        if man_path and man_path.exists():
            try:
                with open(man_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if manifest.get("total_vectors") is not None and manifest["total_vectors"] != loaded_index.ntotal:
                    logger.warning("Manifest total_vectors mismatch at %s", man_path)
                    return None, None
            except Exception as err:
                logger.warning("Failed to read manifest file at %s: %s", man_path, err)

        return loaded_index, loaded_mapping

    def _load(self):
        """
        Load an existing FAISS index and ID mapping.
        Detects partial/interrupted saves or corrupted files,
        and automatically recovers from the previous valid snapshot (.bak).
        """
        # 1. Try loading primary files
        primary_idx, primary_map = self._validate_pair(
            self.index_path,
            self.mapping_path,
            self.manifest_path,
        )

        if primary_idx is not None and primary_map is not None:
            self.index = primary_idx
            self.id_to_chunk_id = primary_map
            self.chunk_id_to_id = {
                chunk_id: int(faiss_id)
                for faiss_id, chunk_id in self.id_to_chunk_id.items()
            }
            return

        # 2. If primary files exist but are corrupted/mismatched, try recovering from backup
        has_primary = self.index_path.exists() or self.mapping_path.exists()
        if has_primary:
            logger.warning(
                "Primary FAISS index or mapping corrupted/mismatched. Attempting recovery from backup..."
            )
            backup_idx, backup_map = self._validate_pair(
                self.backup_index_path,
                self.backup_mapping_path,
                self.backup_manifest_path,
            )

            if backup_idx is not None and backup_map is not None:
                logger.info("Successfully recovered FAISS index from backup.")
                self.index = backup_idx
                self.id_to_chunk_id = backup_map
                self.chunk_id_to_id = {
                    chunk_id: int(faiss_id)
                    for faiss_id, chunk_id in self.id_to_chunk_id.items()
                }
                # Restore backup files to primary location
                self._restore_from_backup()
                return

        # 3. Otherwise start with empty uninitialized state
        self.index = None
        self.id_to_chunk_id = {}
        self.chunk_id_to_id = {}

    def _restore_from_backup(self):
        """Restore backup snapshot files to primary paths."""
        try:
            if self.backup_index_path.exists():
                shutil.copy2(str(self.backup_index_path), str(self.index_path))
            if self.backup_mapping_path.exists():
                shutil.copy2(str(self.backup_mapping_path), str(self.mapping_path))
            if self.backup_manifest_path.exists():
                shutil.copy2(str(self.backup_manifest_path), str(self.manifest_path))
        except Exception as err:
            logger.error("Failed to copy backup files to primary paths: %s", err)

    def _create_index(self, dimension: int):
        """
        Create a cosine-similarity FAISS index.

        Cosine similarity is implemented as:
            normalized vectors + inner product.
        """
        base_index = faiss.IndexFlatIP(dimension)
        self.index = faiss.IndexIDMap2(base_index)

    def _validate_dimension(self, vector):
        """
        Validate that the input vector matches the expected FAISS index dimensionality.
        """
        if self.index is None:
            return

        expected = self.index.d
        actual = vector.shape[1]

        if expected != actual:
            raise ValueError(
                f"Embedding dimension mismatch. "
                f"FAISS expects {expected}, "
                f"but received {actual}."
            )

    def _save(self):
        """
        Persist FAISS index, ID mapping, and manifest in a crash-safe atomic manner.
        1. Write to temporary files.
        2. Validate the temporary snapshot.
        3. Back up current primary files.
        4. Atomically replace active files.
        """
        if self.index is None:
            return

        tmp_id = uuid.uuid4().hex
        tmp_index_path = self.index_path.parent / f"{self.index_path.name}.tmp.{tmp_id}"
        tmp_mapping_path = self.mapping_path.parent / f"{self.mapping_path.name}.tmp.{tmp_id}"
        tmp_manifest_path = self.manifest_path.parent / f"{self.manifest_path.name}.tmp.{tmp_id}"

        manifest_data = {
            "version": tmp_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_vectors": self.index.ntotal,
            "mapped_chunks": len(self.id_to_chunk_id),
            "index_file": self.index_path.name,
            "mapping_file": self.mapping_path.name,
        }

        try:
            # 1. Write to temporary files
            faiss.write_index(self.index, str(tmp_index_path))

            with open(tmp_mapping_path, "w", encoding="utf-8") as file:
                json.dump(self.id_to_chunk_id, file, indent=2)

            with open(tmp_manifest_path, "w", encoding="utf-8") as file:
                json.dump(manifest_data, file, indent=2)

            # 2. Validate temporary snapshot before publishing
            val_idx, val_map = self._validate_pair(
                tmp_index_path,
                tmp_mapping_path,
                tmp_manifest_path,
            )
            if val_idx is None or val_map is None:
                raise RuntimeError("FAISS persistence validation failed for temporary snapshot files.")

            # 3. Preserve existing valid primary snapshot as backup
            if self.index_path.exists() and self.mapping_path.exists():
                try:
                    shutil.copy2(str(self.index_path), str(self.backup_index_path))
                    shutil.copy2(str(self.mapping_path), str(self.backup_mapping_path))
                    if self.manifest_path.exists():
                        shutil.copy2(str(self.manifest_path), str(self.backup_manifest_path))
                except Exception as b_err:
                    logger.warning("Failed to create snapshot backup: %s", b_err)

            # 4. Atomically publish the new validated snapshot
            os.replace(str(tmp_index_path), str(self.index_path))
            os.replace(str(tmp_mapping_path), str(self.mapping_path))
            os.replace(str(tmp_manifest_path), str(self.manifest_path))

        except Exception as e:
            # Clean up temporary files on failure
            for tmp_file in [tmp_index_path, tmp_mapping_path, tmp_manifest_path]:
                if tmp_file.exists():
                    try:
                        tmp_file.unlink()
                    except Exception:
                        pass
            raise e

    def add_embedding(
        self,
        chunk_id: str,
        embedding: list[float],
    ) -> int:
        """
        Add one chunk embedding to FAISS.
        Returns the assigned FAISS integer ID.
        """
        chunk_id_str = str(chunk_id)
        if chunk_id_str in self.chunk_id_to_id:
            return self.chunk_id_to_id[chunk_id_str]

        vector = np.asarray(
            embedding,
            dtype="float32",
        ).reshape(1, -1)

        if self.index is None:
            self._create_index(vector.shape[1])
        else:
            self._validate_dimension(vector)

        faiss.normalize_L2(vector)

        faiss_id = self.index.ntotal

        ids = np.array(
            [faiss_id],
            dtype="int64",
        )

        self.index.add_with_ids(
            vector,
            ids,
        )

        self.id_to_chunk_id[str(faiss_id)] = chunk_id_str
        self.chunk_id_to_id[chunk_id_str] = faiss_id

        self._save()
        return faiss_id

    def add_embeddings(
        self,
        chunks: Union[List[Dict[str, Any]], List[List[float]], np.ndarray],
    ) -> List[int]:
        """
        Add multiple chunk embeddings.
        Supports:
        - List of dicts: [{"chunk_id": "...", "embedding": [...]}]
        - List of embedding vectors: [[...], [...]]
        - Numpy array of embeddings.
        
        Returns the list of assigned FAISS integer IDs.
        """
        if chunks is None or len(chunks) == 0:
            return []

        is_dict_list = isinstance(chunks, list) and len(chunks) > 0 and isinstance(chunks[0], dict)

        if is_dict_list:
            new_chunks = [
                chunk
                for chunk in chunks
                if chunk.get("chunk_id") is None or str(chunk.get("chunk_id")) not in self.chunk_id_to_id
            ]

            if not new_chunks:
                return [
                    self.chunk_id_to_id[str(chunk["chunk_id"])]
                    for chunk in chunks
                    if "chunk_id" in chunk and str(chunk["chunk_id"]) in self.chunk_id_to_id
                ]

            raw_vectors = [chunk["embedding"] for chunk in new_chunks]
            chunk_ids = [chunk.get("chunk_id") for chunk in new_chunks]
        else:
            new_chunks = chunks
            raw_vectors = chunks
            chunk_ids = [None] * len(chunks)

        vectors = np.asarray(
            raw_vectors,
            dtype="float32",
        )
        if len(vectors.shape) == 1:
            vectors = vectors.reshape(1, -1)

        if self.index is None:
            self._create_index(vectors.shape[1])
        else:
            self._validate_dimension(vectors)

        faiss.normalize_L2(vectors)

        start_id = self.index.ntotal

        ids = np.arange(
            start_id,
            start_id + len(new_chunks),
            dtype="int64",
        )

        self.index.add_with_ids(
            vectors,
            ids,
        )

        assigned_ids = []
        for faiss_id, c_id in zip(ids, chunk_ids):
            int_id = int(faiss_id)
            assigned_ids.append(int_id)
            chunk_key = str(c_id) if c_id is not None else str(int_id)
            self.id_to_chunk_id[str(int_id)] = chunk_key
            if c_id is not None:
                self.chunk_id_to_id[str(c_id)] = int_id
            else:
                self.chunk_id_to_id[str(int_id)] = int_id

        self._save()
        return assigned_ids

    def remove_chunk_ids(self, chunk_ids: list[str]):
        """
        Remove vectors associated with the specified chunk IDs from the FAISS index.
        """
        if self.index is None or not chunk_ids:
            return

        faiss_ids = []
        for chunk_id in chunk_ids:
            str_id = str(chunk_id)
            if str_id in self.chunk_id_to_id:
                faiss_id = self.chunk_id_to_id[str_id]
                faiss_ids.append(faiss_id)
                del self.chunk_id_to_id[str_id]
                self.id_to_chunk_id.pop(str(faiss_id), None)

        if faiss_ids:
            ids_array = np.array(faiss_ids, dtype="int64")
            self.index.remove_ids(ids_array)
            self._save()

    def remove_chunk_id(self, chunk_id: str):
        """
        Remove a single vector associated with chunk_id from FAISS.
        """
        self.remove_chunk_ids([chunk_id])

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ):
        """
        Search FAISS using a query embedding.

        Returns:
            [
                {
                    "chunk_id": "...",
                    "score": 0.91
                }
            ]
        """
        if self.index is None:
            return []

        if self.index.ntotal == 0:
            return []

        query_vector = np.asarray(
            query_embedding,
            dtype="float32",
        ).reshape(1, -1)

        self._validate_dimension(query_vector)

        faiss.normalize_L2(query_vector)

        top_k = min(
            top_k,
            self.index.ntotal,
        )

        scores, ids = self.index.search(
            query_vector,
            top_k,
        )

        results = []

        for score, faiss_id in zip(
            scores[0],
            ids[0],
        ):
            if faiss_id == -1:
                continue

            chunk_id = self.id_to_chunk_id.get(
                str(int(faiss_id))
            )

            if chunk_id is None:
                continue

            results.append(
                {
                    "chunk_id": chunk_id,
                    "score": float(score),
                }
            )

        return results

    def clear(self):
        """
        Reset in-memory FAISS index and ID mappings.
        """
        self.index = None
        self.id_to_chunk_id = {}
        self.chunk_id_to_id = {}

    def count(self) -> int:
        """Return total number of vectors in FAISS."""
        return self.index.ntotal if self.index is not None else 0

    def load(self):
        """Load index from disk."""
        self._load()

    def save(self):
        """Save index to disk."""
        self._save()

    def status(self):
        """
        Return the operational status and consistency statistics of the FAISS index.
        """
        return {
            "loaded": self.index is not None,
            "total_vectors": (
                self.index.ntotal
                if self.index is not None
                else 0
            ),
            "mapped_chunks": len(
                self.id_to_chunk_id
            ),
        }


