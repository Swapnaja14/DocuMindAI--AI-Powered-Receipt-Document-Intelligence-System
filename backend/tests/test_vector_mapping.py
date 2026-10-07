import mongomock
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository


def test_vector_mapping_crud():
    client = mongomock.MongoClient()
    db = client["test_db"]
    repo = VectorMappingRepository(db)

    mappings = [
        {"faiss_id": 0, "document_id": "doc_1", "chunk_id": 0},
        {"faiss_id": 1, "document_id": "doc_1", "chunk_id": 1},
        {"faiss_id": 2, "document_id": "doc_2", "chunk_id": 0},
    ]

    # Insert mappings
    repo.insert_mappings(mappings)

    # Lookup single by faiss_id
    res = repo.get_by_faiss_id(1)
    assert res is not None
    assert res["document_id"] == "doc_1"
    assert res["chunk_id"] == 1

    # Lookup multiple by faiss_ids
    results = repo.get_by_faiss_ids([0, 2])
    assert len(results) == 2
    doc_ids = {r["document_id"] for r in results}
    assert doc_ids == {"doc_1", "doc_2"}

    # Get by document_id
    doc1_mappings = repo.get_by_document_id("doc_1")
    assert len(doc1_mappings) == 2

    # Delete by document_id
    repo.delete_by_document_id("doc_1")
    assert repo.get_by_document_id("doc_1") == []
    assert len(repo.get_by_document_id("doc_2")) == 1


def test_vector_mapping_to_chunk_flow():
    client = mongomock.MongoClient()
    db = client["test_db"]
    chunk_repo = ChunkRepository(db)
    mapping_repo = VectorMappingRepository(db)

    # 1. Insert chunks into document_chunks
    chunks = [
        {"document_id": "doc_1", "chunk_id": 0, "text": "Wireless mouse ₹799"},
        {"document_id": "doc_1", "chunk_id": 1, "text": "USB keyboard ₹1299"},
    ]
    chunk_repo.insert_chunks(chunks)

    # 2. Insert vector mapping records
    mappings = [
        {"faiss_id": 0, "document_id": "doc_1", "chunk_id": 0},
        {"faiss_id": 1, "document_id": "doc_1", "chunk_id": 1},
    ]
    mapping_repo.insert_mappings(mappings)

    # 3. Simulate FAISS search returning faiss_id = 0
    faiss_hit_id = 0
    mapping = mapping_repo.get_by_faiss_id(faiss_hit_id)
    assert mapping is not None

    # 4. Resolve back to chunk text
    chunk = chunk_repo.get_chunk(mapping["document_id"], mapping["chunk_id"])
    assert chunk is not None
    assert chunk["text"] == "Wireless mouse ₹799"
