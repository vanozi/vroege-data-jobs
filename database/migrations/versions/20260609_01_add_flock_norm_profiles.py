"""Add flock lay-curve profile parent table and flock relation.

Revision ID: 20260609_01
Revises: 20260608_01
Create Date: 2026-06-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260609_01"
down_revision: Union[str, None] = "20260608_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flock_lay_curve_profiles",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("breed_key", sa.String(), nullable=False),
        sa.Column("breed_name", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "breed_key",
            name="uq_flock_lay_curve_profiles_breed_key",
        ),
        comment="Selectable lay-curve norm profiles that flocks can reference.",
    )
    op.create_index(
        op.f("ix_flock_lay_curve_profiles_breed_key"),
        "flock_lay_curve_profiles",
        ["breed_key"],
        unique=False,
    )

    op.add_column(
        "flock_lay_curve_norms",
        sa.Column("flock_lay_curve_profile_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_flock_lay_curve_norms_flock_lay_curve_profile_id"),
        "flock_lay_curve_norms",
        ["flock_lay_curve_profile_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_flock_lay_curve_norms_profile_id",
        "flock_lay_curve_norms",
        "flock_lay_curve_profiles",
        ["flock_lay_curve_profile_id"],
        ["id"],
    )

    op.add_column(
        "flocks",
        sa.Column("flock_lay_curve_profile_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_flocks_flock_lay_curve_profile_id"),
        "flocks",
        ["flock_lay_curve_profile_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_flocks_profile_id",
        "flocks",
        "flock_lay_curve_profiles",
        ["flock_lay_curve_profile_id"],
        ["id"],
    )

    op.execute(
        """
        INSERT INTO flock_lay_curve_profiles (created_at, updated_at, breed_key, breed_name, source)
        SELECT CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, breed_key, MIN(breed_name), MIN(source)
        FROM flock_lay_curve_norms
        GROUP BY breed_key
        """
    )
    op.execute(
        """
        UPDATE flock_lay_curve_norms AS norm
        SET flock_lay_curve_profile_id = profile.id
        FROM flock_lay_curve_profiles AS profile
        WHERE profile.breed_key = norm.breed_key
        """
    )
    op.execute(
        """
        UPDATE flocks
        SET flock_lay_curve_profile_id = (
            SELECT id
            FROM flock_lay_curve_profiles
            ORDER BY id
            LIMIT 1
        )
        WHERE flock_lay_curve_profile_id IS NULL
          AND (SELECT COUNT(*) FROM flock_lay_curve_profiles) = 1
        """
    )

    op.alter_column(
        "flock_lay_curve_norms",
        "flock_lay_curve_profile_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_flocks_profile_id",
        "flocks",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_flocks_flock_lay_curve_profile_id"),
        table_name="flocks",
    )
    op.drop_column("flocks", "flock_lay_curve_profile_id")

    op.drop_constraint(
        "fk_flock_lay_curve_norms_profile_id",
        "flock_lay_curve_norms",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_flock_lay_curve_norms_flock_lay_curve_profile_id"),
        table_name="flock_lay_curve_norms",
    )
    op.drop_column("flock_lay_curve_norms", "flock_lay_curve_profile_id")

    op.drop_index(
        op.f("ix_flock_lay_curve_profiles_breed_key"),
        table_name="flock_lay_curve_profiles",
    )
    op.drop_table("flock_lay_curve_profiles")
