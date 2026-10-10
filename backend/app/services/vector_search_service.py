from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.repositories.chunk_repository import ChunkRepository


class VectorSearchService:
    """
    Orchestrates semantic vector search:
    1. Converts query text into an embedding via EmbeddingService.
    2. Retrieves top-k similar vectors from FAISSService.
    3. Resolves chunk metadata, page number, and text from ChunkRepository (MongoDB).
    4. Applies optional document-level filtering and similarity score thresholds.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        faiss_service: FAISSService,
        chunk_repository: ChunkRepository,
    ):
        self.embedding_service = embedding_service
        self.faiss_service = faiss_service
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

        When document_id is provided, utilizes iterative candidate expansion
        to guarantee sufficient results even if global top-K results belong to other documents.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if self.faiss_service.index is None or self.faiss_service.index.ntotal == 0:
            return []

        total_vectors = self.faiss_service.count()

        # 1. Convert query into embedding
        query_embedding = (
            self.embedding_service.generate_embedding(
                query
            )
        )

        # 2. Determine initial candidate pool size
        candidate_k = min(max(top_k * 4, 20), total_vectors) if document_id else min(top_k, total_vectors)
        seen_chunk_ids = set()
        results = []

        while candidate_k <= total_vectors:
            faiss_results = self.faiss_service.search(
                query_embedding,
                top_k=candidate_k,
            )

            if not faiss_results:
                break

            # Filter out candidates already evaluated in previous iteration
            new_candidates = [
                m for m in faiss_results if m["chunk_id"] not in seen_chunk_ids
            ]
            if not new_candidates:
                break

            for match in new_candidates:
                seen_chunk_ids.add(match["chunk_id"])

            valid_chunk_ids = [m["chunk_id"] for m in new_candidates]

            # 3. Batch retrieve matching chunks from MongoDB
            mongo_filter: Dict[str, Any] = {
                "$or": [
                    {"chunk_id": {"$in": valid_chunk_ids}},
                    {
                        "_id": {
                            "$in": [
                                ObjectId(cid)
                                for cid in valid_chunk_ids
                                if ObjectId.is_valid(cid)
                            ]
                        }
                    },
                ]
            }
            if document_id:
                mongo_filter["document_id"] = str(document_id)

            hydrated_chunks = list(
                self.chunk_repository.collection.find(mongo_filter)
            )

            chunk_lookup: Dict[str, Any] = {}
            for ch in hydrated_chunks:
                if "chunk_id" in ch:
                    chunk_lookup[str(ch["chunk_id"])] = ch
                chunk_lookup[str(ch["_id"])] = ch

            # 4. Process in rank order
            for match in new_candidates:
                cid = match["chunk_id"]
                score = match["score"]

                if score_threshold is not None and score < score_threshold:
                    break

                chunk = chunk_lookup.get(cid)
                if not chunk:
                    continue

                doc_id = str(chunk.get("document_id", ""))
                if document_id and doc_id != str(document_id):
                    continue

                results.append(
                    {
                        "document_id": doc_id,
                        "chunk_id": chunk.get("chunk_id", str(chunk["_id"])),
                        "score": round(float(score), 4),
                        "text": chunk.get("text", ""),
                        "page_number": chunk.get("page", chunk.get("page_number", 1)),
                    }
                )

                if len(results) >= top_k:
                    return results

            # If document_id is scoped and we haven't reached top_k, expand search depth deeper into FAISS
            if len(results) < top_k and document_id and candidate_k < total_vectors:
                candidate_k = min(candidate_k * 4, total_vectors)
            else:
                break

        return results
