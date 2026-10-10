import pytest
import mongomock
from bson import ObjectId

from app.repositories.chunk_repository import ChunkRepository
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


def test_1_empty_database(tmp_path):
    """
    Test 1 — Empty database
    MongoDB chunks = 0 -> FAISS vectors = 0, loaded = False
    """
    index_path = str(tmp_path / "empty.index")
    mapping_path = str(tmp_path / "empty.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind"]
    chunk_repo = ChunkRepository(db)

    faiss_service = FAISSService(index_path=index_path, mapping_path=mapping_path)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    status = index_service.build_index()

    assert status["total_vectors"] == 0
    assert status["mapped_chunks"] == 0
    assert status["loaded"] is False


def test_2_existing_embeddings(tmp_path):
    """
    Test 2 — Existing embeddings
    MongoDB chunks = 3 -> FAISS vectors = 3, mapping entries = 3
    """
    index_path = str(tmp_path / "existing.index")
    mapping_path = str(tmp_path / "existing.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind"]
    chunk_repo = ChunkRepository(db)

    doc_id = str(ObjectId())
    chunk_repo.insert_chunks([
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_0",
            "text": "Chunk A",
            "embedding": [0.1, 0.2, 0.3],
        },
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_1",
            "text": "Chunk B",
            "embedding": [0.4, 0.5, 0.6],
        },
        {
            "document_id": doc_id,
            "chunk_id": f"{doc_id}_2",
            "text": "Chunk C",
            "embedding": [0.7, 0.8, 0.9],
        },
    ])

    faiss_service = FAISSService(index_path=index_path, mapping_path=mapping_path)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    status = index_service.build_index()

    assert status["loaded"] is True
    assert status["total_vectors"] == 3
    assert status["mapped_chunks"] == 3


def test_3_rebuild_twice_idempotency(tmp_path):
    """
    Test 3 — Rebuild twice
    First build: 3 vectors
    Second build: 3 vectors (no duplicate insertions)
    """
    index_path = str(tmp_path / "rebuild_twice.index")
    mapping_path = str(tmp_path / "rebuild_twice.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind"]
    chunk_repo = ChunkRepository(db)

    doc_id = str(ObjectId())
    chunk_repo.insert_chunks([
        {"document_id": doc_id, "chunk_id": f"{doc_id}_0", "text": "A", "embedding": [0.1, 0.2, 0.3]},
        {"document_id": doc_id, "chunk_id": f"{doc_id}_1", "text": "B", "embedding": [0.4, 0.5, 0.6]},
        {"document_id": doc_id, "chunk_id": f"{doc_id}_2", "text": "C", "embedding": [0.7, 0.8, 0.9]},
    ])

    faiss_service = FAISSService(index_path=index_path, mapping_path=mapping_path)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    # First build
    status_1 = index_service.build_index()
    assert status_1["total_vectors"] == 3
    assert status_1["mapped_chunks"] == 3

    # Second build
    status_2 = index_service.build_index()
    assert status_2["total_vectors"] == 3
    assert status_2["mapped_chunks"] == 3


def test_4_missing_embedding(tmp_path):
    """
    Test 4 — Missing embedding
    Chunk A -> embedding
    Chunk B -> embedding
    Chunk C -> no embedding / None
    FAISS should contain 2 vectors, not 3.
    """
    index_path = str(tmp_path / "missing_emb.index")
    mapping_path = str(tmp_path / "missing_emb.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind"]
    chunk_repo = ChunkRepository(db)

    doc_id = str(ObjectId())
    chunk_repo.insert_chunks([
        {"document_id": doc_id, "chunk_id": f"{doc_id}_0", "text": "A", "embedding": [0.1, 0.2, 0.3]},
        {"document_id": doc_id, "chunk_id": f"{doc_id}_1", "text": "B", "embedding": [0.4, 0.5, 0.6]},
        {"document_id": doc_id, "chunk_id": f"{doc_id}_2", "text": "C"},  # No embedding
    ])

    faiss_service = FAISSService(index_path=index_path, mapping_path=mapping_path)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    status = index_service.build_index()

    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2


def test_5_dimension_mismatch(tmp_path):
    """
    Test 5 — Dimension mismatch
    FAISS initialized with 3 dimensions -> adding 4 dimensions must fail with ValueError.
    """
    index_path = str(tmp_path / "dim_mismatch.index")
    mapping_path = str(tmp_path / "dim_mismatch.json")

    faiss_service = FAISSService(index_path=index_path, mapping_path=mapping_path)
    faiss_service.add_embedding("initial_chunk", [0.1, 0.2, 0.3])  # 3 dimensions

    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        faiss_service.add_embedding("mismatched_chunk", [0.1, 0.2, 0.3, 0.4])  # 4 dimensions
