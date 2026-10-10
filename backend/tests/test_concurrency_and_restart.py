import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import mongomock
import numpy as np
import pytest

from app.core.lock import faiss_lock
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.faiss_service import FAISSService
from app.services.vector_indexing_service import VectorIndexingService
from app.services.vector_search_service import VectorSearchService

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


class FastMockEmbeddingService:
    """
    Deterministic mock embedding service producing 384-dimensional embeddings
    instantly in CPU memory without network or heavy PyTorch overhead.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def generate_embedding(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype("float32")
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(t) for t in texts]


def test_two_chunks_indexed_concurrently(tmp_path):
    """
    Test 1: Two chunks indexed concurrently by separate worker threads.
    Verifies single-writer synchronization, no duplicate IDs, and matching counts.
    """
    index_file = str(tmp_path / "concurrent.index")
    mapping_file = str(tmp_path / "concurrent_mapping.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    mapping_repo = VectorMappingRepository(db)
    embedding_service = FastMockEmbeddingService()

    def worker_index(worker_id: int):
        # Simulated worker process with its own service instance
        faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
        indexer = VectorIndexingService(
            embedding_service=embedding_service,
            faiss_service=faiss_service,
            vector_mapping_repository=mapping_repo,
        )
        chunks = [
            {"chunk_id": f"chunk_w{worker_id}_{i}", "text": f"Worker {worker_id} item {i}"}
            for i in range(2)
        ]
        return indexer.index_chunks(document_id=f"doc_{worker_id}", chunks=chunks)

    # Concurrently execute indexing
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker_index, [1, 2]))

    all_mappings = [m for sub in results for m in sub]
    assert len(all_mappings) == 4

    assigned_ids = [m["faiss_id"] for m in all_mappings]
    # Acceptance criterion: No duplicate IDs
    assert len(set(assigned_ids)) == 4

    # Verify persisted state
    final_faiss = FAISSService(index_path=index_file, mapping_path=mapping_file)
    status = final_faiss.status()
    assert status["total_vectors"] == 4
    assert status["mapped_chunks"] == 4


def test_search_while_chunk_is_being_indexed(tmp_path):
    """
    Test 2: Search while a chunk is actively being indexed.
    Verifies that reader threads never crash or observe half-written files.
    """
    index_file = str(tmp_path / "search_concur.index")
    mapping_file = str(tmp_path / "search_concur.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    embedding_service = FastMockEmbeddingService()

    # Pre-populate initial item
    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    init_emb = embedding_service.generate_embedding("Initial receipt item")
    chunk_repo.insert_chunks([
        {"document_id": "doc_0", "chunk_id": "c0", "text": "Initial receipt item", "embedding": init_emb}
    ])
    faiss_service.add_embedding("c0", init_emb)

    search_service = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
    )

    def write_heavy():
        # Simulated slow writer indexing multiple items
        writer_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
        new_items = [
            {"chunk_id": f"new_chunk_{i}", "embedding": embedding_service.generate_embedding(f"New item {i}")}
            for i in range(5)
        ]
        with faiss_lock():
            writer_service.load()
            writer_service.add_embeddings(new_items)
        return True

    def read_concurrent():
        # Reader searching concurrently
        results = search_service.search("Initial receipt item", top_k=2)
        return results

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_write = executor.submit(write_heavy)
        f_read = executor.submit(read_concurrent)

        write_done = f_write.result()
        read_results = f_read.result()

    assert write_done is True
    # Reader completed cleanly without error and found at least the initial item
    assert len(read_results) >= 1
    assert read_results[0]["chunk_id"] == "c0"


def test_application_restart_with_existing_index(tmp_path):
    """
    Test 3: Application restart with an existing index.
    Verifies clean deserialization and search availability.
    """
    index_file = str(tmp_path / "restart.index")
    mapping_file = str(tmp_path / "restart.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    embedding_service = FastMockEmbeddingService()

    # Process A writes and exits
    app_a = FAISSService(index_path=index_file, mapping_path=mapping_file)
    emb_1 = embedding_service.generate_embedding("Wireless ergonomic mouse ₹899")
    emb_2 = embedding_service.generate_embedding("Mechanical gaming keyboard ₹1999")

    chunk_repo.insert_chunks([
        {"document_id": "d1", "chunk_id": "mouse_1", "text": "Wireless ergonomic mouse ₹899", "embedding": emb_1},
        {"document_id": "d1", "chunk_id": "kb_1", "text": "Mechanical gaming keyboard ₹1999", "embedding": emb_2},
    ])
    app_a.add_embeddings([
        {"chunk_id": "mouse_1", "embedding": emb_1},
        {"chunk_id": "kb_1", "embedding": emb_2},
    ])
    del app_a  # Shutdown process A

    # Process B starts up anew (simulating application restart)
    app_b = FAISSService(index_path=index_file, mapping_path=mapping_file)
    status = app_b.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2

    search_service_b = VectorSearchService(
        embedding_service=embedding_service,
        faiss_service=app_b,
        chunk_repository=chunk_repo,
    )
    search_results = search_service_b.search("mouse", top_k=1)
    assert len(search_results) == 1
    assert search_results[0]["chunk_id"] == "mouse_1"


def test_restart_after_failed_indexing_operation(tmp_path):
    """
    Test 4: Restart after a failed indexing operation.
    Verifies that interrupted saves or corrupted temporary writes do not damage
    the valid active index, and restart recovers gracefully.
    """
    index_file = str(tmp_path / "fail_restart.index")
    mapping_file = str(tmp_path / "fail_restart.json")

    embedding_service = FastMockEmbeddingService()
    service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    # Initial valid index
    service.add_embeddings([
        {"chunk_id": "c1", "embedding": embedding_service.generate_embedding("Valid item 1")},
        {"chunk_id": "c2", "embedding": embedding_service.generate_embedding("Valid item 2")},
    ])
    assert service.count() == 2

    # Simulate an indexing failure during write
    with patch.object(service, "_validate_pair", return_value=(None, None)):
        with pytest.raises(RuntimeError):
            service._save()

    # Simulate restart
    restarted_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    status = restarted_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2
    assert "c1" in restarted_service.chunk_id_to_id
    assert "c2" in restarted_service.chunk_id_to_id


def test_deletion_followed_by_restart(tmp_path):
    """
    Test 5: Deletion followed by restart.
    Verifies vectors are cleanly pruned and restart retains correct post-deletion state.
    """
    index_file = str(tmp_path / "del_restart.index")
    mapping_file = str(tmp_path / "del_restart.json")

    embedding_service = FastMockEmbeddingService()
    service = FAISSService(index_path=index_file, mapping_path=mapping_file)

    service.add_embeddings([
        {"chunk_id": "item_1", "embedding": embedding_service.generate_embedding("Item 1")},
        {"chunk_id": "item_2", "embedding": embedding_service.generate_embedding("Item 2")},
        {"chunk_id": "item_3", "embedding": embedding_service.generate_embedding("Item 3")},
    ])
    assert service.count() == 3

    # Delete item_2
    service.remove_chunk_ids(["item_2"])
    assert service.count() == 2
    del service  # Shutdown

    # Restart
    restarted_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    status = restarted_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2
    assert "item_2" not in restarted_service.chunk_id_to_id
    assert "item_1" in restarted_service.chunk_id_to_id
    assert "item_3" in restarted_service.chunk_id_to_id
