from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import db
from app.repositories.chunk_repository import ChunkRepository
from app.schemas.search import SearchRequest, SearchResponse
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_search_service import VectorSearchService

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
