"""Add timestamp columns to klauw_behandelingen.

Revision ID: 20260510_01
Revises: 20260507_01
Create Date: 2026-05-10 00:00:00
"""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260510_01"
down_revision = "20260507_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "klauw_behandelingen",
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
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
    op.drop_column("klauw_behandelingen", "updated_at")
    op.drop_column("klauw_behandelingen", "created_at")
