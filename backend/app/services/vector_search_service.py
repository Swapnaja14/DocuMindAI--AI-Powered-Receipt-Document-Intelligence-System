from typing import List, Dict, Any, Optional

from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.repositories.vector_mapping_repository import (
    VectorMappingRepository,
)
from app.repositories.chunk_repository import ChunkRepository


class VectorSearchService:

    def __init__(
        self,
        embedding_service: EmbeddingService,
        faiss_service: FAISSService,
        vector_mapping_repository: VectorMappingRepository,
        chunk_repository: ChunkRepository,
    ):
        self.embedding_service = embedding_service
        self.faiss_service = faiss_service
        self.vector_mapping_repository = (
            vector_mapping_repository
        )
        self.chunk_repository = chunk_repository

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search relevant chunks for a given query, with optional document filtering
        and similarity threshold.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if self.faiss_service.count() == 0:
            return []

        # Over-fetch candidate pool from FAISS when document-level filtering is active
        candidate_k = max(top_k * 4, 20) if document_id else top_k

        # 1. Convert query into embedding
        query_embedding = (
            self.embedding_service.generate_embedding(
                query
            )
        )

        # 2. Search FAISS
        faiss_results = self.faiss_service.search(
            query_embedding,
            top_k=candidate_k,
        )

        if not faiss_results:
            return []

        faiss_ids = [
            faiss_id
            for faiss_id, _ in faiss_results
        ]

        # 3. Resolve FAISS IDs to document/chunk IDs
        mappings = (
            self.vector_mapping_repository
            .get_by_faiss_ids(faiss_ids)
        )

        mapping_by_faiss_id = {
            mapping["faiss_id"]: mapping
            for mapping in mappings
        }

        results = []

        # 4. Retrieve actual chunk text and apply document filtering & threshold
        for faiss_id, score in faiss_results:

            if score_threshold is not None and score < score_threshold:
                continue

            mapping = mapping_by_faiss_id.get(
                faiss_id
            )

            if not mapping:
                continue

            doc_id = str(mapping["document_id"])
            if document_id and doc_id != str(document_id):
                continue

            chunk = self.chunk_repository.get_chunk(
                document_id=doc_id,
                chunk_id=mapping["chunk_id"],
            )

            if not chunk:
                continue

            results.append(
                {
                    "document_id": doc_id,
                    "chunk_id": mapping["chunk_id"],
                    "score": round(float(score), 4),
                    "text": chunk["text"],
                }
            )

            if len(results) >= top_k:
                break

        return results
