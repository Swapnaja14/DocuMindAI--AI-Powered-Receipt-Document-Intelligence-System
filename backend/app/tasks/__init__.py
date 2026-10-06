from app.tasks.test_tasks import test_task
from app.tasks.document_tasks import process_ocr, extract_document, process_document
from app.tasks.chunking_tasks import chunk_document

__all__ = [
    "test_task",
    "process_ocr",
    "extract_document",
    "process_document",
    "chunk_document",
]
