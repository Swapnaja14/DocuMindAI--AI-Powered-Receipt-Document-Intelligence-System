import io
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import jwt
import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# Prevent MongoDB indexes creation during test startup
patch("app.main.create_indexes", lambda: None).start()

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.main import app
from app.models.document import DocumentStatus
from app.models.user import UserRole
from app.api.routes.users import get_current_user
from app.api.routes.rag import get_rag_retriever, get_rag_answer_service
from app.api.routes.search import get_document_repository


@pytest.fixture
def mock_security_env(tmp_path):
    """Isolated test environment with mongomock and test users."""
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_security_test"]

    users_col = db["users"]
    docs_col = db["documents"]
    chunks_col = db["document_chunks"]

    now = datetime.now(timezone.utc)
    user_a_id = ObjectId("65c000000000000000000001")
    user_b_id = ObjectId("65c000000000000000000002")

    user_a = {
        "_id": user_a_id,
        "id": str(user_a_id),
        "email": "alice@example.com",
        "password_hash": hash_password("AlicePass123!"),
        "role": UserRole.USER.value,
        "created_at": now,
    }
    user_b = {
        "_id": user_b_id,
        "id": str(user_b_id),
        "email": "bob@example.com",
        "password_hash": hash_password("BobPass456!"),
        "role": UserRole.USER.value,
        "created_at": now,
    }

    users_col.insert_many([user_a, user_b])

    # User A document
    user_a_doc_id = ObjectId("65c0000000000000000000aa")
    doc_path = tmp_path / "alice_invoice.pdf"
    doc_path.write_bytes(b"%PDF-1.4 test invoice contents")

    user_a_doc = {
        "_id": user_a_doc_id,
        "document_id": str(user_a_doc_id),
        "user_id": user_a_id,
        "filename": "alice_secret_invoice.pdf",
        "file_type": "pdf",
        "file_path": str(doc_path),
        "file_size": 250,
        "status": DocumentStatus.COMPLETED.value,
        "ocr_status": "COMPLETED",
        "extraction_status": "COMPLETED",
        "chunking_status": "COMPLETED",
        "vector_status": "INDEXED",
        "chunk_count": 1,
        "ocr": {"raw_text": "Alice Private Receipt: $500", "page_count": 1},
        "extracted_data": {"vendor": "Confidential Corp", "total": 500.0, "currency": "USD"},
        "processing": {"uploaded_at": now},
    }
    docs_col.insert_one(user_a_doc)

    chunks_col.insert_one({
        "chunk_id": f"{user_a_doc_id}_chunk_0",
        "document_id": str(user_a_doc_id),
        "text": "Alice Private Receipt: $500",
        "page": 1,
        "created_at": now,
    })

    return {
        "db": db,
        "users_col": users_col,
        "docs_col": docs_col,
        "chunks_col": chunks_col,
        "user_a": user_a,
        "user_b": user_b,
        "user_a_doc": user_a_doc,
        "tmp_path": tmp_path,
    }


# ==============================================================================
# Step 13.1: Authentication, Token Lifecycle & Cross-User Authorization
# ==============================================================================

