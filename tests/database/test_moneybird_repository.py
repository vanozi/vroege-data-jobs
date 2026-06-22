"""Tests for Moneybird repositories."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database.models.moneybird import MoneybirdSalesInvoice
from database.models.moneybird import MoneybirdReportSnapshot
from database.repositories.moneybird_repository import (
    MoneybirdReportSnapshotsRepository,
    MoneybirdSalesInvoicesRepository,
)


def test_sales_invoice_upsert_updates_existing_row():
    engine = _create_engine()
    repository = MoneybirdSalesInvoicesRepository(_session_factory(engine))

    repository.upsert_moneybird_sales_invoice(
        {
            "administration_id": "admin-1",
            "moneybird_id": "invoice-1",
            "invoice_id": "2026-001",
            "contact_name": "Klant 1",
            "state": "open",
            "invoice_date": date(2026, 6, 1),
            "total_unpaid": Decimal("121.00"),
            "raw_json": {"id": "invoice-1", "state": "open"},
            "synced_at": datetime(2026, 6, 22, 10, 0),
        }
    )
    repository.upsert_moneybird_sales_invoice(
        {
            "administration_id": "admin-1",
            "moneybird_id": "invoice-1",
            "invoice_id": "2026-001",
            "contact_name": "Klant 1",
            "state": "paid",
            "invoice_date": date(2026, 6, 1),
            "total_unpaid": Decimal("0.00"),
            "raw_json": {"id": "invoice-1", "state": "paid"},
            "synced_at": datetime(2026, 6, 22, 11, 0),
        }
    )

    with Session(engine) as session:
        rows = session.exec(select(MoneybirdSalesInvoice)).all()

    assert len(rows) == 1
    assert rows[0].state == "paid"
    assert rows[0].total_unpaid == Decimal("0.00")
    assert rows[0].raw_json == {"id": "invoice-1", "state": "paid"}


def test_report_snapshot_upsert_uses_report_type_and_period():
    engine = _create_engine()
    repository = MoneybirdReportSnapshotsRepository(_session_factory(engine))

    repository.upsert_moneybird_report_snapshot(
        {
            "administration_id": "admin-1",
            "report_type": "profit_loss",
            "period": "this_year",
            "net_profit": Decimal("100.00"),
            "raw_json": {"net_profit": "100.00"},
        }
    )
    repository.upsert_moneybird_report_snapshot(
        {
            "administration_id": "admin-1",
            "report_type": "profit_loss",
            "period": "this_year",
            "net_profit": Decimal("125.50"),
            "raw_json": {"net_profit": "125.50"},
        }
    )

    with Session(engine) as session:
        rows = session.exec(select(MoneybirdReportSnapshot)).all()

    assert len(rows) == 1
    assert rows[0].net_profit == Decimal("125.50")


def _create_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _session_factory(engine):
    def factory():
        return Session(engine)

    return factory
