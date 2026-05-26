"""Convert laying hens feed and water units.

Revision ID: 20260526_04
Revises: 20260526_03
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260526_04"
down_revision: Union[str, Sequence[str], None] = "20260526_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "daily_laying_registrations",
        sa.Column("water_ml", sa.Integer(), nullable=True),
    )
    op.add_column(
        "daily_laying_registrations",
        sa.Column("feed_grams", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE daily_laying_registrations
        SET water_ml = ROUND(water_liters * 1000)::integer
        WHERE water_liters IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE daily_laying_registrations
        SET feed_grams = ROUND(feed_kg * 1000)::integer
        WHERE feed_kg IS NOT NULL
        """
    )
    op.drop_column("daily_laying_registrations", "water_liters")
    op.drop_column("daily_laying_registrations", "feed_kg")


def downgrade() -> None:
    op.add_column(
        "daily_laying_registrations",
        sa.Column("water_liters", sa.Float(), nullable=True),
    )
    op.add_column(
        "daily_laying_registrations",
        sa.Column("feed_kg", sa.Float(), nullable=True),
    )
    op.execute(
        """
        UPDATE daily_laying_registrations
        SET water_liters = water_ml::float / 1000
        WHERE water_ml IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE daily_laying_registrations
        SET feed_kg = feed_grams::float / 1000
        WHERE feed_grams IS NOT NULL
        """
    )
    op.drop_column("daily_laying_registrations", "water_ml")
    op.drop_column("daily_laying_registrations", "feed_grams")
