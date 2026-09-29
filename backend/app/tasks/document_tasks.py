import time
from datetime import datetime, timezone

from bson import ObjectId

from app.celery_app import celery_app
from app.core.database import documents_collection
from app.models.document import DocumentStatus
from app.services.ocr_service import (
    ocr_document,
    OCRProcessingError,
)
from app.services.document_extraction import (
    extract_document_data,
)


@celery_app.task(
    name="process_document",
)
def process_document(document_id: str):
    """
    Asynchronously process an uploaded document.

    Pipeline:
        MongoDB document
            ↓
        OCR
            ↓
        Gemini extraction
            ↓
        Extraction validation
            ↓
        MongoDB update
    """

    start_time = time.perf_counter()

    # ---------------------------------------------------------
    # 1. Validate document ID
    # ---------------------------------------------------------

    if not ObjectId.is_valid(document_id):
        raise ValueError(
            f"Invalid document ID: {document_id}"
        )

    object_id = ObjectId(document_id)

    # ---------------------------------------------------------
    # 2. Load document from MongoDB
    # ---------------------------------------------------------

    document = documents_collection.find_one(
        {"_id": object_id}
    )

    if not document:
        raise ValueError(
            f"Document not found: {document_id}"
        )

    # ---------------------------------------------------------
    # 3. Mark document as PROCESSING
    # ---------------------------------------------------------

    documents_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": DocumentStatus.PROCESSING.value,
            }
        },
    )

    try:
        # -----------------------------------------------------
        # 4. OCR
        # -----------------------------------------------------

        ocr_result = ocr_document(
            document["file_path"]
        )

        raw_text = ocr_result["raw_text"]
        page_count = ocr_result["page_count"]

        # Save OCR result immediately.
        #
        # This is useful because if Gemini fails later,
        # the OCR output is still preserved in MongoDB.
        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "ocr.raw_text": raw_text,
                    "ocr.page_count": page_count,
                }
            },
        )

        # -----------------------------------------------------
        # 5. Gemini extraction + validation
        # -----------------------------------------------------

        extraction_result = extract_document_data(
            raw_text
        )

        extracted_data = extraction_result["data"]
        validation = extraction_result["validation"]

        # -----------------------------------------------------
        # 6. Calculate processing time
        # -----------------------------------------------------

        processing_time_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        now = datetime.now(timezone.utc)

        # -----------------------------------------------------
        # 7. Save extraction + validation + COMPLETED
        # -----------------------------------------------------

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "extracted_data": extracted_data,
                    "validation": validation,
                    "status": DocumentStatus.COMPLETED.value,
                    "processing.processed_at": now,
                    "processing.processing_time_ms": (
                        processing_time_ms
                    ),
                }
            },
        )

        return {
            "document_id": document_id,
            "status": DocumentStatus.COMPLETED.value,
            "processing_time_ms": processing_time_ms,
            "validation": validation,
        }

    except Exception as exc:
        # -----------------------------------------------------
        # 8. Failure handling
        # -----------------------------------------------------

        processing_time_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.FAILED.value,
                    "processing.processing_time_ms": (
                        processing_time_ms
                    ),
                    "processing.error": str(exc),
                }
            },
        )

        raise