from datetime import datetime, timezone
from bson import ObjectId

from app.celery_app import celery_app
from app.core.database import db
from app.models.document import DocumentStatus, VectorStatus
from app.repositories.chunk_repository import ChunkRepository
from app.services.cache_service import invalidate_user_cache_sync
from app.services.chunking_service import chunk_text
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService


@celery_app.task(
    bind=True,
    name="chunk_document",
)
def chunk_document(self, document_id):
    """
    Chunk the OCR text of a processed document, persist chunks in MongoDB (document_chunks),
    generate embeddings, and index vectors into FAISS.
    """
    if isinstance(document_id, dict):
        document_id = document_id.get("document_id")
    else:
        document_id = str(document_id)

    if not ObjectId.is_valid(document_id):
        raise ValueError(f"Invalid document ID: {document_id}")

    object_id = ObjectId(document_id)
    document = db["documents"].find_one({"_id": object_id})

    if not document:
        raise ValueError(f"Document {document_id} not found")

    try:
        db["documents"].update_one(
            {"_id": object_id},
            {
                "$set": {
                    "chunking_status": "PROCESSING",
                    "vector_status": VectorStatus.INDEXING.value,
                    "processing.stage": "chunking_processing",
                }
            },
        )

        # 1. Retrieve raw OCR text
        raw_text = document.get("ocr", {}).get("raw_text", "")

        # 2. Chunk text
        chunks = chunk_text(
            text=raw_text,
            document_id=str(document_id),
        )

        # 3. Persist chunks in document_chunks collection (MongoDB)
        chunk_repo = ChunkRepository(db)
        chunk_repo.delete_document_chunks(str(document_id))
        chunk_repo.insert_chunks(chunks)

        # 4. Attempt Vector Embedding & FAISS Indexing
        vector_status = VectorStatus.INDEXED.value
        try:
            if chunks:
                embedding_service = EmbeddingService()
                faiss_service = FAISSService()

                texts = [chunk["text"] for chunk in chunks]
                embeddings = embedding_service.generate_embeddings(texts)

                chunks_to_index = []
                for chunk, emb in zip(chunks, embeddings):
                    chunk_id = chunk["chunk_id"]
                    chunk_repo.update_embedding(chunk_id, emb)
                    chunks_to_index.append({
                        "chunk_id": chunk_id,
                        "embedding": emb,
                    })

                faiss_service.add_embeddings(chunks_to_index)
        except Exception as indexing_exc:
            # If embedding or FAISS indexing fails, isolate vector_status
            vector_status = VectorStatus.FAILED.value
            db["documents"].update_one(
                {"_id": object_id},
                {
                    "$set": {
                        "vector_status": VectorStatus.FAILED.value,
                        "processing.vector_error": str(indexing_exc),
                    }
                },
            )

        # 5. Mark document processing as COMPLETED
        now = datetime.now(timezone.utc)
        db["documents"].update_one(
            {"_id": object_id},
            {
                "$set": {
                    "chunking_status": "COMPLETED",
                    "vector_status": vector_status,
                    "chunk_count": len(chunks),
                    "status": DocumentStatus.COMPLETED.value,
                    "processing.processed_at": now,
                    "processing.stage": "completed" if vector_status == VectorStatus.INDEXED.value else "completed_vector_failed",
                },
                "$unset": {
                    "chunks": "",
                },
            },
        )

        # 6. Invalidate RAG cache for document owner after chunks and vectors are ready
        user_id = str(document.get("user_id")) if document.get("user_id") else None
        if user_id:
            invalidate_user_cache_sync(user_id)

        return str(document_id)

    except Exception as exc:
        db["documents"].update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.FAILED.value,
                    "chunking_status": "FAILED",
                    "vector_status": VectorStatus.FAILED.value,
                    "processing.stage": "chunking_failed",
                    "processing.error": str(exc),
                }
            },
        )
        raise