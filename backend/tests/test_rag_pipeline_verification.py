import hashlib
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient
import mongomock
import numpy as np
import pytest

from app.api.routes.rag import get_rag_answer_service, get_rag_retriever
from app.api.routes.users import get_current_user
from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.faiss_service import FAISSService
from app.services.rag_retriever import RAGRetriever

# Prevent startup delays in test clients
patch("app.main.create_indexes", lambda: None).start()
patch("app.main.FAISSService", lambda: MagicMock(status=lambda: {"total_vectors": 0, "mapped_chunks": 0, "loaded": True})).start()
mongomock.mongo_client._get_server_version = lambda: "6.0.0"


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


def setup_rag_test_environment(tmp_path):
    """Sets up a realistic isolated MongoDB + FAISS index + Repositories test fixture."""
    index_file = os.path.join(tmp_path, "test_rag.index")
    mapping_file = os.path.join(tmp_path, "test_rag.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_rag_test"]

    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    embedding_service = FastDeterministicEmbeddingService()

    retriever = RAGRetriever(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
        default_score_threshold=0.0,
    )

    return {
        "db": db,
        "chunk_repo": chunk_repo,
        "doc_repo": doc_repo,
        "faiss_service": faiss_service,
        "embedding_service": embedding_service,
        "retriever": retriever,
    }


# =====================================================================
# Checklist Item 1: Relevant evidence
# A question whose answer appears in an indexed receipt.
# Expected: Answer includes a correct value and a valid citation.
# =====================================================================
def test_checklist_1_relevant_evidence(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_id = str(ObjectId())

    # Create document for user
    doc_id = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_id),
        "user_id": user_id,
        "filename": "laptop_receipt.pdf",
    })

    # Create chunk in MongoDB
    chunk_id = f"{doc_id}_c1"
    chunk_text = "Croma Electronics: Apple MacBook Pro M3 total ₹1,99,000 on 2024-03-15"
    vec = env["embedding_service"].generate_embedding("What was my highest laptop purchase?")
    env["chunk_repo"].create_chunk({
        "document_id": doc_id,
        "chunk_id": chunk_id,
        "page": 1,
        "text": chunk_text,
        "embedding": vec,
    })

    # Index in FAISS
    env["faiss_service"].add_embeddings([{"chunk_id": chunk_id, "embedding": vec}])

    # Mock answer service
    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "The highest purchase was the Apple MacBook Pro M3 for ₹1,99,000 [S1].",
            "citations": ["S1"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_id), "id": user_id}
    app.dependency_overrides[get_rag_retriever] = lambda: env["retriever"]
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    client = TestClient(app)
    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What was my highest laptop purchase?", "top_k": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert "₹1,99,000" in data["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["document_id"] == doc_id
    assert data["sources"][0]["filename"] == "laptop_receipt.pdf"
    assert data["sources"][0]["chunk_id"] == chunk_id
    assert data["retrieval"]["sources_used"] == 1


# =====================================================================
# Checklist Item 2: No matching documents
# Ask about a product absent from the user's documents.
# Expected: Insufficient evidence; no fabricated value.
# =====================================================================
def test_checklist_2_no_matching_documents(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_id = str(ObjectId())

    # Empty FAISS index for high-similarity laptop query or zero relevant chunks
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(return_value=[])

    mock_answer_service = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_id), "id": user_id}
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    client = TestClient(app)
    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What luxury yacht did I purchase?", "top_k": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert "couldn't find sufficient relevant evidence" in data["answer"].lower()
    assert data["sources"] == []
    assert data["retrieval"]["sources_used"] == 0
    # Gemini must not even be invoked when no relevant evidence exists
    mock_answer_service.answer.assert_not_called()


# =====================================================================
# Checklist Item 3: Cross-user isolation
# Attempt retrieval when matching chunks belong to another user.
# Expected: No foreign document text or metadata is returned.
# =====================================================================
def test_checklist_3_cross_user_isolation(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_alice = str(ObjectId())
    user_bob = str(ObjectId())

    # Bob has a confidential laptop receipt
    doc_bob = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_bob),
        "user_id": user_bob,
        "filename": "bob_secret_laptop.pdf",
    })
    chunk_bob_id = f"{doc_bob}_c1"
    vec_bob = env["embedding_service"].generate_embedding("laptop purchase")
    env["chunk_repo"].create_chunk({
        "document_id": doc_bob,
        "chunk_id": chunk_bob_id,
        "page": 1,
        "text": "Bob bought Alienware Laptop total ₹3,50,000",
        "embedding": vec_bob,
    })
    env["faiss_service"].add_embeddings([{"chunk_id": chunk_bob_id, "embedding": vec_bob}])

    # Alice queries about laptops; Alice has NO laptop documents
    mock_answer_service = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_alice), "id": user_alice}
    app.dependency_overrides[get_rag_retriever] = lambda: env["retriever"]
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    client = TestClient(app)
    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What laptop did I buy?", "top_k": 5},
    )

    assert response.status_code == 200
    data = response.json()
    # Alice must NOT receive Bob's document or secret details
    assert "Alienware" not in json.dumps(data)
    assert "bob_secret_laptop.pdf" not in json.dumps(data)
    assert data["sources"] == []
    assert data["retrieval"]["sources_used"] == 0


