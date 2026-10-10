from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.routes.rag import get_rag_answer_service, get_rag_retriever
from app.api.routes.users import get_current_user
from app.main import app

# Prevent MongoDB connection timeout during test lifespan startup
patch("app.main.create_indexes", lambda: None).start()


def get_mock_user():
    return {
        "_id": ObjectId("65c000000000000000000001"),
        "id": "65c000000000000000000001",
        "email": "user@example.com",
        "role": "user",
    }


def test_rag_api_unauthorized():
    """Without auth override or token, request must be rejected with 401 or 403."""
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.post("/api/v1/rag/ask", json={"question": "What is my laptop total?"})
    assert response.status_code in (401, 403)


def test_rag_api_success_v1_and_default_prefix():
    """Verifies both /api/v1/rag/ask and /api/rag/ask return 200 with valid grounded response."""
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
            "answer": "The highest purchase was MacBook Pro at ₹1,99,000.",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    for path in ("/api/v1/rag/ask", "/api/rag/ask"):
        response = client.post(
            path,
            json={"question": "What was my highest laptop total?", "top_k": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "The highest purchase was MacBook Pro at ₹1,99,000."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["document_id"] == "doc_101"
        assert data["sources"][0]["filename"] == "apple_laptop.pdf"
        assert data["retrieval"]["top_k"] == 5
        assert data["retrieval"]["sources_used"] == 1


def test_rag_api_no_evidence_fails_closed():
    """When no relevant evidence exists in user documents, returns closed fallback response."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(return_value=[])

    mock_answer_service = MagicMock()
    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "Where is my yacht receipt?", "top_k": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert "couldn't find sufficient relevant evidence" in data["answer"].lower()
    assert data["sources"] == []
    assert data["retrieval"]["sources_used"] == 0
    mock_answer_service.answer.assert_not_called()


def test_rag_api_hallucinated_citations_handled():
    """When model generates claims but cites invalid sources, fallback is triggered."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_1",
                "document_id": "doc_101",
                "filename": "apple_laptop.pdf",
                "page": 1,
                "text": "MacBook Pro total: ₹1,99,000",
                "score": 0.88,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "You bought a Boeing 747 for $50,000,000.",
            "citations": ["S99", "FAKE_DOC"],
        }
    )

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What airplanes did I buy?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "couldn't establish a sufficiently supported answer" in data["answer"].lower()
    assert data["sources"] == []
    assert data["retrieval"]["sources_used"] == 0


def test_rag_api_model_invalid_json_returns_502():
    """When model returns invalid JSON, maps to 502 Bad Gateway without leaking internal errors."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_1",
                "document_id": "doc_101",
                "filename": "apple_laptop.pdf",
                "page": 1,
                "text": "MacBook Pro total: ₹1,99,000",
                "score": 0.88,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        side_effect=ValueError("Gemini returned an invalid JSON response")
    )

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What is the total?"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Unable to generate a valid grounded answer."


def test_rag_api_upstream_rate_limit_returns_429():
    """When Gemini returns rate limit or quota exceeded, maps to 429."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_1",
                "document_id": "doc_101",
                "filename": "apple_laptop.pdf",
                "page": 1,
                "text": "MacBook Pro total: ₹1,99,000",
                "score": 0.88,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        side_effect=RuntimeError("Resource has been exhausted (e.g. check quota, 429 rate limit)")
    )

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What is the total?"},
    )

    assert response.status_code == 429
    assert "rate limit exceeded" in response.json()["detail"].lower()


def test_rag_api_upstream_timeout_returns_504():
    """When Gemini times out, maps to 504 Gateway Timeout."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_1",
                "document_id": "doc_101",
                "filename": "apple_laptop.pdf",
                "page": 1,
                "text": "MacBook Pro total: ₹1,99,000",
                "score": 0.88,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        side_effect=TimeoutError("Request deadline exceeded (timed out)")
    )

    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What is the total?"},
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_rag_api_request_validation_errors():
    """Invalid requests (<3 chars, or top_k out of range) return 422."""
    app.dependency_overrides[get_current_user] = get_mock_user
    client = TestClient(app)

    # Question too short
    res1 = client.post("/api/v1/rag/ask", json={"question": "hi"})
    assert res1.status_code == 422

    # top_k > 10
    res2 = client.post("/api/v1/rag/ask", json={"question": "Valid question?", "top_k": 20})
    assert res2.status_code == 422

    # top_k < 1
    res3 = client.post("/api/v1/rag/ask", json={"question": "Valid question?", "top_k": 0})
    assert res3.status_code == 422
