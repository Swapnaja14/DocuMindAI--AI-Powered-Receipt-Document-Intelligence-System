from typing import List, Optional
from pydantic import BaseModel, Field


class RAGAskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="User question to answer using RAG",
        json_schema_extra={"example": "Which receipt had the highest total among my laptop purchases?"},
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of top relevant chunks to retrieve for grounding",
    )


class RAGSource(BaseModel):
    document_id: str = Field(..., description="Document ID containing the chunk")
    filename: str = Field(..., description="Original filename of the document")
    page: Optional[int] = Field(None, description="Page number where the chunk appears")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    snippet: str = Field(..., description="Excerpt or snippet text used for grounding")


class RetrievalMetadata(BaseModel):
    top_k: int = Field(..., description="Requested top_k retrieval parameter")
    sources_used: int = Field(..., description="Number of source chunks utilized in generation")


class RAGAskResponse(BaseModel):
    answer: str = Field(..., description="LLM-generated answer grounded in retrieved documents")
    sources: List[RAGSource] = Field(default_factory=list, description="Citations and source chunks used")
    retrieval: RetrievalMetadata = Field(..., description="Retrieval statistics and metadata")
