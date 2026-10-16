import asyncio
import httpx
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
    user_a = get_mock_user_a()
    user_b = get_mock_user_b()
    invalidate_user_cache_sync(str(user_a["_id"]))
    invalidate_user_cache_sync(str(user_b["_id"]))

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

    app.dependency_overrides[get_current_user] = lambda: user_a
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


def test_upload_and_indexing_invalidates_cache(tmp_path):
    """
    Verifies the end-to-end upload & indexing cache invalidation flow:
    1. A user indexes a document.
    2. RAG query is cached for that user.
    3. Processing and indexing of a second document completes for the user.
    4. Assert old cache entry is invalidated.
    5. Assert subsequent query re-runs the RAG pipeline.
    """
    import mongomock
    from app.services.faiss_service import FAISSService
    from app.tasks.chunking_tasks import chunk_document

    user_a = get_mock_user_a()
    user_id = str(user_a["_id"])

    index_file = str(tmp_path / "test_indexing_cache.index")
    mapping_file = str(tmp_path / "test_indexing_cache.json")

    client_mock = mongomock.MongoClient()
    client_mock._server_version = "6.0.0"
    mock_db = client_mock["documind"]

    # 1. Insert first document for user A
    doc1_id = str(ObjectId())
    mock_db["documents"].insert_one({
        "_id": ObjectId(doc1_id),
        "user_id": user_a["_id"],
        "status": "EXTRACTION_COMPLETED",
        "ocr": {
            "raw_text": "Receipt #1: Keyboard total ₹2500",
            "page_count": 1,
        },
    })

    with patch("app.tasks.chunking_tasks.db", mock_db), \
         patch("app.tasks.chunking_tasks.FAISSService", lambda **kwargs: FAISSService(index_path=index_file, mapping_path=mapping_file)):
        chunk_document(doc1_id)

    # 2. Query RAG and cache answer
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_keyboard",
                "document_id": doc1_id,
                "filename": "receipt_1.pdf",
                "page": 1,
                "text": "Receipt #1: Keyboard total ₹2500",
                "score": 0.92,
            }
        ]
    )
    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "You purchased a Keyboard for ₹2500.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    test_client = TestClient(app)

    question_payload = {"question": "What keyboard did I buy?"}

    # First ask: Populates cache
    resp1 = test_client.post("/api/v1/rag/ask", json=question_payload)
    assert resp1.status_code == 200
    assert mock_answer_service.answer.call_count == 1

    # Second ask: Cache hit (no new answer call)
    resp2 = test_client.post("/api/v1/rag/ask", json=question_payload)
    assert resp2.status_code == 200
    assert mock_answer_service.answer.call_count == 1

    # 3. Now complete processing of a SECOND document for the same user
    doc2_id = str(ObjectId())
    mock_db["documents"].insert_one({
        "_id": ObjectId(doc2_id),
        "user_id": user_a["_id"],
        "status": "EXTRACTION_COMPLETED",
        "ocr": {
            "raw_text": "Receipt #2: Mouse total ₹800",
            "page_count": 1,
        },
    })

    with patch("app.tasks.chunking_tasks.db", mock_db), \
         patch("app.tasks.chunking_tasks.FAISSService", lambda **kwargs: FAISSService(index_path=index_file, mapping_path=mapping_file)):
        chunk_document(doc2_id)

    # 4. Assert subsequent query re-runs RAG pipeline because cache was invalidated!
    resp3 = test_client.post("/api/v1/rag/ask", json=question_payload)
    assert resp3.status_code == 200
    assert mock_answer_service.answer.call_count == 2


