"""Add Moneybird tables.

Revision ID: 20260622_01
Revises: 20260615_01
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_01"
down_revision: Union[str, Sequence[str], None] = "20260615_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "moneybird_administrations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("time_zone", sa.String(), nullable=True),
        sa.Column("access", sa.String(), nullable=True),
        sa.Column("suspended", sa.Boolean(), nullable=True),
        sa.Column("period_locked_until", sa.Date(), nullable=True),
        sa.Column("period_start_date", sa.Date(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "moneybird_id",
            name="uq_moneybird_administrations_moneybird_id",
        ),
        comment="Moneybird administrations available to the API token.",
    )
    _index("moneybird_administrations", "moneybird_id")
    _index("moneybird_administrations", "name")
    _index("moneybird_administrations", "currency")
    _index("moneybird_administrations", "synced_at")

    op.create_table(
        "moneybird_contacts",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("firstname", sa.String(), nullable=True),
        sa.Column("lastname", sa.String(), nullable=True),
        sa.Column("customer_id", sa.String(), nullable=True),
        sa.Column("supplier_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=True),
        sa.Column("moneybird_version", sa.Integer(), nullable=True),
        sa.Column("moneybird_updated_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_contacts_administration_moneybird_id",
        ),
        comment="Moneybird contacts used as invoice relation dimensions.",
    )
    _entity_indexes(
        "moneybird_contacts",
        ["company_name", "customer_id", "supplier_id", "archived", "synced_at"],
    )

    op.create_table(
        "moneybird_ledger_accounts",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=True),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column("moneybird_version", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_ledger_accounts_administration_moneybird_id",
        ),
        comment="Moneybird ledger accounts for report lookups.",
    )
    _entity_indexes(
        "moneybird_ledger_accounts",
        ["name", "account_type", "account_id", "synced_at"],
    )

    op.create_table(
        "moneybird_sales_invoices",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column("contact_id", sa.String(), nullable=True),
        sa.Column("contact_name", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("total_price_excl_tax", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_price_incl_tax", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_paid", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_unpaid", sa.Numeric(14, 2), nullable=True),
        sa.Column("marked_dubious_on", sa.Date(), nullable=True),
        sa.Column("marked_uncollectible_on", sa.Date(), nullable=True),
        sa.Column("reminder_count", sa.Integer(), nullable=True),
        sa.Column("next_reminder", sa.Date(), nullable=True),
        sa.Column("moneybird_version", sa.Integer(), nullable=True),
        sa.Column("moneybird_updated_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_sales_invoices_administration_moneybird_id",
        ),
        comment="Moneybird sales invoices collected for dashboard reporting.",
    )
    _entity_indexes(
        "moneybird_sales_invoices",
        [
            "invoice_id",
            "contact_id",
            "contact_name",
            "state",
            "invoice_date",
            "due_date",
            "paid_at",
            "synced_at",
        ],
    )

    op.create_table(
        "moneybird_purchase_invoices",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=True),
        sa.Column("contact_name", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("entry_number", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("total_price_excl_tax", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_price_incl_tax", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_price_excl_tax_base", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_price_incl_tax_base", sa.Numeric(14, 2), nullable=True),
        sa.Column("moneybird_version", sa.Integer(), nullable=True),
        sa.Column("moneybird_updated_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_purchase_invoices_administration_moneybird_id",
        ),
        comment="Moneybird purchase invoices collected for dashboard reporting.",
    )
    _entity_indexes(
        "moneybird_purchase_invoices",
        [
            "contact_id",
            "contact_name",
            "reference",
            "entry_number",
            "state",
            "date",
            "due_date",
            "paid_at",
            "synced_at",
        ],
    )

    op.create_table(
        "moneybird_financial_accounts",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_financial_accounts_administration_moneybird_id",
        ),
        comment="Moneybird financial accounts for bank and payment views.",
    )
    _entity_indexes(
        "moneybird_financial_accounts",
        ["type", "name", "identifier", "active", "synced_at"],
    )

    op.create_table(
        "moneybird_financial_mutations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("moneybird_id", sa.String(), nullable=False),
        sa.Column("financial_account_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("amount_open", sa.Numeric(14, 2), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("contra_account_name", sa.String(), nullable=True),
        sa.Column("contra_account_number", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("settlement_state", sa.String(), nullable=True),
        sa.Column("moneybird_version", sa.Integer(), nullable=True),
        sa.Column("moneybird_updated_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "moneybird_id",
            name="uq_moneybird_financial_mutations_administration_moneybird_id",
        ),
        comment="Moneybird financial mutations for bank transaction reporting.",
    )
    _entity_indexes(
        "moneybird_financial_mutations",
        [
            "financial_account_id",
            "date",
            "code",
            "contra_account_number",
            "state",
            "settlement_state",
            "synced_at",
        ],
    )

    op.create_table(
        "moneybird_report_snapshots",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=False),
        sa.Column("report_type", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("total_revenue", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_expenses", sa.Numeric(14, 2), nullable=True),
        sa.Column("gross_profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("operating_profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("net_profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "administration_id",
            "report_type",
            "period",
            name="uq_moneybird_report_snapshots_administration_report_period",
        ),
        comment="Moneybird report snapshots with normalized summary fields.",
    )
    _index("moneybird_report_snapshots", "administration_id")
    _index("moneybird_report_snapshots", "report_type")
    _index("moneybird_report_snapshots", "period")
    _index("moneybird_report_snapshots", "synced_at")

    op.create_table(
        "moneybird_collection_runs",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("administration_id", sa.String(), nullable=True),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("administrations_count", sa.Integer(), nullable=False),
        sa.Column("contacts_count", sa.Integer(), nullable=False),
        sa.Column("ledger_accounts_count", sa.Integer(), nullable=False),
        sa.Column("sales_invoices_count", sa.Integer(), nullable=False),
        sa.Column("purchase_invoices_count", sa.Integer(), nullable=False),
        sa.Column("financial_accounts_count", sa.Integer(), nullable=False),
        sa.Column("financial_mutations_count", sa.Integer(), nullable=False),
        sa.Column("report_snapshots_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Moneybird datajob collection run audit records.",
    )
    _index("moneybird_collection_runs", "administration_id")
    _index("moneybird_collection_runs", "period")
    _index("moneybird_collection_runs", "started_at")
    _index("moneybird_collection_runs", "finished_at")
    _index("moneybird_collection_runs", "status")


def downgrade() -> None:
    for table_name, column_names in reversed(INDEXED_TABLES):
        for column_name in reversed(column_names):
            op.drop_index(op.f(f"ix_{table_name}_{column_name}"), table_name=table_name)

    op.drop_table("moneybird_collection_runs")
    op.drop_table("moneybird_report_snapshots")
    op.drop_table("moneybird_financial_mutations")
    op.drop_table("moneybird_financial_accounts")
    op.drop_table("moneybird_purchase_invoices")
    op.drop_table("moneybird_sales_invoices")
    op.drop_table("moneybird_ledger_accounts")
    op.drop_table("moneybird_contacts")
    op.drop_table("moneybird_administrations")


def _index(table_name: str, column_name: str) -> None:
    op.create_index(
        op.f(f"ix_{table_name}_{column_name}"),
        table_name,
        [column_name],
        unique=False,
    )


def _entity_indexes(table_name: str, column_names: list[str]) -> None:
    _index(table_name, "administration_id")
    _index(table_name, "moneybird_id")
    for column_name in column_names:
        _index(table_name, column_name)


INDEXED_TABLES = [
    (
        "moneybird_administrations",
        ["moneybird_id", "name", "currency", "synced_at"],
    ),
    (
        "moneybird_contacts",
        [
            "administration_id",
            "moneybird_id",
            "company_name",
            "customer_id",
            "supplier_id",
            "archived",
            "synced_at",
        ],
    ),
    (
        "moneybird_ledger_accounts",
        [
            "administration_id",
            "moneybird_id",
            "name",
            "account_type",
            "account_id",
            "synced_at",
        ],
    ),
    (
        "moneybird_sales_invoices",
        [
            "administration_id",
            "moneybird_id",
            "invoice_id",
            "contact_id",
            "contact_name",
            "state",
            "invoice_date",
            "due_date",
            "paid_at",
            "synced_at",
        ],
    ),
    (
        "moneybird_purchase_invoices",
        [
            "administration_id",
            "moneybird_id",
            "contact_id",
            "contact_name",
            "reference",
            "entry_number",
            "state",
            "date",
            "due_date",
            "paid_at",
            "synced_at",
        ],
    ),
    (
        "moneybird_financial_accounts",
        [
            "administration_id",
            "moneybird_id",
            "type",
            "name",
            "identifier",
            "active",
            "synced_at",
        ],
    ),
    (
        "moneybird_financial_mutations",
        [
            "administration_id",
            "moneybird_id",
            "financial_account_id",
            "date",
            "code",
            "contra_account_number",
            "state",
            "settlement_state",
            "synced_at",
        ],
    ),
    (
        "moneybird_report_snapshots",
        ["administration_id", "report_type", "period", "synced_at"],
    ),
    (
        "moneybird_collection_runs",
        ["administration_id", "period", "started_at", "finished_at", "status"],
    ),
]
