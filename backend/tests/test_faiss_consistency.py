import mongomock
from bson import ObjectId
import pytest

from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService
from app.services.vector_search_service import VectorSearchService

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_consistent_state_detection(tmp_path):
    """
    Test that when MongoDB chunks and FAISS vectors match 1:1,
    check_consistency reports consistent: True.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    doc_id = str(ObjectId())
    chunk_repo.insert_chunks([
        {"document_id": doc_id, "chunk_id": f"{doc_id}_0", "text": "Item A", "embedding": [0.1, 0.2, 0.3]},
        {"document_id": doc_id, "chunk_id": f"{doc_id}_1", "text": "Item B", "embedding": [0.4, 0.5, 0.6]},
    ])

    index_service.build_index()

    report = index_service.check_consistency()
    assert report["consistent"] is True
    assert report["mongo_embeddings_count"] == 2
    assert report["faiss_vector_count"] == 2
    assert report["missing_in_faiss_count"] == 0
    assert report["stale_in_faiss_count"] == 0


def test_detect_missing_in_faiss_and_recover(tmp_path):
    """
    Test that introducing a new MongoDB chunk with embedding that is missing from FAISS
    is detected and repaired via rebuild_index().
    """
    index_file = str(tmp_path / "missing.index")
    mapping_file = str(tmp_path / "missing.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    doc_id = str(ObjectId())
    chunk_repo.insert_chunks([
        {"document_id": doc_id, "chunk_id": f"{doc_id}_0", "text": "Item A", "embedding": [0.1, 0.2, 0.3]},
    ])
    index_service.build_index()

    # Introduce a new MongoDB chunk with embedding (not yet in FAISS)
    missing_chunk_id = f"{doc_id}_missing_1"
    chunk_repo.insert_chunks([
        {"document_id": doc_id, "chunk_id": missing_chunk_id, "text": "Item B", "embedding": [0.4, 0.5, 0.6]},
    ])

    # 1. Audit before rebuild: Discrepancy detected
    report_before = index_service.check_consistency()
    assert report_before["consistent"] is False
    assert report_before["missing_in_faiss_count"] == 1
    assert missing_chunk_id in report_before["missing_in_faiss_ids"]
    assert report_before["stale_in_faiss_count"] == 0

    # 2. Execute Recovery Procedure: Rebuild index
    recovery_result = index_service.rebuild_index()

    # 3. Audit after rebuild: Fully synchronized
    assert recovery_result["consistency"]["consistent"] is True
    assert recovery_result["consistency"]["mongo_embeddings_count"] == 2
    assert recovery_result["consistency"]["faiss_vector_count"] == 2
    assert recovery_result["consistency"]["missing_in_faiss_count"] == 0


def test_detect_stale_in_faiss_and_recover(tmp_path):
    """
    Acceptance Criterion:
    Introduce a stale entry (MongoDB chunk deleted, but vector remained in FAISS),
    detect it, rebuild the index, and verify that search results are correct again.
    """
    index_file = str(tmp_path / "stale.index")
    mapping_file = str(tmp_path / "stale.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )
    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    doc_id = str(ObjectId())
    mouse_chunk_id = f"{doc_id}_mouse"
    stale_burger_chunk_id = f"{doc_id}_stale_burger"

    chunk_repo.insert_chunks([
        {
            "document_id": doc_id,
            "chunk_id": mouse_chunk_id,
            "text": "Logitech wireless mouse electronics ₹799",
            "embedding": embedding_service.generate_embedding("Logitech wireless mouse electronics ₹799"),
        },
        {
            "document_id": doc_id,
            "chunk_id": stale_burger_chunk_id,
            "text": "Delicious double cheeseburger ₹299",
            "embedding": embedding_service.generate_embedding("Delicious double cheeseburger ₹299"),
        },
    ])

    # Initial indexing
    index_service.build_index()
    assert index_service.check_consistency()["consistent"] is True

    # Introduce stale entry: Delete the burger chunk from MongoDB
    deleted_count = chunk_repo.delete_chunk_by_id(stale_burger_chunk_id)
    assert deleted_count == 1

    # 1. Audit detects stale entry in FAISS
    report_before = index_service.check_consistency()
    assert report_before["consistent"] is False
    assert report_before["stale_in_faiss_count"] == 1
    assert stale_burger_chunk_id in report_before["stale_in_faiss_ids"]
    assert report_before["mongo_embeddings_count"] == 1
    assert report_before["faiss_vector_count"] == 2

    # 2. Execute Recovery Procedure: Rebuild index
    recovery_result = index_service.rebuild_index()

    # 3. Verify post-recovery consistency
    report_after = recovery_result["consistency"]
    assert report_after["consistent"] is True
    assert report_after["stale_in_faiss_count"] == 0
    assert report_after["faiss_vector_count"] == 1
    assert report_after["mongo_embeddings_count"] == 1

    # 4. Verify search results are correct and stale items are completely gone
    results = search_service.search(query="wireless mouse", top_k=5)
    assert len(results) == 1
    assert results[0]["chunk_id"] == mouse_chunk_id
    assert results[0]["text"] == "Logitech wireless mouse electronics ₹799"
