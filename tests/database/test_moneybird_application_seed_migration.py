"""Tests for the Moneybird application seed migration."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

moneybird_application_migration = importlib.import_module(
    "database.migrations.versions.20260625_01_seed_moneybird_application"
)


def test_moneybird_application_seed_upgrade_is_idempotent_and_downgrades():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    metadata = sa.MetaData()
    applications = sa.Table(
        "applications",
        metadata,
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
    )
    user_application_access = sa.Table(
        "user_application_access",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
    )
    user_application_roles = sa.Table(
        "user_application_roles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_application_access_id", sa.Integer(), nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        original_op = moneybird_application_migration.op
        moneybird_application_migration.op = operations
        try:
            moneybird_application_migration.upgrade()
            moneybird_application_migration.upgrade()

            rows = (
                connection.execute(
                    sa.select(applications).where(
                        applications.c.key == "dashboard_moneybird"
                    )
                )
                .mappings()
                .all()
            )

            assert len(rows) == 1
            assert rows[0]["name"] == "Moneybird"
            assert rows[0]["url"] == "/moneybird"
            assert rows[0]["category"] == "dashboard"
            assert rows[0]["is_active"] is True
            assert rows[0]["display_order"] == 35

            connection.execute(
                user_application_access.insert().values(
                    id=1,
                    application_id=rows[0]["id"],
                )
            )
            connection.execute(
                user_application_roles.insert().values(
                    id=1,
                    user_application_access_id=1,
                )
            )

            moneybird_application_migration.downgrade()

            remaining = connection.execute(
                sa.select(sa.func.count()).select_from(applications)
            ).scalar_one()
            remaining_access = connection.execute(
                sa.select(sa.func.count()).select_from(user_application_access)
            ).scalar_one()
            remaining_roles = connection.execute(
                sa.select(sa.func.count()).select_from(user_application_roles)
            ).scalar_one()

            assert remaining == 0
            assert remaining_access == 0
            assert remaining_roles == 0
        finally:
            moneybird_application_migration.op = original_op
