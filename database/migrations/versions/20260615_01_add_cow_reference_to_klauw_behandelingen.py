"""Add cow reference to klauw behandelingen.

Revision ID: 20260615_01
Revises: 20260609_01
Create Date: 2026-06-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260615_01"
down_revision: Union[str, None] = "20260609_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "klauw_behandelingen",
        sa.Column(
            "animal_id",
            sa.Uuid(),
            nullable=True,
            comment="Animal ID van de gekoppelde koe wanneer deze bepaald kon worden",
        ),
    )
    op.add_column(
        "klauw_behandelingen",
        sa.Column(
            "eartag",
            sa.String(),
            nullable=True,
            comment="Volledig oormerknummer van de gekoppelde koe wanneer deze bepaald kon worden",
        ),
    )
    op.create_index(
        op.f("ix_klauw_behandelingen_animal_id"),
        "klauw_behandelingen",
        ["animal_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_klauw_behandelingen_animal_id",
        "klauw_behandelingen",
        "koeien",
        ["animal_id"],
        ["animal_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_klauw_behandelingen_animal_id",
        "klauw_behandelingen",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_klauw_behandelingen_animal_id"),
        table_name="klauw_behandelingen",
    )
    op.drop_column("klauw_behandelingen", "eartag")
    op.drop_column("klauw_behandelingen", "animal_id")
