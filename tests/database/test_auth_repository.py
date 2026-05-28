"""Tests for shared authentication and authorization repositories."""

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database.models.auth import Application, Role, User
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository


def test_users_repository_creates_and_finds_user_by_normalized_email():
    engine = _create_test_engine()
    repository = UsersRepository(_session_factory(engine))

    created = repository.create_user(
        User(
            email_address=" ADMIN@GebroedersVroege.nl ",
            first_name="Admin",
            password_hash="hashed-password",
        )
    )
    fetched = repository.get_user_by_email("admin@gebroedersvroege.nl")

    assert created.id is not None
    assert created.email_address == "admin@gebroedersvroege.nl"
    assert fetched.id == created.id
    assert fetched.first_name == "Admin"


def test_users_repository_updates_status_and_password_hash():
    engine = _create_test_engine()
    repository = UsersRepository(_session_factory(engine))
    created = _create_user(repository)

    updated = repository.update_user(created.id, {"first_name": "Wouter"})
    inactive = repository.set_user_active(created.id, False)
    with_new_password = repository.set_user_password_hash(created.id, "new-hash")

    assert updated.first_name == "Wouter"
    assert inactive.is_active is False
    assert with_new_password.password_hash == "new-hash"


def test_users_repository_rejects_empty_required_values():
    engine = _create_test_engine()
    repository = UsersRepository(_session_factory(engine))

    try:
        repository.create_user({"email_address": "", "password_hash": "hash"})
    except ValueError as exc:
        assert "Email address" in str(exc)
    else:
        raise AssertionError("Expected empty email address to be rejected.")

    try:
        repository.create_user(
            {"email_address": "admin@example.com", "password_hash": ""}
        )
    except ValueError as exc:
        assert "Password hash" in str(exc)
    else:
        raise AssertionError("Expected empty password hash to be rejected.")


def test_applications_repository_creates_and_lists_portal_applications():
    engine = _create_test_engine()
    repository = ApplicationsRepository(_session_factory(engine))

    repository.create_application(
        Application(
            key=" Kippen ",
            name="Kippen",
            url="/kippen",
            display_order=20,
        )
    )
    repository.create_application(
        {
            "key": "tank-dashboard",
            "name": "Tanken",
            "url": "/tanken",
            "category": "dashboard",
            "display_order": 10,
            "is_active": False,
        }
    )

    all_applications = repository.list_applications()
    active_applications = repository.list_applications(active_only=True)
    fetched = repository.get_application_by_key("KIPPEN")

    assert [application.key for application in all_applications] == [
        "tank-dashboard",
        "kippen",
    ]
    assert [application.key for application in active_applications] == ["kippen"]
    assert fetched.name == "Kippen"


def test_roles_repository_creates_updates_and_lists_roles():
    engine = _create_test_engine()
    repository = RolesRepository(_session_factory(engine))

    admin = repository.create_role(
        Role(key=" ADMIN ", name="Administrator", description="Full access")
    )
    repository.create_role({"key": "worker", "name": "Medewerker", "is_active": False})

    updated = repository.update_role(admin.id, {"description": "Portal beheer"})
    all_roles = repository.list_roles()
    active_roles = repository.list_roles(active_only=True)
    fetched = repository.get_role_by_key("admin")

    assert updated.description == "Portal beheer"
    assert [role.key for role in all_roles] == ["admin", "worker"]
    assert [role.key for role in active_roles] == ["admin"]
    assert fetched.id == admin.id


def test_access_repository_grants_reactivates_and_revokes_application_access():
    engine = _create_test_engine()
    users = UsersRepository(_session_factory(engine))
    applications = ApplicationsRepository(_session_factory(engine))
    access_repository = UserApplicationAccessRepository(_session_factory(engine))
    user = _create_user(users)
    application = _create_application(applications)

    inactive_access = access_repository.grant_application_access(
        user_id=user.id,
        application_id=application.id,
        is_active=False,
    )
    active_access = access_repository.grant_application_access(
        user_id=user.id,
        application_id=application.id,
    )
    active_applications = access_repository.list_user_applications(
        user.id,
        active_only=True,
    )
    revoked = access_repository.revoke_application_access(active_access.id)

    assert inactive_access.id == active_access.id
    assert active_access.is_active is True
    assert [application.key for application in active_applications] == ["kippen"]
    assert revoked.is_active is False
    assert not access_repository.list_user_applications(user.id, active_only=True)


def test_access_repository_assigns_multiple_roles_to_application_access():
    engine = _create_test_engine()
    users = UsersRepository(_session_factory(engine))
    applications = ApplicationsRepository(_session_factory(engine))
    roles = RolesRepository(_session_factory(engine))
    access_repository = UserApplicationAccessRepository(_session_factory(engine))
    user = _create_user(users)
    application = _create_application(applications)
    access = access_repository.grant_application_access(
        user_id=user.id,
        application_id=application.id,
    )
    admin_role = roles.create_role(Role(key="admin", name="Admin"))
    worker_role = roles.create_role(Role(key="worker", name="Worker"))

    admin_assignment = access_repository.grant_application_role(
        access_id=access.id,
        role_id=admin_role.id,
    )
    duplicate_assignment = access_repository.grant_application_role(
        access_id=access.id,
        role_id=admin_role.id,
    )
    access_repository.grant_application_role(
        access_id=access.id,
        role_id=worker_role.id,
    )
    assigned_roles = access_repository.list_user_application_roles(access.id)

    assert duplicate_assignment.id == admin_assignment.id
    assert [role.key for role in assigned_roles] == ["admin", "worker"]
    assert access_repository.revoke_application_role(
        access_id=access.id,
        role_id=worker_role.id,
    )
    assert [
        role.key for role in access_repository.list_user_application_roles(access.id)
    ] == ["admin"]


def _create_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _session_factory(engine):
    return lambda: Session(engine, expire_on_commit=False)


def _create_user(repository: UsersRepository) -> User:
    return repository.create_user(
        User(email_address="admin@example.com", password_hash="hash")
    )


def _create_application(repository: ApplicationsRepository) -> Application:
    return repository.create_application(
        Application(key="kippen", name="Kippen", url="/kippen")
    )
