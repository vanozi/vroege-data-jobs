"""Moneybird bookkeeping models."""

from datetime import date as Date
from datetime import datetime as DateTime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from database.models.base import CreatedTimestampMixin


MoneyAmount = Optional[Decimal]
RawJson = Optional[dict[str, object]]


def money_column(nullable: bool = True) -> Column:
    """Return a standard Moneybird money column."""
    return Column(Numeric(14, 2), nullable=nullable)


class MoneybirdAdministration(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird administration metadata."""

    __tablename__ = "moneybird_administrations"
    __table_args__ = (
        UniqueConstraint(
            "moneybird_id",
            name="uq_moneybird_administrations_moneybird_id",
        ),
        {"comment": "Moneybird administrations available to the API token."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    moneybird_id: str = Field(index=True)
    name: str = Field(index=True)
    language: Optional[str] = Field(default=None)
    currency: Optional[str] = Field(default=None, index=True)
    country: Optional[str] = Field(default=None)
    time_zone: Optional[str] = Field(default=None)
    access: Optional[str] = Field(default=None)
    suspended: Optional[bool] = Field(default=None)
    period_locked_until: Optional[Date] = Field(default=None)
    period_start_date: Optional[Date] = Field(default=None)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdContact(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird contact, customer, supplier, or other relation."""

    __tablename__ = "moneybird_contacts"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_contacts_administration_moneybird_id",
        ),
        {"comment": "Moneybird contacts used as invoice relation dimensions."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    moneybird_id: str = Field(index=True)
    company_name: Optional[str] = Field(default=None, index=True)
    firstname: Optional[str] = Field(default=None)
    lastname: Optional[str] = Field(default=None)
    customer_id: Optional[str] = Field(default=None, index=True)
    supplier_id: Optional[str] = Field(default=None, index=True)
    email: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    archived: Optional[bool] = Field(default=None, index=True)
    moneybird_version: Optional[int] = Field(default=None)
    moneybird_updated_at: Optional[DateTime] = Field(default=None)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdLedgerAccount(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird ledger account metadata."""

    __tablename__ = "moneybird_ledger_accounts"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_ledger_accounts_administration_moneybird_id",
        ),
        {"comment": "Moneybird ledger accounts for report lookups."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    moneybird_id: str = Field(index=True)
    name: str = Field(index=True)
    account_type: Optional[str] = Field(default=None, index=True)
    account_id: Optional[str] = Field(default=None, index=True)
    moneybird_version: Optional[int] = Field(default=None)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdSalesInvoice(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird sales invoice for receivables and revenue views."""

    __tablename__ = "moneybird_sales_invoices"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_sales_invoices_administration_moneybird_id",
        ),
        {"comment": "Moneybird sales invoices collected for dashboard reporting."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    moneybird_id: str = Field(index=True)
    invoice_id: Optional[str] = Field(default=None, index=True)
    contact_id: Optional[str] = Field(default=None, index=True)
    contact_name: Optional[str] = Field(default=None, index=True)
    state: Optional[str] = Field(default=None, index=True)
    invoice_date: Optional[Date] = Field(default=None, index=True)
    due_date: Optional[Date] = Field(default=None, index=True)
    paid_at: Optional[Date] = Field(default=None, index=True)
    sent_at: Optional[DateTime] = Field(default=None)
    currency: Optional[str] = Field(default=None)
    total_price_excl_tax: MoneyAmount = Field(
        default=None,
        sa_column=money_column(),
    )
    total_price_incl_tax: MoneyAmount = Field(
        default=None,
        sa_column=money_column(),
    )
    total_paid: MoneyAmount = Field(default=None, sa_column=money_column())
    total_unpaid: MoneyAmount = Field(default=None, sa_column=money_column())
    marked_dubious_on: Optional[Date] = Field(default=None)
    marked_uncollectible_on: Optional[Date] = Field(default=None)
    reminder_count: Optional[int] = Field(default=None)
    next_reminder: Optional[Date] = Field(default=None)
    moneybird_version: Optional[int] = Field(default=None)
    moneybird_updated_at: Optional[DateTime] = Field(default=None)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdPurchaseInvoice(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird purchase invoice for payables and expense views."""

    __tablename__ = "moneybird_purchase_invoices"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_purchase_invoices_administration_moneybird_id",
        ),
        {"comment": "Moneybird purchase invoices collected for dashboard reporting."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    moneybird_id: str = Field(index=True)
    contact_id: Optional[str] = Field(default=None, index=True)
    contact_name: Optional[str] = Field(default=None, index=True)
    reference: Optional[str] = Field(default=None, index=True)
    entry_number: Optional[int] = Field(default=None, index=True)
    state: Optional[str] = Field(default=None, index=True)
    date: Optional[Date] = Field(default=None, index=True)
    due_date: Optional[Date] = Field(default=None, index=True)
    paid_at: Optional[Date] = Field(default=None, index=True)
    currency: Optional[str] = Field(default=None)
    total_price_excl_tax: MoneyAmount = Field(
        default=None,
        sa_column=money_column(),
    )
    total_price_incl_tax: MoneyAmount = Field(
        default=None,
        sa_column=money_column(),
    )
    total_price_excl_tax_base: MoneyAmount = Field(
        default=None,
        sa_column=money_column(),
    )
    total_price_incl_tax_base: MoneyAmount = Field(
        default=None,
        sa_column=money_column(),
    )
    moneybird_version: Optional[int] = Field(default=None)
    moneybird_updated_at: Optional[DateTime] = Field(default=None)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdFinancialAccount(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird financial account such as bank account or credit card."""

    __tablename__ = "moneybird_financial_accounts"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_financial_accounts_administration_moneybird_id",
        ),
        {"comment": "Moneybird financial accounts for bank and payment views."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    moneybird_id: str = Field(index=True)
    type: Optional[str] = Field(default=None, index=True)
    name: str = Field(index=True)
    identifier: Optional[str] = Field(default=None, index=True)
    currency: Optional[str] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    active: Optional[bool] = Field(default=None, index=True)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdFinancialMutation(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird financial mutation, usually a bank transaction."""

    __tablename__ = "moneybird_financial_mutations"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_financial_mutations_administration_moneybird_id",
        ),
        {"comment": "Moneybird financial mutations for bank transaction reporting."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    moneybird_id: str = Field(index=True)
    financial_account_id: Optional[str] = Field(default=None, index=True)
    amount: MoneyAmount = Field(default=None, sa_column=money_column())
    amount_open: MoneyAmount = Field(default=None, sa_column=money_column())
    date: Optional[Date] = Field(default=None, index=True)
    message: Optional[str] = Field(default=None)
    code: Optional[str] = Field(default=None, index=True)
    contra_account_name: Optional[str] = Field(default=None)
    contra_account_number: Optional[str] = Field(default=None, index=True)
    state: Optional[str] = Field(default=None, index=True)
    settlement_state: Optional[str] = Field(default=None, index=True)
    moneybird_version: Optional[int] = Field(default=None)
    moneybird_updated_at: Optional[DateTime] = Field(default=None)
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdReportSnapshot(CreatedTimestampMixin, SQLModel, table=True):
    """Moneybird report snapshot for profit/loss and balance sheet data."""

    __tablename__ = "moneybird_report_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "administration_id",
            "report_type",
            "period",
            name="uq_moneybird_report_snapshots_administration_report_period",
        ),
        {"comment": "Moneybird report snapshots with normalized summary fields."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: str = Field(index=True)
    report_type: str = Field(index=True)
    period: str = Field(index=True)
    total_revenue: MoneyAmount = Field(default=None, sa_column=money_column())
    total_expenses: MoneyAmount = Field(default=None, sa_column=money_column())
    gross_profit: MoneyAmount = Field(default=None, sa_column=money_column())
    operating_profit: MoneyAmount = Field(default=None, sa_column=money_column())
    net_profit: MoneyAmount = Field(default=None, sa_column=money_column())
    raw_json: RawJson = Field(default=None, sa_column=Column(JSON, nullable=True))
    synced_at: Optional[DateTime] = Field(default=None, index=True)


class MoneybirdCollectionRun(CreatedTimestampMixin, SQLModel, table=True):
    """Audit log for Moneybird collection runs."""

    __tablename__ = "moneybird_collection_runs"
    __table_args__ = {"comment": "Moneybird datajob collection run audit records."}

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_id: Optional[str] = Field(default=None, index=True)
    period: Optional[str] = Field(default=None, index=True)
    started_at: DateTime = Field(index=True)
    finished_at: Optional[DateTime] = Field(default=None, index=True)
    status: str = Field(index=True)
    administrations_count: int = Field(default=0)
    contacts_count: int = Field(default=0)
    ledger_accounts_count: int = Field(default=0)
    sales_invoices_count: int = Field(default=0)
    purchase_invoices_count: int = Field(default=0)
    financial_accounts_count: int = Field(default=0)
    financial_mutations_count: int = Field(default=0)
    report_snapshots_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
