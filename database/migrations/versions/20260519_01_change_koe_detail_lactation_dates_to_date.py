"""Change koe detail lactation datetime columns to date.

Revision ID: 20260519_01
Revises: 20260512_01
Create Date: 2026-05-19 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260519_01"
down_revision = "20260512_01"
branch_labels = None
depends_on = None

DATE_COLUMNS = [
    "last_calving_date",
    "expected_calving_date",
    "expected_dry_off_date",
    "last_insemination_date",
]


def upgrade() -> None:
    for column_name in DATE_COLUMNS:
        op.alter_column(
            "koe_details",
            column_name,
            existing_type=sa.DateTime(),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using=f"{column_name}::date",
        )


def downgrade() -> None:
    for column_name in DATE_COLUMNS:
        op.alter_column(
            "koe_details",
            column_name,
            existing_type=sa.Date(),
            type_=sa.DateTime(),
            existing_nullable=True,
            postgresql_using=f"{column_name}::timestamp",
        )
