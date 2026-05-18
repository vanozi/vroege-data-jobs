"""Change klauw_behandelingen.behandeldatum to date.

Revision ID: 20260511_01
Revises: 20260510_01
Create Date: 2026-05-11 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260511_01"
down_revision = "20260510_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "klauw_behandelingen",
            "behandeldatum",
            existing_type=sa.DateTime(),
            type_=sa.Date(),
            existing_nullable=False,
            postgresql_using="behandeldatum::date",
        )
        return

    with op.batch_alter_table("klauw_behandelingen") as batch_op:
        batch_op.alter_column(
            "behandeldatum",
            existing_type=sa.DateTime(),
            type_=sa.Date(),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "klauw_behandelingen",
            "behandeldatum",
            existing_type=sa.Date(),
            type_=sa.DateTime(),
            existing_nullable=False,
            postgresql_using="behandeldatum::timestamp",
        )
        return

    with op.batch_alter_table("klauw_behandelingen") as batch_op:
        batch_op.alter_column(
            "behandeldatum",
            existing_type=sa.Date(),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
