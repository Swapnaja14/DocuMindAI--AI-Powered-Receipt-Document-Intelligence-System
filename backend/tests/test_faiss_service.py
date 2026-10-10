import sys
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService

# Ensure stdout supports UTF-8 characters (e.g. currency symbols like ₹) on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def test_faiss_index(tmp_path):
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")

    embedding_service = EmbeddingService()
    faiss_service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
    )

    chunks = [
        {"chunk_id": "c0", "text": "Wireless mouse ₹799"},
        {"chunk_id": "c1", "text": "USB keyboard ₹1299"},
        {"chunk_id": "c2", "text": "Apple iPhone 15 ₹69999"},
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
    assert status["total_vectors"] == 3
    assert status["mapped_chunks"] == 3

    query = "computer mouse"
    query_embedding = embedding_service.generate_embedding(query)

    results = faiss_service.search(
        query_embedding,
        top_k=2,
    )

    assert len(results) == 2
    # The mouse chunk should be the most relevant.
    assert results[0]["chunk_id"] == "c0"
    assert results[0]["score"] > 0.4

