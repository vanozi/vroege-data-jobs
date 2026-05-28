"""Replace shared auth email login with username login.

Revision ID: 20260528_02
Revises: 20260528_01
Create Date: 2026-05-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_02"
down_revision: Union[str, None] = "20260528_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    if dialect_name == "postgresql":
        op.execute(
            """
            WITH candidate_usernames AS (
                SELECT
                    id,
                    lower(split_part(email_address, '@', 1)) AS base_username,
                    row_number() OVER (
                        PARTITION BY lower(split_part(email_address, '@', 1))
                        ORDER BY id
                    ) AS duplicate_number
                FROM users
            )
            UPDATE users
            SET username = CASE
                WHEN candidate_usernames.duplicate_number = 1
                THEN candidate_usernames.base_username
                ELSE candidate_usernames.base_username || '-' || users.id::text
            END
            FROM candidate_usernames
            WHERE users.id = candidate_usernames.id
                AND users.username IS NULL
            """
        )
        op.alter_column("users", "username", nullable=False)
        op.drop_index(op.f("ix_users_email_address"), table_name="users")
        op.drop_constraint("uq_users_email_address", "users", type_="unique")
        op.drop_column("users", "email_address")
        op.create_unique_constraint("uq_users_username", "users", ["username"])
    else:
        op.execute(
            """
            WITH candidate_usernames AS (
                SELECT
                    id,
                    lower(
                        CASE
                            WHEN instr(email_address, '@') > 0
                            THEN substr(email_address, 1, instr(email_address, '@') - 1)
                            ELSE email_address
                        END
                    ) AS base_username,
                    row_number() OVER (
                        PARTITION BY lower(
                            CASE
                                WHEN instr(email_address, '@') > 0
                                THEN substr(email_address, 1, instr(email_address, '@') - 1)
                                ELSE email_address
                            END
                        )
                        ORDER BY id
                    ) AS duplicate_number
                FROM users
            )
            UPDATE users
            SET username = CASE
                WHEN (
                    SELECT duplicate_number
                    FROM candidate_usernames
                    WHERE candidate_usernames.id = users.id
                ) = 1
                THEN (
                    SELECT base_username
                    FROM candidate_usernames
                    WHERE candidate_usernames.id = users.id
                )
                ELSE (
                    SELECT base_username
                    FROM candidate_usernames
                    WHERE candidate_usernames.id = users.id
                ) || '-' || users.id
            END
            WHERE username IS NULL
            """
        )
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column("username", nullable=False)
            batch_op.drop_index(op.f("ix_users_email_address"))
            batch_op.drop_constraint("uq_users_email_address", type_="unique")
            batch_op.drop_column("email_address")
            batch_op.create_unique_constraint("uq_users_username", ["username"])

    op.create_index(op.f("ix_users_username"), "users", ["username"])
    op.create_index(
        op.f("ix_users_must_change_password"),
        "users",
        ["must_change_password"],
    )
    op.alter_column("users", "must_change_password", server_default=None)


def downgrade() -> None:
    op.add_column("users", sa.Column("email_address", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE users
        SET email_address = username
        WHERE email_address IS NULL
        """
    )

    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.alter_column("users", "email_address", nullable=False)
        op.drop_constraint("uq_users_username", "users", type_="unique")
        op.drop_index(op.f("ix_users_must_change_password"), table_name="users")
        op.drop_index(op.f("ix_users_username"), table_name="users")
        op.drop_column("users", "must_change_password")
        op.drop_column("users", "username")
        op.create_unique_constraint(
            "uq_users_email_address",
            "users",
            ["email_address"],
        )
    else:
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column("email_address", nullable=False)
            batch_op.drop_constraint("uq_users_username", type_="unique")
            batch_op.drop_index(op.f("ix_users_must_change_password"))
            batch_op.drop_index(op.f("ix_users_username"))
            batch_op.drop_column("must_change_password")
            batch_op.drop_column("username")
            batch_op.create_unique_constraint(
                "uq_users_email_address",
                ["email_address"],
            )

    op.create_index(op.f("ix_users_email_address"), "users", ["email_address"])
