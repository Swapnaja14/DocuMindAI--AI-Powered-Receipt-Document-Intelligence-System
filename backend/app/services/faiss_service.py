import faiss
import numpy as np
from pathlib import Path
from typing import List, Tuple


class FAISSService:
    """
    Manages the FAISS vector index for document chunk embeddings.
    """

    DIMENSION = 384

    def __init__(self, index_path: str = "storage/faiss/index.faiss"):
        self.index_path = Path(index_path)

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.index = faiss.IndexFlatIP(self.DIMENSION)

    def add_embeddings(
        self,
        embeddings: List[List[float]]
    ) -> List[int]:
        """
        Add embeddings to the FAISS index.

        Returns the FAISS vector IDs assigned to the embeddings.
        """

        if not embeddings:
            return []

        vectors = np.asarray(
            embeddings,
            dtype=np.float32
        )

        if vectors.ndim != 2:
            raise ValueError(
                "Embeddings must be a 2-dimensional array"
            )

        if vectors.shape[1] != self.DIMENSION:
            raise ValueError(
                f"Expected embedding dimension "
                f"{self.DIMENSION}, "
                f"got {vectors.shape[1]}"
            )

        start_id = self.index.ntotal

        self.index.add(vectors)

        return list(
            range(
                start_id,
                start_id + len(embeddings)
            )
        )

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Search the FAISS index for the most similar vectors.

        Returns:
            [(vector_id, similarity_score), ...]
        """

        if self.index.ntotal == 0:
            return []

        query_vector = np.asarray(
            [query_embedding],
            dtype=np.float32
        )

        if query_vector.shape[1] != self.DIMENSION:
            raise ValueError(
                f"Expected query dimension "
                f"{self.DIMENSION}, "
                f"got {query_vector.shape[1]}"
            )

        top_k = min(top_k, self.index.ntotal)

        scores, indices = self.index.search(
            query_vector,
            top_k
        )

        return [
            (int(vector_id), float(score))
            for vector_id, score
            in zip(indices[0], scores[0])
        ]

    def save(self) -> None:
        """
        Persist the FAISS index to disk.
        """

        faiss.write_index(
            self.index,
            str(self.index_path)
        )

    def load(self) -> None:
        """
        Load the FAISS index from disk if it exists.
        """

        if self.index_path.exists():
            self.index = faiss.read_index(
                str(self.index_path)
            )

    def count(self) -> int:
        """
        Return the number of vectors currently indexed.
        """

        return self.index.ntotal
