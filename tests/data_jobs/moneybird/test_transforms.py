from datetime import date, datetime
from decimal import Decimal

import pytest

from data_jobs.moneybird import transforms


def test_transform_profit_loss_report_maps_summary_fields():
    synced_at = datetime(2026, 6, 22, 10, 0)

    row = transforms.transform_profit_loss_report(
        {
            "total_revenue": "1000.25",
            "total_expenses": "250.10",
            "gross_profit": "800.15",
            "operating_profit": "760.00",
            "net_profit": "749.90",
        },
        administration_id="admin-1",
        period="this_year",
        synced_at=synced_at,
    )

    assert row["administration_id"] == "admin-1"
    assert row["report_type"] == "profit_loss"
    assert row["period"] == "this_year"
    assert row["total_revenue"] == Decimal("1000.25")
    assert row["net_profit"] == Decimal("749.90")
    assert row["synced_at"] == synced_at


def test_transform_balance_sheet_report_keeps_raw_report():
    report = {"assets": [{"name": "Bank", "amount": "100.00"}]}

    row = transforms.transform_balance_sheet_report(
        report,
        administration_id="admin-1",
        period="this_year",
        synced_at=datetime(2026, 6, 22, 10, 0),
    )

    assert row["report_type"] == "balance_sheet"
    assert row["raw_json"] == report


def test_transform_sales_invoice_maps_contact_amounts_and_dates():
    synced_at = datetime(2026, 6, 22, 10, 0)

    row = transforms.transform_sales_invoice(
        {
            "id": 123456789012345678,
            "invoice_id": "2026-001",
            "contact": {"id": "contact-1", "company_name": "Klant BV"},
            "state": "open",
            "invoice_date": "2026-06-01",
            "due_date": "2026-06-15",
            "paid_at": "",
            "sent_at": "2026-06-02T12:00:00Z",
            "currency": "EUR",
            "total_price_excl_tax": "100.00",
            "total_price_incl_tax": "121.00",
            "total_paid": "0.00",
            "total_unpaid": "121.00",
            "reminder_count": "2",
            "version": "3",
            "updated_at": "2026-06-03T08:30:00+00:00",
        },
        administration_id="admin-1",
        synced_at=synced_at,
    )

    assert row["moneybird_id"] == "123456789012345678"
    assert row["contact_id"] == "contact-1"
    assert row["contact_name"] == "Klant BV"
    assert row["invoice_date"] == date(2026, 6, 1)
    assert row["paid_at"] is None
    assert row["total_unpaid"] == Decimal("121.00")
    assert row["reminder_count"] == 2
    assert row["moneybird_version"] == 3


def test_transform_purchase_invoice_maps_base_amounts():
    row = transforms.transform_purchase_invoice(
        {
            "id": "purchase-1",
            "contact_id": "supplier-1",
            "contact_name": "Leverancier",
            "reference": "INK-001",
            "entry_number": 42,
            "state": "open",
            "date": "2026-06-10",
            "due_date": "2026-07-10",
            "paid_at": None,
            "currency": "EUR",
            "total_price_excl_tax": "200.00",
            "total_price_incl_tax": "242.00",
            "total_price_excl_tax_base": "200.00",
            "total_price_incl_tax_base": "242.00",
            "version": 5,
        },
        administration_id="admin-1",
        synced_at=datetime(2026, 6, 22, 10, 0),
    )

    assert row["moneybird_id"] == "purchase-1"
    assert row["entry_number"] == 42
    assert row["total_price_incl_tax_base"] == Decimal("242.00")


def test_transform_sales_invoice_requires_id():
    with pytest.raises(ValueError, match="sales invoice id"):
        transforms.transform_sales_invoice(
            {},
            administration_id="admin-1",
            synced_at=datetime(2026, 6, 22, 10, 0),
        )
