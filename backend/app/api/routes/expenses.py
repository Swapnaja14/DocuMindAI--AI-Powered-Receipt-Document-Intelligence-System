import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.routes.users import get_current_user
from app.core.database import db
from app.schemas.expense import (
    ExpenseSummaryRequest,
    ExpenseSummaryResponse,
)
from app.services.expense_service import ExpenseService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Expenses"])


def get_expense_service() -> ExpenseService:
    return ExpenseService(db)


@router.get("/expenses/summary", response_model=ExpenseSummaryResponse)
def get_expense_summary(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    document_ids: Optional[str] = Query(
        None, description="Comma-separated list of document IDs to scope the summary"
    ),
    currency: Optional[str] = Query(None, description="Currency filter (e.g. USD, INR)"),
    vendor: Optional[str] = Query(None, description="Vendor filter (case-insensitive substring)"),
    limit_invoices: int = Query(10, ge=1, le=50, description="Max highest-value invoices"),
    current_user=Depends(get_current_user),
    expense_service: ExpenseService = Depends(get_expense_service),
):
    """
    Retrieve structured financial expense summaries strictly scoped to the authenticated user.
    Aggregates:
    - Total expenses partitioned safely by currency (no naive mixed summation)
    - Expenses grouped by vendor
    - Expense trends over time (period grouping)
    - Highest-value invoices ranking
    - Full list of available documents, vendors, and currencies for dynamic UI filters
    """
    user_id = str(current_user.id if hasattr(current_user, "id") else current_user["_id"])

    # Parse comma-separated document_ids if provided
    doc_id_list: Optional[List[str]] = None
    if document_ids and document_ids.strip():
        doc_id_list = [d.strip() for d in document_ids.split(",") if d.strip()]

    params = ExpenseSummaryRequest(
        start_date=start_date,
        end_date=end_date,
        document_ids=doc_id_list,
        currency=currency,
        vendor=vendor,
        limit_invoices=limit_invoices,
    )

    try:
        summary = expense_service.compute_summary(user_id=user_id, params=params)
        return summary
    except Exception as exc:
        logger.error("Failed to compute expense summary for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate expense summary: {str(exc)}",
        )


@router.post("/expenses/summary", response_model=ExpenseSummaryResponse)
def post_expense_summary(
    request: ExpenseSummaryRequest,
    current_user=Depends(get_current_user),
    expense_service: ExpenseService = Depends(get_expense_service),
):
    """
    POST variant for structured expense summary querying with a rich JSON filter payload.
    """
    user_id = str(current_user.id if hasattr(current_user, "id") else current_user["_id"])

    try:
        summary = expense_service.compute_summary(user_id=user_id, params=request)
        return summary
    except Exception as exc:
        logger.error("Failed to compute expense summary for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate expense summary: {str(exc)}",
        )
