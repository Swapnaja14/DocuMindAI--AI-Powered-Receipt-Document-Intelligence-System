import hashlib
import numpy as np
import mongomock
from concurrent.futures import ThreadPoolExecutor
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.faiss_service import FAISSService
from app.services.vector_indexing_service import VectorIndexingService


class FastMockEmbeddingService:
    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        results = []
        for t in texts:
            seed = int(hashlib.md5(t.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            vec = rng.randn(384).astype("float32")
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            results.append(vec.tolist())
        return results


def test_concurrent_vector_indexing(tmp_path):
    index_file = str(tmp_path / "concurrent.index")
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]

    embedding_service = FastMockEmbeddingService()
    mapping_repo = VectorMappingRepository(db)

    def worker_index_doc(doc_num: int):
        # Each simulated worker has its own FAISSService instance loading from shared file
        faiss_service = FAISSService(index_path=index_file)
        service = VectorIndexingService(
            embedding_service=embedding_service,
            faiss_service=faiss_service,
            vector_mapping_repository=mapping_repo,
        )

        doc_id = f"doc_{doc_num}"
        chunks = [
            {"chunk_id": 0, "text": f"Receipt item {doc_num}_A ₹100"},
            {"chunk_id": 1, "text": f"Receipt item {doc_num}_B ₹200"},
        ]

        return service.index_chunks(document_id=doc_id, chunks=chunks)

    # Run 4 workers concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(worker_index_doc, range(4)))

    # 4 workers * 2 chunks = 8 chunks total
    all_mappings = [m for sublist in results for m in sublist]
    assert len(all_mappings) == 8

    # Verify all assigned faiss_ids are completely unique (no collisions)
    assigned_faiss_ids = [m["faiss_id"] for m in all_mappings]
    assert len(set(assigned_faiss_ids)) == 8
    assert set(assigned_faiss_ids) == set(range(8))

    # Verify persisted FAISS index contains all 8 vectors
    final_faiss = FAISSService(index_path=index_file)
    final_faiss.load()
    assert final_faiss.count() == 8
