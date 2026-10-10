import mongomock
import pytest
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_search_service import VectorSearchService

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_semantic_search(tmp_path):
    index_file = str(tmp_path / "search_test.index")
    mapping_file = str(tmp_path / "search_test.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    chunks = [
        {
            "chunk_id": "doc123_0",
            "text": "Wireless mouse ₹799",
            "document_id": "doc123",
        },
        {
            "chunk_id": "doc123_1",
            "text": "USB keyboard ₹1299",
            "document_id": "doc123",
        },
        {
            "chunk_id": "doc123_2",
            "text": "Apple iPhone 15 ₹69999",
            "document_id": "doc123",
        },
    ]

    # Store chunks in MongoDB
    chunk_repo.insert_chunks(chunks)

    # Embed and index chunks into FAISS
    chunks_to_index = []
    for chunk in chunks:
        emb = embedding_service.generate_embedding(chunk["text"])
        chunk_repo.update_embedding(chunk["chunk_id"], emb)
        chunks_to_index.append({
            "chunk_id": chunk["chunk_id"],
            "embedding": emb,
        })
    faiss_service.add_embeddings(chunks_to_index)

    # Search
    results = search_service.search(
        "computer mouse",
        top_k=2,
    )

    assert len(results) == 2
    assert results[0]["document_id"] == "doc123"
    assert results[0]["chunk_id"] == "doc123_0"
    assert "mouse" in results[0]["text"].lower()
    assert results[0]["score"] >= results[1]["score"]


def test_semantic_search_document_filtering(tmp_path):
    index_file = str(tmp_path / "filter_test.index")
    mapping_file = str(tmp_path / "filter_test.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    chunks = [
        {"chunk_id": "doc_a_0", "text": "Wireless ergonomic mouse ₹999", "document_id": "doc_a"},
        {"chunk_id": "doc_a_1", "text": "Mouse pad large ₹299", "document_id": "doc_a"},
        {"chunk_id": "doc_b_0", "text": "Gaming optical mouse ₹1499", "document_id": "doc_b"},
    ]

    chunk_repo.insert_chunks(chunks)

    chunks_to_index = []
    for chunk in chunks:
        emb = embedding_service.generate_embedding(chunk["text"])
        chunk_repo.update_embedding(chunk["chunk_id"], emb)
        chunks_to_index.append({
            "chunk_id": chunk["chunk_id"],
            "embedding": emb,
        })
    faiss_service.add_embeddings(chunks_to_index)

    # Search specifically within doc_b
    results = search_service.search(
        query="mouse",
        top_k=5,
        document_id="doc_b",
    )

    assert len(results) == 1
    assert results[0]["document_id"] == "doc_b"
    assert "Gaming optical mouse" in results[0]["text"]


def test_semantic_search_threshold(tmp_path):
    index_file = str(tmp_path / "threshold_test.index")
    mapping_file = str(tmp_path / "threshold_test.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    chunks = [
        {"chunk_id": "doc_receipt_0", "text": "Wireless mouse ₹799", "document_id": "doc_receipt"},
    ]

    chunk_repo.insert_chunks(chunks)
    emb = embedding_service.generate_embedding(chunks[0]["text"])
    chunk_repo.update_embedding(chunks[0]["chunk_id"], emb)
    faiss_service.add_embeddings([{"chunk_id": chunks[0]["chunk_id"], "embedding": emb}])

    # Out of domain query filtered by threshold
    results = search_service.search(
        "What is the employee leave policy?",
        top_k=5,
        score_threshold=0.85,
    )
    assert results == []


def test_empty_query_error(tmp_path):
    index_file = str(tmp_path / "empty.index")
    mapping_file = str(tmp_path / "empty.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    search_service = VectorSearchService(
        embedding_service=EmbeddingService(),
        faiss_service=FAISSService(index_path=index_file, mapping_path=mapping_file),
        chunk_repository=ChunkRepository(db),
    )

    with pytest.raises(ValueError):
        search_service.search(query="")


def test_document_filtering_strict_guarantee(tmp_path):
    """
    Verifies that when document_id is specified:
    1. Every returned result strictly belongs to that document_id.
    2. Other documents containing relevant chunks are ignored.
    """
    index_file = str(tmp_path / "doc_filter.index")
    mapping_file = str(tmp_path / "doc_filter.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    chunks = [
        # Doc 1 (Electronics Store)
        {"chunk_id": "doc_1_0", "text": "Logitech MX Master Wireless Mouse ₹6499", "document_id": "doc_1"},
        {"chunk_id": "doc_1_1", "text": "USB-C Charging Cable ₹899", "document_id": "doc_1"},
        # Doc 2 (Office Store with another wireless mouse)
        {"chunk_id": "doc_2_0", "text": "Dell Optical Wireless Mouse ₹999", "document_id": "doc_2"},
        {"chunk_id": "doc_2_1", "text": "A4 Paper Ream ₹350", "document_id": "doc_2"},
    ]

    chunk_repo.insert_chunks(chunks)
    chunks_for_faiss = []
    for chunk in chunks:
        emb = embedding_service.generate_embedding(chunk["text"])
        chunk_repo.update_embedding(chunk["chunk_id"], emb)
        chunks_for_faiss.append({"chunk_id": chunk["chunk_id"], "embedding": emb})
    faiss_service.add_embeddings(chunks_for_faiss)

    # Search specifically within doc_2
    results = search_service.search(
        query="wireless mouse",
        top_k=5,
        document_id="doc_2",
    )

    assert len(results) >= 1
    # Every result must have document_id == "doc_2"
    for r in results:
        assert r["document_id"] == "doc_2"
    assert "Dell Optical Wireless Mouse" in results[0]["text"]


def test_missing_mongodb_chunk_graceful_skip(tmp_path):
    """
    Architectural resilience test:
    FAISS contains a vector for chunk_id, but the chunk was deleted/missing from MongoDB.
    VectorSearchService must gracefully skip the missing chunk and continue returning valid chunks.
    """
    index_file = str(tmp_path / "resilience.index")
    mapping_file = str(tmp_path / "resilience.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    chunks = [
        {"chunk_id": "chunk_alive_1", "text": "Logitech Wireless Mouse M185 ₹799", "document_id": "doc_100"},
        {"chunk_id": "chunk_ghost_2", "text": "High-end Gaming Wireless Mouse RGB ₹4999", "document_id": "doc_100"},
        {"chunk_id": "chunk_alive_3", "text": "USB Receiver Adapter ₹299", "document_id": "doc_100"},
    ]

    # Insert into MongoDB and FAISS
    chunk_repo.insert_chunks(chunks)
    chunks_for_faiss = []
    for chunk in chunks:
        emb = embedding_service.generate_embedding(chunk["text"])
        chunk_repo.update_embedding(chunk["chunk_id"], emb)
        chunks_for_faiss.append({"chunk_id": chunk["chunk_id"], "embedding": emb})
    faiss_service.add_embeddings(chunks_for_faiss)

    # Simulate chunk_ghost_2 being deleted from MongoDB (FAISS index still has the vector)
    chunk_repo.collection.delete_one({"chunk_id": "chunk_ghost_2"})

    # Search for "gaming wireless mouse" - chunk_ghost_2 would be rank 1 in FAISS
    results = search_service.search(
        query="gaming wireless mouse",
        top_k=3,
    )

    # Search should NOT crash and should return the remaining existing chunk
    assert len(results) >= 1
    returned_chunk_ids = [r["chunk_id"] for r in results]
    assert "chunk_ghost_2" not in returned_chunk_ids
    assert "chunk_alive_1" in returned_chunk_ids

