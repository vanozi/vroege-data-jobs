"""Tests for shared auth bootstrap helpers."""

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from shared_auth import bootstrap
from shared_auth import service


def test_bootstrap_requires_admin_username_when_database_has_no_users():
    context = _create_context()

    try:
        bootstrap.bootstrap_shared_auth(context.session_factory)
    except ValueError as exc:
        assert "AUTH_BOOTSTRAP_USERNAME" in str(exc)
    else:
        raise AssertionError("Expected missing first-admin username to be rejected.")

    assert [application.key for application in context.applications.list_applications()]
    assert [role.key for role in context.roles.list_roles()] == [
        "admin",
        "viewer",
        "worker",
    ]


def test_bootstrap_seeds_core_apps_roles_and_first_admin_access():
    context = _create_context()

    result = bootstrap.bootstrap_shared_auth(
        context.session_factory,
        bootstrap.BootstrapAdminConfig(
            username="admin",
            password="correct-password",
            first_name="Admin",
            last_name="User",
        ),
    )
    user = context.users.get_user_by_username("ADMIN")
    applications = context.applications.list_applications()

    assert result.applications_seeded == 5
    assert result.roles_seeded == 3
    assert result.admin_user_created
    assert result.admin_access_grants == 5
    assert result.admin_role_grants == 6
    assert user.first_name == "Admin"
    assert user.must_change_password is False
    assert service.verify_password(user.password_hash, "correct-password")
    assert [application.key for application in applications] == [
        "kippen",
        "dashboard_kippen",
        "dashboard_klauwgezondheid",
        "dashboard_tank_terminal",
        "user_administration",
    ]
    assert _role_keys_for(context, user.id, "user_administration") == ["admin"]
    assert _role_keys_for(context, user.id, "kippen") == ["admin", "worker"]
    assert _role_keys_for(context, user.id, "dashboard_kippen") == ["viewer"]
    assert _role_keys_for(context, user.id, "dashboard_klauwgezondheid") == ["viewer"]
    assert _role_keys_for(context, user.id, "dashboard_tank_terminal") == ["viewer"]


def test_bootstrap_is_idempotent_for_core_records_and_grants():
    context = _create_context()
    config = bootstrap.BootstrapAdminConfig(
        username="admin",
        password="correct-password",
    )

    bootstrap.bootstrap_shared_auth(context.session_factory, config)
    second_result = bootstrap.bootstrap_shared_auth(context.session_factory, config)

    assert second_result.admin_user_updated
    assert len(context.users.list_users()) == 1
    assert len(context.applications.list_applications()) == 5
    assert len(context.roles.list_roles()) == 3
    assert len(context.access.list_user_applications(1)) == 5


def test_bootstrap_skips_admin_when_users_exist_and_no_admin_config():
    context = _create_context()
    context.users.create_user(
        {
            "username": "existing",
            "password_hash": service.hash_password("password"),
        }
    )

    result = bootstrap.bootstrap_shared_auth(context.session_factory)

    assert not result.admin_user_created
    assert not result.admin_user_updated
    assert result.admin_access_grants == 0
    assert result.messages == [
        "Core applications and roles were seeded; admin user skipped."
    ]


class _BootstrapTestContext:
    def __init__(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        def session_factory():
            return Session(engine, expire_on_commit=False)

        self.session_factory = session_factory
        self.users = UsersRepository(session_factory)
        self.applications = ApplicationsRepository(session_factory)
        self.roles = RolesRepository(session_factory)
        self.access = UserApplicationAccessRepository(session_factory)


def _create_context() -> _BootstrapTestContext:
    return _BootstrapTestContext()


def _role_keys_for(
    context: _BootstrapTestContext,
    user_id: int,
    application_key: str,
) -> list[str]:
    application = context.applications.get_application_by_key(application_key)
    access = context.access.get_user_application_access(
        user_id=user_id,
        application_id=application.id,
    )
    return [role.key for role in context.access.list_user_application_roles(access.id)]