def test_rag_request_succeeds_when_cache_read_fails():
    """
    Simulate get_cached_answer raising an unexpected connection exception.
    Verify the endpoint fails open: performs retrieval, generation, and returns a valid 200 answer.
    """
    user_a = get_mock_user_a()

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_failopen",
                "document_id": "doc_fo",
                "filename": "receipt_failopen.pdf",
                "page": 1,
                "text": "Total amount is $150",
                "score": 0.89,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "The total amount is $150.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    with patch(
        "app.api.routes.rag.get_cached_answer",
        AsyncMock(side_effect=ConnectionError("Redis unavailable")),
    ):
        response = client.post(
            "/api/v1/rag/ask",
            json={"question": "What is the total amount?"},
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "The total amount is $150."
        assert mock_retriever.retrieve.call_count == 1
        assert mock_answer_service.answer.call_count == 1


def test_rag_request_succeeds_when_cache_write_fails():
    """
    Let the RAG pipeline succeed, then simulate cache_answer failing with an unexpected connection exception.
    Verify the endpoint fails open: returns the generated 200 answer without breaking the request.
    """
    user_a = get_mock_user_a()

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_writefail",
                "document_id": "doc_wf",
                "filename": "receipt_writefail.pdf",
                "page": 1,
                "text": "Flight ticket ₹8,400",
                "score": 0.91,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "Flight ticket was ₹8,400.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    with patch(
        "app.api.routes.rag.cache_answer",
        AsyncMock(side_effect=ConnectionError("Redis write connection refused")),
    ):
        response = client.post(
            "/api/v1/rag/ask",
            json={"question": "How much was the flight ticket?"},
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "Flight ticket was ₹8,400."
        assert mock_retriever.retrieve.call_count == 1
        assert mock_answer_service.answer.call_count == 1


def test_cached_rag_response_matches_normal_response():
    """
    Verifies that:
    1. A request causing a cache miss returns a full valid RAGAskResponse.
    2. The identical request causes a cache hit.
    3. The second response has exactly the same structure, types, and values.
    4. Retrieval and Gemini call counts do not increment on the cache hit.
    """
    user_a = get_mock_user_a()
    invalidate_user_cache_sync(str(user_a["_id"]))

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_compat_1",
                "document_id": "doc_compat_101",
                "filename": "office_supplies.pdf",
                "page": 2,
                "text": "Office chairs: 4 units at $120 each. Total: $480.",
                "score": 0.94,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "You purchased 4 office chairs for a total of $480.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    request_payload = {
        "question": "How many office chairs were bought and what was the cost?",
        "top_k": 5,
    }

    # 1. First request: Cache Miss
    resp1 = client.post("/api/v1/rag/ask", json=request_payload)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Verify all expected model fields exist on cache miss
    assert "answer" in data1
    assert "sources" in data1
    assert "retrieval" in data1
    assert data1["retrieval"]["top_k"] == 5
    assert data1["retrieval"]["sources_used"] == 1
    assert len(data1["sources"]) == 1
    assert data1["sources"][0]["chunk_id"] == "c_compat_1"
    assert data1["sources"][0]["filename"] == "office_supplies.pdf"
    assert data1["sources"][0]["page"] == 2
    assert mock_retriever.retrieve.call_count == 1
    assert mock_answer_service.answer.call_count == 1

    # 2. Second request: Cache Hit
    resp2 = client.post("/api/v1/rag/ask", json=request_payload)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # 3. Assert identical structure and values
    assert data1 == data2

    # 4. Assert retrieval and LLM call counts did not increase
    assert mock_retriever.retrieve.call_count == 1
    assert mock_answer_service.answer.call_count == 1


