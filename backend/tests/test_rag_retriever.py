import hashlib
import mongomock
from bson import ObjectId
import numpy as np
import pytest

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.faiss_service import FAISSService
from app.services.rag_retriever import RAGRetriever

mongomock.mongo_client._get_server_version = lambda: "6.0.0"


class MockFastEmbeddingService:
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

    async def embed_query(self, text: str) -> list[float]:
        return self.generate_embedding(text)


@pytest.mark.anyio
async def test_retriever_enforces_user_ownership(tmp_path):
    """
    Test 1: User A and User B both have chunks in FAISS.
    When User A queries, only User A's documents are returned.
    User B's chunks are strictly excluded.
    """
    index_file = str(tmp_path / "rag.index")
    mapping_file = str(tmp_path / "rag.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    emb_service = MockFastEmbeddingService()

    user_a_id = str(ObjectId())
    user_b_id = str(ObjectId())

    # Create Document for User A
    doc_a_id = str(ObjectId())
    db["documents"].insert_one({
        "_id": ObjectId(doc_a_id),
        "user_id": user_a_id,
        "filename": "user_a_laptop.pdf",
    })

    # Create Document for User B
    doc_b_id = str(ObjectId())
    db["documents"].insert_one({
        "_id": ObjectId(doc_b_id),
        "user_id": user_b_id,
        "filename": "user_b_laptop.pdf",
    })

    # Chunks for User A
    chunk_a = {
        "_id": ObjectId(),
        "document_id": doc_a_id,
        "chunk_id": f"{doc_a_id}_c0",
        "text": "User A purchased MacBook Pro ₹1,99,000",
        "page": 1,
        "embedding": emb_service.generate_embedding("MacBook Pro laptop purchase"),
    }
    # Chunks for User B
    chunk_b = {
        "_id": ObjectId(),
        "document_id": doc_b_id,
        "chunk_id": f"{doc_b_id}_c0",
        "text": "User B purchased Dell XPS laptop ₹1,20,000",
        "page": 1,
        "embedding": emb_service.generate_embedding("Dell XPS laptop purchase"),
    }

    db["document_chunks"].insert_many([chunk_a, chunk_b])
    faiss_service.add_embeddings([
        {"chunk_id": chunk_a["chunk_id"], "embedding": chunk_a["embedding"]},
        {"chunk_id": chunk_b["chunk_id"], "embedding": chunk_b["embedding"]},
    ])

    retriever = RAGRetriever(
        embedding_service=emb_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
        default_score_threshold=0.0,
    )

    # Query as User A
    results_a = await retriever.retrieve(
        question="MacBook Pro laptop purchase",
        user_id=user_a_id,
        top_k=5,
    )

    # Only User A's document must be present
    assert len(results_a) == 1
    assert results_a[0]["document_id"] == doc_a_id
    assert results_a[0]["filename"] == "user_a_laptop.pdf"
    assert results_a[0]["chunk_id"] == chunk_a["chunk_id"]
    assert "User A purchased MacBook Pro" in results_a[0]["text"]
    assert results_a[0]["page"] == 1


@pytest.mark.anyio
async def test_retriever_score_threshold_filtering(tmp_path):
    """
    Test 2: Results below the configured score threshold are discarded.
    """
    index_file = str(tmp_path / "thresh.index")
    mapping_file = str(tmp_path / "thresh.json")

    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    emb_service = MockFastEmbeddingService()

    user_id = str(ObjectId())
    doc_id = str(ObjectId())
    db["documents"].insert_one({
        "_id": ObjectId(doc_id),
        "user_id": user_id,
        "filename": "receipt.pdf",
    })

    chunk_high = {
        "_id": ObjectId(),
        "document_id": doc_id,
        "chunk_id": "c_high",
        "text": "Electronics invoice wireless mouse ₹799",
        "page": 1,
        "embedding": emb_service.generate_embedding("wireless mouse"),
    }
    chunk_low = {
        "_id": ObjectId(),
        "document_id": doc_id,
        "chunk_id": "c_low",
        "text": "Grocery broccoli fresh produce $2.99",
        "page": 2,
        "embedding": emb_service.generate_embedding("grocery broccoli produce"),
    }

    db["document_chunks"].insert_many([chunk_high, chunk_low])
    faiss_service.add_embeddings([
        {"chunk_id": chunk_high["chunk_id"], "embedding": chunk_high["embedding"]},
        {"chunk_id": chunk_low["chunk_id"], "embedding": chunk_low["embedding"]},
    ])

    retriever = RAGRetriever(
        embedding_service=emb_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
        default_score_threshold=0.50,  # High threshold
    )

    results = await retriever.retrieve(
        question="wireless mouse",
        user_id=user_id,
        top_k=5,
    )

    # Only high-scoring mouse chunk passes
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c_high"
    assert results[0]["score"] >= 0.50


@pytest.mark.anyio
async def test_retriever_empty_index_or_missing_user():
    """
    Test 3: Empty index or invalid user returns empty list without error.
    """
    client = mongomock.MongoClient()
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)
    faiss_service = FAISSService(index_path="nonexistent.index", mapping_path="nonexistent.json")
    emb_service = MockFastEmbeddingService()

    retriever = RAGRetriever(
        embedding_service=emb_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
    )

    # Empty index
    results = await retriever.retrieve(question="hello?", user_id="user123")
    assert results == []

    # Empty user_id
    results_no_user = await retriever.retrieve(question="hello?", user_id="")
    assert results_no_user == []


@pytest.mark.anyio
async def test_retriever_tolerates_deleted_mongodb_chunk(tmp_path):
    """
    Test 4: Chunk exists in FAISS but was deleted from MongoDB.
    Retriever gracefully skips it.
    """
    index_file = str(tmp_path / "deleted.index")
    mapping_file = str(tmp_path / "deleted.json")

    client = mongomock.MongoClient()
    db = client["documind_test"]
    chunk_repo = ChunkRepository(db)
    doc_repo = DocumentRepository(db)

    faiss_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    emb_service = MockFastEmbeddingService()

    user_id = str(ObjectId())
    doc_id = str(ObjectId())
    db["documents"].insert_one({"_id": ObjectId(doc_id), "user_id": user_id, "filename": "doc.pdf"})

    # Add 2 items to FAISS
    emb1 = emb_service.generate_embedding("Item 1")
    emb2 = emb_service.generate_embedding("Item 2")
    faiss_service.add_embeddings([
        {"chunk_id": "c1", "embedding": emb1},
        {"chunk_id": "c2_deleted", "embedding": emb2},
    ])

    # Only c1 exists in MongoDB, c2_deleted is missing
    db["document_chunks"].insert_one({
        "_id": ObjectId(),
        "document_id": doc_id,
        "chunk_id": "c1",
        "text": "Valid item 1 text",
        "page": 1,
    })

    retriever = RAGRetriever(
        embedding_service=emb_service,
        faiss_service=faiss_service,
        chunk_repository=chunk_repo,
        document_repository=doc_repo,
        default_score_threshold=0.0,
    )

    results = await retriever.retrieve(question="Item 1", user_id=user_id, top_k=5)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c1"
