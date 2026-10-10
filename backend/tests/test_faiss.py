from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService


def test_faiss_add_and_search(tmp_path):
    index_file = str(tmp_path / "test_index.faiss")
    mapping_file = str(tmp_path / "test_mapping.json")

    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    chunks = [
        {"chunk_id": "chunk_0", "text": "Wireless mouse ₹799"},
        {"chunk_id": "chunk_1", "text": "USB keyboard ₹1299"},
        {"chunk_id": "chunk_2", "text": "Apple iPhone 15 ₹69999"},
        {"chunk_id": "chunk_3", "text": "Fresh organic milk 1L"},
    ]

    chunks_for_faiss = [
        {
            "chunk_id": chunk["chunk_id"],
            "embedding": embedding_service.generate_embedding(chunk["text"]),
        }
        for chunk in chunks
    ]
    faiss_service.add_embeddings(chunks_for_faiss)

    status = faiss_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 4
    assert status["mapped_chunks"] == 4

    # Search for an electronics/mouse related query
    query = "computer mouse hardware"
    query_vector = embedding_service.generate_embedding(query)
    results = faiss_service.search(query_vector, top_k=2)

    assert len(results) == 2
    top_result = results[0]

    # The top result should be chunk_0 (Wireless mouse)
    assert top_result["chunk_id"] == "chunk_0"
    assert isinstance(top_result["score"], float)
    assert -1.0 <= top_result["score"] <= 1.0


def test_faiss_save_and_load(tmp_path):
    index_file = str(tmp_path / "test.faiss")
    mapping_file = str(tmp_path / "test.json")
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    chunks = [
        {"chunk_id": "chunk_a", "text": "Grocery invoice receipt"},
        {"chunk_id": "chunk_b", "text": "Restaurant dinner bill"},
    ]
    chunks_for_faiss = [
        {
            "chunk_id": chunk["chunk_id"],
            "embedding": embedding_service.generate_embedding(chunk["text"]),
        }
        for chunk in chunks
    ]
    faiss_service.add_embeddings(chunks_for_faiss)

    loaded_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    status = loaded_service.status()

    assert status["loaded"] is True
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2

    query_vector = embedding_service.generate_embedding("dinner food bill")
    results = loaded_service.search(query_vector, top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk_b"


def test_faiss_empty_search(tmp_path):
    index_file = str(tmp_path / "empty_test.faiss")
    mapping_file = str(tmp_path / "empty_test.json")
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    results = faiss_service.search([0.0] * 384, top_k=3)
    assert results == []
    assert faiss_service.status()["total_vectors"] == 0


def test_faiss_remove_chunks(tmp_path):
    index_file = str(tmp_path / "remove_test.faiss")
    mapping_file = str(tmp_path / "remove_test.json")
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    chunks = [
        {"chunk_id": "chunk_1", "text": "Item 1"},
        {"chunk_id": "chunk_2", "text": "Item 2"},
        {"chunk_id": "chunk_3", "text": "Item 3"},
    ]
    chunks_for_faiss = [
        {
            "chunk_id": c["chunk_id"],
            "embedding": embedding_service.generate_embedding(c["text"]),
        }
        for c in chunks
    ]
    faiss_service.add_embeddings(chunks_for_faiss)
    assert faiss_service.status()["total_vectors"] == 3

    # Remove chunk_2
    faiss_service.remove_chunk_id("chunk_2")

    status = faiss_service.status()
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2
    assert "chunk_2" not in faiss_service.chunk_id_to_id


