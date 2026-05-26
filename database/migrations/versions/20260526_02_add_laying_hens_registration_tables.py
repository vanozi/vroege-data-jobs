"""Add laying hens registration tables.

Revision ID: 20260526_02
Revises: 20260526_01
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260526_02"
down_revision: Union[str, Sequence[str], None] = "20260526_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_laying_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(), nullable=True),
        sa.Column("first_quality_eggs", sa.Integer(), nullable=False),
        sa.Column("second_quality_eggs", sa.Integer(), nullable=False),
        sa.Column("total_eggs", sa.Integer(), nullable=False),
        sa.Column("water_liters", sa.Float(), nullable=True),
        sa.Column("feed_kg", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_daily_laying_registrations_house_date",
        ),
        comment="Daily laying calendar rows for egg counts, feed, water, and notes.",
    )
    op.create_index(
        op.f("ix_daily_laying_registrations_house_id"),
        "daily_laying_registrations",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_laying_registrations_registration_date"),
        "daily_laying_registrations",
        ["registration_date"],
        unique=False,
    )

    op.create_table(
        "dead_hen_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("found_at", sa.DateTime(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("stable_side", sa.String(), nullable=True),
        sa.Column("section_number", sa.Integer(), nullable=True),
        sa.Column("walkway", sa.String(), nullable=True),
        sa.Column("found_place", sa.String(), nullable=True),
        sa.Column("suspected_cause", sa.String(), nullable=True),
        sa.Column("observations", sa.String(), nullable=True),
        sa.Column("registered_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Dead hen observations with stable side, section, and place.",
    )
    op.create_index(
        op.f("ix_dead_hen_registrations_found_at"),
        "dead_hen_registrations",
        ["found_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dead_hen_registrations_house_id"),
        "dead_hen_registrations",
        ["house_id"],
        unique=False,
    )

    op.create_table(
        "outside_nest_egg_rounds",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("round_at", sa.DateTime(), nullable=False),
        sa.Column("egg_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("registered_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Outside-nest egg collection rounds with date/time and count.",
    )
    op.create_index(
        op.f("ix_outside_nest_egg_rounds_house_id"),
        "outside_nest_egg_rounds",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outside_nest_egg_rounds_round_at"),
        "outside_nest_egg_rounds",
        ["round_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_outside_nest_egg_rounds_round_at"),
        table_name="outside_nest_egg_rounds",
    )
    op.drop_index(
        op.f("ix_outside_nest_egg_rounds_house_id"),
        table_name="outside_nest_egg_rounds",
    )
    op.drop_table("outside_nest_egg_rounds")

    op.drop_index(
        op.f("ix_dead_hen_registrations_house_id"),
        table_name="dead_hen_registrations",
    )
    op.drop_index(
        op.f("ix_dead_hen_registrations_found_at"),
        table_name="dead_hen_registrations",
    )
    op.drop_table("dead_hen_registrations")

    op.drop_index(
        op.f("ix_daily_laying_registrations_registration_date"),
        table_name="daily_laying_registrations",
    )
    op.drop_index(
        op.f("ix_daily_laying_registrations_house_id"),
        table_name="daily_laying_registrations",
    )
    op.drop_table("daily_laying_registrations")
