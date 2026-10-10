import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId
from fastapi.testclient import TestClient
import mongomock
import numpy as np
import pytest

from app.api.routes.rag import get_rag_answer_service, get_rag_retriever
from app.api.routes.search import get_document_repository, get_search_rag_retriever
from app.api.routes.users import get_current_user
from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.faiss_service import FAISSService
from app.services.rag_retriever import RAGRetriever

from contextlib import asynccontextmanager

# Prevent test startup delays
patch("app.main.create_indexes", lambda: None).start()
patch("app.core.database.create_indexes", lambda: None).start()
patch("app.main.FAISSService", lambda: MagicMock(status=lambda: {"total_vectors": 0, "mapped_chunks": 0, "loaded": True})).start()
mongomock.mongo_client._get_server_version = lambda: "6.0.0"

@asynccontextmanager
async def _noop_lifespan(app):
    yield

app.router.lifespan_context = _noop_lifespan


class FastDeterministicEmbeddingService:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def generate_embedding(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.lower().encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype("float32")
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    async def embed_query(self, text: str) -> list[float]:
        return self.generate_embedding(text)


def setup_test_env(tmp_path):
    index_file = os.path.join(tmp_path, "search_modes.index")
    mapping_file = os.path.join(tmp_path, "search_modes.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_modes_test"]

    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    embedding_service = FastDeterministicEmbeddingService()

    retriever = RAGRetriever(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
        default_score_threshold=-1.0,
    )

    return {
        "db": db,
        "chunk_repo": chunk_repo,
        "doc_repo": doc_repo,
        "faiss_service": faiss_service,
        "embedding_service": embedding_service,
        "retriever": retriever,
    }


# ============================================================================
# Mode A: Structured Filtering Tests
# ============================================================================
def test_mode_a_structured_filtering_by_vendor(tmp_path):
    env = setup_test_env(tmp_path)
    user_a = str(ObjectId())
    user_b = str(ObjectId())

    # User A document from Amazon
    env["db"]["documents"].insert_one({
        "_id": ObjectId(),
        "user_id": user_a,
        "filename": "amazon_invoice.pdf",
        "extracted_data": {
            "vendor": "Amazon India",
            "invoice_number": "INV-101",
            "total": 3500.0,
            "currency": "INR",
            "date": "2024-02-10",
            "items": [{"description": "Keyboard", "amount": 3500.0}],
        },
    })

    # User A document from Walmart
    env["db"]["documents"].insert_one({
        "_id": ObjectId(),
        "user_id": user_a,
        "filename": "walmart_receipt.pdf",
        "extracted_data": {
            "vendor": "Walmart",
            "invoice_number": "W-555",
            "total": 1200.0,
            "currency": "USD",
            "date": "2024-01-15",
            "items": [{"description": "Groceries", "amount": 1200.0}],
        },
    })

    # User B document from Amazon (must be isolated)
    env["db"]["documents"].insert_one({
        "_id": ObjectId(),
        "user_id": user_b,
        "filename": "bob_amazon.pdf",
        "extracted_data": {
            "vendor": "Amazon",
            "total": 9999.0,
        },
    })

    # Override repository and auth dependencies
    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_a), "id": user_a}
    app.dependency_overrides[get_document_repository] = lambda: env["doc_repo"]
    client = TestClient(app)

    try:
        # 1. Filter by vendor "Amazon"
        res = client.post("/api/v1/search/filters", json={"vendor": "Amazon"})
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "structured"
        assert data["total_matches"] == 1
        assert data["receipts"][0]["vendor"] == "Amazon India"
        assert data["receipts"][0]["total"] == 3500.0

        # 2. Filter by numeric range total >= 2000
        res_range = client.post("/api/v1/search/filters", json={"min_total": 2000.0})
        assert res_range.status_code == 200
        data_range = res_range.json()
        assert data_range["total_matches"] == 1
        assert data_range["receipts"][0]["total"] == 3500.0

        # 3. Filter by currency "USD"
        res_curr = client.post("/api/v1/search/filters", json={"currency": "USD"})
        assert res_curr.status_code == 200
        data_curr = res_curr.json()
        assert data_curr["total_matches"] == 1
        assert data_curr["receipts"][0]["vendor"] == "Walmart"
    finally:
        app.dependency_overrides.clear()