def test_password_hashing_security():
    """Verify password hashing algorithm adheres to modern standards."""
    raw_password = "SecurePassword@2026"
    hashed = hash_password(raw_password)

    # Must be hashed and not store plaintext
    assert hashed != raw_password
    assert len(hashed) > 20

    # Verification must succeed for correct password and fail for wrong password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_token_lifecycle_and_validation(mock_security_env):
    """Verify token generation, signature validation, expiry, and claim enforcement."""
    env = mock_security_env
    user_a_id = str(env["user_a"]["_id"])

    # 1. Valid token
    token = create_access_token(user_a_id)
    decoded_sub = decode_access_token(token)
    assert decoded_sub == user_a_id

    # 2. Expired token
    expired_payload = {
        "sub": user_a_id,
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(Exception):
        decode_access_token(expired_token)

    # 3. Tampered token signature
    tampered_token = token[:-5] + "XXXXX"
    with pytest.raises(Exception):
        decode_access_token(tampered_token)

    # 4. Missing sub claim
    missing_sub_payload = {
        "user": user_a_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    missing_sub_token = jwt.encode(missing_sub_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(Exception):
        decode_access_token(missing_sub_token)


def test_cross_user_access_blocked_on_document_by_id(mock_security_env):
    """
    Negative Test: User B cannot retrieve User A's document by guessing its MongoDB ID.
    Must return 404 Not Found to prevent ID enumeration.
    """
    env = mock_security_env
    user_b = env["user_b"]
    user_a_doc_id = str(env["user_a_doc"]["_id"])

    with patch("app.api.routes.documents.documents_collection", env["docs_col"]):
        app.dependency_overrides[get_current_user] = lambda: user_b
        client = TestClient(app)
        try:
            resp = client.get(f"/api/v1/documents/{user_a_doc_id}")
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Document not found."
        finally:
            app.dependency_overrides.clear()


def test_cross_user_access_blocked_on_document_chunks(mock_security_env):
    """
    Negative Test: User B cannot retrieve chunks of User A's document.
    Must return 404 Not Found.
    """
    env = mock_security_env
    user_b = env["user_b"]
    user_a_doc_id = str(env["user_a_doc"]["_id"])

    with patch("app.api.routes.documents.documents_collection", env["docs_col"]), \
         patch("app.api.routes.documents.db", env["db"]):
        app.dependency_overrides[get_current_user] = lambda: user_b
        client = TestClient(app)
        try:
            resp = client.get(f"/api/v1/documents/{user_a_doc_id}/chunks")
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Document not found."
        finally:
            app.dependency_overrides.clear()


def test_cross_user_deletion_blocked(mock_security_env):
    """
    Negative Test: User B cannot delete User A's document.
    Must return 404 and User A's document must remain untouched.
    """
    env = mock_security_env
    user_b = env["user_b"]
    user_a_doc_id = str(env["user_a_doc"]["_id"])

    with patch("app.api.routes.documents.documents_collection", env["docs_col"]), \
         patch("app.api.routes.documents.db", env["db"]):
        app.dependency_overrides[get_current_user] = lambda: user_b
        client = TestClient(app)
        try:
            resp = client.delete(f"/api/v1/documents/{user_a_doc_id}")
            assert resp.status_code == 404
            # Document still exists in database
            assert env["docs_col"].find_one({"_id": ObjectId(user_a_doc_id)}) is not None
        finally:
            app.dependency_overrides.clear()


def test_operational_cache_metrics_endpoint_requires_auth():
    """
    Verify operational endpoint /api/v1/rag/cache/metrics rejects unauthenticated access.
    """
    client = TestClient(app)
    # Request without Authorization header
    resp = client.get("/api/v1/rag/cache/metrics")
    assert resp.status_code == 401 or resp.status_code == 403


def test_logout_and_account_deletion_lifecycle(mock_security_env):
    """
    Verify logout and account deletion endpoints cleanly remove user and resources.
    """
    env = mock_security_env
    user_a = env["user_a"]
    user_a_id = user_a["_id"]

    with patch("app.api.routes.users.users_collection", env["users_col"]), \
         patch("app.api.routes.users.documents_collection", env["docs_col"]), \
         patch("app.api.routes.users.db", env["db"]):
        app.dependency_overrides[get_current_user] = lambda: user_a
        client = TestClient(app)
        try:
            # 1. Logout
            logout_resp = client.post("/api/v1/auth/logout")
            assert logout_resp.status_code == 200
            assert logout_resp.json()["message"] == "Successfully logged out"

            # 2. Account deletion
            del_resp = client.delete("/api/v1/users/me")
            assert del_resp.status_code == 204

            # Verify user record is deleted
            assert env["users_col"].find_one({"_id": user_a_id}) is None
            # Verify user documents are deleted
            assert env["docs_col"].find_one({"user_id": user_a_id}) is None
            # Verify user chunks are deleted
            assert env["chunks_col"].find_one({"document_id": str(env["user_a_doc"]["_id"])}) is None
        finally:
            app.dependency_overrides.clear()


# ==============================================================================
# Step 13.2: File Upload Hardening & Content Validation
# ==============================================================================

def test_upload_valid_pdf_success(mock_security_env):
    """Upload a structurally valid PDF document."""
    env = mock_security_env
    user_a = env["user_a"]

    # Create a minimal valid 1-page PDF using PyMuPDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Official Hardware Receipt\nTotal: $120.00")
    pdf_bytes = doc.tobytes()
    doc.close()

    with patch("app.api.routes.documents.documents_collection", env["docs_col"]), \
         patch("app.api.routes.documents.chain") as mock_chain:
        mock_chain.return_value.apply_async.return_value = None
        app.dependency_overrides[get_current_user] = lambda: user_a
        client = TestClient(app)
        try:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("receipt.pdf", pdf_bytes, "application/pdf")},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["file_type"] == "pdf"
            assert data["status"] == "UPLOADED"
        finally:
            app.dependency_overrides.clear()


def test_upload_disguised_executable_rejected():
    """
    Anti-Spoofing: An attacker sends a shell script / binary disguised with
    'application/pdf' content type and '.pdf' filename.
    Must be rejected with 400 Bad Request.
    """
    user_a = {"_id": ObjectId("65c000000000000000000001")}
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app)

    malicious_script = b"#!/bin/bash\necho 'Hacked system'\nrm -rf /"
    try:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("invoice.pdf", malicious_script, "application/pdf")},
        )
        assert resp.status_code == 400
        assert "Invalid file signature" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_upload_corrupt_malformed_pdf_rejected():
    """
    Malformed File: File has %PDF- signature but corrupted internal PDF xref structure.
    Must be safely caught by PyMuPDF and rejected with 400 Bad Request.
    """
    user_a = {"_id": ObjectId("65c000000000000000000001")}
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app)

    corrupt_pdf_bytes = b"%PDF-1.4\n%%EOF_CORRUPTED_TRUNCATED_TRAILER"
    try:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("corrupted.pdf", corrupt_pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 400
        assert "Malformed or unreadable PDF document" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_upload_empty_file_rejected():
    """Empty 0-byte file upload must be rejected with 400 Bad Request."""
    user_a = {"_id": ObjectId("65c000000000000000000001")}
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app)

    try:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "Uploaded file is empty" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_upload_file_exceeding_max_size():
    """Files exceeding maximum allowed file size must be rejected with 413."""
    user_a = {"_id": ObjectId("65c000000000000000000001")}
    app.dependency_overrides[get_current_user] = lambda: user_a
    client = TestClient(app)

    # Simulate file exceeding 10 MB limit
    with patch("app.api.routes.documents.MAX_FILE_SIZE", 500):
        try:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("oversized.pdf", b"%PDF-1.4" + b"X" * 1000, "application/pdf")},
            )
            assert resp.status_code == 413
            assert "exceeds the maximum allowed size" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


