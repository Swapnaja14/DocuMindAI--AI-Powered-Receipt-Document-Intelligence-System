import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.search import get_embedding_service, get_faiss_service
from app.api.routes.users import get_current_user
from app.core.database import db
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.rag import (
    RAGAskRequest,
    RAGAskResponse,
    RAGSource,
    RetrievalMetadata,
)
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.rag_answer_service import RAGAnswerService
from app.services.rag_citations import validate_citations
from app.services.rag_context_builder import build_context
from app.services.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])

_rag_retriever: Optional[RAGRetriever] = None
_rag_answer_service: Optional[RAGAnswerService] = None


def get_rag_retriever(
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


def get_rag_answer_service() -> RAGAnswerService:
    global _rag_answer_service
    if _rag_answer_service is None:
        _rag_answer_service = RAGAnswerService()
    return _rag_answer_service


@router.post("/ask", response_model=RAGAskResponse)
async def ask_question(
    request: RAGAskRequest,
    current_user=Depends(get_current_user),
    retriever: RAGRetriever = Depends(get_rag_retriever),
    answer_service: RAGAnswerService = Depends(get_rag_answer_service),
):
    """
    RAG question-answering endpoint over authenticated user's documents.
    """
    # 1. Derive user ID safely from authentication dependency
    if hasattr(current_user, "id"):
        user_id = str(current_user.id)
    elif isinstance(current_user, dict):
        user_id = str(current_user.get("_id") or current_user.get("id"))
    else:
        user_id = str(getattr(current_user, "_id", ""))

    # 2. Retrieve relevant chunks for this user (enforces multi-tenant scoping).
    try:
        chunks = await retriever.retrieve(
            question=request.question,
            user_id=user_id,
            top_k=request.top_k,
        )
    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document evidence.",
        ) from exc

    # 3. Fail closed if there is no useful evidence.
    if not chunks:
        return RAGAskResponse(
            answer=(
                "I couldn't find sufficient relevant evidence "
                "in your documents to answer this question."
            ),
            sources=[],
            retrieval=RetrievalMetadata(
                top_k=request.top_k,
                sources_used=0,
            ),
        )

    # 4. Construct context and source metadata.
    context, sources = build_context(chunks)

    # 5. Ask Gemini to answer from the retrieved evidence.
    try:
        result = await answer_service.answer(
            question=request.question,
            context=context,
        )
    except ValueError as exc:
        # Log technical details internally, without exposing raw prompts or provider responses
        logger.warning("RAG answer validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to generate a valid grounded answer.",
        ) from exc
    except Exception as exc:
        logger.error("RAG upstream provider error: %s", exc)
        exc_str = str(exc).lower()
        if "rate" in exc_str or "quota" in exc_str or "429" in exc_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Upstream AI provider rate limit exceeded. Please try again shortly.",
            ) from exc
        elif "timeout" in exc_str or "deadline" in exc_str or "timed out" in exc_str:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Upstream AI provider timed out. Please try again.",
            ) from exc
        elif "unauthorized" in exc_str or "api_key" in exc_str or "permission" in exc_str:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Upstream AI service configuration error.",
            ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to generate a valid grounded answer.",
            ) from exc

    # 6. Validate the model-generated source labels.
    cited_sources = validate_citations(
        result.get("citations", []),
        sources,
    )

    if not cited_sources:
        return RAGAskResponse(
            answer=(
                "I couldn't establish a sufficiently supported "
                "answer from the retrieved evidence."
            ),
            sources=[],
            retrieval=RetrievalMetadata(
                top_k=request.top_k,
                sources_used=0,
            ),
        )

    # 7. Convert validated evidence to the public response.
    return RAGAskResponse(
        answer=result["answer"],
        sources=[
            RAGSource(**{
                key: source[key]
                for key in (
                    "document_id",
                    "filename",
                    "page",
                    "chunk_id",
                    "snippet",
                )
            })
            for source in cited_sources
        ],
        retrieval=RetrievalMetadata(
            top_k=request.top_k,
            sources_used=len(cited_sources),
        ),
    )
