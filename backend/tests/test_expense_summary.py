import mongomock
import pytest
from bson import ObjectId
from unittest.mock import patch
from fastapi.testclient import TestClient

mongomock.mongo_client._get_server_version = lambda: "6.0.0"
patch("app.main.create_indexes", lambda: None).start()
patch("app.core.database.create_indexes", lambda: None).start()

from app.api.routes.expenses import get_expense_service
from app.api.routes.users import get_current_user
from app.main import app
from app.services.expense_service import ExpenseService, parse_receipt_date


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    client._server_version = "6.0.0"
    return client["test_expense_db"]


@pytest.fixture
def seed_test_data(mock_db):
    user_a = str(ObjectId("65c000000000000000000111"))
    user_b = str(ObjectId("65c000000000000000000222"))

    docs = [
        # User A - USD Documents
        {
            "_id": ObjectId("65c111111111111111111001"),
            "user_id": user_a,
            "filename": "dell_laptop_inv.pdf",
            "status": "COMPLETED",
            "extracted_data": {
                "vendor": "Dell Technologies",
                "invoice_number": "INV-DELL-901",
                "date": "2024-01-15",
                "currency": "USD",
                "total": 1450.00,
                "tax": 116.00,
                "items": [{"description": "XPS 15", "amount": 1450.00}],
            },
            "created_at": "2024-01-15T10:00:00Z",
        },
        {
            "_id": ObjectId("65c111111111111111111002"),
            "user_id": user_a,
            "filename": "wholefoods_receipt.pdf",
            "status": "COMPLETED",
            "extracted_data": {
                "vendor": "Whole Foods Market",
                "invoice_number": "WF-3312",
                "date": "2024-01-20",
                "currency": "USD",
                "total": 150.00,
                "tax": 12.00,
                "items": [{"description": "Groceries", "amount": 150.00}],
            },
            "created_at": "2024-01-20T14:30:00Z",
        },
        {
            "_id": ObjectId("65c111111111111111111003"),
            "user_id": user_a,
            "filename": "wholefoods_receipt_feb.pdf",
            "status": "COMPLETED",
            "extracted_data": {
                "vendor": "Whole Foods Market",
                "invoice_number": "WF-3450",
                "date": "2024-02-10",
                "currency": "USD",
                "total": 100.00,
                "tax": 8.00,
                "items": [{"description": "Organic Produce", "amount": 100.00}],
            },
            "created_at": "2024-02-10T11:00:00Z",
        },
        # User A - INR Documents
        {
            "_id": ObjectId("65c111111111111111111004"),
            "user_id": user_a,
            "filename": "bestbuy_mumbai.pdf",
            "status": "COMPLETED",
            "extracted_data": {
                "vendor": "BestBuy Electronics",
                "invoice_number": "BB-IN-88",
                "date": "2024-02-14",
                "currency": "INR",
                "total": 8500.00,
                "tax": 1530.00,
                "items": [{"description": "Monitor", "amount": 8500.00}],
            },
            "created_at": "2024-02-14T12:00:00Z",
        },
        # User B - Strictly separate tenant
        {
            "_id": ObjectId("65c222222222222222222001"),
            "user_id": user_b,
            "filename": "user_b_private_invoice.pdf",
            "status": "COMPLETED",
            "extracted_data": {
                "vendor": "Private Corp",
                "invoice_number": "PRIV-001",
                "date": "2024-02-01",
                "currency": "USD",
                "total": 99999.00,
                "tax": 5000.00,
                "items": [{"description": "Confidential", "amount": 99999.00}],
            },
            "created_at": "2024-02-01T10:00:00Z",
        },
    ]

    mock_db["documents"].insert_many(docs)
    return {
        "user_a": user_a,
        "user_b": user_b,
        "db": mock_db,
    }


def test_date_parser_helper():
    assert parse_receipt_date("2024-05-12") == "2024-05-12"
    assert parse_receipt_date("05/12/2024") == "2024-05-12"
    assert parse_receipt_date("12/05/2024") == "2024-05-12" or parse_receipt_date("12/05/2024") == "2024-12-05"
    assert parse_receipt_date("January 15, 2024") == "2024-01-15"
    assert parse_receipt_date("invalid-date", fallback_datetime="2024-03-01T12:00:00Z") == "2024-03-01"
    assert parse_receipt_date(None) is None


def test_expense_service_multi_currency_totals(seed_test_data):
    env = seed_test_data
    svc = ExpenseService(env["db"])
    summary = svc.compute_summary(user_id=env["user_a"])

    # Must contain exactly 2 currencies: USD and INR
    assert len(summary.total_expenses) == 2
    currencies = {t.currency: t for t in summary.total_expenses}
    assert "USD" in currencies
    assert "INR" in currencies

    # USD Totals: 1450 + 150 + 100 = 1700.00
    usd = currencies["USD"]
    assert usd.total_amount == 1700.00
    assert usd.receipt_count == 3
    assert usd.total_tax == 136.00  # 116 + 12 + 8
    assert usd.average_amount == round(1700.00 / 3, 2)

    # INR Totals: 8500.00
    inr = currencies["INR"]
    assert inr.total_amount == 8500.00
    assert inr.receipt_count == 1
    assert inr.total_tax == 1530.00

    # User B's 99999.00 expense must NEVER appear for User A
    assert all(t.total_amount < 90000.00 for t in summary.total_expenses)
    assert summary.overall_document_count == 4


