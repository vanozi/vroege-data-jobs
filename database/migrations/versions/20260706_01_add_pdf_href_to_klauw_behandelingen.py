"""Add source PDF link to klauw behandelingen.

Revision ID: 20260706_01
Revises: 20260625_01
Create Date: 2026-07-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260706_01"
down_revision: Union[str, Sequence[str], None] = "20260625_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "klauw_behandelingen",
        sa.Column(
            "pdf_href",
            sa.String(),
            nullable=True,
            comment="Bronlink van de Klauwscore Alle notaties PDF waaruit deze behandeling is geimporteerd",
        ),
    )
    op.create_index(
        op.f("ix_klauw_behandelingen_pdf_href"),
        "klauw_behandelingen",
        ["pdf_href"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_klauw_behandelingen_pdf_href"),
        table_name="klauw_behandelingen",
    )
    op.drop_column("klauw_behandelingen", "pdf_href")
