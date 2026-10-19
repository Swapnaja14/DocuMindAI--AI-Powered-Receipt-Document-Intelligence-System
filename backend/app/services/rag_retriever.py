import inspect
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService

logger = logging.getLogger(__name__)


class RAGRetriever:
    """
    Retrieves evidence chunks from FAISS and MongoDB strictly scoped to the authenticated user.
    Enforces tenant isolation, similarity threshold filtering, and citation metadata extraction.
    """

    DEFAULT_SCORE_THRESHOLD = 0.20

    def __init__(
        self,
        embedding_service: EmbeddingService,
        faiss_service: FAISSService,
        chunk_repository: ChunkRepository,
        document_repository: DocumentRepository,
        default_score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ):
        self.embedding_service = embedding_service
        self.faiss_service = faiss_service
        self.chunk_repository = chunk_repository
        self.document_repository = document_repository
        self.default_score_threshold = default_score_threshold

    async def _embed_question(self, question: str) -> List[float]:
        """Support both async and synchronous embedding service methods."""
        if hasattr(self.embedding_service, "embed_query"):
            fn = self.embedding_service.embed_query
        elif hasattr(self.embedding_service, "generate_embedding"):
            fn = self.embedding_service.generate_embedding
        else:
            raise AttributeError("EmbeddingService has no embed_query or generate_embedding method")

        if inspect.iscoroutinefunction(fn):
            return await fn(question)
        return fn(question)

    async def retrieve(
        self,
        question: str,
        user_id: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve user-authorized evidence chunks for a question:
        1. Validates inputs & checks index availability.
        2. Generates query embedding.
        3. Searches FAISS with adaptive candidate expansion to handle multi-user indices.
        4. Batch resolves MongoDB chunks and validates parent document user ownership.
        5. Discards unowned, missing, or below-threshold chunks.
        6. Returns structured evidence with citation metadata.
        """
        if not question or not question.strip():
            return []

        if not user_id:
            logger.warning("RAGRetriever called without a valid user_id.")
            return []

        user_id_str = str(user_id)
        effective_threshold = (
            score_threshold
            if score_threshold is not None
            else self.default_score_threshold
        )

        # 1. Index availability check
        if self.faiss_service.index is None or self.faiss_service.index.ntotal == 0:
            return []

        total_vectors = self.faiss_service.count()

        # 2. Embed the question
        query_vector = await self._embed_question(question)

        # 3. Adaptive candidate search in FAISS
        candidate_k = min(max(top_k * 4, 20), total_vectors)
        seen_chunk_ids = set()
        user_authorized_results: List[Dict[str, Any]] = []

        while candidate_k <= total_vectors:
            faiss_matches = self.faiss_service.search(
                query_vector,
                top_k=candidate_k,
            )

            if not faiss_matches:
                break

            # Filter candidates we haven't processed yet
            new_matches = [
                m for m in faiss_matches if m.get("chunk_id") not in seen_chunk_ids
            ]
            if not new_matches:
                break

            for m in new_matches:
                seen_chunk_ids.add(m.get("chunk_id"))

            chunk_ids = [m["chunk_id"] for m in new_matches if m.get("chunk_id")]
            if not chunk_ids:
                break

            # 4. Batch retrieve chunks from MongoDB
            chunks = self.chunk_repository.get_by_ids(chunk_ids)
            chunk_map: Dict[str, Any] = {}
            for ch in chunks:
                if "chunk_id" in ch:
                    chunk_map[str(ch["chunk_id"])] = ch
                chunk_map[str(ch["_id"])] = ch

            # 5. Extract unique document IDs and batch verify user ownership
            parent_doc_ids = list({
                str(ch["document_id"])
                for ch in chunks
                if ch.get("document_id") is not None
            })

            user_documents = self.document_repository.get_user_documents_by_ids(
                parent_doc_ids, user_id=user_id_str
            )
            # Map by both string ID and ObjectId
            user_doc_map: Dict[str, Any] = {}
            for doc in user_documents:
                user_doc_map[str(doc["_id"])] = doc

            # 6. Preserve FAISS rank order & apply ownership + similarity thresholds
            threshold_exhausted = False
            for match in new_matches:
                chunk_id = match.get("chunk_id")
                score = match.get("score", 0.0)

                # Similarity threshold check
                if effective_threshold is not None and score < effective_threshold:
                    # Chunks are returned in descending score order; remaining candidates will also be below threshold
                    threshold_exhausted = True
                    break

                chunk = chunk_map.get(str(chunk_id))
                if not chunk:
                    # Skip chunks deleted from MongoDB (consistency tolerance)
                    continue

                parent_doc_id = str(chunk.get("document_id", ""))
                document = user_doc_map.get(parent_doc_id)

                # Ownership check: must belong to the authenticated user
                if not document:
                    continue

                filename = (
                    document.get("filename")
                    or document.get("original_filename")
                    or "document.pdf"
                )
                page = chunk.get("page", chunk.get("page_number", 1))

                ext_data = document.get("extracted_data") or {}

                user_authorized_results.append(
                    {
                        "chunk_id": str(chunk.get("chunk_id", chunk["_id"])),
                        "document_id": parent_doc_id,
                        "filename": filename,
                        "text": chunk.get("text", ""),
                        "page": int(page) if page is not None else None,
                        "score": round(float(score), 4),
                        "extracted_total": ext_data.get("total"),
                        "extracted_currency": ext_data.get("currency"),
                        "extracted_vendor": ext_data.get("vendor"),
                        "extracted_date": ext_data.get("date"),
                    }
                )

                if len(user_authorized_results) >= top_k:
                    return user_authorized_results

            if threshold_exhausted:
                break

            # Expand search deeper if we haven't collected top_k user-owned chunks
            if len(user_authorized_results) < top_k and candidate_k < total_vectors:
                candidate_k = min(candidate_k * 4, total_vectors)
            else:
                break

        return user_authorized_results
