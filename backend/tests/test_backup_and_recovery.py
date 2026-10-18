import os
import shutil
from pathlib import Path
import mongomock
import pytest

from app.services.backup_service import BackupService
from app.services.faiss_service import FAISSService


@pytest.fixture
def mock_backup_env(tmp_path):
    """Set up an isolated temporary environment for backup and recovery testing."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    faiss_dir = tmp_path / "faiss"
    faiss_dir.mkdir(parents=True, exist_ok=True)
    faiss_index_path = faiss_dir / "index.faiss"

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Use mongomock for complete isolation
    mongo_client = mongomock.MongoClient()
    mock_db = mongo_client["test_documind"]

    # Seed initial test data
    user_id = "user_rec_001"
    doc_id = "doc_rec_001"
    chunk_id = "chunk_rec_001"

    mock_db.users.insert_one({
        "_id": user_id,
        "email": "recovery_test@example.com",
        "hashed_password": "test_argon2_hash",
    })

    mock_db.documents.insert_one({
        "_id": doc_id,
        "user_id": user_id,
        "filename": "tax_receipt_2026.pdf",
        "status": "COMPLETED",
        "extracted_data": {"vendor": "Office Supplies Corp", "total_amount": 450.0},
    })

    mock_db.document_chunks.insert_one({
        "_id": chunk_id,
        "document_id": doc_id,
        "chunk_id": chunk_id,
        "content": "Invoice total amount: $450.00 from Office Supplies Corp.",
        "embedding": [0.05] * 384,
    })

    mock_db.vector_mappings.insert_one({
        "faiss_id": 0,
        "document_id": doc_id,
        "chunk_id": chunk_id,
    })

    # Create dummy upload files
    test_pdf = upload_dir / "tax_receipt_2026.pdf"
    test_pdf.write_bytes(b"%PDF-1.5 test document stream payload")

    # Initialize and seed FAISS index
    faiss_service = FAISSService(
        index_path=str(faiss_index_path),
        mapping_path=str(faiss_index_path.with_suffix(".json")),
    )
    faiss_service.add_embeddings([{"chunk_id": chunk_id, "embedding": [0.05] * 384}])

    service = BackupService(
        upload_dir=str(upload_dir),
        faiss_index_path=str(faiss_index_path),
        database=mock_db,
    )

    return {
        "service": service,
        "db": mock_db,
        "upload_dir": upload_dir,
        "faiss_index_path": faiss_index_path,
        "backup_dir": backup_dir,
        "doc_id": doc_id,
        "chunk_id": chunk_id,
    }


def test_complete_disaster_recovery_snapshot_and_restoration(mock_backup_env):
    """
    Step 13.7: Test at least one restoration or index-rebuild procedure.
    A backup that has never been restored is not yet a verified recovery strategy.
    """
    service: BackupService = mock_backup_env["service"]
    db = mock_backup_env["db"]
    upload_dir = mock_backup_env["upload_dir"]
    faiss_path = mock_backup_env["faiss_index_path"]
    backup_dir = mock_backup_env["backup_dir"]

    # 1. Generate full snapshot
    bundle = service.create_full_snapshot(output_root=backup_dir)
    assert bundle.exists()
    assert bundle.suffix == ".gz"

    # 2. Simulate catastrophic disaster: purge DB, delete uploads, wipe FAISS
    db.users.delete_many({})
    db.documents.delete_many({})
    db.document_chunks.delete_many({})
    db.vector_mappings.delete_many({})
    assert db.documents.count_documents({}) == 0

    shutil.rmtree(upload_dir)
    upload_dir.mkdir()
    assert len(list(upload_dir.iterdir())) == 0

    if faiss_path.exists():
        faiss_path.unlink()
    mapping_file = faiss_path.with_suffix(".json")
    if mapping_file.exists():
        mapping_file.unlink()

    # 3. Perform restoration from snapshot bundle
    restore_result = service.restore_full_snapshot(bundle_path=bundle)
    assert restore_result["status"] == "success"

    # 4. Verify MongoDB state restored
    restored_doc = db.documents.find_one({"_id": mock_backup_env["doc_id"]})
    assert restored_doc is not None
    assert restored_doc["filename"] == "tax_receipt_2026.pdf"
    assert restored_doc["extracted_data"]["total_amount"] == 450.0

    restored_chunk = db.document_chunks.find_one({"_id": mock_backup_env["chunk_id"]})
    assert restored_chunk is not None
    assert len(restored_chunk["embedding"]) == 384

    # 5. Verify upload storage files restored
    restored_file = upload_dir / "tax_receipt_2026.pdf"
    assert restored_file.exists()
    assert restored_file.read_bytes() == b"%PDF-1.5 test document stream payload"

    # 6. Verify FAISS index restored and searchable
    faiss_check = FAISSService(
        index_path=str(faiss_path),
        mapping_path=str(mapping_file),
    )
    status = faiss_check.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 1
    assert status["mapped_chunks"] == 1

    search_res = faiss_check.search([0.05] * 384, top_k=1)
    assert len(search_res) == 1
    assert search_res[0]["chunk_id"] == mock_backup_env["chunk_id"]


def test_faiss_disaster_recovery_rebuild_from_database(mock_backup_env):
    """
    Step 13.7: Test index rebuild procedure.
    Verifies FAISS can be completely rebuilt from MongoDB chunks if index is lost/corrupt.
    """
    service: BackupService = mock_backup_env["service"]
    faiss_path = mock_backup_env["faiss_index_path"]
    mapping_file = faiss_path.with_suffix(".json")

    # Destroy the FAISS index and mapping
    if faiss_path.exists():
        faiss_path.unlink()
    if mapping_file.exists():
        mapping_file.unlink()

    # Trigger rebuild directly from database
    rebuild_res = service.rebuild_faiss_from_database()
    assert rebuild_res["status"]["loaded"] is True
    assert rebuild_res["status"]["total_vectors"] == 1
    assert rebuild_res["status"]["mapped_chunks"] == 1
    assert rebuild_res["consistency"]["consistent"] is True

    # Confirm search works on rebuilt index
    rebuilt_faiss = FAISSService(
        index_path=str(faiss_path),
        mapping_path=str(mapping_file),
    )
    results = rebuilt_faiss.search([0.05] * 384, top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == mock_backup_env["chunk_id"]
