"""Tests for the Moneybird Alembic migration."""

import importlib

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool
from alembic.migration import MigrationContext
from alembic.operations import Operations

moneybird_migration = importlib.import_module(
    "database.migrations.versions.20260622_01_add_moneybird_tables"
)


def test_moneybird_migration_upgrade_and_downgrade():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        original_op = moneybird_migration.op
        moneybird_migration.op = operations
        try:
            moneybird_migration.upgrade()
            table_names = set(inspect(connection).get_table_names())

            assert "moneybird_administrations" in table_names
            assert "moneybird_sales_invoices" in table_names
            assert "moneybird_collection_runs" in table_names

            moneybird_migration.downgrade()
            table_names = set(inspect(connection).get_table_names())

            assert "moneybird_administrations" not in table_names
            assert "moneybird_sales_invoices" not in table_names
            assert "moneybird_collection_runs" not in table_names
        finally:
            moneybird_migration.op = original_op
