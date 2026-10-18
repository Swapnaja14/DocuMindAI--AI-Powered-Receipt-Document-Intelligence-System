"""
Document definitions for Phase 12 RAG evaluation dataset.
Contains raw text, metadata, and structured fields for the 8 canonical evaluation receipts.
"""

from typing import Any, Dict, List

EVALUATION_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "document_id": "doc_tech_bestbuy",
        "filename": "bestbuy_electronics_receipt.txt",
        "vendor": "BestBuy Electronics",
        "date": "2026-09-15",
        "currency": "INR",
        "subtotal": 7398.00,
        "tax": 1331.64,
        "total": 8729.64,
        "invoice_number": "BB-88219",
        "payment_method": "Visa Credit Card ending in 4412",
        "category": "Electronics & Hardware",
        "items": [
            {"name": "Logitech MX Master Wireless Mouse", "quantity": 1, "price": 6499.00},
            {"name": "USB-C Fast Charging Cable 2m", "quantity": 1, "price": 899.00},
        ],
        "raw_text": (
            "BESTBUY ELECTRONICS INDIA PVT LTD\n"
            "Store #482, Phoenix Marketcity, Pune\n"
            "Invoice / Receipt: BB-88219\n"
            "Date: 2026-09-15 14:23 IST\n"
            "Cashier: Rahul M.\n\n"
            "ITEMS PURCHASED:\n"
            "1. Logitech MX Master Wireless Mouse - Qty: 1 - INR 6499.00\n"
            "2. USB-C Fast Charging Cable 2m - Qty: 1 - INR 899.00\n\n"
            "Subtotal: INR 7398.00\n"
            "CGST (9%): INR 665.82\n"
            "SGST (9%): INR 665.82\n"
            "Total Tax (18%): INR 1331.64\n"
            "Total Amount Paid: INR 8729.64\n"
            "Payment Method: Visa Credit Card ending in 4412\n"
            "Return Policy: 14 days with original receipt."
        ),
    },
    {
        "document_id": "doc_grocery_wholefoods",
        "filename": "wholefoods_market_receipt.txt",
        "vendor": "Whole Foods Market",
        "date": "2026-09-22",
        "currency": "USD",
        "subtotal": 18.46,
        "tax": 1.11,
        "total": 19.57,
        "invoice_number": "WF-10492",
        "payment_method": "Apple Pay (Visa 8810)",
        "category": "Groceries",
        "items": [
            {"name": "Organic Hass Avocados (4ct)", "quantity": 1, "price": 5.99},
            {"name": "Almond Milk Unsweetened 64oz", "quantity": 1, "price": 3.49},
            {"name": "Organic Sourdough Bread", "quantity": 1, "price": 4.99},
            {"name": "Fresh Strawberries 1lb", "quantity": 1, "price": 3.99},
        ],
        "raw_text": (
            "WHOLE FOODS MARKET\n"
            "Downtown Market #102, Seattle WA\n"
            "Receipt: WF-10492\n"
            "Date: 2026-09-22 10:15 AM\n\n"
            "ITEMS:\n"
            "Organic Hass Avocados 4pk - $5.99\n"
            "Almond Milk Unsweetened 64oz - $3.49\n"
            "Organic Sourdough Bread - $4.99\n"
            "Fresh Strawberries 1lb - $3.99\n\n"
            "Subtotal: $18.46\n"
            "Sales Tax (6.0%): $1.11\n"
            "Total Balance Due: $19.57\n"
            "Payment: Apple Pay (Visa 8810)\n"
            "Thank you for shopping organic!"
        ),
    },
    {
        "document_id": "doc_office_staples",
        "filename": "staples_supplies_invoice.txt",
        "vendor": "Staples Office Supplies",
        "date": "2026-09-28",
        "currency": "INR",
        "subtotal": 2199.00,
        "tax": 263.88,
        "total": 2462.88,
        "invoice_number": "STP-5521",
        "payment_method": "Mastercard ending in 9102",
        "category": "Office Supplies",
        "items": [
            {"name": "Multipurpose Copy Paper 500 Sheets (5 Reams)", "quantity": 1, "price": 1450.00},
            {"name": "Gel Pen Set 10-Pack Black", "quantity": 1, "price": 299.00},
            {"name": "Heavy Duty Desk Stapler with 5000 Pins", "quantity": 1, "price": 450.00},
        ],
        "raw_text": (
            "STAPLES OFFICE SUPPLIES CO.\n"
            "Order / Invoice ID: STP-5521\n"
            "Date: 2026-09-28\n"
            "Customer ID: CUST-4910\n\n"
            "LINE ITEMS:\n"
            "- Multipurpose Copy Paper 500 Sheets (5 Reams): INR 1450.00\n"
            "- Gel Pen Set 10-Pack Black: INR 299.00\n"
            "- Heavy Duty Desk Stapler with 5000 Pins: INR 450.00\n\n"
            "Subtotal: INR 2199.00\n"
            "GST (12%): INR 263.88\n"
            "Final Total: INR 2462.88\n"
            "Paid via Mastercard ending in 9102"
        ),
    },
    {
        "document_id": "doc_hardware_homedepot",
        "filename": "home_depot_hardware_receipt.txt",
        "vendor": "The Home Depot",
        "date": "2026-10-04",
        "currency": "USD",
        "subtotal": 143.94,
        "tax": 4.86,
        "total": 148.80,
        "invoice_number": "HD-77310",
        "payment_method": "Cash",
        "category": "Hardware & Tools",
        "items": [
            {"name": "DeWalt 20V Cordless Drill Kit", "quantity": 1, "price": 119.00},
            {"name": "25ft Magnetic Tape Measure", "quantity": 1, "price": 14.97},
            {"name": "Magnetic Screwdriver Set 6-Piece", "quantity": 1, "price": 9.97},
        ],
        "raw_text": (
            "THE HOME DEPOT #0491\n"
            "Store: San Jose, CA\n"
            "Invoice #: HD-77310\n"
            "Date: 2026-10-04 16:42\n\n"
            "ITEMS PURCHASED:\n"
            "02887719 DeWalt 20V Cordless Drill Kit: $119.00\n"
            "08442109 25ft Magnetic Tape Measure: $14.97\n"
            "01994821 Magnetic Screwdriver Set 6-Piece: $9.97\n\n"
            "SUBTOTAL: $143.94\n"
            "SALES TAX: $4.86\n"
            "TOTAL: $148.80\n"
            "CASH TENDERED: $150.00\n"
            "CHANGE RETURNED: $1.20"
        ),
    },
    {
        "document_id": "doc_saas_aws",
        "filename": "aws_cloud_monthly_invoice.txt",
        "vendor": "Amazon Web Services",
        "date": "2026-09-30",
        "currency": "USD",
        "subtotal": 84.50,
        "tax": 0.00,
        "total": 84.50,
        "invoice_number": "AWS-2026-09-881",
        "payment_method": "Corporate Amex ending in 1004",
        "category": "Cloud & Software",
        "items": [
            {"name": "Amazon Elastic Compute Cloud (EC2)", "quantity": 1, "price": 52.00},
            {"name": "Amazon Simple Storage Service (S3)", "quantity": 1, "price": 14.50},
            {"name": "Amazon CloudWatch Alarms & Metrics", "quantity": 1, "price": 8.00},
            {"name": "Amazon Route 53 DNS Queries", "quantity": 1, "price": 10.00},
        ],
        "raw_text": (
            "AMAZON WEB SERVICES, INC.\n"
            "TAX INVOICE\n"
            "Invoice Number: AWS-2026-09-881\n"
            "Billing Period: September 1, 2026 - September 30, 2026\n"
            "Invoice Date: 2026-09-30\n"
            "Account ID: 9482-1049-3321\n\n"
            "SERVICE CHARGES:\n"
            "- Amazon Elastic Compute Cloud (EC2): $52.00\n"
            "- Amazon Simple Storage Service (S3): $14.50\n"
            "- Amazon CloudWatch Alarms & Metrics: $8.00\n"
            "- Amazon Route 53 DNS Queries: $10.00\n\n"
            "Total Charges Before Tax: $84.50\n"
            "Tax (0.0%): $0.00\n"
            "Total Amount Due: $84.50 USD\n"
            "Payment Status: Paid in full via Corporate Amex ending in 1004"
        ),
    },
    {
        "document_id": "doc_saas_github",
        "filename": "github_enterprise_invoice.txt",
        "vendor": "GitHub, Inc.",
        "date": "2026-10-01",
        "currency": "USD",
        "subtotal": 39.00,
        "tax": 0.00,
        "total": 39.00,
        "invoice_number": "GH-99318",
        "payment_method": "Corporate Amex ending in 1004",
        "category": "Cloud & Software",
        "items": [
            {"name": "GitHub Enterprise Team - 2 Seats", "quantity": 2, "price": 20.00},
            {"name": "GitHub Copilot Business - 1 Seat", "quantity": 1, "price": 19.00},
        ],
        "raw_text": (
            "GITHUB, INC.\n"
            "Invoice Number: GH-99318\n"
            "Date of Issue: 2026-10-01\n"
            "Subscription Term: Oct 1, 2026 - Oct 31, 2026\n\n"
            "SUBSCRIPTIONS:\n"
            "- GitHub Enterprise Team (2 user seats @ $10.00/seat): $20.00\n"
            "- GitHub Copilot Business (1 user seat): $19.00\n\n"
            "Subtotal: $39.00\n"
            "Tax: $0.00\n"
            "Total: $39.00 USD\n"
            "Charged to Corporate Amex ending in 1004"
        ),
    },
    {
        "document_id": "doc_hardware_dell",
        "filename": "dell_technologies_invoice.txt",
        "vendor": "Dell Technologies Inc.",
        "date": "2026-10-10",
        "currency": "USD",
        "subtotal": 1450.00,
        "tax": 0.00,
        "total": 1450.00,
        "invoice_number": "DELL-2026-44102",
        "payment_method": "Bank Wire Transfer ref #WT-89420",
        "category": "Electronics & Hardware",
        "items": [
            {"name": "Dell UltraSharp 32 4K USB-C Hub Monitor (U3223QE)", "quantity": 1, "price": 850.00},
            {"name": "Dell Thunderbolt 4 Dock (WD22TB4)", "quantity": 1, "price": 350.00},
            {"name": "Dell 3-Year ProSupport Plus Warranty", "quantity": 1, "price": 250.00},
        ],
        "raw_text": (
            "DELL TECHNOLOGIES INC.\n"
            "COMMERCIAL INVOICE\n"
            "Invoice Number: DELL-2026-44102\n"
            "Date: 2026-10-10\n"
            "Customer: DocuMind AI Engineering\n\n"
            "HARDWARE & SERVICES:\n"
            "1. Dell UltraSharp 32 4K USB-C Hub Monitor (U3223QE) - $850.00\n"
            "2. Dell Thunderbolt 4 Dock (WD22TB4) - $350.00\n"
            "3. Dell 3-Year ProSupport Plus Warranty - $250.00\n\n"
            "Subtotal: $1450.00\n"
            "Tax (Tax Exempt Entity): $0.00\n"
            "Invoice Total: $1450.00 USD\n"
            "Payment Terms: Paid in full via Bank Wire Transfer ref #WT-89420"
        ),
    },
    {
        "document_id": "doc_dining_starbucks",
        "filename": "starbucks_cafe_receipt.txt",
        "vendor": "Starbucks Coffee Company",
        "date": "2026-09-08",
        "currency": "USD",
        "subtotal": 14.25,
        "tax": 0.00,
        "total": 14.25,
        "invoice_number": "SBX-3012",
        "payment_method": "Starbucks Rewards Card",
        "category": "Dining & Coffee",
        "items": [
            {"name": "Caffe Latte Grande", "quantity": 1, "price": 5.25},
            {"name": "Iced Caramel Macchiato Venti", "quantity": 1, "price": 5.75},
            {"name": "Warm Butter Croissant", "quantity": 1, "price": 3.25},
        ],
        "raw_text": (
            "STARBUCKS STORE #1492\n"
            "Order ID: SBX-3012\n"
            "Date: 2026-09-08 08:30 AM\n\n"
            "ORDER DETAILS:\n"
            "1 Caffe Latte Grande: $5.25\n"
            "1 Iced Caramel Macchiato Venti: $5.75\n"
            "1 Warm Butter Croissant: $3.25\n\n"
            "Subtotal: $14.25\n"
            "Tax (Included in price): $0.00\n"
            "Total: $14.25\n"
            "Paid with: Starbucks Rewards Card\n"
            "Have a wonderful morning!"
        ),
    },
]
