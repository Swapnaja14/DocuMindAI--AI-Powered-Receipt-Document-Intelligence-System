import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId

from app.schemas.expense import (
    AvailableDocumentItem,
    CurrencyExpenseTotal,
    ExpenseSummaryRequest,
    ExpenseSummaryResponse,
    ExpenseTrendPoint,
    HighestValueInvoice,
    VendorExpenseSummary,
)


def parse_receipt_date(
    date_str: Optional[Any],
    fallback_datetime: Optional[Any] = None,
) -> Optional[str]:
    """
    Normalizes a receipt date string into 'YYYY-MM-DD' format.
    Falls back to fallback_datetime if date_str is missing or unparseable.
    """
    if date_str and isinstance(date_str, str):
        cleaned = date_str.strip()

        # Check ISO format YYYY-MM-DD directly
        iso_match = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", cleaned)
        if iso_match:
            year, month, day = iso_match.groups()
            try:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except ValueError:
                pass

        # Check common formats: MM/DD/YYYY, DD/MM/YYYY, Month DD YYYY
        common_formats = [
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%m-%d-%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in common_formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Fallback to created_at or uploaded_at if available
    if fallback_datetime:
        if isinstance(fallback_datetime, datetime):
            return fallback_datetime.strftime("%Y-%m-%d")
        elif isinstance(fallback_datetime, str):
            try:
                # Truncate at T or space if present
                clean_fb = fallback_datetime.split("T")[0].split(" ")[0]
                if re.match(r"^\d{4}-\d{2}-\d{2}$", clean_fb):
                    return clean_fb
            except Exception:
                pass

    return None


class ExpenseService:
    """
    Business logic and aggregation service for multi-tenant expense summaries.
    Ensures strict tenant isolation, currency partitioning, and structured calculation.
    """

    def __init__(self, db):
        self.collection = db["documents"]

    def compute_summary(
        self,
        user_id: Union[str, ObjectId],
        params: Optional[ExpenseSummaryRequest] = None,
    ) -> ExpenseSummaryResponse:
        """
        Computes structured expense analytics strictly scoped to user_id.
        """
        params = params or ExpenseSummaryRequest()

        # 1. Multi-tenant database query: fetch user's documents
        user_conditions: List[Dict[str, Any]] = [{"user_id": str(user_id)}]
        if ObjectId.is_valid(str(user_id)):
            user_conditions.append({"user_id": ObjectId(str(user_id))})

        all_user_docs = list(self.collection.find({"$or": user_conditions}))

        # 2. Extract portfolio-wide options for filtering UI
        available_currencies_set = set()
        available_vendors_set = set()
        available_documents_list: List[AvailableDocumentItem] = []

        # Normalized candidate records
        parsed_records: List[Dict[str, Any]] = []

        for doc in all_user_docs:
            ext = doc.get("extracted_data") or {}
            raw_total = ext.get("total")

            # Extract currency
            raw_curr = (ext.get("currency") or "USD").strip().upper()
            if not raw_curr or len(raw_curr) > 6:
                raw_curr = "USD"

            # Normalize vendor
            raw_vendor = (
                ext.get("vendor")
                or doc.get("filename")
                or "Unknown Merchant"
            ).strip()

            # Normalize date
            fallback_dt = (
                doc.get("created_at")
                or doc.get("processing", {}).get("uploaded_at")
            )
            norm_date = parse_receipt_date(ext.get("date"), fallback_dt)

            doc_id_str = str(doc["_id"])
            filename = str(doc.get("filename") or "receipt.pdf")

            # Numeric total validation
            total_val: Optional[float] = None
            if raw_total is not None:
                try:
                    total_val = round(float(raw_total), 2)
                except (ValueError, TypeError):
                    total_val = None

            # Collect available filter values if it has extracted information
            if total_val is not None:
                available_currencies_set.add(raw_curr)
                if ext.get("vendor") and ext.get("vendor").strip():
                    available_vendors_set.add(ext.get("vendor").strip())

            available_documents_list.append(
                AvailableDocumentItem(
                    id=doc_id_str,
                    filename=filename,
                    vendor=ext.get("vendor"),
                    date=norm_date,
                    currency=raw_curr if total_val is not None else None,
                    total=total_val,
                )
            )

            # We only aggregate records that have a valid numeric total
            if total_val is not None and total_val >= 0:
                raw_tax = ext.get("tax")
                tax_val = 0.0
                if raw_tax is not None:
                    try:
                        tax_val = round(float(raw_tax), 2)
                    except (ValueError, TypeError):
                        tax_val = 0.0

                items = ext.get("items") or []

                parsed_records.append({
                    "document_id": doc_id_str,
                    "filename": filename,
                    "vendor": raw_vendor,
                    "invoice_number": ext.get("invoice_number"),
                    "date": norm_date,
                    "currency": raw_curr,
                    "total": total_val,
                    "tax": tax_val,
                    "items_count": len(items),
                })

        # 3. Apply active query filters
        filtered_records = parsed_records

        # Filter by document_ids
        if params.document_ids and len(params.document_ids) > 0:
            doc_id_filter = set(str(d).strip() for d in params.document_ids if str(d).strip())
            if doc_id_filter:
                filtered_records = [
                    r for r in filtered_records if r["document_id"] in doc_id_filter
                ]

        # Filter by currency
        if params.currency and params.currency.strip():
            target_curr = params.currency.strip().upper()
            filtered_records = [
                r for r in filtered_records if r["currency"] == target_curr
            ]

        # Filter by vendor substring
        if params.vendor and params.vendor.strip():
            v_query = params.vendor.strip().lower()
            filtered_records = [
                r for r in filtered_records
                if v_query in r["vendor"].lower() or v_query in r["filename"].lower()
            ]

        # Filter by date range (YYYY-MM-DD)
        if params.start_date and params.start_date.strip():
            s_date = params.start_date.strip()
            filtered_records = [
                r for r in filtered_records
                if r["date"] and r["date"] >= s_date
            ]

        if params.end_date and params.end_date.strip():
            e_date = params.end_date.strip()
            filtered_records = [
                r for r in filtered_records
                if r["date"] and r["date"] <= e_date
            ]

        # 4. Compute Totals partitioned by Currency (preventing naive multi-currency summation)
        currency_totals: Dict[str, Dict[str, Any]] = {}
        for r in filtered_records:
            curr = r["currency"]
            if curr not in currency_totals:
                currency_totals[curr] = {
                    "total_amount": 0.0,
                    "total_tax": 0.0,
                    "count": 0,
                }
            currency_totals[curr]["total_amount"] += r["total"]
            currency_totals[curr]["total_tax"] += r["tax"]
            currency_totals[curr]["count"] += 1

        total_expenses_list: List[CurrencyExpenseTotal] = []
        for curr, data in sorted(currency_totals.items()):
            tot = round(data["total_amount"], 2)
            cnt = data["count"]
            avg = round(tot / cnt, 2) if cnt > 0 else 0.0
            tax_tot = round(data["total_tax"], 2)
            total_expenses_list.append(
                CurrencyExpenseTotal(
                    currency=curr,
                    total_amount=tot,
                    total_tax=tax_tot,
                    receipt_count=cnt,
                    average_amount=avg,
                )
            )

        # 5. Compute Expenses by Vendor (partitioned by currency for accuracy)
        vendor_curr_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for r in filtered_records:
            key = (r["vendor"], r["currency"])
            if key not in vendor_curr_map:
                vendor_curr_map[key] = {
                    "total": 0.0,
                    "count": 0,
                    "latest_date": r["date"],
                }
            vendor_curr_map[key]["total"] += r["total"]
            vendor_curr_map[key]["count"] += 1
            # Track newest date
            if r["date"] and (
                not vendor_curr_map[key]["latest_date"]
                or r["date"] > vendor_curr_map[key]["latest_date"]
            ):
                vendor_curr_map[key]["latest_date"] = r["date"]

        expenses_by_vendor_list: List[VendorExpenseSummary] = []
        for (v_name, curr), v_data in vendor_curr_map.items():
            curr_total = currency_totals.get(curr, {}).get("total_amount", 0.0)
            percentage = (
                round((v_data["total"] / curr_total) * 100, 1)
                if curr_total > 0
                else 0.0
            )
            expenses_by_vendor_list.append(
                VendorExpenseSummary(
                    vendor=v_name,
                    currency=curr,
                    total_amount=round(v_data["total"], 2),
                    receipt_count=v_data["count"],
                    percentage_of_currency=percentage,
                    latest_date=v_data["latest_date"],
                )
            )

        # Sort vendors descending by total spend
        expenses_by_vendor_list.sort(key=lambda v: v.total_amount, reverse=True)

        # 6. Compute Expense Trends over time (monthly aggregation YYYY-MM)
        trend_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for r in filtered_records:
            # Group by year-month YYYY-MM
            period = r["date"][:7] if r["date"] and len(r["date"]) >= 7 else "Undated"
            t_key = (period, r["currency"])
            if t_key not in trend_map:
                trend_map[t_key] = {"total": 0.0, "count": 0}
            trend_map[t_key]["total"] += r["total"]
            trend_map[t_key]["count"] += 1

        expense_trends_list: List[ExpenseTrendPoint] = [
            ExpenseTrendPoint(
                period=period,
                currency=curr,
                total_amount=round(data["total"], 2),
                receipt_count=data["count"],
            )
            for (period, curr), data in trend_map.items()
        ]
        # Sort chronologically by period
        expense_trends_list.sort(key=lambda t: t.period)

        # 7. Highest-Value Invoices
        sorted_invoices = sorted(filtered_records, key=lambda r: r["total"], reverse=True)
        top_invoices = sorted_invoices[: params.limit_invoices]

        highest_value_invoices_list: List[HighestValueInvoice] = [
            HighestValueInvoice(
                document_id=inv["document_id"],
                filename=inv["filename"],
                vendor=inv["vendor"],
                invoice_number=inv["invoice_number"],
                date=inv["date"],
                currency=inv["currency"],
                total=inv["total"],
                tax=inv["tax"],
                items_count=inv["items_count"],
            )
            for inv in top_invoices
        ]

        applied_filters_dict = {
            "start_date": params.start_date,
            "end_date": params.end_date,
            "document_ids": params.document_ids,
            "currency": params.currency,
            "vendor": params.vendor,
            "limit_invoices": params.limit_invoices,
        }

        return ExpenseSummaryResponse(
            total_expenses=total_expenses_list,
            overall_document_count=len(filtered_records),
            expenses_by_vendor=expenses_by_vendor_list,
            expense_trends=expense_trends_list,
            highest_value_invoices=highest_value_invoices_list,
            available_currencies=sorted(list(available_currencies_set)),
            available_vendors=sorted(list(available_vendors_set)),
            available_documents=available_documents_list,
            applied_filters=applied_filters_dict,
        )
