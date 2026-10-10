from typing import List, Optional, Union
from pydantic import BaseModel, Field


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