def test_invalid_cached_json_treated_as_cache_miss():
    """
    Verifies that if cached JSON fails model validation against RAGAskResponse,
    it is treated as a cache miss, regenerated via retriever and LLM, and returned cleanly.
    """
    user_a = get_mock_user_a()
    invalidate_user_cache_sync(str(user_a["_id"]))

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_regen_1",
                "document_id": "doc_regen_202",
                "filename": "monitor.pdf",
                "page": 1,
                "text": "Dell 27-inch 4K Monitor: $399",
                "score": 0.95,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "Dell 27-inch 4K Monitor cost $399.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    request_payload = {"question": "How much was the Dell monitor?"}

    # Simulate get_cached_answer returning malformed data missing required fields
    invalid_cached_data = {
        "corrupted_field": "bad_data",
    }

    with patch(
        "app.api.routes.rag.get_cached_answer",
        AsyncMock(return_value=invalid_cached_data),
    ):
        response = client.post("/api/v1/rag/ask", json=request_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Dell 27-inch 4K Monitor cost $399."
        assert len(data["sources"]) == 1
        assert data["retrieval"]["sources_used"] == 1
        # Confirms model validation failed gracefully, fell back to miss, and regenerated
        assert mock_retriever.retrieve.call_count == 1
        assert mock_answer_service.answer.call_count == 1


def test_endpoint_inflight_request_rejected_on_generation_change():
    """
    Verifies at the HTTP endpoint level that an in-flight RAG request cannot
    write a stale cached response if an invalidation occurs during retrieval.
    """
    user_a = get_mock_user_a()
    user_id = str(user_a["_id"])
    invalidate_user_cache_sync(user_id)

    async def retrieve_with_concurrent_invalidation(*args, **kwargs):
        # Simulate a concurrent document mutation/invalidation while retrieval is running
        invalidate_user_cache_sync(user_id)
        return [
            {
                "chunk_id": "c_stale_1",
                "document_id": "doc_stale_101",
                "filename": "stale_doc.pdf",
                "page": 1,
                "text": "Old obsolete value: $999",
                "score": 0.90,
            }
        ]

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(side_effect=retrieve_with_concurrent_invalidation)

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "Old obsolete value was $999.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    question_payload = {"question": "What is the obsolete value?"}

    # 1. First request starts at generation G, but during retrieval invalidation happens
    resp1 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp1.status_code == 200
    assert resp1.json()["answer"] == "Old obsolete value was $999."
    assert mock_retriever.retrieve.call_count == 1
    assert mock_answer_service.answer.call_count == 1

    # 2. Second request: Because the in-flight write was rejected, this MUST be a cache miss!
    resp2 = client.post("/api/v1/rag/ask", json=question_payload)
    assert resp2.status_code == 200
    # Must invoke retriever and LLM again, proving stale write did not repopulate cache
    assert mock_retriever.retrieve.call_count == 2
    assert mock_answer_service.answer.call_count == 2


@pytest.mark.asyncio
async def test_concurrent_identical_requests_avoid_duplicate_generation():
    """
    Verifies that simultaneous cache misses for the same uncached query do not
    trigger a cache stampede. Exactly one request acquires the lock and invokes
    the LLM/retriever, while other concurrent requests wait and read the cached response.
    """
    user_a = get_mock_user_a()
    user_id = str(user_a["_id"])
    await invalidate_user_cache(user_id)

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_stampede_1",
                "document_id": "doc_stampede_101",
                "filename": "annual_budget.pdf",
                "page": 1,
                "text": "Total cloud infrastructure spend for Q3 is $45,000.",
                "score": 0.96,
            }
        ]
    )

    async def slow_gemini_generation(*args, **kwargs):
        # Simulate LLM generation latency
        await asyncio.sleep(0.2)
        return {
            "answer": "Total cloud infrastructure spend for Q3 was $45,000.",
            "citations": ["S1"],
        }

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(side_effect=slow_gemini_generation)

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"question": "What is the total cloud infrastructure spend for Q3?"}
        # Fire 6 identical concurrent requests simultaneously
        tasks = [ac.post("/api/v1/rag/ask", json=payload) for _ in range(6)]
        responses = await asyncio.gather(*tasks)

    # All 6 requests must succeed with status 200 and get the exact answer
    for resp in responses:
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Total cloud infrastructure spend for Q3 was $45,000."

    # Under stampede protection, retriever and LLM are called ONLY ONCE across all 6 concurrent requests!
    assert mock_answer_service.answer.call_count == 1
    assert mock_retriever.retrieve.call_count == 1
