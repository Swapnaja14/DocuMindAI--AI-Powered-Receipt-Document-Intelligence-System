import mongomock
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_indexing_service import VectorIndexingService
from app.services.vector_search_service import VectorSearchService
from app.api.routes.search import get_vector_search_service


def test_search_api_endpoint(tmp_path):
    # Setup test environment
    index_file = str(tmp_path / "api_test.index")
    client_db = mongomock.MongoClient()["test_documind"]

    chunk_repo = ChunkRepository(client_db)
    mapping_repo = VectorMappingRepository(client_db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)

    indexing_service = VectorIndexingService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
    )

    doc_id = "doc123"
    chunks = [
        {"chunk_id": 0, "text": "Wireless mouse ₹799", "document_id": doc_id},
        {"chunk_id": 1, "text": "USB keyboard ₹1299", "document_id": doc_id},
    ]

    chunk_repo.insert_chunks(chunks)
    indexing_service.index_chunks(document_id=doc_id, chunks=chunks)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
        chunk_repository=chunk_repo,
    )

    # Override dependency in FastAPI app
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)

        payload = {
            "query": "computer mouse",
            "top_k": 5,
        }

        response = client.post("/api/search", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        results = data["results"]
        assert len(results) == 2

        top_hit = results[0]
        assert top_hit["document_id"] == "doc123"
        assert top_hit["chunk_id"] == 0
        assert "Wireless mouse" in top_hit["text"]
        assert isinstance(top_hit["score"], float)
        assert top_hit["score"] > 0.5

    finally:
        app.dependency_overrides.clear()


def test_search_api_empty_query_validation():
    client = TestClient(app)
    response = client.post("/api/search", json={"query": ""})
    assert response.status_code == 422