# =====================================================================
# Checklist Item 4: Invalid citation
# Simulate Gemini returning an unknown source ID.
# Expected: Unsupported answer is rejected or retried safely.
# =====================================================================
def test_checklist_4_invalid_citation(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_id = str(ObjectId())

    # Valid chunk exists
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_valid_1",
                "document_id": "doc_101",
                "filename": "groceries.pdf",
                "page": 1,
                "text": "Apples and milk: ₹450",
                "score": 0.9,
            }
        ]
    )

    # Gemini hallucinates an unsupported answer with fake citation IDs
    mock_answer_service = MagicMock()
    mock_answer_service.answer = AsyncMock(
        return_value={
            "answer": "You purchased a private jet for $100M [S99].",
            "citations": ["S99", "INVALID_SOURCE"],
        }
    )

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_id), "id": user_id}
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service

    client = TestClient(app)
    response = client.post(
        "/api/v1/rag/ask",
        json={"question": "What did I buy?"},
    )

    assert response.status_code == 200
    data = response.json()
    # Hallucinated answer must be safely replaced
    assert "couldn't establish a sufficiently supported answer" in data["answer"].lower()
    assert data["sources"] == []
    assert data["retrieval"]["sources_used"] == 0


# =====================================================================
# Checklist Item 5: Deleted chunk
# Delete a MongoDB chunk while its FAISS entry still exists.
# Expected: Stale index entry is skipped.
# =====================================================================
def test_checklist_5_deleted_chunk_skipped(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_id = str(ObjectId())

    doc_id = str(ObjectId())
    env["db"]["documents"].insert_one({
        "_id": ObjectId(doc_id),
        "user_id": user_id,
        "filename": "receipt.pdf",
    })

    # Chunk is in FAISS, but NEVER in MongoDB (or deleted from MongoDB)
    stale_chunk_id = f"{doc_id}_stale_chunk"
    vec = env["embedding_service"].generate_embedding("laptop")
    env["faiss_service"].add_embeddings([{"chunk_id": stale_chunk_id, "embedding": vec}])

    # No matching chunk in MongoDB -> retriever should gracefully return []
    import asyncio
    retrieved = asyncio.run(
        env["retriever"].retrieve(
            question="laptop",
            user_id=user_id,
            top_k=5,
        )
    )
    assert retrieved == []


# =====================================================================
# Checklist Item 6: Provider failure
# Simulate a Gemini timeout or malformed JSON.
# Expected: Controlled error response; no stack trace exposed.
# =====================================================================
def test_checklist_6_provider_failure(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_id = str(ObjectId())

    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "c_1",
                "document_id": "doc_1",
                "filename": "doc.pdf",
                "page": 1,
                "text": "Total ₹1,000",
                "score": 0.8,
            }
        ]
    )

    # Case A: Timeout -> 504 Gateway Timeout
    mock_answer_service_timeout = MagicMock()
    mock_answer_service_timeout.answer = AsyncMock(side_effect=TimeoutError("Connection timed out"))

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_id), "id": user_id}
    app.dependency_overrides[get_rag_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service_timeout

    client = TestClient(app)
    res_timeout = client.post("/api/v1/rag/ask", json={"question": "Total?"})
    assert res_timeout.status_code == 504
    assert res_timeout.json()["detail"] == "Upstream AI provider timed out. Please try again."

    # Case B: Malformed JSON from Gemini -> 502 Bad Gateway
    mock_answer_service_malformed = MagicMock()
    mock_answer_service_malformed.answer = AsyncMock(side_effect=ValueError("Invalid JSON"))
    app.dependency_overrides[get_rag_answer_service] = lambda: mock_answer_service_malformed

    res_malformed = client.post("/api/v1/rag/ask", json={"question": "Total?"})
    assert res_malformed.status_code == 502
    assert res_malformed.json()["detail"] == "Unable to generate a valid grounded answer."
    # Ensure no internal traceback is returned
    assert "traceback" not in json.dumps(res_malformed.json()).lower()


# =====================================================================
# Checklist Item 7: Index unavailable
# Run a request with an uninitialized FAISS service.
# Expected: Controlled service error, not a misleading answer.
# =====================================================================
def test_checklist_7_index_unavailable(tmp_path):
    env = setup_rag_test_environment(tmp_path)
    user_id = str(ObjectId())

    # Simulate broken/uninitialized index raising an error during retrieve
    broken_retriever = MagicMock()
    broken_retriever.retrieve = AsyncMock(side_effect=RuntimeError("FAISS index unavailable"))

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_id), "id": user_id}
    app.dependency_overrides[get_rag_retriever] = lambda: broken_retriever
    app.dependency_overrides[get_rag_answer_service] = lambda: MagicMock()

    client = TestClient(app)
    response = client.post("/api/v1/rag/ask", json={"question": "Total?"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to retrieve document evidence."
    # Does not fabricate an answer
    assert "answer" not in response.json()
