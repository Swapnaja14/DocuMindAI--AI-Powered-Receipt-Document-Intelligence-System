from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.models.document import DocumentStatus


class OCRData(BaseModel):
    raw_text: str = ""
    page_count: int = 0


class ExtractedData(BaseModel):
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None


class Chunk(BaseModel):
    chunk_id: str
    text: str
    page: int


class ProcessingData(BaseModel):
    uploaded_at: datetime
    processed_at: datetime | None = None
    processing_time_ms: int | None = None


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    file_path: str
    file_size: int
    status: DocumentStatus
    ocr: OCRData
    extracted_data: ExtractedData
    chunks: List[Chunk]
    processing: ProcessingData

class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_type: str  
    file_size: int
    status: DocumentStatus
    uploaded_at: datetime
    