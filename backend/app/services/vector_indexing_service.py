from typing import List, Dict, Any

from app.core.lock import faiss_lock
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.repositories.vector_mapping_repository import (
    VectorMappingRepository,
)


class VectorIndexingService:
    """
    Orchestrates the indexing of document chunks:
    1. Idempotently checks if the document is already indexed.
    2. Generates embeddings in parallel (outside lock).
    3. Acquires distributed lock to serialize FAISS mutations.
    4. Reloads latest FAISS index, adds vectors, creates mappings, and saves index.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        faiss_service: FAISSService,
        vector_mapping_repository: VectorMappingRepository,
    ):
        self.embedding_service = embedding_service
        self.faiss_service = faiss_service
        self.vector_mapping_repository = (
            vector_mapping_repository
        )

    def index_chunks(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        force_reindex: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Index chunks safely and idempotently.
        If document chunks are already indexed, returns existing mappings
        without duplicating vectors in FAISS.
        """

        if not chunks:
            return []

        doc_id_str = str(document_id)

        # 1. Fast idempotency check before computing embeddings
        existing_mappings = self.vector_mapping_repository.get_by_document_id(doc_id_str)
        if existing_mappings and len(existing_mappings) == len(chunks) and not force_reindex:
            return existing_mappings

        # 2. Step outside lock: Generate embeddings for all chunks in batch
        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        embeddings = (
            self.embedding_service.generate_embeddings(texts)
        )

        # 3. Step inside lock: Synchronize latest index state, assign IDs, and save
        with faiss_lock():
            # Double-check existing mappings under lock to avoid race conditions
            existing_mappings = self.vector_mapping_repository.get_by_document_id(doc_id_str)
            if existing_mappings and len(existing_mappings) == len(chunks) and not force_reindex:
                return existing_mappings

            # Synchronize in-memory index with latest disk state
            self.faiss_service.load()

            # If force re-indexing, remove old mappings
            if existing_mappings:
                self.vector_mapping_repository.delete_by_document_id(doc_id_str)

            faiss_ids = (
                self.faiss_service.add_embeddings(
                    embeddings
                )
            )

            mappings = []
            for chunk, faiss_id in zip(chunks, faiss_ids):
                mappings.append(
                    {
                        "faiss_id": faiss_id,
                        "document_id": doc_id_str,
                        "chunk_id": chunk["chunk_id"],
                    }
                )

            self.vector_mapping_repository.insert_mappings(
                mappings
            )

        return mappings
