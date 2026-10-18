from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationCategory(str, Enum):
    DIRECT_LOOKUP = "direct_lookup"
    NUMERIC_LOOKUP = "numeric_lookup"
    EXPENSE_RANKING = "expense_ranking"
    AGGREGATION = "aggregation"
    DATE_FILTERING = "date_filtering"
    MULTI_DOCUMENT = "multi_document"
    MISSING_INFORMATION = "missing_information"
    AMBIGUOUS_QUESTION = "ambiguous_question"


class EvaluationItem(BaseModel):
    id: str = Field(..., description="Unique question identifier, e.g., DEV_DL_01")
    category: EvaluationCategory = Field(..., description="Target RAG evaluation category")
    question: str = Field(..., description="Natural language question")
    expected_answer: str = Field(..., description="Canonical expected answer description")
    supporting_document_ids: List[str] = Field(
        default_factory=list,
        description="IDs of documents containing the necessary evidence",
    )
    evidence_snippets: List[str] = Field(
        default_factory=list,
        description="Text fragments that must be retrieved as evidence",
    )
    key_entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key entities (numbers, currency, vendors, dates) expected in the answer",
    )
    should_abstain: bool = Field(
        default=False,
        description="Whether the system should abstain due to missing or unsupported evidence",
    )
    evaluation_criteria: str = Field(
        ...,
        description="Specific verification rules (e.g. requires exact match, currency symbol, date boundaries)",
    )


class EvaluationBenchmark(BaseModel):
    name: str = Field(..., description="Benchmark dataset name (e.g. dev_set or holdout_set)")
    version: str = Field("1.0.0", description="Dataset schema version")
    description: str = Field(..., description="Overview of dataset scope and purpose")
    items: List[EvaluationItem] = Field(default_factory=list)
