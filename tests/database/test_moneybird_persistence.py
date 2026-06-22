"""Tests for Moneybird persistence helpers."""

from database.persistence import moneybird


class FakeMoneybirdSalesInvoicesRepository:
    def __init__(self):
        self.rows = []

    def upsert_moneybird_sales_invoice(self, row):
        self.rows.append(row)


def test_save_moneybird_sales_invoices_dry_run_without_repository():
    rows = [{"administration_id": "admin-1", "moneybird_id": "invoice-1"}]

    saved_count = moneybird.save_moneybird_sales_invoices(
        rows,
        repository=None,
        dry_run=True,
    )

    assert saved_count == 1


def test_save_moneybird_sales_invoices_upserts_rows():
    repository = FakeMoneybirdSalesInvoicesRepository()
    rows = [
        {"administration_id": "admin-1", "moneybird_id": "invoice-1"},
        {"administration_id": "admin-1", "moneybird_id": "invoice-2"},
    ]

    saved_count = moneybird.save_moneybird_sales_invoices(
        rows,
        repository=repository,
    )

    assert saved_count == 2
    assert repository.rows == rows