# ============================================================================
# Mode B: Semantic Search Tests
# ============================================================================
def test_mode_b_semantic_search(tmp_path):
    env = setup_test_env(tmp_path)
    user_a = str(ObjectId())
    user_b = str(ObjectId())

    # User A chunks
    doc_a = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_a),
        "user_id": user_a,
        "filename": "logitech_mouse.pdf",
    })
    chunk_a_id = f"{doc_a}_c1"
    vec_a = env["embedding_service"].generate_embedding("computer accessories wireless mouse")
    env["chunk_repo"].create_chunk({
        "document_id": doc_a,
        "chunk_id": chunk_a_id,
        "page": 1,
        "text": "Logitech Wireless Optical Mouse ₹899",
        "embedding": vec_a,
    })
    env["faiss_service"].add_embeddings([{"chunk_id": chunk_a_id, "embedding": vec_a}])

    # User B chunk (must be isolated)
    doc_b = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_b),
        "user_id": user_b,
        "filename": "bob_mouse.pdf",
    })
    chunk_b_id = f"{doc_b}_c1"
    vec_b = env["embedding_service"].generate_embedding("computer accessories keyboard")
    env["chunk_repo"].create_chunk({
        "document_id": doc_b,
        "chunk_id": chunk_b_id,
        "page": 1,
        "text": "Mechanical Gaming Keyboard ₹4,500",
        "embedding": vec_b,
    })
    env["faiss_service"].add_embeddings([{"chunk_id": chunk_b_id, "embedding": vec_b}])

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_a), "id": user_a}
    app.dependency_overrides[get_search_rag_retriever] = lambda: env["retriever"]

    client = TestClient(app)
    try:
        res = client.post(
            "/api/v1/search/semantic",
            json={"query": "Find computer accessories", "top_k": 5},
        )

        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "semantic"
        assert data["total_results"] == 1
        assert data["results"][0]["document_id"] == doc_a
        assert data["results"][0]["filename"] == "logitech_mouse.pdf"
        assert "Logitech" in data["results"][0]["text"]
        assert "score" in data["results"][0]
    finally:
        app.dependency_overrides.clear()


# ============================================================================
# Mode C: RAG Question Answering & "Highest Purchase" Edge Case
# ============================================================================
def test_mode_c_rag_highest_purchase_handling(tmp_path):
    env = setup_test_env(tmp_path)
    user_a = str(ObjectId())

    # Document 1: Budget Laptop
    doc_1 = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_1),
        "user_id": user_a,
        "filename": "acer_laptop.pdf",
        "extracted_data": {
            "vendor": "Acer Store",
            "total": 45000.0,
            "currency": "INR",
            "date": "2023-11-01",
        },
    })
    chunk_1_id = f"{doc_1}_c1"
    vec_1 = env["embedding_service"].generate_embedding("Acer Aspire 5 Laptop")
    env["chunk_repo"].create_chunk({
        "document_id": doc_1,
        "chunk_id": chunk_1_id,
        "page": 1,
        "text": "Acer Aspire 5 Laptop purchase total ₹45,000",
        "embedding": vec_1,
    })
    env["faiss_service"].add_embeddings([{"chunk_id": chunk_1_id, "embedding": vec_1}])

    # Document 2: Premium Laptop (Higher total)
    doc_2 = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_2),
        "user_id": user_a,
        "filename": "apple_macbook.pdf",
        "extracted_data": {
            "vendor": "Apple Store",
            "total": 199000.0,
            "currency": "INR",
            "date": "2024-03-20",
        },
    })
    chunk_2_id = f"{doc_2}_c1"
    vec_2 = env["embedding_service"].generate_embedding("Apple MacBook Pro 16")
    env["chunk_repo"].create_chunk({
        "document_id": doc_2,
        "chunk_id": chunk_2_id,
        "page": 1,
        "text": "Apple MacBook Pro 16 M3 Max total ₹1,99,000",
        "embedding": vec_2,
    })
    env["faiss_service"].add_embeddings([{"chunk_id": chunk_2_id, "embedding": vec_2}])

    # Verify that retriever attaches extracted totals
    import asyncio
    question = "What was my highest laptop purchase?"
    retrieved = asyncio.run(
        env["retriever"].retrieve(
            question=question,
            user_id=user_a,
            top_k=5,
        )
    )
    assert len(retrieved) == 2
    # Verify structured fields are attached
    assert any(r.get("extracted_total") == 199000.0 for r in retrieved)
    assert any(r.get("extracted_total") == 45000.0 for r in retrieved)

    # Determine the source ID for doc_2 based on retrieval rank order
    doc_2_source_id = "S1" if retrieved[0]["document_id"] == doc_2 else "S2"

    # Mock answer service comparing both receipts
    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": f"Among your retrieved receipts, the highest laptop purchase was ₹1,99,000 for the Apple MacBook Pro 16 [{doc_2_source_id}].",
            "citations": [doc_2_source_id],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_a), "id": user_a}
    app.dependency_overrides[get_rag_retriever] = lambda: env["retriever"]
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    client = TestClient(app)
    try:
        res = client.post(
            "/api/v1/rag/ask",
            json={"question": question, "top_k": 5},
        )

        assert res.status_code == 200
        data = res.json()
        assert "₹1,99,000" in data["answer"]
        assert len(data["sources"]) == 1
        assert data["sources"][0]["document_id"] == doc_2
        assert data["sources"][0]["filename"] == "apple_macbook.pdf"
        assert data["retrieval"]["sources_used"] == 1
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        print("Running Mode A: Structured Filtering...", flush=True)
        test_mode_a_structured_filtering_by_vendor(td)
        print("[PASS] Mode A passed!", flush=True)
        print("Running Mode B: Semantic Search...", flush=True)
        test_mode_b_semantic_search(td)
        print("[PASS] Mode B passed!", flush=True)
        print("Running Mode C: RAG Question Answering & Highest Purchase Edge Case...", flush=True)
        test_mode_c_rag_highest_purchase_handling(td)
        print("[PASS] Mode C passed!", flush=True)
        print("=== ALL 3 SEARCH MODES VERIFIED SUCCESSFULLY! ===", flush=True)
