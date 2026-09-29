from typing import Optional, List
from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    description: str = Field(
        description="Description / name of the purchased item"
    )
    quantity: Optional[float] = Field(
        default=None,
        description="Quantity purchased"
    )
    unit_price: Optional[float] = Field(
        default=None,
        description="Price per unit"
    )
    amount: Optional[float] = Field(
        default=None,
        description="Total amount for this line item"
    )


class ExtractedInvoice(BaseModel):
    vendor: Optional[str] = Field(
        default=None,
        description="Vendor or merchant name"
    )
    invoice_number: Optional[str] = Field(
        default=None,
        description="Invoice, receipt, or bill number"
    )
    date: Optional[str] = Field(
        default=None,
        description="Invoice or receipt date as written in the document"
    )
    currency: Optional[str] = Field(
        default=None,
        description="Currency code such as INR, USD, EUR"
    )
    subtotal: Optional[float] = Field(
        default=None,
        description="Subtotal before tax"
    )
    tax: Optional[float] = Field(
        default=None,
        description="Total tax amount"
    )
    total: Optional[float] = Field(
        default=None,
        description="Final total amount"
    )
    items: List[ExtractedItem] = Field(
        default_factory=list,
        description="Purchased items appearing on the document"
    )