def test_expense_service_vendor_breakdown(seed_test_data):
    env = seed_test_data
    svc = ExpenseService(env["db"])
    summary = svc.compute_summary(user_id=env["user_a"])

    vendors = {f"{v.vendor}_{v.currency}": v for v in summary.expenses_by_vendor}

    # Dell Technologies USD: 1450.00 (85.3% of USD)
    assert "Dell Technologies_USD" in vendors
    dell = vendors["Dell Technologies_USD"]
    assert dell.total_amount == 1450.00
    assert dell.receipt_count == 1
    assert dell.percentage_of_currency == round((1450.00 / 1700.00) * 100, 1)

    # Whole Foods Market USD: 250.00 across 2 receipts (150 + 100)
    assert "Whole Foods Market_USD" in vendors
    wf = vendors["Whole Foods Market_USD"]
    assert wf.total_amount == 250.00
    assert wf.receipt_count == 2
    assert wf.latest_date == "2024-02-10"


def test_expense_service_trends_and_highest_invoices(seed_test_data):
    env = seed_test_data
    svc = ExpenseService(env["db"])
    summary = svc.compute_summary(user_id=env["user_a"])

    # Trends: 2024-01 USD (1600.00), 2024-02 USD (100.00), 2024-02 INR (8500.00)
    periods = {(t.period, t.currency): t.total_amount for t in summary.expense_trends}
    assert periods[("2024-01", "USD")] == 1600.00  # 1450 + 150
    assert periods[("2024-02", "USD")] == 100.00
    assert periods[("2024-02", "INR")] == 8500.00

    # Highest value invoices: Top 1 in INR is 8500, top 1 in USD is 1450
    assert len(summary.highest_value_invoices) == 4
    top1 = summary.highest_value_invoices[0]
    assert top1.total == 8500.00
    assert top1.currency == "INR"
    assert top1.vendor == "BestBuy Electronics"

    top2 = summary.highest_value_invoices[1]
    assert top2.total == 1450.00
    assert top2.currency == "USD"
    assert top2.vendor == "Dell Technologies"


def test_expense_service_date_and_document_filters(seed_test_data):
    env = seed_test_data
    svc = ExpenseService(env["db"])

    from app.schemas.expense import ExpenseSummaryRequest

    # Filter by date range: Only January 2024
    jan_filter = ExpenseSummaryRequest(start_date="2024-01-01", end_date="2024-01-31")
    jan_summary = svc.compute_summary(user_id=env["user_a"], params=jan_filter)
    assert jan_summary.overall_document_count == 2
    assert len(jan_summary.total_expenses) == 1
    assert jan_summary.total_expenses[0].currency == "USD"
    assert jan_summary.total_expenses[0].total_amount == 1600.00

    # Filter by specific document ID
    doc_id = "65c111111111111111111001"
    doc_filter = ExpenseSummaryRequest(document_ids=[doc_id])
    doc_summary = svc.compute_summary(user_id=env["user_a"], params=doc_filter)
    assert doc_summary.overall_document_count == 1
    assert doc_summary.highest_value_invoices[0].document_id == doc_id
    assert doc_summary.highest_value_invoices[0].vendor == "Dell Technologies"

    # Filter by vendor
    v_filter = ExpenseSummaryRequest(vendor="Whole Foods")
    v_summary = svc.compute_summary(user_id=env["user_a"], params=v_filter)
    assert v_summary.overall_document_count == 2
    assert v_summary.total_expenses[0].total_amount == 250.00


def test_api_endpoint_expense_summary(seed_test_data):
    env = seed_test_data
    user_a = env["user_a"]
    svc = ExpenseService(env["db"])

    app.dependency_overrides[get_current_user] = lambda: {"_id": ObjectId(user_a), "id": user_a}
    app.dependency_overrides[get_expense_service] = lambda: svc

    client = TestClient(app)
    try:
        # Test GET
        res_get = client.get("/api/v1/expenses/summary?currency=USD")
        assert res_get.status_code == 200
        data_get = res_get.json()
        assert len(data_get["total_expenses"]) == 1
        assert data_get["total_expenses"][0]["currency"] == "USD"
        assert data_get["total_expenses"][0]["total_amount"] == 1700.00
        assert data_get["overall_document_count"] == 3
        assert len(data_get["available_currencies"]) == 2  # USD and INR available
        assert "Dell Technologies" in data_get["available_vendors"]

        # Test POST
        res_post = client.post(
            "/api/v1/expenses/summary",
            json={"vendor": "Dell", "limit_invoices": 5},
        )
        assert res_post.status_code == 200
        data_post = res_post.json()
        assert data_post["overall_document_count"] == 1
        assert data_post["highest_value_invoices"][0]["vendor"] == "Dell Technologies"
    finally:
        app.dependency_overrides.clear()


def test_empty_user_expenses(mock_db):
    empty_user = str(ObjectId("65c333333333333333333001"))
    svc = ExpenseService(mock_db)
    summary = svc.compute_summary(user_id=empty_user)
    assert summary.overall_document_count == 0
    assert summary.total_expenses == []
    assert summary.expenses_by_vendor == []
    assert summary.expense_trends == []
    assert summary.highest_value_invoices == []
    assert summary.available_currencies == []
    assert summary.available_vendors == []
    assert summary.available_documents == []
