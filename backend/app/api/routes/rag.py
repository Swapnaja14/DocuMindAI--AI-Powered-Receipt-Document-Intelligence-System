import logging
import time
import uuid
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
from app.services.cache_metrics import cache_metrics
from app.services.cache_service import (
    acquire_lock,
    cache_answer,
    get_cached_answer,
    get_user_generation,
    make_cache_key,
    release_lock,
    wait_for_cached_answer,
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
    start_time = time.perf_counter()

    # 1. Derive user ID safely from authentication dependency
    if hasattr(current_user, "id"):
        user_id = str(current_user.id)
    elif isinstance(current_user, dict):
        user_id = str(current_user.get("_id") or current_user.get("id"))
    else:
        user_id = str(getattr(current_user, "_id", ""))

    # 2. Derive user generation and check Redis cache
    generation = await get_user_generation(user_id)
    cache_key = make_cache_key(
        user_id=user_id,
        query=request.question,
        context={
            "top_k": request.top_k,
        },
        generation=generation,
    )

    try:
        raw_cached = await get_cached_answer(cache_key)
        if raw_cached is not None:
            # Recheck generation before returning hit to guarantee freshness
            current_gen = await get_user_generation(user_id)
            if current_gen != generation:
                logger.info(
                    "Generation changed (%s -> %s) during cache lookup for user %s; discarding stale hit",
                    generation,
                    current_gen,
                    user_id,
                )
                raw_cached = None
                generation = current_gen
                cache_key = make_cache_key(
                    user_id=user_id,
                    query=request.question,
                    context={"top_k": request.top_k},
                    generation=generation,
                )
            else:
                try:
                    validated_cached = RAGAskResponse.model_validate(raw_cached)
                    hit_latency_ms = (time.perf_counter() - start_time) * 1000
                    cache_metrics.record_hit(hit_latency_ms)
                    return validated_cached
                except Exception as val_exc:
                    logger.warning(
                        "Cached RAG response failed model validation, falling back to cache miss: %s",
                        val_exc,
                    )
                    cache_metrics.record_invalid_entry()
    except Exception as exc:
        logger.warning("RAG cache read failed or bypassed: %s", exc)

    # 2.1 Cache stampede protection: acquire distributed lock
    lock_token = uuid.uuid4().hex
    lock_key = f"{cache_key}:lock"
    lock_acquired = False

    try:
        lock_acquired = await acquire_lock(lock_key, lock_token, ttl=15)
        if not lock_acquired:
            # Another concurrent request is actively generating this answer.
            # Wait for it to finish and populate the cache.
            waited_cached = await wait_for_cached_answer(
                cache_key=cache_key,
                lock_key=lock_key,
                timeout=5.0,
                poll_interval=0.05,
            )
            if waited_cached is not None:
                try:
                    validated = RAGAskResponse.model_validate(waited_cached)
                    hit_latency_ms = (time.perf_counter() - start_time) * 1000
                    cache_metrics.record_hit(hit_latency_ms)
                    return validated
                except Exception as val_exc:
                    logger.warning(
                        "Waited cached RAG response failed model validation: %s",
                        val_exc,
                    )
                    cache_metrics.record_invalid_entry()
            # If wait timed out or lock was freed without result, try acquiring lock once more
            lock_acquired = await acquire_lock(lock_key, lock_token, ttl=15)
        else:
            # Lock acquired: check cache again in case another request wrote it right before we acquired lock
            double_check = await get_cached_answer(cache_key)
            if double_check is not None:
                try:
                    validated = RAGAskResponse.model_validate(double_check)
                    await release_lock(lock_key, lock_token)
                    lock_acquired = False
                    hit_latency_ms = (time.perf_counter() - start_time) * 1000
                    cache_metrics.record_hit(hit_latency_ms)
                    return validated
                except Exception:
                    cache_metrics.record_invalid_entry()
    except Exception as lock_exc:
        logger.warning("Error during cache lock acquisition/wait: %s", lock_exc)

    try:
        # 3. Retrieve relevant chunks for this user (enforces multi-tenant scoping).
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

        # 4. Fail closed if there is no useful evidence.
        if not chunks:
            miss_latency_ms = (time.perf_counter() - start_time) * 1000
            cache_metrics.record_miss(miss_latency_ms)
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

        # 5. Construct context and source metadata.
        context, sources = build_context(chunks)

        # 6. Ask Gemini to answer from the retrieved evidence.
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

        # 7. Validate the model-generated source labels.
        cited_sources = validate_citations(
            result.get("citations", []),
            sources,
        )

        if not cited_sources:
            miss_latency_ms = (time.perf_counter() - start_time) * 1000
            cache_metrics.record_miss(miss_latency_ms)
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

        # 8. Convert validated evidence to the public response.
        response = RAGAskResponse(
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

        # 9. Cache successful grounded answer (fail-open)
        try:
            response_data = response.model_dump(mode="json")
            await cache_answer(
                cache_key,
                response_data,
                user_id=user_id,
                expected_generation=generation,
            )
        except Exception as exc:
            logger.warning("RAG cache write failed: %s", exc)

        miss_latency_ms = (time.perf_counter() - start_time) * 1000
        cache_metrics.record_miss(miss_latency_ms)

        return response
    finally:
        if lock_acquired:
            try:
                await release_lock(lock_key, lock_token)
            except Exception as exc:
                logger.warning("Failed to release lock %s: %s", lock_key, exc)


@router.get("/cache/metrics")
async def get_rag_cache_metrics():
    """Return operational metrics and hit-ratio report for the RAG cache."""
    return {
        "summary": cache_metrics.get_summary(),
        "report": cache_metrics.format_report(),
    }
