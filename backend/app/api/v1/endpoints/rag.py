"""
V1 endpoint router for RAG Question-Answering.
Re-exports from app.api.routes.rag.
"""

from app.api.routes.rag import (
    router,
    get_rag_retriever,
    get_rag_answer_service,
    ask_question,
)

__all__ = [
    "router",
    "get_rag_retriever",
    "get_rag_answer_service",
    "ask_question",
]
