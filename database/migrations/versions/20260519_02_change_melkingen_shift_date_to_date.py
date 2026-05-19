"""Change melkingen shift_date datetime column to date.

Revision ID: 20260519_02
Revises: 20260519_01
Create Date: 2026-05-19 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260519_02"
down_revision = "20260519_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "melkingen",
        "shift_date",
        existing_type=sa.DateTime(),
        type_=sa.Date(),
        existing_nullable=False,
        postgresql_using="shift_date::date",
    )


def downgrade() -> None:
    op.alter_column(
        "melkingen",
        "shift_date",
        existing_type=sa.Date(),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="shift_date::timestamp",
    )
