"""Tests for the shared authentication service."""

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database.models.auth import Application, Role, User
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from shared_auth import service
from shared_auth.exceptions import ApplicationAccessDeniedError
from shared_auth.exceptions import ApplicationRoleDeniedError
from shared_auth.exceptions import AuthenticationRequiredError
from shared_auth.service import SharedAuthService


def test_password_hashing_and_verification():
    password_hash = service.hash_password("correct-password")

    assert password_hash != "correct-password"
    assert service.verify_password(password_hash, "correct-password")
    assert not service.verify_password(password_hash, "wrong-password")
    assert not service.verify_password("", "correct-password")


def test_hash_password_rejects_empty_password():
    try:
        service.hash_password(" ")
    except ValueError as exc:
        assert "Password" in str(exc)
    else:
        raise AssertionError("Expected empty password to be rejected.")


def test_authenticate_user_accepts_active_user_with_valid_password():
    context = _create_context()
    user = context.users.create_user(
        User(
            username="admin@example.com",
            password_hash=service.hash_password("correct-password"),
        )
    )

    authenticated = context.service.authenticate_user(
        "ADMIN@example.com",
        "correct-password",
    )

    assert authenticated.id == user.id


def test_change_user_password_clears_required_password_change():
    context = _create_context()
    user = context.users.create_user(
        User(
            username="admin",
            password_hash=service.hash_password("default-password"),
            must_change_password=True,
        )
    )

    updated = context.service.change_user_password(user.id, "new-password")

    assert service.verify_password(updated.password_hash, "new-password")
    assert updated.must_change_password is False


def test_authenticate_user_rejects_inactive_or_invalid_credentials():
    context = _create_context()
    context.users.create_user(
        User(
            username="admin@example.com",
            password_hash=service.hash_password("correct-password"),
            is_active=False,
        )
    )

    assert (
        context.service.authenticate_user("admin@example.com", "correct-password")
        is None
    )
    assert context.service.authenticate_user("missing@example.com", "password") is None
    assert context.service.authenticate_user("admin@example.com", "wrong") is None


def test_user_can_access_only_active_granted_applications():
    context = _create_context()
    user = _create_user(context)
    kippen = _create_application(context, "kippen")
    tanken = _create_application(context, "dashboard_tank_terminal")
    inactive_application = _create_application(
        context,
        "inactive_dashboard",
        is_active=False,
    )
    context.access.grant_application_access(
        user_id=user.id,
        application_id=kippen.id,
    )
    context.access.grant_application_access(
        user_id=user.id,
        application_id=inactive_application.id,
    )
    context.access.grant_application_access(
        user_id=user.id,
        application_id=tanken.id,
        is_active=False,
    )

    assert context.service.user_can_access_application(user.id, "kippen")
    assert not context.service.user_can_access_application(
        user.id,
        "dashboard_tank_terminal",
    )
    assert not context.service.user_can_access_application(
        user.id,
        "inactive_dashboard",
    )
    assert not context.service.user_can_access_application(user.id, "unknown")


def test_accessible_application_listing_returns_active_user_applications_in_order():
    context = _create_context()
    user = _create_user(context)
    tanken = _create_application(context, "dashboard_tank_terminal", display_order=20)
    kippen = _create_application(context, "kippen", display_order=10)
    inactive_user = context.users.create_user(
        User(
            username="inactive@example.com",
            password_hash=service.hash_password("password"),
            is_active=False,
        )
    )
    context.access.grant_application_access(
        user_id=user.id,
        application_id=tanken.id,
    )
    context.access.grant_application_access(
        user_id=user.id,
        application_id=kippen.id,
    )

    applications = context.service.list_accessible_applications(user.id)

    assert [application.key for application in applications] == [
        "kippen",
        "dashboard_tank_terminal",
    ]
    assert context.service.list_accessible_applications(inactive_user.id) == []
    assert context.service.list_accessible_applications(None) == []


def test_user_has_application_role_supports_multiple_active_roles():
    context = _create_context()
    user = _create_user(context)
    application = _create_application(context, "kippen")
    access = context.access.grant_application_access(
        user_id=user.id,
        application_id=application.id,
    )
    admin = _create_role(context, "admin")
    worker = _create_role(context, "worker")
    viewer = _create_role(context, "viewer", is_active=False)
    context.access.grant_application_role(access_id=access.id, role_id=admin.id)
    context.access.grant_application_role(access_id=access.id, role_id=worker.id)
    context.access.grant_application_role(access_id=access.id, role_id=viewer.id)

    assert context.service.user_has_application_role(user.id, "kippen", "admin")
    assert context.service.user_has_any_application_role(
        user.id,
        "kippen",
        ["viewer", "worker"],
    )
    assert not context.service.user_has_application_role(user.id, "kippen", "viewer")
    assert not context.service.user_has_any_application_role(user.id, "kippen", [])
    assert not context.service.user_has_application_role(user.id, "unknown", "admin")


def test_require_application_access_returns_application_or_raises():
    context = _create_context()
    user = _create_user(context)
    application = _create_application(context, "kippen")
    context.access.grant_application_access(
        user_id=user.id,
        application_id=application.id,
    )

    allowed = context.service.require_application_access(user.id, "kippen")

    assert allowed.id == application.id

    try:
        context.service.require_application_access(None, "kippen")
    except AuthenticationRequiredError:
        pass
    else:
        raise AssertionError("Expected missing user session to be rejected.")

    try:
        context.service.require_application_access(user.id, "dashboard")
    except ApplicationAccessDeniedError:
        pass
    else:
        raise AssertionError("Expected missing app access to be rejected.")


def test_require_application_role_returns_application_or_raises():
    context = _create_context()
    user = _create_user(context)
    application = _create_application(context, "kippen")
    access = context.access.grant_application_access(
        user_id=user.id,
        application_id=application.id,
    )
    worker = _create_role(context, "worker")
    context.access.grant_application_role(access_id=access.id, role_id=worker.id)

    allowed = context.service.require_application_role(user.id, "kippen", "worker")

    assert allowed.id == application.id

    try:
        context.service.require_application_role(user.id, "kippen", "admin")
    except ApplicationRoleDeniedError:
        pass
    else:
        raise AssertionError("Expected missing role to be rejected.")


class _AuthTestContext:
    def __init__(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        def session_factory():
            return Session(engine, expire_on_commit=False)

        self.users = UsersRepository(session_factory)
        self.applications = ApplicationsRepository(session_factory)
        self.roles = RolesRepository(session_factory)
        self.access = UserApplicationAccessRepository(session_factory)
        self.service = SharedAuthService(
            users_repository=self.users,
            applications_repository=self.applications,
            roles_repository=self.roles,
            access_repository=self.access,
        )


def _create_context() -> _AuthTestContext:
    return _AuthTestContext()


def _create_user(context: _AuthTestContext) -> User:
    return context.users.create_user(
        User(
            username="worker@example.com",
            password_hash=service.hash_password("password"),
        )
    )


def _create_application(
    context: _AuthTestContext,
    key: str,
    *,
    is_active: bool = True,
    display_order: int = 100,
) -> Application:
    return context.applications.create_application(
        Application(
            key=key,
            name=key,
            url=f"/{key}",
            is_active=is_active,
            display_order=display_order,
        )
    )


def _create_role(
    context: _AuthTestContext,
    key: str,
    *,
    is_active: bool = True,
) -> Role:
    return context.roles.create_role(
        Role(
            key=key,
            name=key,
            is_active=is_active,
        )
    )
