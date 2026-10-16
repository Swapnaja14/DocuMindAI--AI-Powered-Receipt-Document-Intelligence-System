import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.routes.rag import get_rag_answer_service, get_rag_retriever
from app.api.routes.users import get_current_user
from app.main import app
from app.services.cache_service import (
    get_cached_answer,
    invalidate_user_cache,
    invalidate_user_cache_sync,
    make_cache_key,
)

# Prevent MongoDB connection timeout during test lifespan startup
patch("app.main.create_indexes", lambda: None).start()


def get_mock_user_a():
    return {
        "_id": ObjectId("65c000000000000000000001"),
        "id": "65c000000000000000000001",
        "email": "user_a@example.com",
        "role": "user",
    }


def get_mock_user_b():
    return {
        "_id": ObjectId("65c000000000000000000002"),
        "id": "65c000000000000000000002",
        "email": "user_b@example.com",
        "role": "user",
    }


def test_rag_cache_hit_and_user_isolation():
    """
    Verifies that:
    1. First request misses cache, invokes LLM + retriever, and populates Redis.
    2. Second identical request hits cache and does NOT invoke LLM or retriever.
    3. Different user asking same question does NOT get User A's cache (isolation).
    """
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_1",
                "document_id": "doc_101",
                "filename": "apple_laptop.pdf",
                "page": 1,
                "text": "MacBook Pro 16-inch total: ₹1,99,000",
                "score": 0.88,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "MacBook Pro total is ₹1,99,000.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = get_mock_user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    question_payload = {"question": "What is the total spent on MacBook?"}

    # First request: Cache Miss
    resp1 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp1.status_code == 200
    assert resp1.json()["answer"] == "MacBook Pro total is ₹1,99,000."
    assert mock_retriever.retrieve.call_count == 1
    assert mock_answer_service.answer.call_count == 1

    # Second request with same user and query: Cache Hit!
    resp2 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp2.status_code == 200
    assert resp2.json()["answer"] == "MacBook Pro total is ₹1,99,000."
    # The retriever and answer service should NOT be called again
    assert mock_retriever.retrieve.call_count == 1
    assert mock_answer_service.answer.call_count == 1

    # User B asking the same question: Must be isolated (Cache Miss for User B)
    app.dependency_overrides[get_current_user] = get_mock_user_b
    resp3 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp3.status_code == 200
    assert mock_retriever.retrieve.call_count == 2
    assert mock_answer_service.answer.call_count == 2


def test_document_deletion_invalidates_cache():
    """
    Verifies that deleting a document invalidates the user's RAG answer cache.
    """
    user_a = get_mock_user_a()
    user_id = str(user_a["_id"])
    doc_id = str(ObjectId("65c000000000000000000010"))

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_2",
                "document_id": doc_id,
                "filename": "receipt_to_delete.pdf",
                "page": 1,
                "text": "Receipt total: $50",
                "score": 0.90,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "Receipt total was $50.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    question_payload = {"question": "How much was the receipt total?"}

    # 1. Ask question -> Populates cache
    resp1 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp1.status_code == 200
    assert mock_answer_service.answer.call_count == 1

    # 2. Verify cache hit would occur
    resp2 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp2.status_code == 200
    assert mock_answer_service.answer.call_count == 1

    # 3. Simulate document deletion via DELETE /api/documents/{doc_id}
    with patch("app.api.routes.documents.documents_collection") as mock_docs, \
         patch("app.api.routes.documents.ChunkRepository") as mock_chunk_repo_cls, \
         patch("pathlib.Path.exists", return_value=False):

        mock_docs.find_one.return_value = {
            "_id": ObjectId(doc_id),
            "user_id": user_a["_id"],
            "file_path": "/fake/path.pdf",
        }
        del_resp = client.delete(f"/api/documents/{doc_id}")
        assert del_resp.status_code == 204

    # 4. Now asking question again MUST miss cache because deletion invalidated user's cache!
    resp3 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp3.status_code == 200
    assert mock_answer_service.answer.call_count == 2


def test_sync_cache_invalidation_for_celery():
    """
    Verifies that synchronous invalidation used in Celery chunking tasks clears user cache keys.
    """
    user_id = "test_celery_user_999"
    key = make_cache_key(user_id=user_id, query="What is in my latest invoice?")

    # Insert a test cache entry synchronously using Redis
    import redis as sync_redis
    r = sync_redis.Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
    r.set(key, '{"answer": "Invoice is $100"}', ex=300)
    assert r.get(key) is not None

    # Call synchronous invalidation (as called by Celery chunk_document)
    deleted = invalidate_user_cache_sync(user_id)
    assert deleted >= 1
    assert r.get(key) is None
