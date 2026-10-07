import mongomock
from bson import ObjectId
from unittest.mock import patch, MagicMock

from app.tasks.chunking_tasks import chunk_document
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.faiss_service import FAISSService

# Fix mongomock server version parsing on Windows
mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_chunk_and_index_document_task(tmp_path):
    index_file = str(tmp_path / "test_task.index")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    mock_db = client["documind"]

    # Insert a sample document ready for chunking & indexing
    doc_id = str(ObjectId())
    mock_db["documents"].insert_one({
        "_id": ObjectId(doc_id),
        "status": "EXTRACTION_COMPLETED",
        "ocr": {
            "raw_text": "Receipt #12345\nWireless mouse ₹799\nTotal ₹799",
            "page_count": 1,
        },
    })

    with patch("app.tasks.chunking_tasks.db", mock_db), \
         patch("app.tasks.chunking_tasks.FAISSService", lambda index_path: FAISSService(index_path=index_file)):

        result_id = chunk_document(doc_id)

        assert result_id == doc_id

        # Verify MongoDB document status updates
        doc = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})
        assert doc["status"] == "COMPLETED"
        assert doc["chunking_status"] == "COMPLETED"
        assert doc["vector_status"] == "INDEXED"
        assert doc["chunk_count"] > 0

        # Verify chunks were persisted in document_chunks collection
        chunk_repo = ChunkRepository(mock_db)
        chunks = chunk_repo.get_document_chunks(doc_id)
        assert len(chunks) > 0

        # Verify vector mappings were created
        mapping_repo = VectorMappingRepository(mock_db)
        mappings = mapping_repo.get_by_document_id(doc_id)
        assert len(mappings) == len(chunks)
        assert mappings[0]["faiss_id"] == 0


def test_chunk_document_isolated_vector_failure():
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    mock_db = client["documind"]

    doc_id = str(ObjectId())
    mock_db["documents"].insert_one({
        "_id": ObjectId(doc_id),
        "status": "EXTRACTION_COMPLETED",
        "ocr": {
            "raw_text": "Receipt #999\nItem A ₹100",
            "page_count": 1,
        },
    })

    # Simulate FAISS indexing failure
    with patch("app.tasks.chunking_tasks.db", mock_db), \
         patch("app.tasks.chunking_tasks.VectorIndexingService.index_chunks", side_effect=RuntimeError("FAISS disk write error")):

        result_id = chunk_document(doc_id)

        assert result_id == doc_id

        doc = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})
        # Document itself completed chunking & extraction, but vector_status is marked FAILED
        assert doc["status"] == "COMPLETED"
        assert doc["chunking_status"] == "COMPLETED"
        assert doc["vector_status"] == "FAILED"
        assert "FAISS disk write error" in doc["processing"]["vector_error"]
