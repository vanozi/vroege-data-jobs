"""Add timestamp columns to klauw_behandelingen.

Revision ID: 20260510_01
Revises: 20260507_01
Create Date: 2026-05-10 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260510_01"
down_revision = "20260507_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = _get_column_names("klauw_behandelingen")
    if "created_at" not in existing_columns:
        op.add_column(
            "klauw_behandelingen",
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if "updated_at" not in existing_columns:
        op.add_column(
            "klauw_behandelingen",
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    op.execute(
        sa.text(
            """
            UPDATE klauw_behandelingen
            SET created_at = COALESCE(created_at, NOW()),
                updated_at = COALESCE(updated_at, NOW())
            """
        )
    )

    op.alter_column("klauw_behandelingen", "created_at", nullable=False)
    op.alter_column("klauw_behandelingen", "updated_at", nullable=False)


def downgrade() -> None:
    existing_columns = _get_column_names("klauw_behandelingen")
    if "updated_at" in existing_columns:
        op.drop_column("klauw_behandelingen", "updated_at")
    if "created_at" in existing_columns:
        op.drop_column("klauw_behandelingen", "created_at")


def _get_column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}
