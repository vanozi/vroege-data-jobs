"""Add tank terminal transactions.

Revision ID: 20260522_01
Revises: 20260519_04
Create Date: 2026-05-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260522_01"
down_revision: Union[str, Sequence[str], None] = "20260519_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tank_transactions",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transaction_number", sa.String(), nullable=False),
        sa.Column("vehicle", sa.String(), nullable=True),
        sa.Column("driver", sa.String(), nullable=True),
        sa.Column("transaction_type", sa.String(), nullable=True),
        sa.Column("acquisition_mode", sa.String(), nullable=True),
        sa.Column("transaction_status", sa.String(), nullable=True),
        sa.Column("start_date_time", sa.DateTime(), nullable=False),
        sa.Column("product", sa.String(), nullable=True),
        sa.Column("quantity_liters", sa.Float(), nullable=False),
        sa.Column("transaction_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("meter_value", sa.Float(), nullable=True),
        sa.Column("meter_type", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment=(
            "Diesel tank terminal transactions, including machine, driver, "
            "quantity, meter reading, and transaction timestamp."
        ),
    )
    op.create_index(
        op.f("ix_tank_transactions_start_date_time"),
        "tank_transactions",
        ["start_date_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tank_transactions_transaction_number"),
        "tank_transactions",
        ["transaction_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tank_transactions_transaction_number"),
        table_name="tank_transactions",
    )
    op.drop_index(
        op.f("ix_tank_transactions_start_date_time"),
        table_name="tank_transactions",
    )
    op.drop_table("tank_transactions")
