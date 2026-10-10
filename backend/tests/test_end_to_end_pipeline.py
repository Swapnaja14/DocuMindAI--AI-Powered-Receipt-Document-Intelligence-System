import mongomock
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import DocumentStatus, VectorStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_search_service import VectorSearchService
from app.api.routes.search import get_vector_search_service
from app.tasks.document_tasks import process_ocr, extract_document
from app.tasks.chunking_tasks import chunk_document

# Fix mongomock server version parsing on Windows
mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_end_to_end_production_pipeline(tmp_path):
    """
    End-to-end test simulating the complete production pipeline:
    1. Upload / Document creation in MongoDB
    2. Celery OCR task (extracts text)
    3. Celery Extraction task (Gemini structured extraction)
    4. Celery Chunking & Vector Indexing task:
       - Chunk generation
       - Embedding generation
       - FAISS vector addition
       - Vector mappings creation
       - FAISS index persistence
       - document.vector_status = INDEXED
    5. POST /api/search query ("What did I buy?")
       - Returns actual chunks from the uploaded document
    """
    # 1. Setup isolated test database and FAISS index
    index_file = str(tmp_path / "e2e_index.faiss")
    mapping_file = str(tmp_path / "e2e_mapping.json")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    mock_db = client["documind_e2e"]
    mock_docs_collection = mock_db["documents"]

    # Repositories & Services
    chunk_repo = ChunkRepository(mock_db)
    mapping_repo = VectorMappingRepository(mock_db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    # 2. Simulate PDF Upload & initial MongoDB Document creation
    sample_pdf = tmp_path / "receipt_electronics.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4 Mock receipt content")

    initial_doc = {
        "user_id": "test_user_456",
        "filename": "receipt_electronics.pdf",
        "file_type": "pdf",
        "file_path": str(sample_pdf),
        "file_size": 1024,
        "status": DocumentStatus.UPLOADED.value,
        "ocr_status": "PENDING",
        "extraction_status": "PENDING",
        "chunking_status": "PENDING",
        "vector_status": VectorStatus.PENDING.value,
        "chunk_count": 0,
        "ocr": {"raw_text": "", "page_count": 0},
        "extracted_data": {},
        "processing": {"stage": "uploaded"},
    }
    insert_result = mock_docs_collection.insert_one(initial_doc)
    doc_id = str(insert_result.inserted_id)

    # 3. Mock OCR service to return rich purchase receipt text
    mock_ocr_text = (
        "Croma Electronics Store Invoice #9842\n"
        "Date: 2026-10-05\n"
        "Items Purchased:\n"
        "1. Sony Bravia 55-inch 4K OLED Smart TV - Qty: 1 - Price: Rs 84,990\n"
        "2. JBL Cinema Soundbar Wireless Subwoofer - Qty: 1 - Price: Rs 14,999\n"
        "3. High Speed Gold Plated HDMI 2.1 Cable - Qty: 2 - Price: Rs 1,498\n"
        "Subtotal: Rs 1,01,487\n"
        "GST (18%): Rs 18,267.66\n"
        "Total Amount Paid: Rs 1,19,754.66 via Credit Card"
    )

    # Mock Gemini extraction result
    mock_extraction_data = {
        "merchant": "Croma Electronics Store",
        "date": "2026-10-05",
        "total_amount": 119754.66,
        "items": [
            {"name": "Sony Bravia 55-inch 4K OLED Smart TV", "price": 84990.0},
            {"name": "JBL Cinema Soundbar Wireless Subwoofer", "price": 14999.0},
            {"name": "High Speed Gold Plated HDMI 2.1 Cable", "price": 1498.0},
        ],
    }

    # Patch database collections & FAISS path across tasks
    with patch("app.tasks.document_tasks.documents_collection", mock_docs_collection), \
         patch("app.tasks.document_tasks.ocr_document", return_value={"raw_text": mock_ocr_text, "page_count": 1}), \
         patch("app.tasks.document_tasks.extract_document_data", return_value={"data": mock_extraction_data, "validation": {"status": "valid"}}), \
         patch("app.tasks.chunking_tasks.db", mock_db), \
         patch("app.tasks.chunking_tasks.FAISSService", lambda *args, **kwargs: faiss_service):

        # --- STEP A: Celery Task 1: OCR ---
        ocr_result_id = process_ocr(doc_id)
        assert ocr_result_id == doc_id
        doc_after_ocr = mock_docs_collection.find_one({"_id": insert_result.inserted_id})
        assert doc_after_ocr["ocr_status"] == "COMPLETED"
        assert doc_after_ocr["ocr"]["raw_text"] == mock_ocr_text

        # --- STEP B: Celery Task 2: Gemini Extraction ---
        extract_result_id = extract_document(doc_id)
        assert extract_result_id == doc_id
        doc_after_extract = mock_docs_collection.find_one({"_id": insert_result.inserted_id})
        assert doc_after_extract["extraction_status"] == "COMPLETED"
        assert doc_after_extract["extracted_data"]["merchant"] == "Croma Electronics Store"

        # --- STEP C: Celery Task 3: Chunking & Vector Indexing ---
        chunk_result_id = chunk_document(doc_id)
        assert chunk_result_id == doc_id

    # 4. Assert Document Status & Vector State in MongoDB
    final_doc = mock_docs_collection.find_one({"_id": insert_result.inserted_id})
    assert final_doc["status"] == DocumentStatus.COMPLETED.value
    assert final_doc["chunking_status"] == "COMPLETED"
    assert final_doc["vector_status"] == VectorStatus.INDEXED.value
    assert final_doc["chunk_count"] > 0

    # 5. Assert MongoDB Chunks & FAISS Index Status
    stored_chunks = chunk_repo.get_document_chunks(doc_id)
    assert len(stored_chunks) == final_doc["chunk_count"]
    assert stored_chunks[0]["chunk_id"] == f"{doc_id}_0"
    assert "Sony Bravia" in stored_chunks[0]["text"]

    # 6. Assert FAISS vector count & disk mapping consistency
    status = faiss_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == len(stored_chunks)
    assert status["mapped_chunks"] == len(stored_chunks)

    # 7. Execute POST /api/search with query "What did I buy?"
    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )
    app.dependency_overrides[get_vector_search_service] = lambda: search_service

    try:
        client = TestClient(app)

        # Search Query 1: "What did I buy?"
        response = client.post(
            "/api/search",
            json={
                "query": "What did I buy?",
                "top_k": 3,
            },
        )
        assert response.status_code == 200
        search_data = response.json()

        assert "results" in search_data
        results = search_data["results"]
        assert len(results) > 0
        assert results[0]["document_id"] == doc_id
        assert isinstance(results[0]["score"], float)
        assert results[0]["score"] > 0.3

        # Search Query 2: Specific item "OLED Smart TV soundbar"
        specific_response = client.post(
            "/api/search",
            json={
                "query": "Sony OLED Smart TV soundbar price",
                "top_k": 1,
            },
        )
        assert specific_response.status_code == 200
        specific_results = specific_response.json()["results"]
        assert len(specific_results) == 1
        assert "Sony Bravia" in specific_results[0]["text"] or "Croma" in specific_results[0]["text"]
        assert specific_results[0]["document_id"] == doc_id

    finally:
        app.dependency_overrides.clear()
