import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.users import get_current_user
from app.core.database import db
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.search import (
    FilterSearchRequest,
    FilterSearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultItem,
    StructuredReceiptItem,
)
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.rag_retriever import RAGRetriever
from app.services.vector_search_service import VectorSearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Search"])

_embedding_service: Optional[EmbeddingService] = None
_faiss_service: Optional[FAISSService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_faiss_service() -> FAISSService:
    global _faiss_service
    if _faiss_service is None:
        _faiss_service = FAISSService()
    return _faiss_service


def get_vector_search_service(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    faiss_service: FAISSService = Depends(get_faiss_service),
) -> VectorSearchService:
    chunk_repo = ChunkRepository(db)
    return VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )


def get_search_rag_retriever(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    faiss_service: FAISSService = Depends(get_faiss_service),
) -> RAGRetriever:
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    return RAGRetriever(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
    )


def get_document_repository() -> DocumentRepository:
    return DocumentRepository(db)


# ============================================================================
# Mode A — Structured Filtering (MongoDB)
# ============================================================================
@router.post("/search/filters", response_model=FilterSearchResponse)
def search_filters(
    request: FilterSearchRequest,
    current_user=Depends(get_current_user),
    doc_repo: DocumentRepository = Depends(get_document_repository),
):
    """
    Mode A: Structured filtering across MongoDB receipts.
    Queries indexed fields (vendor, total range, currency, date range)
    strictly scoped to the authenticated user's documents.
    Does not invoke FAISS or Gemini.
    """
    user_id = str(current_user.id if hasattr(current_user, "id") else current_user["_id"])

    try:
        documents = doc_repo.find_user_documents_filtered(
            user_id=user_id,
            vendor=request.vendor,
            min_total=request.min_total,
            max_total=request.max_total,
            currency=request.currency,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit,
        )

        receipts = []
        for d in documents:
            ext = d.get("extracted_data") or {}
            items = ext.get("items") or []
            created = d.get("created_at")
            created_str = (
                created.isoformat()
                if hasattr(created, "isoformat")
                else str(created) if created else None
            )

            receipts.append(
                StructuredReceiptItem(
                    document_id=str(d["_id"]),
                    filename=str(
                        d.get("filename")
                        or d.get("original_filename")
                        or "receipt.pdf"
                    ),
                    vendor=ext.get("vendor"),
                    invoice_number=ext.get("invoice_number"),
                    date=ext.get("date"),
                    currency=ext.get("currency"),
                    total=float(ext["total"]) if ext.get("total") is not None else None,
                    subtotal=float(ext["subtotal"]) if ext.get("subtotal") is not None else None,
                    tax=float(ext["tax"]) if ext.get("tax") is not None else None,
                    items_count=len(items),
                    created_at=created_str,
                )
            )

        return FilterSearchResponse(
            mode="structured",
            total_matches=len(receipts),
            receipts=receipts,
        )
    except Exception as e:
        logger.error("Structured filter search error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Structured filter search failed: {str(e)}",
        )


# ============================================================================
# Mode B — Semantic Search (FAISS + MongoDB)
# ============================================================================
@router.post("/search/semantic", response_model=SemanticSearchResponse)
async def search_semantic(
    request: SemanticSearchRequest,
    current_user=Depends(get_current_user),
    retriever: RAGRetriever = Depends(get_search_rag_retriever),
):
    """
    Mode B: Semantic vector search using FAISS + MongoDB.
    Embeds the query, retrieves similar chunks, and returns matches with
    similarity scores strictly scoped to the authenticated user.
    No LLM call is necessary.
    """
    user_id = str(current_user.id if hasattr(current_user, "id") else current_user["_id"])

    try:
        chunks = await retriever.retrieve(
            question=request.query,
            user_id=user_id,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )

        if request.document_id:
            chunks = [
                c for c in chunks
                if str(c.get("document_id")) == str(request.document_id)
            ]

        results = [
            SemanticSearchResultItem(
                document_id=str(c["document_id"]),
                chunk_id=str(c["chunk_id"]),
                filename=str(c["filename"]),
                score=float(c["score"]),
                text=str(c["text"]),
                page=c.get("page"),
            )
            for c in chunks
        ]

        return SemanticSearchResponse(
            mode="semantic",
            query=request.query,
            total_results=len(results),
            results=results,
        )
    except Exception as e:
        logger.error("Semantic search error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}",
        )


# ============================================================================
# Legacy Semantic Search Route (Backward Compatibility)
# ============================================================================
@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    search_service: VectorSearchService = Depends(get_vector_search_service),
):
    """
    Semantic search across indexed document chunks using FAISS and MongoDB.
    """
    try:
        results = search_service.search(
            query=request.query,
            top_k=request.top_k,
            document_id=request.document_id,
            score_threshold=request.score_threshold,
        )
        return SearchResponse(results=results)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}",
        )
