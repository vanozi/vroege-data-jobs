"""Add shared authentication and authorization tables.

Revision ID: 20260528_01
Revises: 20260527_02
Create Date: 2026-05-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_01"
down_revision: Union[str, None] = "20260527_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_address", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_address", name="uq_users_email_address"),
        comment="Shared users for central app authentication.",
    )
    op.create_index(op.f("ix_users_email_address"), "users", ["email_address"])
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"])

    op.create_table(
        "applications",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_applications_key"),
        comment="Applications and dashboards protected by shared auth.",
    )
    op.create_index(
        "ix_applications_active_order",
        "applications",
        ["is_active", "display_order"],
    )
    op.create_index(op.f("ix_applications_category"), "applications", ["category"])
    op.create_index(
        op.f("ix_applications_display_order"),
        "applications",
        ["display_order"],
    )
    op.create_index(op.f("ix_applications_is_active"), "applications", ["is_active"])
    op.create_index(op.f("ix_applications_key"), "applications", ["key"])

    op.create_table(
        "roles",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_roles_key"),
        comment="Role definitions for per-application authorization.",
    )
    op.create_index(op.f("ix_roles_is_active"), "roles", ["is_active"])
    op.create_index(op.f("ix_roles_key"), "roles", ["key"])

    op.create_table(
        "user_application_access",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "application_id",
            name="uq_user_application_access_user_application",
        ),
        comment="User access grants scoped to one application.",
    )
    op.create_index(
        op.f("ix_user_application_access_application_id"),
        "user_application_access",
        ["application_id"],
    )
    op.create_index(
        op.f("ix_user_application_access_is_active"),
        "user_application_access",
        ["is_active"],
    )
    op.create_index(
        op.f("ix_user_application_access_user_id"),
        "user_application_access",
        ["user_id"],
    )
    op.create_index(
        "ix_user_application_access_user_active",
        "user_application_access",
        ["user_id", "is_active"],
    )

    op.create_table(
        "user_application_roles",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_application_access_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(
            ["user_application_access_id"],
            ["user_application_access.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_application_access_id",
            "role_id",
            name="uq_user_application_roles_access_role",
        ),
        comment="Multiple role assignments for one application access grant.",
    )
    op.create_index(
        op.f("ix_user_application_roles_role_id"),
        "user_application_roles",
        ["role_id"],
    )
    op.create_index(
        op.f("ix_user_application_roles_user_application_access_id"),
        "user_application_roles",
        ["user_application_access_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_application_roles_user_application_access_id"),
        table_name="user_application_roles",
    )
    op.drop_index(
        op.f("ix_user_application_roles_role_id"),
        table_name="user_application_roles",
    )
    op.drop_table("user_application_roles")

    op.drop_index(
        "ix_user_application_access_user_active",
        table_name="user_application_access",
    )
    op.drop_index(
        op.f("ix_user_application_access_user_id"),
        table_name="user_application_access",
    )
    op.drop_index(
        op.f("ix_user_application_access_is_active"),
        table_name="user_application_access",
    )
    op.drop_index(
        op.f("ix_user_application_access_application_id"),
        table_name="user_application_access",
    )
    op.drop_table("user_application_access")

    op.drop_index(op.f("ix_roles_key"), table_name="roles")
    op.drop_index(op.f("ix_roles_is_active"), table_name="roles")
    op.drop_table("roles")

    op.drop_index(op.f("ix_applications_key"), table_name="applications")
    op.drop_index(op.f("ix_applications_is_active"), table_name="applications")
    op.drop_index(op.f("ix_applications_display_order"), table_name="applications")
    op.drop_index(op.f("ix_applications_category"), table_name="applications")
    op.drop_index("ix_applications_active_order", table_name="applications")
    op.drop_table("applications")

    op.drop_index(op.f("ix_users_is_active"), table_name="users")
    op.drop_index(op.f("ix_users_email_address"), table_name="users")
    op.drop_table("users")
