"""Add laying hen flocks.

Revision ID: 20260526_03
Revises: 20260526_02
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260526_03"
down_revision: Union[str, Sequence[str], None] = "20260526_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flocks",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flock_name", sa.String(), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("placement_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("bird_count", sa.Integer(), nullable=False),
        sa.Column("breed", sa.String(), nullable=True),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Laying hen flocks with lifecycle metadata and active date range.",
    )
    op.create_index(op.f("ix_flocks_archived_at"), "flocks", ["archived_at"])
    op.create_index(op.f("ix_flocks_date_of_birth"), "flocks", ["date_of_birth"])
    op.create_index(op.f("ix_flocks_end_date"), "flocks", ["end_date"])
    op.create_index(op.f("ix_flocks_flock_name"), "flocks", ["flock_name"])
    op.create_index(
        "ix_flocks_house_active_dates",
        "flocks",
        ["house_id", "placement_date", "end_date"],
    )
    op.create_index(op.f("ix_flocks_house_id"), "flocks", ["house_id"])
    op.create_index(op.f("ix_flocks_is_active"), "flocks", ["is_active"])
    op.create_index(op.f("ix_flocks_placement_date"), "flocks", ["placement_date"])

    op.add_column(
        "daily_laying_registrations",
        sa.Column("flock_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_daily_laying_registrations_flock_id_flocks",
        "daily_laying_registrations",
        "flocks",
        ["flock_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_daily_laying_registrations_flock_id"),
        "daily_laying_registrations",
        ["flock_id"],
    )

    op.add_column(
        "dead_hen_registrations",
        sa.Column("flock_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dead_hen_registrations_flock_id_flocks",
        "dead_hen_registrations",
        "flocks",
        ["flock_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_dead_hen_registrations_flock_id"),
        "dead_hen_registrations",
        ["flock_id"],
    )

    op.add_column(
        "outside_nest_egg_rounds",
        sa.Column("flock_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_outside_nest_egg_rounds_flock_id_flocks",
        "outside_nest_egg_rounds",
        "flocks",
        ["flock_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_outside_nest_egg_rounds_flock_id"),
        "outside_nest_egg_rounds",
        ["flock_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_outside_nest_egg_rounds_flock_id"),
        table_name="outside_nest_egg_rounds",
    )
    op.drop_constraint(
        "fk_outside_nest_egg_rounds_flock_id_flocks",
        "outside_nest_egg_rounds",
        type_="foreignkey",
    )
    op.drop_column("outside_nest_egg_rounds", "flock_id")

    op.drop_index(
        op.f("ix_dead_hen_registrations_flock_id"),
        table_name="dead_hen_registrations",
    )
    op.drop_constraint(
        "fk_dead_hen_registrations_flock_id_flocks",
        "dead_hen_registrations",
        type_="foreignkey",
    )
    op.drop_column("dead_hen_registrations", "flock_id")

    op.drop_index(
        op.f("ix_daily_laying_registrations_flock_id"),
        table_name="daily_laying_registrations",
    )
    op.drop_constraint(
        "fk_daily_laying_registrations_flock_id_flocks",
        "daily_laying_registrations",
        type_="foreignkey",
    )
    op.drop_column("daily_laying_registrations", "flock_id")

    op.drop_index(op.f("ix_flocks_placement_date"), table_name="flocks")
    op.drop_index(op.f("ix_flocks_is_active"), table_name="flocks")
    op.drop_index(op.f("ix_flocks_house_id"), table_name="flocks")
    op.drop_index("ix_flocks_house_active_dates", table_name="flocks")
    op.drop_index(op.f("ix_flocks_flock_name"), table_name="flocks")
    op.drop_index(op.f("ix_flocks_end_date"), table_name="flocks")
    op.drop_index(op.f("ix_flocks_date_of_birth"), table_name="flocks")
    op.drop_index(op.f("ix_flocks_archived_at"), table_name="flocks")
    op.drop_table("flocks")
