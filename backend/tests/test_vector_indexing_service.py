import mongomock
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_indexing_service import VectorIndexingService


def test_index_chunks(tmp_path):

    index_file = str(tmp_path / "test_index.faiss")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)
    vector_mapping_repository = VectorMappingRepository(db)

    service = VectorIndexingService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=vector_mapping_repository,
    )

    chunks = [
        {
            "chunk_id": 0,
            "text": "Wireless mouse ₹799",
        },
        {
            "chunk_id": 1,
            "text": "USB keyboard ₹1299",
        },
        {
            "chunk_id": 2,
            "text": "HDMI cable ₹499",
        },
    ]

    mappings = service.index_chunks(
        document_id="document123",
        chunks=chunks,
    )

    # 1. Assert returned mappings
    assert len(mappings) == 3

    assert mappings[0]["faiss_id"] == 0
    assert mappings[0]["document_id"] == "document123"
    assert mappings[0]["chunk_id"] == 0

    assert mappings[1]["faiss_id"] == 1
    assert mappings[1]["document_id"] == "document123"
    assert mappings[1]["chunk_id"] == 1

    assert mappings[2]["faiss_id"] == 2
    assert mappings[2]["document_id"] == "document123"
    assert mappings[2]["chunk_id"] == 2

    # 2. Verify MongoDB vector_mappings collection
    saved_mappings = vector_mapping_repository.get_by_document_id("document123")
    assert len(saved_mappings) == 3
    assert saved_mappings[0]["faiss_id"] == 0
    assert saved_mappings[0]["chunk_id"] == 0
    assert saved_mappings[1]["faiss_id"] == 1
    assert saved_mappings[1]["chunk_id"] == 1
    assert saved_mappings[2]["faiss_id"] == 2
    assert saved_mappings[2]["chunk_id"] == 2

    # 3. Verify FAISS index vector count
    assert faiss_service.count() == 3


def test_index_chunks_idempotency(tmp_path):
    index_file = str(tmp_path / "idempotent.faiss")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file)
    vector_mapping_repository = VectorMappingRepository(db)

    service = VectorIndexingService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        vector_mapping_repository=vector_mapping_repository,
    )

    chunks = [
        {"chunk_id": 0, "text": "Wireless mouse ₹799"},
        {"chunk_id": 1, "text": "USB keyboard ₹1299"},
    ]

    # First indexing run
    mappings_1 = service.index_chunks(document_id="doc_retry", chunks=chunks)
    assert len(mappings_1) == 2
    assert faiss_service.count() == 2

    # Simulated Celery task retry (identical call)
    mappings_2 = service.index_chunks(document_id="doc_retry", chunks=chunks)
    assert len(mappings_2) == 2

    # Ensure FAISS vector count DID NOT increase (no duplicate vectors)
    assert faiss_service.count() == 2

    # Ensure vector mappings remain exactly 2
    db_mappings = vector_mapping_repository.get_by_document_id("doc_retry")
    assert len(db_mappings) == 2
    assert db_mappings[0]["faiss_id"] == 0
    assert db_mappings[1]["faiss_id"] == 1


def test_index_empty_chunks(tmp_path):

    index_file = str(tmp_path / "empty_index.faiss")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    service = VectorIndexingService(
        embedding_service=EmbeddingService(),
        faiss_service=FAISSService(index_path=index_file),
        vector_mapping_repository=VectorMappingRepository(db),
    )

    mappings = service.index_chunks(document_id="document123", chunks=[])
    assert mappings == []
