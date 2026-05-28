"""Route tests for the central application portal."""

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from dashboard_portal import app as portal_app
from database.models.auth import Application, Role, User
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from shared_auth import service


def test_index_redirects_to_login_without_session(monkeypatch):
    client, _context = _client(monkeypatch)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_login_with_wrong_credentials_fails(monkeypatch):
    client, _context = _client(monkeypatch)

    response = client.post(
        "/login",
        data={"email_address": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "onjuist" in response.text


def test_login_with_correct_credentials_shows_accessible_applications(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    kippen = _create_application(context, "kippen", "Kippen", "/kippen", "app", 10)
    tanken = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        20,
    )
    _create_application(
        context,
        "dashboard_klauwgezondheid",
        "Klauwgezondheid",
        "/klauwgezondheid",
        "dashboard",
        30,
    )
    _grant_access(context, user.id, kippen.id)
    _grant_access(context, user.id, tanken.id)

    response = client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "Kippen" in index_response.text
    assert "Tanken" in index_response.text
    assert "Klauwgezondheid" not in index_response.text
    assert 'href="/tank-terminal"' in index_response.text


def test_dashboard_tiles_are_filtered_by_active_access(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    tanken = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        10,
    )
    inactive_dashboard = _create_application(
        context,
        "dashboard_klauwgezondheid",
        "Klauwgezondheid",
        "/klauwgezondheid",
        "dashboard",
        20,
        is_active=False,
    )
    _grant_access(context, user.id, tanken.id)
    _grant_access(context, user.id, inactive_dashboard.id)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "Tanken" in response.text
    assert "Klauwgezondheid" not in response.text


def test_user_administration_tile_is_database_backed(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    user_admin = _create_application(
        context,
        "user_administration",
        "Gebruikersbeheer",
        "/admin/users",
        "admin",
        100,
    )
    access = _grant_access(context, user.id, user_admin.id)
    role = context.roles.create_role(Role(key="admin", name="Admin"))
    context.access.grant_application_role(access_id=access.id, role_id=role.id)

    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )
    response = client.get("/")

    assert response.status_code == 200
    assert "Gebruikersbeheer" in response.text
    assert 'href="/admin/users"' in response.text


def test_admin_users_requires_active_admin_role(monkeypatch):
    client, context = _client(monkeypatch)
    _create_user(context, "admin@example.com", "correct-password")
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get("/admin/users")

    assert response.status_code == 403


def test_admin_users_list_shows_users_for_admin(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    _create_user(context, "worker@example.com", "password")
    _grant_user_administration_admin(context, admin.id)
    _login(client)

    response = client.get("/admin/users")

    assert response.status_code == 200
    assert "Gebruikersbeheer" in response.text
    assert "admin@example.com" in response.text
    assert "worker@example.com" in response.text


def test_admin_create_user_form_and_post(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    _grant_user_administration_admin(context, admin.id)
    _login(client)

    form_response = client.get("/admin/users/new")
    post_response = client.post(
        "/admin/users/new",
        data={
            "email_address": "new@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "temporary-password",
            "is_active": "on",
        },
    )
    created = context.users.get_user_by_email("new@example.com")

    assert form_response.status_code == 200
    assert "Gebruiker toevoegen" in form_response.text
    assert post_response.status_code == 302
    assert post_response.headers["Location"] == f"/admin/users/{created.id}/access"
    assert created.first_name == "New"
    assert created.last_name == "User"
    assert created.is_active
    assert service.verify_password(created.password_hash, "temporary-password")


def test_admin_create_user_validates_required_fields(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    _grant_user_administration_admin(context, admin.id)
    _login(client)

    response = client.post(
        "/admin/users/new",
        data={"email_address": "", "password": ""},
    )

    assert response.status_code == 400
    assert "E-mailadres is verplicht." in response.text
    assert "Standaard wachtwoord is verplicht." in response.text


def test_admin_edit_user_updates_user(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    worker = _create_user(context, "worker@example.com", "password")
    _grant_user_administration_admin(context, admin.id)
    _login(client)

    response = client.post(
        f"/admin/users/{worker.id}/edit",
        data={
            "email_address": "worker.updated@example.com",
            "first_name": "Worker",
            "last_name": "Updated",
        },
    )
    updated = context.users.get_user_by_id(worker.id)

    assert response.status_code == 302
    assert response.headers["Location"] == "/admin/users"
    assert updated.email_address == "worker.updated@example.com"
    assert updated.first_name == "Worker"
    assert updated.last_name == "Updated"
    assert not updated.is_active


def test_admin_reset_password(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    worker = _create_user(context, "worker@example.com", "old-password")
    _grant_user_administration_admin(context, admin.id)
    _login(client)

    response = client.post(
        f"/admin/users/{worker.id}/reset-password",
        data={"password": "new-password"},
    )
    updated = context.users.get_user_by_id(worker.id)

    assert response.status_code == 302
    assert response.headers["Location"] == f"/admin/users/{worker.id}/edit"
    assert service.verify_password(updated.password_hash, "new-password")


def test_admin_user_access_form_updates_access_and_roles(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    worker = _create_user(context, "worker@example.com", "password")
    _grant_user_administration_admin(context, admin.id)
    kippen = _create_application(context, "kippen", "Kippen", "/kippen", "app", 10)
    worker_role = context.roles.create_role(Role(key="worker", name="Worker"))
    _login(client)

    form_response = client.get(f"/admin/users/{worker.id}/access")
    post_response = client.post(
        f"/admin/users/{worker.id}/access",
        data={
            f"application_{kippen.id}": "on",
            f"role_{kippen.id}_{worker_role.id}": "on",
        },
    )
    access = context.access.get_user_application_access(
        user_id=worker.id,
        application_id=kippen.id,
    )
    roles = context.access.list_user_application_roles(access.id)

    assert form_response.status_code == 200
    assert "Applicatietoegang" in form_response.text
    assert post_response.status_code == 302
    assert post_response.headers["Location"] == f"/admin/users/{worker.id}/access"
    assert access.is_active
    assert [role.key for role in roles] == ["worker"]


def test_admin_user_access_form_revokes_access(monkeypatch):
    client, context = _client(monkeypatch)
    admin = _create_user(context, "admin@example.com", "correct-password")
    worker = _create_user(context, "worker@example.com", "password")
    _grant_user_administration_admin(context, admin.id)
    kippen = _create_application(context, "kippen", "Kippen", "/kippen", "app", 10)
    context.access.grant_application_access(user_id=worker.id, application_id=kippen.id)
    _login(client)

    response = client.post(f"/admin/users/{worker.id}/access", data={})
    access = context.access.get_user_application_access(
        user_id=worker.id,
        application_id=kippen.id,
    )

    assert response.status_code == 302
    assert not access.is_active


def test_logout_clears_session(monkeypatch):
    client, context = _client(monkeypatch)
    _create_user(context, "admin@example.com", "correct-password")
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.post("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert client.get("/").status_code == 302


def test_auth_verify_requires_session(monkeypatch):
    client, _context = _client(monkeypatch)

    response = client.get("/auth/verify")

    assert response.status_code == 401


def test_auth_verify_allows_authenticated_unmapped_path(monkeypatch):
    client, context = _client(monkeypatch)
    _create_user(context, "admin@example.com", "correct-password")
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get("/auth/verify", headers={"X-Forwarded-Uri": "/"})

    assert response.status_code == 204


def test_auth_verify_is_application_aware(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    tanken = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        10,
    )
    _create_application(
        context,
        "dashboard_klauwgezondheid",
        "Klauwgezondheid",
        "/klauwgezondheid",
        "dashboard",
        20,
    )
    _grant_access(context, user.id, tanken.id)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    allowed = client.get(
        "/auth/verify",
        headers={"X-Forwarded-Uri": "/tank-terminal"},
    )
    denied = client.get(
        "/auth/verify",
        headers={"X-Forwarded-Uri": "/klauwgezondheid"},
    )

    assert allowed.status_code == 204
    assert denied.status_code == 403


def test_forward_auth_allows_dashboard_manifest_when_user_has_access(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    klauwgezondheid = _create_application(
        context,
        "dashboard_klauwgezondheid",
        "Klauwgezondheid",
        "/klauwgezondheid",
        "dashboard",
        10,
    )
    _grant_access(context, user.id, klauwgezondheid.id)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get(
        "/auth/verify",
        headers={"X-Forwarded-Uri": "/klauwgezondheid/manifest.json"},
    )

    assert response.status_code == 204


def test_forward_auth_uses_original_uri_fallback(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    tanken = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        10,
    )
    _grant_access(context, user.id, tanken.id)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get(
        "/auth/verify",
        headers={"X-Original-Uri": "/tank-terminal/?view=transactions"},
    )

    assert response.status_code == 204


def test_forward_auth_uses_path_query_fallback(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    tanken = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        10,
    )
    _grant_access(context, user.id, tanken.id)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get("/auth/verify?path=/tank-terminal")

    assert response.status_code == 204


def test_forward_auth_denies_inactive_access(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    tanken = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        10,
    )
    _grant_access(context, user.id, tanken.id, is_active=False)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get(
        "/auth/verify",
        headers={"X-Forwarded-Uri": "/tank-terminal"},
    )

    assert response.status_code == 403


def test_auth_verify_rejects_inactive_application(monkeypatch):
    client, context = _client(monkeypatch)
    user = _create_user(context, "admin@example.com", "correct-password")
    application = _create_application(
        context,
        "dashboard_tank_terminal",
        "Tanken",
        "/tank-terminal",
        "dashboard",
        10,
        is_active=False,
    )
    _grant_access(context, user.id, application.id)
    client.post(
        "/login",
        data={
            "email_address": "admin@example.com",
            "password": "correct-password",
        },
    )

    response = client.get(
        "/auth/verify",
        headers={"X-Forwarded-Uri": "/tank-terminal"},
    )

    assert response.status_code == 403


def test_application_key_for_path_maps_known_prefixes():
    assert portal_app.application_key_for_path("/kippen/dashboard") == "kippen"
    assert (
        portal_app.application_key_for_path("/klauwgezondheid/?query=true")
        == "dashboard_klauwgezondheid"
    )
    assert (
        portal_app.application_key_for_path("/tank-terminal")
        == "dashboard_tank_terminal"
    )
    assert (
        portal_app.application_key_for_path(
            "https://app.gebroedersvroege.nl/tank-terminal/manifest.json"
        )
        == "dashboard_tank_terminal"
    )
    assert portal_app.application_key_for_path("/admin/users") == "user_administration"
    assert portal_app.application_key_for_path("/") is None


class _PortalTestContext:
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


def _client(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET_KEY", "test-secret")
    context = _PortalTestContext()
    app = portal_app.create_app(session_factory=context.session_factory)
    app.config.update(TESTING=True)
    return app.test_client(), context


def _login(client, email_address: str = "admin@example.com"):
    return client.post(
        "/login",
        data={
            "email_address": email_address,
            "password": "correct-password",
        },
    )


def _create_user(
    context: _PortalTestContext,
    email_address: str,
    password: str,
) -> User:
    return context.users.create_user(
        User(
            email_address=email_address,
            password_hash=service.hash_password(password),
        )
    )


def _create_application(
    context: _PortalTestContext,
    key: str,
    name: str,
    url: str,
    category: str,
    display_order: int,
    *,
    is_active: bool = True,
) -> Application:
    return context.applications.create_application(
        Application(
            key=key,
            name=name,
            url=url,
            category=category,
            display_order=display_order,
            is_active=is_active,
        )
    )


def _grant_access(
    context: _PortalTestContext,
    user_id: int,
    application_id: int,
    *,
    is_active: bool = True,
):
    return context.access.grant_application_access(
        user_id=user_id,
        application_id=application_id,
        is_active=is_active,
    )


def _grant_user_administration_admin(
    context: _PortalTestContext,
    user_id: int,
) -> None:
    application = _create_application(
        context,
        "user_administration",
        "Gebruikersbeheer",
        "/admin/users",
        "admin",
        100,
    )
    role = context.roles.get_role_by_key("admin")
    if role is None:
        role = context.roles.create_role(Role(key="admin", name="Admin"))

    access = _grant_access(context, user_id, application.id)
    context.access.grant_application_role(access_id=access.id, role_id=role.id)
