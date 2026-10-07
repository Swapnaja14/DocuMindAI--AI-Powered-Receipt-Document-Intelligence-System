from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService


def test_faiss_add_and_search():
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path="storage/faiss/test_index.faiss")

    chunks = [
        "Wireless mouse ₹799",
        "USB keyboard ₹1299",
        "Apple iPhone 15 ₹69999",
        "Fresh organic milk 1L",
    ]

    embeddings = embedding_service.generate_embeddings(chunks)
    assigned_ids = faiss_service.add_embeddings(embeddings)

    assert assigned_ids == [0, 1, 2, 3]
    assert faiss_service.count() == 4

    # Search for an electronics/mouse related query
    query = "computer mouse hardware"
    query_vector = embedding_service.generate_embedding(query)
    results = faiss_service.search(query_vector, top_k=2)

    assert len(results) == 2
    top_vector_id, top_score = results[0]

    # The top result should be index 0 (Wireless mouse)
    assert top_vector_id == 0
    assert isinstance(top_score, float)
    assert -1.0 <= top_score <= 1.0


def test_faiss_save_and_load(tmp_path):
    index_file = str(tmp_path / "test.faiss")
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)

    chunks = ["Grocery invoice receipt", "Restaurant dinner bill"]
    embeddings = embedding_service.generate_embeddings(chunks)
    faiss_service.add_embeddings(embeddings)
    faiss_service.save()

    loaded_service = FAISSService(index_path=index_file)
    loaded_service.load()

    assert loaded_service.count() == 2

    query_vector = embedding_service.generate_embedding("dinner food bill")
    results = loaded_service.search(query_vector, top_k=1)
    assert len(results) == 1
    assert results[0][0] == 1


def test_faiss_empty_search():
    faiss_service = FAISSService(index_path="storage/faiss/empty_test.faiss")
    results = faiss_service.search([0.0] * 384, top_k=3)
    assert results == []
    assert faiss_service.count() == 0
