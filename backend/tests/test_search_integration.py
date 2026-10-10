import mongomock
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_search_service import VectorSearchService
from app.api.routes.search import get_vector_search_service

# Ensure mongomock uses a modern server version string on Windows
mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_real_semantic_search(tmp_path):
    """
    Real end-to-end integration test verifying schema contract on FastAPI /api/search.
    """
    index_file = str(tmp_path / "integration_search.index")
    mapping_file = str(tmp_path / "integration_mapping.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_integration"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    doc_id = str(ObjectId())
    chunks = [
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_0",
            "page": 1,
            "text": "Wireless Logitech mouse purchased for $24.99.",
        },
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_1",
            "page": 1,
            "text": "Whole wheat bread and milk.",
        },
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_2",
            "page": 1,
            "text": "USB keyboard and wireless mouse.",
        },
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_3",
            "page": 1,
            "text": "Restaurant dinner with Italian wine and pasta.",
        },
    ]

    chunk_repo.insert_chunks(chunks)
    chunks_for_faiss = []
    for c in chunks:
        emb = embedding_service.generate_embedding(c["text"])
        chunk_repo.update_embedding(c["chunk_id"], emb)
        chunks_for_faiss.append({"chunk_id": c["chunk_id"], "embedding": emb})
    faiss_service.add_embeddings(chunks_for_faiss)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)
        query = "wireless mouse"

        response = client.post(
            "/api/search",
            json={
                "query": query,
                "top_k": 3,
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert "results" in data
        assert len(data["results"]) <= 3

        for result in data["results"]:
            assert "chunk_id" in result
            assert "score" in result
            assert "text" in result
            assert isinstance(result["score"], float)

    finally:
        app.dependency_overrides.clear()


def test_semantic_retrieval_quality(tmp_path):
    """
    Retrieval quality check:
    Proves that semantic search ranks relevant chunks above unrelated chunks.

    Given:
      Chunk 1: "Wireless Logitech mouse purchased for $24.99."
      Chunk 2: "Whole wheat bread and milk."
      Chunk 3: "USB keyboard and wireless mouse."
      Chunk 4: "Restaurant dinner."

    Query:
      "wireless mouse"

    Expected:
      - Top 2 results MUST be Chunk 1 and Chunk 3 (in either order).
      - Chunk 2 and Chunk 4 MUST NOT outrank Chunk 1 or Chunk 3.
      - Scores for relevant chunks must be significantly higher than unrelated chunks.
    """
    index_file = str(tmp_path / "quality_check.index")
    mapping_file = str(tmp_path / "quality_mapping.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_quality"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    doc_id = str(ObjectId())
    chunk_1_id = f"{doc_id}_c1"
    chunk_2_id = f"{doc_id}_c2"
    chunk_3_id = f"{doc_id}_c3"
    chunk_4_id = f"{doc_id}_c4"

    chunks = [
        {
            "document_id": doc_id,
            "chunk_id": chunk_1_id,
            "page": 1,
            "text": "Wireless Logitech mouse purchased for $24.99.",
        },
        {
            "document_id": doc_id,
            "chunk_id": chunk_2_id,
            "page": 1,
            "text": "Whole wheat bread and milk.",
        },
        {
            "document_id": doc_id,
            "chunk_id": chunk_3_id,
            "page": 1,
            "text": "USB keyboard and wireless mouse.",
        },
        {
            "document_id": doc_id,
            "chunk_id": chunk_4_id,
            "page": 1,
            "text": "Restaurant dinner.",
        },
    ]

    # Save to MongoDB
    chunk_repo.insert_chunks(chunks)

    # Embed and index into FAISS
    chunks_for_faiss = []
    for c in chunks:
        emb = embedding_service.generate_embedding(c["text"])
        chunk_repo.update_embedding(c["chunk_id"], emb)
        chunks_for_faiss.append({"chunk_id": c["chunk_id"], "embedding": emb})
    faiss_service.add_embeddings(chunks_for_faiss)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)

        # 1. Search for "wireless mouse"
        response = client.post(
            "/api/search",
            json={
                "query": "wireless mouse",
                "top_k": 4,
            },
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 4

        top_2_chunk_ids = {results[0]["chunk_id"], results[1]["chunk_id"]}
        bottom_2_chunk_ids = {results[2]["chunk_id"], results[3]["chunk_id"]}

        # Top 2 MUST be the two wireless mouse chunks
        assert top_2_chunk_ids == {chunk_1_id, chunk_3_id}
        # Bottom 2 MUST be bread/milk and restaurant dinner
        assert bottom_2_chunk_ids == {chunk_2_id, chunk_4_id}

        # Assert similarity score margin: relevant chunks must score > 0.50, unrelated < 0.20
        assert results[0]["score"] > 0.50
        assert results[1]["score"] > 0.50
        assert results[2]["score"] < 0.25
        assert results[3]["score"] < 0.20

        # Score of 2nd relevant chunk must be strictly greater than 3rd chunk
        assert results[1]["score"] > results[2]["score"]

        # 2. Reverse search for "groceries and bakery items"
        response_grocery = client.post(
            "/api/search",
            json={
                "query": "groceries and bakery items",
                "top_k": 1,
            },
        )
        assert response_grocery.status_code == 200
        grocery_results = response_grocery.json()["results"]
        assert len(grocery_results) == 1
        assert grocery_results[0]["chunk_id"] == chunk_2_id
        assert "Whole wheat bread and milk" in grocery_results[0]["text"]

    finally:
        app.dependency_overrides.clear()
