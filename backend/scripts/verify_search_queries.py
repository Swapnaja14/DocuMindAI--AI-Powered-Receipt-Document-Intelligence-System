import sys
import io
from pathlib import Path

# Configure utf-8 standard output for Windows consoles
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import db
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService


def seed_sample_receipts():
    """
    Seeds a diverse set of realistic receipt documents into MongoDB.
    """
    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()

    doc_1 = str(ObjectId())  # Tech & Electronics
    doc_2 = str(ObjectId())  # Grocery Store
    doc_3 = str(ObjectId())  # Office Supplies
    doc_4 = str(ObjectId())  # Restaurant & Food
    doc_5 = str(ObjectId())  # Hardware & Tools

    sample_chunks = [
        # 1. Electronics Receipt
        {
            "document_id": doc_1,
            "chunk_id": f"{doc_1}_0",
            "page": 1,
            "text": "BestBuy Electronics Store #482\nLogitech MX Master Wireless Mouse INR 6499\nUSB-C Fast Charging Cable INR 899\nSubtotal: INR 7398\nGST/Tax Amount (18%): INR 1331.64\nTotal Paid: INR 8729.64\nPayment: Visa Credit Card",
        },
        # 2. Grocery Receipt
        {
            "document_id": doc_2,
            "chunk_id": f"{doc_2}_0",
            "page": 1,
            "text": "Whole Foods Market - Downtown Grocery\nOrganic Hass Avocados (4ct) $5.99\nAlmond Milk Unsweetened 64oz $3.49\nOrganic Sourdough Bread $4.99\nFresh Strawberries 1lb $3.99\nSubtotal: $18.46\nSales Tax (6%): $1.11\nTotal Grocery Amount: $19.57",
        },
        # 3. Office Supplies Receipt
        {
            "document_id": doc_3,
            "chunk_id": f"{doc_3}_0",
            "page": 1,
            "text": "Staples Office Supplies Co.\nMultipurpose Copy Paper 500 Sheets (5 Reams) INR 1450\nGel Pen Set 10-Pack Black INR 299\nHeavy Duty Desk Stapler with 5000 Pins INR 450\nSubtotal: INR 2199\nTax Amount: INR 263.88\nTotal: INR 2462.88",
        },
        # 4. Restaurant Receipt
        {
            "document_id": doc_4,
            "chunk_id": f"{doc_4}_0",
            "page": 1,
            "text": "The Bistro Kitchen & Italian Restaurant\n1x Truffle Pasta INR 650\n1x Woodfired Margherita Pizza INR 550\n2x Sparkling Lemonade INR 300\nService Charge (5%): INR 75\nVAT/Tax Amount (5%): INR 75\nGrand Total: INR 1650",
        },
        # 5. Hardware Store
        {
            "document_id": doc_5,
            "chunk_id": f"{doc_5}_0",
            "page": 1,
            "text": "Home Depot Hardware Tools\nDeWalt Cordless Drill Driver Kit INR 8999\nScrewdriver 12-Piece Precision Set INR 1200\nMeasuring Tape 25ft INR 350\nTotal Tax Amount: INR 1898.82\nTotal Invoice: INR 12447.82",
        },
    ]

    print("Generating embeddings and saving sample receipts to MongoDB...")
    for chunk in sample_chunks:
        emb = embedding_service.generate_embedding(chunk["text"])
        chunk["embedding"] = emb
        chunk_repo.collection.delete_many({"chunk_id": chunk["chunk_id"]})
        chunk_repo.create_chunk(chunk)

    print(f"Successfully stored {len(sample_chunks)} sample chunks in MongoDB.")
    return [doc_1, doc_2, doc_3, doc_4, doc_5]


def build_index():
    """
    Builds the FAISS vector index from MongoDB embeddings.
    """
    chunk_repo = ChunkRepository(db)
    faiss_service = FAISSService()
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )

    status = index_service.build_index()
    print("FAISS Index build status:", status)
    return faiss_service


def test_queries():
    """
    Runs semantic search queries against FastAPI /api/search.
    """
    client = TestClient(app)

    queries = [
        "wireless mouse",
        "grocery purchase",
        "tax amount",
        "Whole Foods",
        "office supplies",
    ]

    print("\n" + "=" * 80)
    print("RUNNING SEMANTIC SEARCH VERIFICATION")
    print("=" * 80)

    for q in queries:
        print(f"\n>> QUERY: \"{q}\"")
        payload = {
            "query": q,
            "top_k": 2,
        }
        response = client.post("/api/search", json=payload)
        assert response.status_code == 200, f"Search failed: {response.text}"

        data = response.json()
        results = data.get("results", [])

        if not results:
            print("   [No results returned]")
            continue

        for idx, item in enumerate(results, 1):
            score = item["score"]
            doc_id = item["document_id"]
            page = item.get("page_number", 1)
            first_line = item["text"].split("\n")[0]
            print(f"   Rank #{idx} | Cosine Similarity Score: {score:.4f} | Page: {page} | Doc: {doc_id}")
            print(f"      Header: \"{first_line}\"")
            print(f"      Matched Text: {item['text'][:120]}...\n")


