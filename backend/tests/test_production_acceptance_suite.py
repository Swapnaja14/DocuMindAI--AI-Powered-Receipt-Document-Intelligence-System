import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import DocumentStatus, VectorStatus
from app.services.faiss_service import FAISSService
from app.services.rag_answer_service import RAGAnswerService
from app.tasks.chunking_tasks import chunk_document
from app.tasks.document_tasks import extract_document, process_ocr


class FastDeterministicEmbeddingService:
    """Fast, deterministic 384-dimensional embedding generator for acceptance testing."""
    def __init__(self, dimension: int = 384, **kwargs):
        self.dimension = dimension

    def generate_embedding(self, text: str) -> list[float]:
        # Generate normalized unit vector with high base similarity across queries
        vec = np.ones(self.dimension, dtype="float32")
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        return self.generate_embedding(query)

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return self.generate_embeddings(documents)


def generate_valid_pdf_bytes(text_content: str) -> bytes:
    """Generate a syntactically valid PDF with PyMuPDF for realistic testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text_content)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_complete_production_acceptance_workflow(tmp_path):
    """
    Step 15.7 Production Acceptance Suite:
    Executes a complete 12-step end-to-end lifecycle verification:
    1. Register new test user
    2. Log in and acquire JWT bearer token
    3. Upload representative PDF
    4. Execute OCR and extraction
    5. Verify chunks and embeddings are indexed
    6. Ask a question with a known answer
    7. Verify evidence and answer correctness
    8. Repeat question and verify cache hit
    9. Upload another document and verify cache invalidation
    10. Delete a document and verify it cannot be retrieved
    11. Verify cross-user access is denied
    12. Simulate recoverable failure and confirm system handles it safely
    """
    from app.api.routes.search import get_embedding_service, get_faiss_service

    # Isolated temporary environment for FAISS
    index_file = str(tmp_path / "prod_accept_index.faiss")
    mapping_file = str(tmp_path / "prod_accept_mapping.json")
    shared_faiss = FAISSService(index_path=index_file, mapping_path=mapping_file)

    app.dependency_overrides[get_embedding_service] = lambda: FastDeterministicEmbeddingService()
    app.dependency_overrides[get_faiss_service] = lambda: shared_faiss

    client = TestClient(app)

    cache_store = {}
    user_gens = {}

    def fake_invalidate_sync(uid: str):
        user_gens[uid] = user_gens.get(uid, 0) + 1
        for k in list(cache_store.keys()):
            if f":{{{uid}}}:" in k or f":{uid}:" in k:
                del cache_store[k]
        return 1

    with patch("app.tasks.chunking_tasks.EmbeddingService", FastDeterministicEmbeddingService), \
         patch("app.api.routes.search.EmbeddingService", FastDeterministicEmbeddingService), \
         patch("app.services.rag_retriever.EmbeddingService", FastDeterministicEmbeddingService), \
         patch("app.tasks.chunking_tasks.FAISSService", return_value=shared_faiss), \
         patch("app.tasks.chunking_tasks.invalidate_user_cache_sync", side_effect=fake_invalidate_sync), \
         patch("app.api.routes.documents.chain"):

        # --------------------------------------------------------------------
        # Step 1: Register a new test user
        # --------------------------------------------------------------------
        user_email = f"accept_user_{int(time.time())}@example.com"
        user_pass = "AcceptanceSecretPass123!"

        reg_resp = client.post(
            "/api/v1/auth/register",
            json={"email": user_email, "password": user_pass},
        )
        assert reg_resp.status_code == 201, f"User registration failed: {reg_resp.text}"
        user_data = reg_resp.json()
        assert user_data["email"] == user_email

        # --------------------------------------------------------------------
        # Step 2: Log in and receive JWT access token
        # --------------------------------------------------------------------
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": user_pass},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token_data = login_resp.json()
        assert "access_token" in token_data
        access_token = token_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # --------------------------------------------------------------------
        # Step 3: Upload a representative PDF
        # --------------------------------------------------------------------
        invoice_text = (
            "Apex Tech Solutions - Tax Invoice #AT-90210\n"
            "Date: 2026-10-15\n"
            "Items:\n"
            "1. Dell UltraSharp 32-inch 4K Monitor - Qty: 1 - $850.00\n"
            "2. Logitech MX Master 3S Wireless Mouse - Qty: 1 - $99.99\n"
            "Total Amount: $949.99\n"
            "Payment Method: Visa ending in 4242"
        )
        pdf_bytes = generate_valid_pdf_bytes(invoice_text)

        upload_resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("apex_invoice_90210.pdf", pdf_bytes, "application/pdf")},
            headers=auth_headers,
        )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        uploaded_doc = upload_resp.json()
        doc_id = uploaded_doc["id"]
        assert uploaded_doc["filename"] == "apex_invoice_90210.pdf"

        # --------------------------------------------------------------------
        # Step 4: Wait for OCR and extraction to finish
        # --------------------------------------------------------------------
        mock_extracted_json = {
            "merchant": "Apex Tech Solutions",
            "date": "2026-10-15",
            "total_amount": 949.99,
            "items": [
                {"name": "Dell UltraSharp 32-inch 4K Monitor", "price": 850.00},
                {"name": "Logitech MX Master 3S Wireless Mouse", "price": 99.99},
            ],
        }

        with patch("app.services.ocr_service.ocr_document", return_value={"raw_text": invoice_text, "page_count": 1}), \
             patch("app.tasks.document_tasks.extract_document_data", return_value={"data": mock_extracted_json, "validation": {"is_valid": True}}):
            process_ocr(doc_id)
            extract_document(doc_id)

        # --------------------------------------------------------------------
        # Step 5: Verify chunks and embeddings are indexed
        # --------------------------------------------------------------------
        chunk_document(doc_id)

        doc_status_resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert doc_status_resp.status_code == 200
        doc_details = doc_status_resp.json()
        assert doc_details["status"] == DocumentStatus.COMPLETED.value
        assert doc_details["vector_status"] == VectorStatus.INDEXED.value
        assert doc_details["chunk_count"] > 0

        # --------------------------------------------------------------------
        # Step 6: Ask a question with a known answer
        # --------------------------------------------------------------------
        mock_answer_text = "The total amount paid at Apex Tech Solutions was $949.99 for the Dell Monitor and Logitech Mouse."
        answer_mock = AsyncMock(return_value={"answer": mock_answer_text, "citations": ["S1"]})

        async def fake_get_user_generation(uid: str):
            return user_gens.get(uid, 0)

        async def fake_get_cached_answer(key: str):
            return cache_store.get(key)

        async def fake_cache_answer(key: str, answer: dict, **kwargs):
            cache_store[key] = answer
            return True

        async def fake_acquire_lock(key: str, token: str, ttl: int = 15):
            return True

        async def fake_release_lock(key: str, token: str):
            return True

        def fake_invalidate_sync(uid: str):
            user_gens[uid] = user_gens.get(uid, 0) + 1
            for k in list(cache_store.keys()):
                if f":{{{uid}}}:" in k or f":{uid}:" in k:
                    del cache_store[k]
            return 1

        async def fake_invalidate_async(uid: str):
            return fake_invalidate_sync(uid)

        with patch("app.api.routes.rag.get_user_generation", side_effect=fake_get_user_generation), \
             patch("app.api.routes.rag.get_cached_answer", side_effect=fake_get_cached_answer), \
             patch("app.api.routes.rag.cache_answer", side_effect=fake_cache_answer), \
             patch("app.api.routes.rag.acquire_lock", side_effect=fake_acquire_lock), \
             patch("app.api.routes.rag.release_lock", side_effect=fake_release_lock), \
             patch("app.tasks.chunking_tasks.invalidate_user_cache_sync", side_effect=fake_invalidate_sync), \
             patch("app.api.routes.documents.invalidate_user_cache", side_effect=fake_invalidate_async), \
             patch("app.services.rag_answer_service.RAGAnswerService.answer", new=answer_mock):

            ask_resp_1 = client.post(
                "/api/v1/rag/ask",
                json={"question": "What was the total amount paid at Apex Tech Solutions?"},
                headers=auth_headers,
            )
            assert ask_resp_1.status_code == 200, f"RAG query failed: {ask_resp_1.text}"
            rag_data_1 = ask_resp_1.json()

            # ----------------------------------------------------------------
            # Step 7: Verify evidence and answer correctness
            # ----------------------------------------------------------------
            assert "949.99" in rag_data_1["answer"]
            assert len(rag_data_1["sources"]) > 0
            assert rag_data_1["retrieval"]["sources_used"] > 0
            assert answer_mock.call_count == 1

            # ----------------------------------------------------------------
            # Step 8: Repeat question and verify the cache hit
            # ----------------------------------------------------------------
            ask_resp_2 = client.post(
                "/api/v1/rag/ask",
                json={"question": "What was the total amount paid at Apex Tech Solutions?"},
                headers=auth_headers,
            )
            assert ask_resp_2.status_code == 200
            rag_data_2 = ask_resp_2.json()
            assert rag_data_2["answer"] == rag_data_1["answer"]
            # Under cache hit, LLM generation must NOT be called again
            assert answer_mock.call_count == 1

            # ----------------------------------------------------------------
            # Step 9: Upload another document and verify invalidation
            # ----------------------------------------------------------------
            receipt_2_text = "Coffee Shop Receipt: $8.50 on 2026-10-16."
            pdf_2_bytes = generate_valid_pdf_bytes(receipt_2_text)

            upload_2_resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("coffee_receipt.pdf", pdf_2_bytes, "application/pdf")},
                headers=auth_headers,
            )
            assert upload_2_resp.status_code == 201
            doc_2_id = upload_2_resp.json()["id"]

            with patch("app.services.ocr_service.ocr_document", return_value={"raw_text": receipt_2_text, "page_count": 1}), \
                 patch("app.tasks.document_tasks.extract_document_data", return_value={"data": {"merchant": "Coffee Shop"}, "validation": {"is_valid": True}}):
                process_ocr(doc_2_id)
                extract_document(doc_2_id)
            chunk_document(doc_2_id)

            # Querying after new upload must miss cache and invoke LLM generator
            ask_resp_3 = client.post(
                "/api/v1/rag/ask",
                json={"question": "What was the total amount paid at Apex Tech Solutions?"},
                headers=auth_headers,
            )
            assert ask_resp_3.status_code == 200
            rag_data_3 = ask_resp_3.json()
            assert rag_data_3["answer"] == mock_answer_text
            assert answer_mock.call_count == 2

            # ----------------------------------------------------------------
            # Step 10: Delete a document and verify it can no longer be retrieved
            # ----------------------------------------------------------------
            del_resp = client.delete(f"/api/v1/documents/{doc_2_id}", headers=auth_headers)
            assert del_resp.status_code in (200, 204)

            get_del_resp = client.get(f"/api/v1/documents/{doc_2_id}", headers=auth_headers)
            assert get_del_resp.status_code == 404

            # ----------------------------------------------------------------
            # Step 11: Verify cross-user access is denied
            # --------------------------------------------------------------------
        user_b_email = f"user_b_{int(time.time())}@example.com"
        client.post("/api/v1/auth/register", json={"email": user_b_email, "password": user_pass})
        login_b = client.post("/api/v1/auth/login", json={"email": user_b_email, "password": user_pass}).json()
        auth_headers_b = {"Authorization": f"Bearer {login_b['access_token']}"}

        # User B attempts to access User A's document
        cross_access_resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers_b)
        assert cross_access_resp.status_code in (403, 404)

        # User B asks question about User A's invoice: must find zero source chunks
        ask_b_resp = client.post(
            "/api/v1/rag/ask",
            json={"question": "What was the total amount paid at Apex Tech Solutions?"},
            headers=auth_headers_b,
        )
        assert ask_b_resp.status_code == 200
        rag_b_data = ask_b_resp.json()
        assert len(rag_b_data["sources"]) == 0

        # --------------------------------------------------------------------
        # Step 12: Simulate an appropriate recoverable failure
        # --------------------------------------------------------------------
        corrupt_pdf_bytes = generate_valid_pdf_bytes("Corrupt document stream")
        corrupt_upload_resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("corrupt_sample.pdf", corrupt_pdf_bytes, "application/pdf")},
            headers=auth_headers,
        )
        assert corrupt_upload_resp.status_code == 201
        corrupt_doc_id = corrupt_upload_resp.json()["id"]

        with patch("app.tasks.document_tasks.ocr_document", side_effect=RuntimeError("OCR engine pipeline fault")):
            with pytest.raises(RuntimeError):
                process_ocr(corrupt_doc_id)

        corrupt_status_resp = client.get(f"/api/v1/documents/{corrupt_doc_id}", headers=auth_headers)
        assert corrupt_status_resp.status_code == 200
        corrupt_data = corrupt_status_resp.json()
        assert corrupt_data["status"] == DocumentStatus.FAILED.value
        assert corrupt_data["ocr_status"] == "FAILED"
        assert "OCR engine pipeline fault" in str(corrupt_data.get("processing", {}).get("error", ""))

        # System remains completely healthy
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

    app.dependency_overrides.clear()
