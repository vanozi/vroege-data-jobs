"""Ensure klauw_behandelingen.id has a PostgreSQL sequence default.

Revision ID: 20260512_01
Revises: 20260511_01
Create Date: 2026-05-12 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260512_01"
down_revision = "20260511_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            CREATE SEQUENCE IF NOT EXISTS klauw_behandelingen_id_seq
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER SEQUENCE klauw_behandelingen_id_seq
            OWNED BY klauw_behandelingen.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE klauw_behandelingen
            ALTER COLUMN id SET DEFAULT nextval('klauw_behandelingen_id_seq')
            """
        )
    )
    op.execute(
        sa.text(
            """
            SELECT setval(
                'klauw_behandelingen_id_seq',
                GREATEST(COALESCE((SELECT MAX(id) FROM klauw_behandelingen), 0) + 1, 1),
                false
            )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            ALTER TABLE klauw_behandelingen
            ALTER COLUMN id DROP DEFAULT
            """
        )
    )
