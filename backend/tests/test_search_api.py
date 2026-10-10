import mongomock
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_search_service import VectorSearchService
from app.api.routes.search import get_vector_search_service

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_real_end_to_end_semantic_search_pipeline(tmp_path):
    """
    Real end-to-end integration test:
    Real Query ("wireless mouse")
       ↓
    FastAPI POST /api/search
       ↓
    EmbeddingService (all-MiniLM-L6-v2)
       ↓
    FAISSService (IndexFlatIP + IndexIDMap2 + chunk_mapping.json)
       ↓
    Top-K chunk IDs
       ↓
    ChunkRepository (MongoDB)
       ↓
    Full response with text, score, page_number, and document_id.
    """
    index_file = str(tmp_path / "e2e_chunks.index")
    mapping_file = str(tmp_path / "e2e_chunk_mapping.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_e2e"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    doc_receipt_1 = str(ObjectId())
    doc_receipt_2 = str(ObjectId())
    doc_receipt_3 = str(ObjectId())

    # Insert realistic receipt chunks into MongoDB
    receipt_chunks = [
        {
            "document_id": doc_receipt_1,
            "chunk_id": f"{doc_receipt_1}_0",
            "page": 1,
            "text": "Electronics Store Receipt #10492\nLogitech Wireless Mouse M185 ₹799\nUSB receiver included\nTotal ₹799",
        },
        {
            "document_id": doc_receipt_2,
            "chunk_id": f"{doc_receipt_2}_0",
            "page": 1,
            "text": "Office Furniture Mart\nErgonomic High Back Mesh Office Chair ₹7499\nWarranty: 3 years\nTotal ₹7499",
        },
        {
            "document_id": doc_receipt_3,
            "chunk_id": f"{doc_receipt_3}_0",
            "page": 1,
            "text": "Supermarket Fresh Mart\nOrganic Apples 1kg ₹220\nWhole Wheat Bread ₹50\nMilk 1L ₹65\nTotal ₹335",
        },
    ]

    # Save to MongoDB
    chunk_repo.insert_chunks(receipt_chunks)

    # Generate real embeddings and index into FAISS
    chunks_for_faiss = []
    for chunk in receipt_chunks:
        emb = embedding_service.generate_embedding(chunk["text"])
        chunk_repo.update_embedding(chunk["chunk_id"], emb)
        chunks_for_faiss.append({
            "chunk_id": chunk["chunk_id"],
            "embedding": emb,
        })

    faiss_service.add_embeddings(chunks_for_faiss)

    # Verify FAISS health status before query
    status = faiss_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 3
    assert status["mapped_chunks"] == 3

    # Wire up search service and FastAPI client
    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)

        # Execute semantic search for "wireless mouse"
        payload = {
            "query": "wireless mouse",
            "top_k": 3,
        }
        response = client.post("/api/search", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        results = data["results"]
        assert len(results) >= 1

        # The top result must be the Electronics Store receipt containing the wireless mouse
        top_hit = results[0]
        assert top_hit["document_id"] == doc_receipt_1
        assert top_hit["chunk_id"] == f"{doc_receipt_1}_0"
        assert "Wireless Mouse" in top_hit["text"]
        assert top_hit["page_number"] == 1
        assert isinstance(top_hit["score"], float)
        assert top_hit["score"] > 0.45

        # Top score must be strictly higher than unrelated receipts (chair, groceries)
        if len(results) > 1:
            assert top_hit["score"] > results[1]["score"]

    finally:
        app.dependency_overrides.clear()


def test_search_api_empty_query_validation():
    client = TestClient(app)
    response = client.post("/api/search", json={"query": ""})
    assert response.status_code == 422


def test_search_api_valid_query_no_matches_returns_empty_list(tmp_path):
    """
    Test POST /api/search with a valid query that yields no matches above threshold:
    Must return HTTP 200 with {"results": []} (not an error).
    """
    index_file = str(tmp_path / "empty_match.index")
    mapping_file = str(tmp_path / "empty_match.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_api_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    doc_id = str(ObjectId())
    chunk = {
        "document_id": doc_id,
        "chunk_id": f"{doc_id}_0",
        "page": 1,
        "text": "Grocery store purchase apples milk",
    }
    chunk_repo.insert_chunks([chunk])
    emb = embedding_service.generate_embedding(chunk["text"])
    chunk_repo.update_embedding(chunk["chunk_id"], emb)
    faiss_service.add_embeddings([{"chunk_id": chunk["chunk_id"], "embedding": emb}])

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)
        # Query with impossible similarity threshold
        response = client.post(
            "/api/search",
            json={
                "query": "quantum computer supernova astrophysics",
                "top_k": 3,
                "score_threshold": 0.98,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["results"] == []
    finally:
        app.dependency_overrides.clear()



def test_search_api_document_filtering(tmp_path):
    """
    Test POST /api/search with document_id filter:
    Ensures every returned result belongs to the requested document_id.
    """
    index_file = str(tmp_path / "api_doc_filter.index")
    mapping_file = str(tmp_path / "api_doc_filter.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_api_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    doc_target = str(ObjectId())
    doc_other = str(ObjectId())

    chunks = [
        {
            "document_id": doc_target,
            "chunk_id": f"{doc_target}_0",
            "page": 1,
            "text": "Logitech Wireless Mouse M185 Black ₹799",
        },
        {
            "document_id": doc_other,
            "chunk_id": f"{doc_other}_0",
            "page": 1,
            "text": "HP Wireless Mouse Multi-device 430 ₹1299",
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
        payload = {
            "query": "wireless mouse",
            "top_k": 5,
            "document_id": doc_target,
        }
        response = client.post("/api/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        results = data["results"]

        assert len(results) == 1
        assert results[0]["document_id"] == doc_target
        assert results[0]["chunk_id"] == f"{doc_target}_0"
        assert "Logitech" in results[0]["text"]
    finally:
        app.dependency_overrides.clear()


def test_search_api_missing_mongodb_chunk_resilience(tmp_path):
    """
    Test POST /api/search architectural resilience:
    When a chunk exists in FAISS but was deleted from MongoDB, the search skips
    the missing record and continues without crashing.
    """
    index_file = str(tmp_path / "api_resilience.index")
    mapping_file = str(tmp_path / "api_resilience.json")

    client_db = mongomock.MongoClient()
    client_db._server_version = "6.0.0"
    db = client_db["documind_api_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    doc_id = str(ObjectId())
    chunks = [
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_0",
            "page": 1,
            "text": "Existing Document Wireless Mouse ₹899",
        },
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_1",
            "page": 1,
            "text": "Ghost chunk to be deleted from MongoDB ₹2500",
        },
    ]

    chunk_repo.insert_chunks(chunks)
    chunks_for_faiss = []
    for c in chunks:
        emb = embedding_service.generate_embedding(c["text"])
        chunk_repo.update_embedding(c["chunk_id"], emb)
        chunks_for_faiss.append({"chunk_id": c["chunk_id"], "embedding": emb})
    faiss_service.add_embeddings(chunks_for_faiss)

    # Delete ghost chunk from MongoDB
    chunk_repo.collection.delete_one({"chunk_id": f"{doc_id}_1"})

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)
        payload = {
            "query": "Ghost chunk",
            "top_k": 5,
        }
        response = client.post("/api/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        results = data["results"]

        # Ghost chunk is excluded, but existing chunk can still match without error
        returned_ids = [r["chunk_id"] for r in results]
        assert f"{doc_id}_1" not in returned_ids
    finally:
        app.dependency_overrides.clear()

