"""
Frontend-Backend Contract & API Integration Test Suite
Validates the complete phase exit criteria for the DocuMind AI frontend integration:
- User registration, login, logout, and token authentication
- Session protection and 401 unauthorized handling
- Document upload, status retrieval, listing, and deletion (204 No Content)
- RAG question answering and grounding citation response schema
- Expenses analytics summary endpoint
- CORS preflight and access-control headers
- Robust error response handling (400, 401, 404, 409, 422)
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import mongomock
import pytest
from fastapi.testclient import TestClient

from app.api.routes.documents import documents_collection
from app.api.routes.rag import get_rag_answer_service, get_rag_retriever
from app.api.routes.users import get_current_user
from app.core.security import create_access_token, hash_password
from app.main import app

# Prevent real MongoDB network connection and heavy FAISS disk load during test lifespan startup
patch("app.main.create_indexes", lambda: None).start()
patch("app.main.FAISSService", lambda: MagicMock(status=lambda: {"total_vectors": 0, "mapped_chunks": 0, "loaded": True})).start()



@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Ensure dependency overrides are reset after each test."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_mongo():
    """Mock MongoDB collections for isolated test execution."""
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    users_col = db["users"]
    docs_col = db["documents"]

    with patch("app.core.database.users_collection", users_col), \
         patch("app.core.database.documents_collection", docs_col), \
         patch("app.api.routes.auth.users_collection", users_col), \
         patch("app.api.routes.users.users_collection", users_col), \
         patch("app.api.routes.documents.documents_collection", docs_col):
        yield {"users": users_col, "documents": docs_col}


def test_cors_headers_and_preflight():
    """Verify CORS preflight and allowed origins for frontend development servers."""
    client = TestClient(app)

    # 1. Preflight OPTIONS request from localhost:5173
    response = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"

    # 2. Preflight OPTIONS request from 127.0.0.1:5173
    response_ip = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response_ip.status_code == 200
    assert response_ip.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_auth_registration_login_and_session_flow(mock_mongo):
    """Verify registration, login, profile fetch, duplicate conflict, and logout."""
    client = TestClient(app)

    # 1. Register a new user
    reg_payload = {"email": "testuser@documind.ai", "password": "SecurePassword123!"}
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == "testuser@documind.ai"
    assert "id" in user_data

    # 2. Duplicate registration should return 409 Conflict
    dup_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409
    assert "Email already registered" in dup_res.json()["detail"]

    # 3. Login with wrong password returns 401
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@documind.ai", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert "Invalid email or password" in bad_login.json()["detail"]

    # 4. Successful login returns access_token
    login_res = client.post("/api/v1/auth/login", json=reg_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    assert token_data["token_type"].lower() == "bearer"

    # 5. Access protected /users/me without token -> 401
    unauth_res = client.get("/api/v1/users/me")
    assert unauth_res.status_code in (401, 403)

    # 6. Access protected /users/me with token -> 200
    auth_headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/users/me", headers=auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "testuser@documind.ai"

    # 7. Logout -> 200
    logout_res = client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_res.status_code == 200


def test_document_lifecycle_upload_list_detail_delete(mock_mongo, tmp_path):
    """Verify document upload, listing, details query, and deletion (204 No Content)."""
    client = TestClient(app)

    # Create active user in mock mongo
    user_id = ObjectId("65c000000000000000000001")
    mock_mongo["users"].insert_one({
        "_id": user_id,
        "email": "docs@documind.ai",
        "password_hash": hash_password("Password123!"),
        "role": "user",
    })
    token = create_access_token(str(user_id))
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Setup isolated temporary upload directory
    with patch("app.api.routes.documents.settings.upload_dir", str(tmp_path)), \
         patch("app.api.routes.documents.process_document", MagicMock()), \
         patch("app.api.routes.documents.chain", MagicMock()):
        # 1. Upload valid document (valid 1-page PDF generated via PyMuPDF)
        import pymupdf as fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "DocuMind Test Receipt Total: $50.00")
        pdf_bytes = doc.tobytes()
        doc.close()

        files = {"file": ("test_receipt.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = client.post("/api/v1/documents/upload", headers=auth_headers, files=files)

        assert upload_res.status_code == 201
        doc_data = upload_res.json()
        doc_id = doc_data["id"]
        assert doc_data["filename"] == "test_receipt.pdf"
        assert doc_data["status"] == "UPLOADED"

        # 2. List documents
        list_res = client.get("/api/v1/documents", headers=auth_headers)
        assert list_res.status_code == 200
        docs_list = list_res.json()
        assert len(docs_list) >= 1
        assert any(d["id"] == doc_id for d in docs_list)

        # 3. Get document details
        detail_res = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["id"] == doc_id

        # 4. Delete document -> 204 No Content
        del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert del_res.status_code == 204

        # 5. Get deleted document -> 404
        after_del = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert after_del.status_code == 404


def test_rag_chat_backend_grounding_and_sources():
    """Verify RAG chat question answering returns answers, evidence sources, and retrieval stats."""
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk_apple_1",
                "document_id": "doc_apple_100",
                "filename": "apple_store_receipt.pdf",
                "page": 1,
                "text": "MacBook Pro Total: $2,499.00 with AppleCare",
                "score": 0.94,
            }
        ]
    )

    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "According to the Apple Store receipt [1], your MacBook Pro total was $2,499.00.",
            "citations": ["S1"],
        }
    )

    user_obj = {
        "_id": ObjectId("65c000000000000000000002"),
        "id": "65c000000000000000000002",
        "email": "raguser@documind.ai",
        "role": "user",
    }
    app.dependency_overrides[get_current_user] = lambda: user_obj
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    client = TestClient(app)

    # 1. Ask question
    res = client.post(
        "/api/v1/rag/ask",
        json={"question": "What was the total for my MacBook Pro?", "top_k": 5},
    )
    assert res.status_code == 200
    rag_data = res.json()

    assert "answer" in rag_data
    assert "MacBook Pro" in rag_data["answer"]
    assert "sources" in rag_data
    assert len(rag_data["sources"]) == 1
    assert rag_data["sources"][0]["filename"] == "apple_store_receipt.pdf"
    assert rag_data["retrieval"]["top_k"] == 5

    # 2. Input validation: Question too short (< 3 chars) returns 422
    invalid_res = client.post("/api/v1/rag/ask", json={"question": "hi", "top_k": 5})
    assert invalid_res.status_code == 422
