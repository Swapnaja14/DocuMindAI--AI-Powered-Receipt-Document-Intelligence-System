from app.services.embedding_service import EmbeddingService


def test_embedding_generation():

    service = EmbeddingService()

    text = "Wireless mouse ₹799"

    embedding = service.generate_embedding(text)

    print("\nEmbedding dimension:", len(embedding))
    print("First 10 values:", embedding[:10])

    assert len(embedding) == 384
    assert all(isinstance(value, float) for value in embedding)


def test_multiple_chunks_embeddings():

    service = EmbeddingService()

    chunks = [
        "Wireless mouse ₹799",
        "USB keyboard ₹1299",
        "Apple iPhone 15 ₹69999",
    ]

    embeddings = service.generate_embeddings(chunks)

    print("\nNumber of chunks:", len(embeddings))
    print("Embedding dimension:", len(embeddings[0]))

    assert len(embeddings) == 3
    assert len(embeddings[0]) == 384
    assert len(embeddings[1]) == 384
    assert len(embeddings[2]) == 384
    assert all(isinstance(val, float) for chunk_emb in embeddings for val in chunk_emb)