def test_upload_user_storage_quota_enforced(mock_security_env):
    """
    Storage Quota: When user storage quota is exceeded, reject with 413 Request Entity Too Large.
    """
    env = mock_security_env
    user_a = env["user_a"]

    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    # Pre-populate user storage to simulate approaching quota limit
    with patch("app.api.routes.documents.documents_collection", env["docs_col"]), \
         patch("app.core.config.settings.max_user_storage_mb", 0.0001):  # Very small quota ~100 bytes
        app.dependency_overrides[get_current_user] = lambda: user_a
        client = TestClient(app)
        try:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("receipt.pdf", pdf_bytes, "application/pdf")},
            )
            assert resp.status_code == 413
            assert "storage quota" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()


def test_upload_user_document_count_quota_enforced(mock_security_env):
    """
    Document Count Quota: When user exceeds maximum document count, reject with 400.
    """
    env = mock_security_env
    user_a = env["user_a"]

    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    with patch("app.api.routes.documents.documents_collection", env["docs_col"]), \
         patch("app.core.config.settings.max_user_documents", 1):  # User A already has 1 document
        app.dependency_overrides[get_current_user] = lambda: user_a
        client = TestClient(app)
        try:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("receipt2.pdf", pdf_bytes, "application/pdf")},
            )
            assert resp.status_code == 400
            assert "document limit" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()
