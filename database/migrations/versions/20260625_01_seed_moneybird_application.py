"""Seed Moneybird dashboard application.

Revision ID: 20260625_01
Revises: 20260622_01
Create Date: 2026-06-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260625_01"
down_revision: Union[str, Sequence[str], None] = "20260622_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APPLICATION_KEY = "dashboard_moneybird"


applications_table = sa.table(
    "applications",
    sa.column("id", sa.Integer),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
    sa.column("key", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("url", sa.String),
    sa.column("category", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("display_order", sa.Integer),
)

user_application_access_table = sa.table(
    "user_application_access",
    sa.column("id", sa.Integer),
    sa.column("application_id", sa.Integer),
)

user_application_roles_table = sa.table(
    "user_application_roles",
    sa.column("user_application_access_id", sa.Integer),
)


def upgrade() -> None:
    connection = op.get_bind()
    application_data = {
        "updated_at": sa.func.now(),
        "key": APPLICATION_KEY,
        "name": "Moneybird",
        "description": "Boekhoudkundig overzicht van facturen, rapporten en bankmutaties.",
        "url": "/moneybird",
        "category": "dashboard",
        "is_active": True,
        "display_order": 35,
    }

    application_id = connection.execute(
        sa.select(applications_table.c.id).where(
            applications_table.c.key == APPLICATION_KEY
        )
    ).scalar_one_or_none()
    if application_id is None:
        connection.execute(
            applications_table.insert().values(
                created_at=sa.func.now(),
                **application_data,
            )
        )
        return

    connection.execute(
        applications_table.update()
        .where(applications_table.c.id == application_id)
        .values(**application_data)
    )


def downgrade() -> None:
    connection = op.get_bind()
    application_id = connection.execute(
        sa.select(applications_table.c.id).where(
            applications_table.c.key == APPLICATION_KEY
        )
    ).scalar_one_or_none()
    if application_id is None:
        return

    access_ids = connection.execute(
        sa.select(user_application_access_table.c.id).where(
            user_application_access_table.c.application_id == application_id
        )
    ).scalars()
    access_ids = list(access_ids)
    if access_ids:
        connection.execute(
            user_application_roles_table.delete().where(
                user_application_roles_table.c.user_application_access_id.in_(
                    access_ids
                )
            )
        )
        connection.execute(
            user_application_access_table.delete().where(
                user_application_access_table.c.id.in_(access_ids)
            )
        )

    connection.execute(
        applications_table.delete().where(applications_table.c.id == application_id)
    )
