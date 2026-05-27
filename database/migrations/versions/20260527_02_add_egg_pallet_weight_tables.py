"""Add egg pallet weight tables.

Revision ID: 20260527_02
Revises: 20260527_01
Create Date: 2026-05-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_02"
down_revision: Union[str, None] = "20260527_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "egg_packaging_weight_configs",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_name", sa.String(), nullable=False),
        sa.Column(
            "empty_packaging_weight_kg",
            sa.Numeric(10, 3),
            nullable=False,
        ),
        sa.Column(
            "egg_count_per_pallet",
            sa.Integer(),
            server_default="10800",
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.CheckConstraint(
            "empty_packaging_weight_kg >= 0",
            name="ck_egg_packaging_weight_configs_empty_weight_non_negative",
        ),
        sa.CheckConstraint(
            "egg_count_per_pallet > 0",
            name="ck_egg_packaging_weight_configs_egg_count_positive",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_egg_packaging_weight_configs_valid_dates",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Supplier empty packaging weights and eggs-per-pallet settings.",
    )
    op.create_index(
        op.f("ix_egg_packaging_weight_configs_archived_at"),
        "egg_packaging_weight_configs",
        ["archived_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_packaging_weight_configs_end_date"),
        "egg_packaging_weight_configs",
        ["end_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_packaging_weight_configs_is_active"),
        "egg_packaging_weight_configs",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_packaging_weight_configs_start_date"),
        "egg_packaging_weight_configs",
        ["start_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_packaging_weight_configs_supplier_name"),
        "egg_packaging_weight_configs",
        ["supplier_name"],
        unique=False,
    )
    op.create_index(
        "ix_egg_packaging_weight_configs_supplier_dates",
        "egg_packaging_weight_configs",
        ["supplier_name", "start_date", "end_date", "is_active"],
        unique=False,
    )

    op.create_table(
        "egg_pallet_weight_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("flock_id", sa.Integer(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(), nullable=True),
        sa.Column("packaging_weight_config_id", sa.Integer(), nullable=False),
        sa.Column("supplier_name", sa.String(), nullable=False),
        sa.Column("pallet_weight_kg", sa.Numeric(10, 3), nullable=False),
        sa.Column("empty_packaging_weight_kg", sa.Numeric(10, 3), nullable=False),
        sa.Column(
            "egg_count_per_pallet",
            sa.Integer(),
            server_default="10800",
            nullable=False,
        ),
        sa.Column("egg_weight_grams", sa.Numeric(10, 4), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["flock_id"],
            ["flocks.id"],
        ),
        sa.ForeignKeyConstraint(
            ["packaging_weight_config_id"],
            ["egg_packaging_weight_configs.id"],
        ),
        sa.CheckConstraint(
            "pallet_weight_kg >= 0",
            name="ck_egg_pallet_weight_registrations_pallet_weight_non_negative",
        ),
        sa.CheckConstraint(
            "empty_packaging_weight_kg >= 0",
            name="ck_egg_pallet_weight_registrations_empty_weight_non_negative",
        ),
        sa.CheckConstraint(
            "pallet_weight_kg >= empty_packaging_weight_kg",
            name="ck_egg_pallet_weight_registrations_pallet_above_empty",
        ),
        sa.CheckConstraint(
            "egg_count_per_pallet > 0",
            name="ck_egg_pallet_weight_registrations_egg_count_positive",
        ),
        sa.CheckConstraint(
            "egg_weight_grams >= 0",
            name="ck_egg_pallet_weight_registrations_egg_weight_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment=(
            "Pallet weight rows with copied packaging config values and calculated "
            "average egg weight in grams."
        ),
    )
    op.create_index(
        op.f("ix_egg_pallet_weight_registrations_flock_id"),
        "egg_pallet_weight_registrations",
        ["flock_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_pallet_weight_registrations_house_id"),
        "egg_pallet_weight_registrations",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        "ix_egg_pallet_weight_registrations_house_date",
        "egg_pallet_weight_registrations",
        ["house_id", "registration_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_pallet_weight_registrations_packaging_weight_config_id"),
        "egg_pallet_weight_registrations",
        ["packaging_weight_config_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_pallet_weight_registrations_registration_date"),
        "egg_pallet_weight_registrations",
        ["registration_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_egg_pallet_weight_registrations_supplier_name"),
        "egg_pallet_weight_registrations",
        ["supplier_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_egg_pallet_weight_registrations_supplier_name"),
        table_name="egg_pallet_weight_registrations",
    )
    op.drop_index(
        op.f("ix_egg_pallet_weight_registrations_registration_date"),
        table_name="egg_pallet_weight_registrations",
    )
    op.drop_index(
        op.f("ix_egg_pallet_weight_registrations_packaging_weight_config_id"),
        table_name="egg_pallet_weight_registrations",
    )
    op.drop_index(
        "ix_egg_pallet_weight_registrations_house_date",
        table_name="egg_pallet_weight_registrations",
    )
    op.drop_index(
        op.f("ix_egg_pallet_weight_registrations_house_id"),
        table_name="egg_pallet_weight_registrations",
    )
    op.drop_index(
        op.f("ix_egg_pallet_weight_registrations_flock_id"),
        table_name="egg_pallet_weight_registrations",
    )
    op.drop_table("egg_pallet_weight_registrations")

    op.drop_index(
        "ix_egg_packaging_weight_configs_supplier_dates",
        table_name="egg_packaging_weight_configs",
    )
    op.drop_index(
        op.f("ix_egg_packaging_weight_configs_supplier_name"),
        table_name="egg_packaging_weight_configs",
    )
    op.drop_index(
        op.f("ix_egg_packaging_weight_configs_start_date"),
        table_name="egg_packaging_weight_configs",
    )
    op.drop_index(
        op.f("ix_egg_packaging_weight_configs_is_active"),
        table_name="egg_packaging_weight_configs",
    )
    op.drop_index(
        op.f("ix_egg_packaging_weight_configs_end_date"),
        table_name="egg_packaging_weight_configs",
    )
    op.drop_index(
        op.f("ix_egg_packaging_weight_configs_archived_at"),
        table_name="egg_packaging_weight_configs",
    )
    op.drop_table("egg_packaging_weight_configs")
