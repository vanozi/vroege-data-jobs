"""Shared authentication and authorization models."""

from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from database.models.base import CreatedTimestampMixin


class User(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Shared identity for the central application portal."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email_address", name="uq_users_email_address"),
        {"comment": "Shared users for central app authentication."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    email_address: str = Field(index=True)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    password_hash: str
    is_active: bool = Field(default=True, index=True)


class Application(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Application or dashboard available through the central portal."""

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("key", name="uq_applications_key"),
        Index("ix_applications_active_order", "is_active", "display_order"),
        {"comment": "Applications and dashboards protected by shared auth."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    name: str
    description: Optional[str] = Field(default=None)
    url: str
    category: str = Field(default="app", index=True)
    is_active: bool = Field(default=True, index=True)
    display_order: int = Field(default=100, index=True)


class Role(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Database-backed role that can be assigned inside applications."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("key", name="uq_roles_key"),
        {"comment": "Role definitions for per-application authorization."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    name: str
    description: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True, index=True)


class UserApplicationAccess(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Application access grant for one user."""

    __tablename__ = "user_application_access"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "application_id",
            name="uq_user_application_access_user_application",
        ),
        Index(
            "ix_user_application_access_user_active",
            "user_id",
            "is_active",
        ),
        {"comment": "User access grants scoped to one application."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    is_active: bool = Field(default=True, index=True)


class UserApplicationRole(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Role assignment for a user application access grant."""

    __tablename__ = "user_application_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_application_access_id",
            "role_id",
            name="uq_user_application_roles_access_role",
        ),
        {"comment": "Multiple role assignments for one application access grant."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_application_access_id: int = Field(
        foreign_key="user_application_access.id",
        index=True,
    )
    role_id: int = Field(foreign_key="roles.id", index=True)
