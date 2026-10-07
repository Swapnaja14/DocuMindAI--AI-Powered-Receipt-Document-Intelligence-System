from datetime import datetime, timezone
from bson import ObjectId

from app.celery_app import celery_app
from app.core.database import db
from app.models.document import DocumentStatus, VectorStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.vector_mapping_repository import VectorMappingRepository
from app.services.chunking_service import chunk_text
from app.services.embedding_service import EmbeddingService
from app.services.faiss_service import FAISSService
from app.services.vector_indexing_service import VectorIndexingService


@celery_app.task(
    bind=True,
    name="chunk_document",
)
def chunk_document(self, document_id):
    """
    Chunk the OCR text of a processed document, persist chunks in document_chunks,
    and index vectors into FAISS with resilient status tracking.
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

        # 3. Persist chunks in document_chunks collection
        chunk_repo = ChunkRepository(db)
        chunk_repo.delete_document_chunks(str(document_id))
        chunk_repo.insert_chunks(chunks)

        # 4. Attempt Vector Indexing
        vector_status = VectorStatus.INDEXED.value
        try:
            if chunks:
                embedding_service = EmbeddingService()
                faiss_service = FAISSService(index_path="storage/faiss/index.faiss")
                faiss_service.load()
                vector_mapping_repo = VectorMappingRepository(db)
                vector_mapping_repo.delete_by_document_id(str(document_id))

                vector_indexing_service = VectorIndexingService(
                    embedding_service=embedding_service,
                    faiss_service=faiss_service,
                    vector_mapping_repository=vector_mapping_repo,
                )
                vector_indexing_service.index_chunks(
                    document_id=str(document_id),
                    chunks=chunks,
                )
        except Exception as indexing_exc:
            # If FAISS indexing fails, isolate vector_status so document is not marked completely broken
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