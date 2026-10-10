import logging
from typing import Any, Dict, Set
from app.repositories.chunk_repository import ChunkRepository
from app.services.faiss_service import FAISSService

logger = logging.getLogger(__name__)


class FAISSIndexService:
    """
    Synchronizes existing MongoDB chunk embeddings into the FAISS vector index,
    performs bidirectional MongoDB <-> FAISS consistency checks,
    and provides recovery workflows for stale or missing embeddings.
    """

    def __init__(
        self,
        chunk_repository: ChunkRepository,
        faiss_service: FAISSService,
    ):
        self.chunk_repository = chunk_repository
        self.faiss_service = faiss_service

    def check_consistency(self) -> Dict[str, Any]:
        """
        Perform a bidirectional audit between MongoDB chunk embeddings and FAISS index:
        1. MongoDB chunks with valid embeddings.
        2. FAISS vector IDs and mapping entries.
        3. Chunk IDs missing from FAISS (present in MongoDB but absent in FAISS).
        4. Stale FAISS entries (present in FAISS but deleted/absent in MongoDB).
        """
        self.faiss_service.load()
        mongo_chunks = self.chunk_repository.get_chunks_with_embeddings()
        mongo_chunk_ids: Set[str] = {
            str(c.get("chunk_id") or c["_id"])
            for c in mongo_chunks
        }

        faiss_chunk_ids: Set[str] = set(self.faiss_service.id_to_chunk_id.values())
        faiss_vector_count = self.faiss_service.count()
        mapping_count = len(self.faiss_service.id_to_chunk_id)

        missing_in_faiss = sorted(list(mongo_chunk_ids - faiss_chunk_ids))
        stale_in_faiss = sorted(list(faiss_chunk_ids - mongo_chunk_ids))
        internal_mismatch = (faiss_vector_count != mapping_count)

        is_consistent = (
            len(missing_in_faiss) == 0
            and len(stale_in_faiss) == 0
            and not internal_mismatch
            and faiss_vector_count == len(mongo_chunk_ids)
        )

        return {
            "consistent": is_consistent,
            "mongo_embeddings_count": len(mongo_chunk_ids),
            "faiss_vector_count": faiss_vector_count,
            "faiss_mapping_count": mapping_count,
            "missing_in_faiss_count": len(missing_in_faiss),
            "missing_in_faiss_ids": missing_in_faiss,
            "stale_in_faiss_count": len(stale_in_faiss),
            "stale_in_faiss_ids": stale_in_faiss,
            "internal_mismatch": internal_mismatch,
        }

    def build_index(self, force_clean: bool = False) -> Dict[str, Any]:
        """
        Read all chunks with embeddings from MongoDB and add them to FAISS.
        If force_clean is True, clears existing index first to purge stale vectors.
        """
        if force_clean:
            self.faiss_service.clear()

        chunks = (
            self.chunk_repository
            .get_chunks_with_embeddings()
        )

        vectors = []

        for chunk in chunks:
            # Use chunk_id if available, falling back to MongoDB _id
            chunk_identifier = chunk.get("chunk_id") or str(chunk["_id"])
            vectors.append(
                {
                    "chunk_id": str(chunk_identifier),
                    "embedding": chunk["embedding"],
                }
            )

        if vectors:
            self.faiss_service.add_embeddings(vectors)
        elif force_clean:
            self.faiss_service.clear()

        return self.faiss_service.status()

    def rebuild_index(self) -> Dict[str, Any]:
        """
        Full recovery procedure: Cleanly wipes stale FAISS vectors and rebuilds
        exclusively from active MongoDB chunk embeddings.
        Returns the rebuilt status and post-rebuild consistency report.
        """
        status = self.build_index(force_clean=True)
        consistency = self.check_consistency()
        return {
            "status": status,
            "consistency": consistency,
        }

