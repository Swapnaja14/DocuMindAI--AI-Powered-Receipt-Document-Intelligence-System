from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from app.models.document import DocumentStatus


class OCRData(BaseModel):
    raw_text: str = ""
    page_count: int = 0


class ExtractedItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class ExtractedData(BaseModel):
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    items: List[ExtractedItem] = []


class ValidationData(BaseModel):
    is_valid: bool = True
    status: str = "VALIDATED"
    errors: List[str] = []
    error: Optional[List[str]] = None


class Chunk(BaseModel):
    chunk_id: str
    text: str
    page: int


class ChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    page: int
    text: str
    created_at: Optional[datetime] = None


class ProcessingData(BaseModel):
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    stage: Optional[str] = None
    error: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    file_path: str
    file_size: int
    status: DocumentStatus
    ocr_status: Optional[str] = "PENDING"
    extraction_status: Optional[str] = "PENDING"
    chunking_status: Optional[str] = "PENDING"
    chunk_count: Optional[int] = 0
    ocr: OCRData
    extracted_data: ExtractedData
    validation: Optional[ValidationData] = None
    chunks: Optional[List[Chunk]] = None
    processing: ProcessingData


class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_type: str  
    file_size: int
    status: DocumentStatus
    uploaded_at: datetime