def test_document_filtering(doc_1, doc_2):
    """
    Verifies document-level filtering on real datasets.
    """
    client = TestClient(app)

    print("\n" + "=" * 80)
    print("RUNNING DOCUMENT FILTERING VERIFICATION")
    print("=" * 80)

    # 1. Search across entire collection
    print('\n>> UNFILTERED SEARCH: query="wireless mouse", top_k=5')
    resp_all = client.post("/api/search", json={"query": "wireless mouse", "top_k": 5})
    assert resp_all.status_code == 200
    results_all = resp_all.json()["results"]
    print(f"   Found {len(results_all)} results across collection:")
    for r in results_all:
        first_line = r["text"].split("\n")[0]
        print(f"   - Doc: {r['document_id']} | Score: {r['score']:.4f} | Header: {first_line}")

    # 2. Search strictly within doc_1 (Electronics)
    print(f'\n>> FILTERED SEARCH: query="wireless mouse", document_id="{doc_1}"')
    resp_doc1 = client.post("/api/search", json={"query": "wireless mouse", "top_k": 5, "document_id": doc_1})
    assert resp_doc1.status_code == 200
    results_doc1 = resp_doc1.json()["results"]
    print(f"   Found {len(results_doc1)} results strictly within doc_1:")
    for r in results_doc1:
        assert r["document_id"] == doc_1, f"Expected doc_1, got {r['document_id']}"
        print(f"   - [MATCH] Doc: {r['document_id']} (VERIFIED) | Score: {r['score']:.4f}")

    # 3. Search strictly within doc_2 (Whole Foods Grocery)
    print(f'\n>> FILTERED SEARCH: query="wireless mouse", document_id="{doc_2}"')
    resp_doc2 = client.post("/api/search", json={"query": "wireless mouse", "top_k": 5, "document_id": doc_2})
    assert resp_doc2.status_code == 200
    results_doc2 = resp_doc2.json()["results"]
    print(f"   Found {len(results_doc2)} results strictly within doc_2:")
    for r in results_doc2:
        assert r["document_id"] == doc_2, f"Expected doc_2, got {r['document_id']}"
        print(f"   - [MATCH] Doc: {r['document_id']} (VERIFIED) | Score: {r['score']:.4f}")


def test_architectural_resilience():
    """
    Verifies that if a chunk is deleted/missing in MongoDB while remaining in FAISS,
    the search pipeline skips it gracefully without throwing an exception.
    """
    client = TestClient(app)
    chunk_repo = ChunkRepository(db)
    embedding_service = EmbeddingService()
    faiss_service = FAISSService()

    print("\n" + "=" * 80)
    print("RUNNING ARCHITECTURAL RESILIENCE (MISSING MONGODB CHUNK) CHECK")
    print("=" * 80)

    # 1. Create a temporary ghost chunk in MongoDB & FAISS
    ghost_doc_id = str(ObjectId())
    ghost_chunk_id = f"{ghost_doc_id}_ghost"
    ghost_text = "Ghost Receipt with Special Unique Gadget Item INR 99999"
    emb = embedding_service.generate_embedding(ghost_text)

    chunk_repo.create_chunk({
        "document_id": ghost_doc_id,
        "chunk_id": ghost_chunk_id,
        "text": ghost_text,
        "embedding": emb,
        "page": 1,
    })
    faiss_service.add_embedding(ghost_chunk_id, emb)

    # 2. Delete the chunk from MongoDB only (simulating out-of-sync or hard delete)
    chunk_repo.collection.delete_one({"chunk_id": ghost_chunk_id})
    print(f"   Simulated deletion: Chunk '{ghost_chunk_id}' deleted from MongoDB, present in FAISS.")

    # 3. Query for that exact text
    resp = client.post("/api/search", json={"query": "Special Unique Gadget Item", "top_k": 3})
    assert resp.status_code == 200, f"Search failed with error: {resp.text}"
    results = resp.json().get("results", [])

    returned_chunk_ids = [r["chunk_id"] for r in results]
    assert ghost_chunk_id not in returned_chunk_ids, "Ghost chunk should be skipped!"

    print("   [SUCCESS] Search executed gracefully with HTTP 200, ghost chunk was safely skipped.\n")


if __name__ == "__main__":
    docs = seed_sample_receipts()
    build_index()
    test_queries()
    if docs:
        test_document_filtering(docs[0], docs[1])
    test_architectural_resilience()

