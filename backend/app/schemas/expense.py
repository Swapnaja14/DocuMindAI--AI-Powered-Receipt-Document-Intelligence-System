from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExpenseSummaryRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="Filter receipts on or after this date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Filter receipts on or before this date (YYYY-MM-DD)")
    document_ids: Optional[List[str]] = Field(None, description="Optional list of specific document IDs to filter")
    currency: Optional[str] = Field(None, description="Filter by currency code (e.g. USD, INR, EUR)")
    vendor: Optional[str] = Field(None, description="Filter by vendor name (case-insensitive substring)")
    limit_invoices: int = Field(10, ge=1, le=50, description="Maximum number of highest-value invoices to return")


class CurrencyExpenseTotal(BaseModel):
    currency: str = Field(..., description="Currency code (e.g. USD, INR, EUR)")
    total_amount: float = Field(..., description="Total expenses in this currency")
    total_tax: float = Field(0.0, description="Total tax paid in this currency")
    receipt_count: int = Field(..., description="Number of receipts denominated in this currency")
    average_amount: float = Field(0.0, description="Average spend per receipt in this currency")


class VendorExpenseSummary(BaseModel):
    vendor: str = Field(..., description="Vendor name")
    currency: str = Field(..., description="Currency code")
    total_amount: float = Field(..., description="Total spent with this vendor in this currency")
    receipt_count: int = Field(..., description="Number of receipts from this vendor")
    percentage_of_currency: float = Field(..., description="Percentage of total spend in this currency")
    latest_date: Optional[str] = Field(None, description="Date of the most recent receipt from this vendor")


class ExpenseTrendPoint(BaseModel):
    period: str = Field(..., description="Time period label (e.g. YYYY-MM or YYYY-MM-DD)")
    currency: str = Field(..., description="Currency code")
    total_amount: float = Field(..., description="Total spent in this period")
    receipt_count: int = Field(..., description="Number of receipts in this period")


class HighestValueInvoice(BaseModel):
    document_id: str = Field(..., description="Document identifier")
    filename: str = Field(..., description="Uploaded receipt filename")
    vendor: Optional[str] = Field(None, description="Vendor / Merchant name")
    invoice_number: Optional[str] = Field(None, description="Invoice or receipt number")
    date: Optional[str] = Field(None, description="Invoice or receipt transaction date")
    currency: str = Field("USD", description="Currency code")
    total: float = Field(..., description="Final invoice total amount")
    tax: Optional[float] = Field(None, description="Total tax amount")
    items_count: int = Field(0, description="Number of line items extracted")


class AvailableDocumentItem(BaseModel):
    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Document filename")
    vendor: Optional[str] = Field(None, description="Vendor name")
    date: Optional[str] = Field(None, description="Transaction date")
    currency: Optional[str] = Field(None, description="Currency")
    total: Optional[float] = Field(None, description="Total amount")


class ExpenseSummaryResponse(BaseModel):
    total_expenses: List[CurrencyExpenseTotal] = Field(default_factory=list, description="Aggregated totals partitioned by currency")
    overall_document_count: int = Field(0, description="Total number of receipts matching the filters")
    expenses_by_vendor: List[VendorExpenseSummary] = Field(default_factory=list, description="Expense breakdown by vendor and currency")
    expense_trends: List[ExpenseTrendPoint] = Field(default_factory=list, description="Expense trends over time")
    highest_value_invoices: List[HighestValueInvoice] = Field(default_factory=list, description="Top highest-value invoices")
    available_currencies: List[str] = Field(default_factory=list, description="List of all available currencies in user's documents")
    available_vendors: List[str] = Field(default_factory=list, description="List of all available vendors in user's documents")
    available_documents: List[AvailableDocumentItem] = Field(default_factory=list, description="List of user's documents for filtering")
    applied_filters: Dict[str, Any] = Field(default_factory=dict, description="Echo of filters applied to this summary")
