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


@celery_app.task(name="process_ocr")
def process_ocr(document_id: str) -> str:
    """
    Asynchronously run OCR on an uploaded document and persist raw OCR text.
    Standardized to return document_id for clean Celery chaining.
    """
    if isinstance(document_id, dict):
        document_id = document_id.get("document_id")
    else:
        document_id = str(document_id)

    if not ObjectId.is_valid(document_id):
        raise ValueError(f"Invalid document ID: {document_id}")

    object_id = ObjectId(document_id)
    document = documents_collection.find_one({"_id": object_id})

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    documents_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": DocumentStatus.PROCESSING.value,
                "ocr_status": "PROCESSING",
                "processing.stage": "ocr_processing",
                "processing.error": None,
            }
        },
    )

    try:
        file_path = document.get("file_path")
        if not file_path:
            raise OCRProcessingError("Document does not contain a file path.")

        ocr_result = ocr_document(file_path)
        raw_text = ocr_result["raw_text"]
        page_count = ocr_result["page_count"]

        if not raw_text.strip():
            raise OCRProcessingError(
                "OCR completed successfully, but no text was detected in the document."
            )

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "ocr.raw_text": raw_text,
                    "ocr.page_count": page_count,
                    "ocr_status": "COMPLETED",
                    "status": DocumentStatus.OCR_COMPLETED.value,
                    "processing.stage": "ocr_completed",
                }
            },
        )

        return str(document_id)

    except Exception as exc:
        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.FAILED.value,
                    "ocr_status": "FAILED",
                    "processing.stage": "ocr_failed",
                    "processing.error": str(exc),
                }
            },
        )
        raise


@celery_app.task(name="extract_document")
def extract_document(document_id: str) -> str:
    """
    Asynchronously run structured extraction via Gemini on the OCR text.
    Standardized to return document_id for clean Celery chaining.
    """
    if isinstance(document_id, dict):
        document_id = document_id.get("document_id")
    else:
        document_id = str(document_id)

    if not ObjectId.is_valid(document_id):
        raise ValueError(f"Invalid document ID: {document_id}")

    object_id = ObjectId(document_id)
    document = documents_collection.find_one({"_id": object_id})

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    documents_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "extraction_status": "PROCESSING",
                "processing.stage": "extraction_processing",
            }
        },
    )

    try:
        raw_text = document.get("ocr", {}).get("raw_text", "")
        if not raw_text.strip():
            raise ValueError(f"No OCR text found for document: {document_id}")

        extraction_result = extract_document_data(raw_text)
        extracted_data = extraction_result["data"]
        validation = extraction_result["validation"]

        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "extracted_data": extracted_data,
                    "validation": validation,
                    "extraction_status": "COMPLETED",
                    "status": DocumentStatus.EXTRACTION_COMPLETED.value,
                    "processing.stage": "extraction_completed",
                }
            },
        )

        return str(document_id)

    except Exception as exc:
        documents_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": DocumentStatus.FAILED.value,
                    "extraction_status": "FAILED",
                    "processing.stage": "extraction_failed",
                    "processing.error": str(exc),
                }
            },
        )
        raise


@celery_app.task(name="process_document")
def process_document(document_id: str) -> str:
    """
    Composite task executing OCR, Extraction, and Chunking sequentially.
    Kept for backward compatibility.
    """
    from app.tasks.chunking_tasks import chunk_document

    process_ocr(document_id)
    extract_document(document_id)
    chunk_document(document_id)
    return str(document_id)