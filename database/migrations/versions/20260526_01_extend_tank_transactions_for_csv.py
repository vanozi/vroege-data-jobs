"""Extend tank transactions for selected CSV export fields.

Revision ID: 20260526_01
Revises: 20260522_01
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260526_01"
down_revision: Union[str, Sequence[str], None] = "20260522_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CSV_COLUMNS = [
    ("dispenser", sa.String()),
    ("tank", sa.String()),
    ("vehicle_number", sa.String()),
    ("driver_number", sa.String()),
    ("transaction_result", sa.String()),
    ("transaction_date", sa.Date()),
    ("transaction_hour", sa.String()),
    ("quantity_units", sa.String()),
    ("odometer", sa.Float()),
    ("hours_counter", sa.Float()),
    ("vehicle_identifier", sa.String()),
    ("driver_identifier", sa.String()),
]


def upgrade() -> None:
    for column_name, column_type in CSV_COLUMNS:
        op.add_column(
            "tank_transactions",
            sa.Column(column_name, column_type, nullable=True),
        )


def downgrade() -> None:
    for column_name, _column_type in reversed(CSV_COLUMNS):
        op.drop_column("tank_transactions", column_name)
