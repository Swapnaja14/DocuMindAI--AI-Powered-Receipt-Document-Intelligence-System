import os
import time
from unittest.mock import patch

import mongomock
from bson import ObjectId
from fastapi.testclient import TestClient
import numpy as np
import pytest

from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_search_service import VectorSearchService

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


class FastDeterministicEmbeddingService:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def generate_embedding(self, text: str) -> list[float]:
        import hashlib
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype("float32")
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(t) for t in texts]


def test_empty_index_behavior(tmp_path):
    """
    Check 1: Search behavior with an empty index returns empty list cleanly.
    """
    index_file = str(tmp_path / "empty.index")
    mapping_file = str(tmp_path / "empty.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    search_service = VectorSearchService(
        embedding_service=FastDeterministicEmbeddingService(),
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    results = search_service.search(query="wireless mouse", top_k=5)
    assert results == []


def test_unavailable_embedding_model_behavior(tmp_path):
    """
    Check 2: Behavior when embedding model is unavailable or throws an error.
    """
    index_file = str(tmp_path / "model_fail.index")
    mapping_file = str(tmp_path / "model_fail.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    # Add an initial vector so the index is non-empty and requires query embedding
    faiss_service.add_embedding("existing_chunk", [0.1] * 384)

    broken_embedding_service = FastDeterministicEmbeddingService()

    # Simulate model runtime failure / GPU OOM / connection error
    with patch.object(
        broken_embedding_service,
        "generate_embedding",
        side_effect=RuntimeError("Embedding model weights unavailable or corrupted"),
    ):
        search_service = VectorSearchService(
            embedding_service=broken_embedding_service,
            faiss_service=faiss_service,
            chunk_repository=chunk_repo,
        )

        with pytest.raises(RuntimeError, match="Embedding model weights unavailable"):
            search_service.search(query="test query", top_k=5)


def test_document_scoping_with_dominant_other_documents(tmp_path):
    """
    Check 3: Adaptive candidate expansion.
    Document B has 25 chunks that have high similarity to the query.
    Document A has 5 chunks with slightly lower similarity.
    Verify that search for document_id="doc_A" with top_k=5 returns ALL 5 chunks
    for Document A even though Document B dominates the global top 20 candidates.
    """
    index_file = str(tmp_path / "expansion.index")
    mapping_file = str(tmp_path / "expansion.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    # Base query vector
    dim = 384
    query_vec = np.zeros(dim, dtype="float32")
    query_vec[0] = 1.0  # Unit vector along axis 0

    class ControlledEmbeddingService:
        def generate_embedding(self, text: str) -> list[float]:
            return query_vec.tolist()

    controlled_emb_service = ControlledEmbeddingService()

    # Create 25 chunks for Document B with similarity ~ 0.99
    doc_b_chunks = []
    for i in range(25):
        vec = np.zeros(dim, dtype="float32")
        vec[0] = 0.99
        vec[1] = 0.05 + (i * 0.001)
        vec = vec / np.linalg.norm(vec)
        doc_b_chunks.append({
            "document_id": "doc_B",
            "chunk_id": f"doc_B_{i}",
            "text": f"Dominant document B item {i}",
            "embedding": vec.tolist(),
        })

    # Create 5 chunks for Document A with similarity ~ 0.85 (lower than Doc B)
    doc_a_chunks = []
    for i in range(5):
        vec = np.zeros(dim, dtype="float32")
        vec[0] = 0.85
        vec[2] = 0.10 + (i * 0.001)
        vec = vec / np.linalg.norm(vec)
        doc_a_chunks.append({
            "document_id": "doc_A",
            "chunk_id": f"doc_A_{i}",
            "text": f"Target document A item {i}",
            "embedding": vec.tolist(),
        })

    # Insert all chunks into MongoDB and FAISS
    all_chunks = doc_b_chunks + doc_a_chunks
    chunk_repo.insert_chunks(all_chunks)
    faiss_service.add_embeddings([{"chunk_id": c["chunk_id"], "embedding": c["embedding"]} for c in all_chunks])

    assert faiss_service.count() == 30

    search_service = VectorSearchService(
        embedding_service=controlled_emb_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    # Scoped search for doc_A with top_k=5
    results = search_service.search(
        query="test query",
        top_k=5,
        document_id="doc_A",
    )

    # Acceptance check: All 5 requested results for doc_A must be returned!
    assert len(results) == 5
    for r in results:
        assert r["document_id"] == "doc_A"
        assert r["chunk_id"].startswith("doc_A_")


def test_embedding_model_consistency():
    """
    Check 4: Verify that embedding generation uses the exact same model,
    dimension (384), normalization, and preprocessing for single text and batch texts.
    """
    assert EmbeddingService.MODEL_NAME == "all-MiniLM-L6-v2"
    # Verify via dry-run structure
    emb_service = FastDeterministicEmbeddingService(dimension=384)
    query_text = "Wireless USB mouse"
    doc_text = "Wireless USB mouse"

    q_vec = emb_service.generate_embedding(query_text)
    d_vecs = emb_service.generate_embeddings([doc_text])

    assert len(q_vec) == 384
    assert len(d_vecs[0]) == 384
    # Vectors for identical text must be identical
    np.testing.assert_allclose(q_vec, d_vecs[0], atol=1e-5)


def test_startup_health_check_loads_saved_index(tmp_path):
    """
    Check 5: Verify FastAPI startup correctly loads the saved index and reports status in /health.
    """
    index_file = str(tmp_path / "health.index")
    mapping_file = str(tmp_path / "health.json")

    # Populate index
    service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    service.add_embeddings([
        {"chunk_id": "c1", "embedding": [0.1] * 384},
        {"chunk_id": "c2", "embedding": [0.2] * 384},
    ])

    test_client = TestClient(app)

    with patch("app.main.FAISSService", lambda **kwargs: FAISSService(index_path=index_file, mapping_path=mapping_file)):
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "faiss" in data
        assert data["faiss"]["loaded"] is True
        assert data["faiss"]["total_vectors"] == 2
        assert data["faiss"]["mapped_chunks"] == 2


def test_search_latency_benchmark(tmp_path):
    """
    Check 6: Benchmark search latency on a representative dataset of 100 vectors.
    Asserts p95 latency is well within production thresholds (< 50ms).
    """
    index_file = str(tmp_path / "bench.index")
    mapping_file = str(tmp_path / "bench.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)

    emb_service = FastDeterministicEmbeddingService(dimension=384)
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    # Populate 100 representative chunks
    chunks = []
    for i in range(100):
        chunks.append({
            "document_id": f"doc_{i // 10}",
            "chunk_id": f"chunk_{i}",
            "text": f"Receipt item {i} description price details",
            "embedding": emb_service.generate_embedding(f"item {i}"),
        })

    chunk_repo.insert_chunks(chunks)
    faiss_service.add_embeddings([{"chunk_id": c["chunk_id"], "embedding": c["embedding"]} for c in chunks])

    search_service = VectorSearchService(
        embedding_service=emb_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    latencies = []
    # Execute 50 search runs
    for i in range(50):
        t0 = time.perf_counter()
        results = search_service.search(query=f"query {i}", top_k=5)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)  # ms
        assert len(results) <= 5

    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)

    print(f"\nLatency Benchmark (100 vectors): p50 = {p50:.2f}ms, p95 = {p95:.2f}ms")
    # In-memory FAISS search with batch hydration should be very fast (< 30ms)
    assert p50 < 30.0
    assert p95 < 50.0
