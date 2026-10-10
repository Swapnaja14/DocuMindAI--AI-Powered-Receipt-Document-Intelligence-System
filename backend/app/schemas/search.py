from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    STRUCTURED = "structured"
    SEMANTIC = "semantic"
    RAG = "rag"


# ============================================================================
# Mode A — Structured Filtering Schemas
# ============================================================================

class FilterSearchRequest(BaseModel):
    vendor: Optional[str] = Field(None, description="Filter by vendor name (case-insensitive substring)")
    min_total: Optional[float] = Field(None, ge=0, description="Minimum receipt total")
    max_total: Optional[float] = Field(None, ge=0, description="Maximum receipt total")
    currency: Optional[str] = Field(None, description="Filter by currency code (e.g. INR, USD, EUR)")
    start_date: Optional[str] = Field(None, description="Filter receipts after or on this date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Filter receipts before or on this date (YYYY-MM-DD)")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of receipts to return")


class StructuredReceiptItem(BaseModel):
    document_id: str
    filename: str
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = None
    total: Optional[float] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    items_count: int = 0
    created_at: Optional[str] = None


class FilterSearchResponse(BaseModel):
    mode: str = "structured"
    total_matches: int
    receipts: List[StructuredReceiptItem]


# ============================================================================
# Mode B — Semantic Search Schemas
# ============================================================================

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query string")
    top_k: int = Field(5, ge=1, le=50, description="Number of top similar chunks to return")
    document_id: Optional[str] = Field(None, description="Optional document ID to scope the search")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum similarity score threshold")


class SemanticSearchResultItem(BaseModel):
    document_id: str
    chunk_id: str
    filename: str
    score: float
    text: str
    page: Optional[int] = None


class SemanticSearchResponse(BaseModel):
    mode: str = "semantic"
    query: str
    total_results: int
    results: List[SemanticSearchResultItem]


# ============================================================================
# Legacy / Backward Compatible Schemas
# ============================================================================

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    top_k: int = Field(5, ge=1, le=50, description="Number of top similar chunks to return")
    document_id: Optional[str] = Field(None, description="Optional document ID to scope the search")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Optional minimum similarity score threshold")


class SearchResultItem(BaseModel):
    document_id: str
    chunk_id: Union[str, int]
    score: float
    text: str
    page_number: Optional[int] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
