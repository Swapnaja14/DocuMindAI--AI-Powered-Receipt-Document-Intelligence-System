import mongomock
import pytest
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_indexing_service import VectorIndexingService
from app.services.vector_search_service import VectorSearchService


def test_semantic_search(tmp_path):

    index_file = str(tmp_path / "search_test.index")
    client = mongomock.MongoClient()
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    mapping_repo = VectorMappingRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)

    indexing_service = VectorIndexingService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
    )

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
        chunk_repository=chunk_repo,
    )

    chunks = [
        {
            "chunk_id": 0,
            "text": "Wireless mouse ₹799",
            "document_id": "doc123",
        },
        {
            "chunk_id": 1,
            "text": "USB keyboard ₹1299",
            "document_id": "doc123",
        },
        {
            "chunk_id": 2,
            "text": "Apple iPhone 15 ₹69999",
            "document_id": "doc123",
        },
    ]

    # Store chunks in MongoDB
    chunk_repo.insert_chunks(chunks)

    # Index chunks first
    indexing_service.index_chunks(
        document_id="doc123",
        chunks=chunks,
    )

    # Search
    results = search_service.search(
        "computer mouse",
        top_k=2,
    )

    assert len(results) == 2

    assert results[0]["document_id"] == "doc123"
    assert results[0]["chunk_id"] == 0

    assert "mouse" in results[0]["text"].lower()

    assert (
        results[0]["score"]
        >= results[1]["score"]
    )


def test_semantic_search_document_filtering(tmp_path):

    index_file = str(tmp_path / "filter_test.index")
    client = mongomock.MongoClient()
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    mapping_repo = VectorMappingRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)

    indexing_service = VectorIndexingService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
    )

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
        chunk_repository=chunk_repo,
    )

    # Chunks from document A
    chunks_doc_a = [
        {"chunk_id": 0, "text": "Wireless ergonomic mouse ₹999", "document_id": "doc_a"},
        {"chunk_id": 1, "text": "Mouse pad large ₹299", "document_id": "doc_a"},
    ]
    # Chunks from document B
    chunks_doc_b = [
        {"chunk_id": 0, "text": "Gaming optical mouse ₹1499", "document_id": "doc_b"},
    ]

    chunk_repo.insert_chunks(chunks_doc_a)
    chunk_repo.insert_chunks(chunks_doc_b)

    indexing_service.index_chunks(document_id="doc_a", chunks=chunks_doc_a)
    indexing_service.index_chunks(document_id="doc_b", chunks=chunks_doc_b)

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
    client = mongomock.MongoClient()
    db = client["documind_test"]

    chunk_repo = ChunkRepository(db)
    mapping_repo = VectorMappingRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)

    indexing_service = VectorIndexingService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
    )

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=mapping_repo,
        chunk_repository=chunk_repo,
    )

    chunks = [
        {"chunk_id": 0, "text": "Wireless mouse ₹799", "document_id": "doc_receipt"},
    ]

    chunk_repo.insert_chunks(chunks)
    indexing_service.index_chunks(document_id="doc_receipt", chunks=chunks)

    # Out of domain query filtered by threshold
    results = search_service.search(
        "What is the employee leave policy?",
        top_k=5,
        score_threshold=0.60,
    )
    assert results == []


def test_empty_query_error():

    client = mongomock.MongoClient()
    db = client["documind_test"]

    search_service = VectorSearchService(
        embedding_service=EmbeddingService(),
        faiss_service=FAISSService(index_path="storage/faiss/empty.index"),
        vector_mapping_repository=VectorMappingRepository(db),
        chunk_repository=ChunkRepository(db),
    )

    with pytest.raises(ValueError):
        search_service.search(query="")
