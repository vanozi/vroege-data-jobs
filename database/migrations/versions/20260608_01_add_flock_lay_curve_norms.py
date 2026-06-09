"""Add flock_lay_curve_norms table.

Revision ID: 20260608_01
Revises: 20260528_02
Create Date: 2026-06-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260608_01"
down_revision: Union[str, None] = "20260528_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flock_lay_curve_norms",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("breed_key", sa.String(), nullable=False),
        sa.Column("breed_name", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("age_weeks", sa.Integer(), nullable=False),
        sa.Column("lay_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("egg_weight_grams", sa.Numeric(5, 2), nullable=False),
        sa.Column("egg_mass_grams", sa.Numeric(5, 2), nullable=False),
        sa.Column("feed_intake_grams_per_day", sa.Numeric(6, 2), nullable=False),
        sa.Column("feed_conversion_ratio", sa.Numeric(5, 3), nullable=False),
        sa.Column("liveability_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("hen_weight_grams", sa.Integer(), nullable=True),
        sa.Column("cumulative_eggs_per_placed_hen", sa.Numeric(7, 1), nullable=False),
        sa.Column("cumulative_egg_kg_per_placed_hen", sa.Numeric(7, 2), nullable=False),
        sa.Column(
            "cumulative_feed_kg_per_placed_hen", sa.Numeric(7, 2), nullable=False
        ),
        sa.Column("cumulative_feed_conversion_ratio", sa.Numeric(5, 3), nullable=False),
        sa.CheckConstraint(
            "age_weeks BETWEEN 18 AND 100",
            name="ck_flock_lay_curve_norms_age_weeks_range",
        ),
        sa.UniqueConstraint(
            "breed_key",
            "age_weeks",
            name="uq_flock_lay_curve_norms_breed_week",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment=(
            "Manufacturer breed norm curve per age week. "
            "breed_key example: dekalb_white_scharrel_voliere."
        ),
    )
    op.create_index(
        "ix_flock_lay_curve_norms_breed_key_week",
        "flock_lay_curve_norms",
        ["breed_key", "age_weeks"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flock_lay_curve_norms_breed_key"),
        "flock_lay_curve_norms",
        ["breed_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_flock_lay_curve_norms_breed_key"),
        table_name="flock_lay_curve_norms",
    )
    op.drop_index(
        "ix_flock_lay_curve_norms_breed_key_week",
        table_name="flock_lay_curve_norms",
    )
    op.drop_table("flock_lay_curve_norms")
