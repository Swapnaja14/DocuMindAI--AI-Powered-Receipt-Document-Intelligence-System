import sys
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService

# Ensure stdout supports UTF-8 characters (e.g. currency symbols like ₹) on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def test_faiss_index():

    embedding_service = EmbeddingService()

    faiss_service = FAISSService(
        index_path="storage/faiss/test.index"
    )

    chunks = [
        "Wireless mouse ₹799",
        "USB keyboard ₹1299",
        "Apple iPhone 15 ₹69999",
    ]

    embeddings = embedding_service.generate_embeddings(
        chunks
    )

    vector_ids = faiss_service.add_embeddings(
        embeddings
    )

    assert vector_ids == [0, 1, 2]

    assert faiss_service.count() == 3

    query = "computer mouse"

    query_embedding = (
        embedding_service.generate_embedding(query)
    )

    results = faiss_service.search(
        query_embedding,
        top_k=2
    )

    print("\nSearch results:")

    for vector_id, score in results:
        text_preview = chunks[vector_id].encode("ascii", "replace").decode("ascii")
        print(
            f"FAISS ID: {vector_id}, "
            f"Score: {score:.4f}, "
            f"Text: {text_preview}"
        )

    assert len(results) == 2

    # The mouse chunk should be the most relevant.
    assert results[0][0] == 0
