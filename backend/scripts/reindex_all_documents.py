import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("Importing modules...", flush=True)
from app.core.database import db
from app.models.document import DocumentStatus, VectorStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking_service import chunk_text
print("Importing EmbeddingService...", flush=True)
from app.services.embedding_service import EmbeddingService
print("Importing FAISSService...", flush=True)
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService


def reindex_all():
    print("=== REINDEXING ALL VALIDATED/COMPLETED DOCUMENTS ===", flush=True)
    chunk_repo = ChunkRepository(db)
    print("Initializing EmbeddingService...", flush=True)
    embedding_service = EmbeddingService()
    print("Initializing FAISSService...", flush=True)
    faiss_service = FAISSService()

    docs = list(db["documents"].find({
        "status": {"$in": ["VALIDATED", "COMPLETED"]},
        "ocr.raw_text": {"$exists": True, "$ne": ""}
    }))

    print(f"Found {len(docs)} documents to chunk & index.", flush=True)

    total_chunks = 0
    for doc in docs:
        doc_id = str(doc["_id"])
        filename = doc.get("filename", "unknown")
        raw_text = doc.get("ocr", {}).get("raw_text", "")

        if not raw_text.strip():
            print(f"Skipping {filename} ({doc_id}) - raw_text is empty", flush=True)
            continue

        print(f"\nProcessing {filename} ({doc_id}) [raw_text: {len(raw_text)} chars]...", flush=True)

        # 1. Chunk text
        chunks = chunk_text(text=raw_text, document_id=doc_id)
        if not chunks:
            print(f"  Warning: No chunks generated for {filename}", flush=True)
            continue

        print(f"  Generated {len(chunks)} chunks.", flush=True)

        # 2. Persist chunks in document_chunks
        chunk_repo.delete_document_chunks(doc_id)
        chunk_repo.insert_chunks(chunks)

        # 3. Generate embeddings
        texts = [c["text"] for c in chunks]
        embeddings = embedding_service.generate_embeddings(texts)

        for chunk, emb in zip(chunks, embeddings):
            chunk_id = chunk["chunk_id"]
            chunk_repo.update_embedding(chunk_id, emb)

        # 4. Update document metadata
        db["documents"].update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": DocumentStatus.COMPLETED.value,
                    "chunking_status": "COMPLETED",
                    "vector_status": VectorStatus.INDEXED.value,
                    "chunk_count": len(chunks),
                    "processing.stage": "completed",
                    "processing.processed_at": datetime.now(timezone.utc),
                },
                "$unset": {
                    "chunks": "",
                }
            }
        )
        total_chunks += len(chunks)
        print(f"  Successfully embedded & updated {filename} ({len(chunks)} chunks).", flush=True)

    print(f"\n=== REBUILDING FAISS INDEX FROM MONGODB ===", flush=True)
    index_service = FAISSIndexService(
        chunk_repository=chunk_repo,
        faiss_service=faiss_service,
    )
    rebuild_res = index_service.rebuild_index()
    print("Rebuild status:", rebuild_res, flush=True)

    print("\n=== CONSISTENCY CHECK ===", flush=True)
    audit = index_service.check_consistency()
    for k, v in audit.items():
        print(f"  {k}: {v}", flush=True)

    if audit["consistent"]:
        print(f"\nSUCCESS! All {audit['faiss_vector_count']} vectors are indexed and synchronized.", flush=True)
    else:
        print("\nWARNING: Discrepancy remaining after rebuild.", flush=True)


if __name__ == "__main__":
    reindex_all()
