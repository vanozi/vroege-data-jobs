"""Split laying hens daily registrations.

Revision ID: 20260527_01
Revises: 20260526_04
Create Date: 2026-05-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260527_01"
down_revision: Union[str, Sequence[str], None] = "20260526_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "egg_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("flock_id", sa.Integer(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(), nullable=True),
        sa.Column("first_quality_eggs", sa.Integer(), nullable=False),
        sa.Column("second_quality_eggs", sa.Integer(), nullable=False),
        sa.Column("total_eggs", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["flock_id"],
            ["flocks.id"],
            name="fk_egg_registrations_flock_id_flocks",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_egg_registrations_house_date",
        ),
        comment="Daily egg count rows for first and second quality eggs.",
    )
    op.create_index(
        op.f("ix_egg_registrations_flock_id"),
        "egg_registrations",
        ["flock_id"],
    )
    op.create_index(
        op.f("ix_egg_registrations_house_id"),
        "egg_registrations",
        ["house_id"],
    )
    op.create_index(
        op.f("ix_egg_registrations_registration_date"),
        "egg_registrations",
        ["registration_date"],
    )

    op.create_table(
        "feed_water_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("flock_id", sa.Integer(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(), nullable=True),
        sa.Column("water_ml", sa.Integer(), nullable=False),
        sa.Column("feed_grams", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["flock_id"],
            ["flocks.id"],
            name="fk_feed_water_registrations_flock_id_flocks",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_feed_water_registrations_house_date",
        ),
        comment="Daily feed and water usage rows in grams and milliliters.",
    )
    op.create_index(
        op.f("ix_feed_water_registrations_flock_id"),
        "feed_water_registrations",
        ["flock_id"],
    )
    op.create_index(
        op.f("ix_feed_water_registrations_house_id"),
        "feed_water_registrations",
        ["house_id"],
    )
    op.create_index(
        op.f("ix_feed_water_registrations_registration_date"),
        "feed_water_registrations",
        ["registration_date"],
    )

    op.execute(
        """
        INSERT INTO egg_registrations (
            created_at,
            updated_at,
            house_id,
            flock_id,
            registration_date,
            weekday,
            first_quality_eggs,
            second_quality_eggs,
            total_eggs,
            notes,
            created_by
        )
        SELECT
            created_at,
            updated_at,
            house_id,
            flock_id,
            registration_date,
            weekday,
            COALESCE(first_quality_eggs, 0),
            COALESCE(second_quality_eggs, 0),
            COALESCE(total_eggs, 0),
            notes,
            created_by
        FROM daily_laying_registrations
        WHERE flock_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO feed_water_registrations (
            created_at,
            updated_at,
            house_id,
            flock_id,
            registration_date,
            weekday,
            water_ml,
            feed_grams,
            notes,
            created_by
        )
        SELECT
            created_at,
            updated_at,
            house_id,
            flock_id,
            registration_date,
            weekday,
            COALESCE(water_ml, 0),
            COALESCE(feed_grams, 0),
            notes,
            created_by
        FROM daily_laying_registrations
        WHERE flock_id IS NOT NULL
        """
    )
    op.drop_table("daily_laying_registrations")


def downgrade() -> None:
    op.create_table(
        "daily_laying_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.String(), nullable=False),
        sa.Column("flock_id", sa.Integer(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(), nullable=True),
        sa.Column("first_quality_eggs", sa.Integer(), nullable=False),
        sa.Column("second_quality_eggs", sa.Integer(), nullable=False),
        sa.Column("total_eggs", sa.Integer(), nullable=False),
        sa.Column("water_ml", sa.Integer(), nullable=True),
        sa.Column("feed_grams", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["flock_id"],
            ["flocks.id"],
            name="fk_daily_laying_registrations_flock_id_flocks",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_daily_laying_registrations_house_date",
        ),
        comment="Daily laying calendar rows for egg counts, feed, water, and notes.",
    )
    op.create_index(
        op.f("ix_daily_laying_registrations_flock_id"),
        "daily_laying_registrations",
        ["flock_id"],
    )
    op.create_index(
        op.f("ix_daily_laying_registrations_house_id"),
        "daily_laying_registrations",
        ["house_id"],
    )
    op.create_index(
        op.f("ix_daily_laying_registrations_registration_date"),
        "daily_laying_registrations",
        ["registration_date"],
    )
    op.execute(
        """
        INSERT INTO daily_laying_registrations (
            created_at,
            updated_at,
            house_id,
            flock_id,
            registration_date,
            weekday,
            first_quality_eggs,
            second_quality_eggs,
            total_eggs,
            water_ml,
            feed_grams,
            notes,
            created_by
        )
        SELECT
            COALESCE(e.created_at, fw.created_at),
            COALESCE(e.updated_at, fw.updated_at),
            COALESCE(e.house_id, fw.house_id),
            COALESCE(e.flock_id, fw.flock_id),
            COALESCE(e.registration_date, fw.registration_date),
            COALESCE(e.weekday, fw.weekday),
            COALESCE(e.first_quality_eggs, 0),
            COALESCE(e.second_quality_eggs, 0),
            COALESCE(e.total_eggs, 0),
            fw.water_ml,
            fw.feed_grams,
            COALESCE(e.notes, fw.notes),
            COALESCE(e.created_by, fw.created_by)
        FROM egg_registrations e
        FULL OUTER JOIN feed_water_registrations fw
            ON e.house_id = fw.house_id
            AND e.registration_date = fw.registration_date
        """
    )
    op.drop_table("feed_water_registrations")
    op.drop_table("egg_registrations")
