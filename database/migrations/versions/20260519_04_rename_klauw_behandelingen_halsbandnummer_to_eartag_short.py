"""Rename klauw_behandelingen.halsbandnummer to eartag_short.

Revision ID: 20260519_04
Revises: 20260519_03
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260519_04"
down_revision: Union[str, Sequence[str], None] = "20260519_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "klauw_behandelingen",
        "halsbandnummer",
        existing_type=sa.Integer(),
        type_=sa.String(),
        existing_nullable=False,
        postgresql_using="halsbandnummer::text",
        existing_comment="Halsbandnummer van de koe die behandeld is - koppeling naar de koe",
    )
    op.alter_column(
        "klauw_behandelingen",
        "halsbandnummer",
        new_column_name="eartag_short",
        existing_type=sa.String(),
        existing_nullable=False,
        comment="Kort oormerknummer van de koe die behandeld is - koppeling naar koeien.eartag_short",
        existing_comment="Halsbandnummer van de koe die behandeld is - koppeling naar de koe",
    )


def downgrade() -> None:
    op.alter_column(
        "klauw_behandelingen",
        "eartag_short",
        new_column_name="halsbandnummer",
        existing_type=sa.String(),
        existing_nullable=False,
        comment="Halsbandnummer van de koe die behandeld is - koppeling naar de koe",
        existing_comment="Kort oormerknummer van de koe die behandeld is - koppeling naar koeien.eartag_short",
    )
    op.alter_column(
        "klauw_behandelingen",
        "halsbandnummer",
        existing_type=sa.String(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="halsbandnummer::integer",
        existing_comment="Halsbandnummer van de koe die behandeld is - koppeling naar de koe",
    )
