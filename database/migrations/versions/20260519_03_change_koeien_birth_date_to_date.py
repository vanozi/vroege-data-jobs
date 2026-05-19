"""Change koeien birth_date datetime column to date.

Revision ID: 20260519_03
Revises: 20260519_02
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260519_03"
down_revision: Union[str, Sequence[str], None] = "20260519_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "koeien",
        "birth_date",
        existing_type=sa.DateTime(),
        type_=sa.Date(),
        existing_nullable=False,
        postgresql_using="birth_date::date",
    )


def downgrade() -> None:
    op.alter_column(
        "koeien",
        "birth_date",
        existing_type=sa.Date(),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="birth_date::timestamp",
    )
