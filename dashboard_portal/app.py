"""Flask app factory for the central application portal."""

from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse

from flask import Flask, abort, flash, redirect, render_template, request, session
from flask import url_for

from dashboard_portal import config
from database.models.auth import User
from database import database
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from shared_auth import service
from shared_auth.service import SharedAuthService


PATH_APPLICATION_KEYS = [
    ("/admin", "user_administration"),
    ("/kippen", "kippen"),
    ("/klauwgezondheid", "dashboard_klauwgezondheid"),
    ("/tank-terminal", "dashboard_tank_terminal"),
]


def create_app(session_factory=None) -> Flask:
    """Create and configure the central application portal."""
    portal_config = config.load_dashboard_portal_config()
    session_factory = session_factory or database.get_session
    auth_service = _create_auth_service(session_factory)
    users_repository = UsersRepository(session_factory)
    applications_repository = ApplicationsRepository(session_factory)
    roles_repository = RolesRepository(session_factory)
    access_repository = UserApplicationAccessRepository(session_factory)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=portal_config.secret_key,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=portal_config.session_hours),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=portal_config.cookie_secure,
    )

    @app.get("/")
    def index():
        user = auth_service.get_active_user(session.get("user_id"))
        if user is None:
            session.clear()
            return redirect(url_for("login"))

        return render_template(
            "dashboards.html",
            applications=auth_service.list_accessible_applications(user.id),
            user=user,
        )

    @app.get("/login")
    def login():
        return render_template("login.html", error=None)

    @app.post("/login")
    def login_post():
        email_address = request.form.get("email_address") or request.form.get(
            "username",
            "",
        )
        password = request.form.get("password", "")
        user = auth_service.authenticate_user(email_address, password)

        if user is None:
            return (
                render_template(
                    "login.html",
                    error="E-mailadres of wachtwoord is onjuist.",
                ),
                401,
            )

        session.clear()
        session.permanent = True
        session["user_id"] = user.id
        session["email_address"] = user.email_address
        session["display_name"] = _display_name(user)
        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/auth/verify")
    def verify_auth():
        user = auth_service.get_active_user(session.get("user_id"))
        if user is None:
            return "", 401

        application_key = application_key_for_path(_forwarded_path())
        if application_key is None:
            return "", 204

        if auth_service.user_can_access_application(user.id, application_key):
            return "", 204

        return "", 403

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/admin/users")
    def admin_users_list():
        _require_user_administration_admin(auth_service)
        return render_template(
            "admin_users.html",
            users=users_repository.list_users(),
        )

    @app.get("/admin/users/new")
    def admin_users_new():
        _require_user_administration_admin(auth_service)
        return render_template(
            "admin_user_form.html",
            title="Gebruiker toevoegen",
            values={},
            errors={},
            action_url=url_for("admin_users_new_post"),
            submit_label="Gebruiker opslaan",
            show_password=True,
        )

    @app.post("/admin/users/new")
    def admin_users_new_post():
        _require_user_administration_admin(auth_service)
        values = _user_form_values(request.form)
        errors = _validate_user_form(values, require_password=True)
        if users_repository.get_user_by_email(values["email_address"]) is not None:
            errors["email_address"] = "Dit e-mailadres bestaat al."

        if errors:
            return (
                render_template(
                    "admin_user_form.html",
                    title="Gebruiker toevoegen",
                    values=values,
                    errors=errors,
                    action_url=url_for("admin_users_new_post"),
                    submit_label="Gebruiker opslaan",
                    show_password=True,
                ),
                400,
            )

        user = users_repository.create_user(
            User(
                email_address=values["email_address"],
                first_name=values["first_name"],
                last_name=values["last_name"],
                password_hash=service.hash_password(values["password"]),
                is_active=values["is_active"],
            )
        )
        flash("Gebruiker opgeslagen.", "success")
        return redirect(url_for("admin_user_access", user_id=user.id))

    @app.get("/admin/users/<int:user_id>/edit")
    def admin_users_edit(user_id: int):
        _require_user_administration_admin(auth_service)
        user = users_repository.get_user_by_id(user_id)
        if user is None:
            abort(404)

        return render_template(
            "admin_user_form.html",
            title="Gebruiker aanpassen",
            values=_values_from_user(user),
            errors={},
            action_url=url_for("admin_users_edit_post", user_id=user.id),
            submit_label="Wijzigingen opslaan",
            show_password=False,
        )

    @app.post("/admin/users/<int:user_id>/edit")
    def admin_users_edit_post(user_id: int):
        _require_user_administration_admin(auth_service)
        user = users_repository.get_user_by_id(user_id)
        if user is None:
            abort(404)

        values = _user_form_values(request.form)
        errors = _validate_user_form(values, require_password=False)
        existing_user = users_repository.get_user_by_email(values["email_address"])
        if existing_user is not None and existing_user.id != user.id:
            errors["email_address"] = "Dit e-mailadres bestaat al."

        if errors:
            return (
                render_template(
                    "admin_user_form.html",
                    title="Gebruiker aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for("admin_users_edit_post", user_id=user.id),
                    submit_label="Wijzigingen opslaan",
                    show_password=False,
                ),
                400,
            )

        users_repository.update_user(
            user.id,
            {
                "email_address": values["email_address"],
                "first_name": values["first_name"],
                "last_name": values["last_name"],
                "is_active": values["is_active"],
            },
        )
        flash("Gebruiker aangepast.", "success")
        return redirect(url_for("admin_users_list"))

    @app.post("/admin/users/<int:user_id>/reset-password")
    def admin_users_reset_password(user_id: int):
        _require_user_administration_admin(auth_service)
        user = users_repository.get_user_by_id(user_id)
        if user is None:
            abort(404)

        password = request.form.get("password", "")
        if password.strip() == "":
            flash("Nieuw wachtwoord is verplicht.", "danger")
            return redirect(url_for("admin_users_edit", user_id=user.id))

        users_repository.set_user_password_hash(
            user.id,
            service.hash_password(password),
        )
        flash("Wachtwoord aangepast.", "success")
        return redirect(url_for("admin_users_edit", user_id=user.id))

    @app.get("/admin/users/<int:user_id>/access")
    def admin_user_access(user_id: int):
        _require_user_administration_admin(auth_service)
        user = users_repository.get_user_by_id(user_id)
        if user is None:
            abort(404)

        return render_template(
            "admin_user_access.html",
            user=user,
            application_access=_application_access_rows(
                user.id,
                applications_repository,
                roles_repository,
                access_repository,
            ),
        )

    @app.post("/admin/users/<int:user_id>/access")
    def admin_user_access_post(user_id: int):
        _require_user_administration_admin(auth_service)
        user = users_repository.get_user_by_id(user_id)
        if user is None:
            abort(404)

        _update_application_access_from_form(
            user.id,
            request.form,
            applications_repository,
            roles_repository,
            access_repository,
        )
        flash("Applicatietoegang aangepast.", "success")
        return redirect(url_for("admin_user_access", user_id=user.id))

    return app


def application_key_for_path(path: str) -> Optional[str]:
    """Return the application key that owns a request path."""
    normalized_path = _normalize_path(path)
    for prefix, application_key in PATH_APPLICATION_KEYS:
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return application_key

    return None


def _require_user_administration_admin(auth_service: SharedAuthService):
    user_id = session.get("user_id")
    user = auth_service.get_active_user(user_id)
    if user is None:
        abort(401)
    if not auth_service.user_has_application_role(
        user.id,
        "user_administration",
        "admin",
    ):
        abort(403)

    return user


def _create_auth_service(session_factory) -> SharedAuthService:
    return SharedAuthService(
        users_repository=UsersRepository(session_factory),
        applications_repository=ApplicationsRepository(session_factory),
        roles_repository=RolesRepository(session_factory),
        access_repository=UserApplicationAccessRepository(session_factory),
    )


def _forwarded_path() -> str:
    forwarded_uri = (
        request.headers.get("X-Forwarded-Uri")
        or request.headers.get("X-Original-Uri")
        or request.args.get("path")
        or request.path
    )
    return forwarded_uri


def _normalize_path(path: str) -> str:
    parsed_path = urlparse(path).path
    if not parsed_path.startswith("/"):
        parsed_path = f"/{parsed_path}"

    if parsed_path != "/" and parsed_path.endswith("/"):
        parsed_path = parsed_path.rstrip("/")

    return parsed_path


def _display_name(user) -> str:
    parts = [
        part
        for part in [user.first_name, user.last_name]
        if part is not None and part.strip()
    ]
    if parts:
        return " ".join(parts)

    return user.email_address


def _user_form_values(form_data) -> dict[str, object]:
    return {
        "email_address": form_data.get("email_address", "").strip(),
        "first_name": form_data.get("first_name", "").strip() or None,
        "last_name": form_data.get("last_name", "").strip() or None,
        "password": form_data.get("password", ""),
        "is_active": form_data.get("is_active") == "on",
    }


def _validate_user_form(
    values: dict[str, object],
    *,
    require_password: bool,
) -> dict[str, str]:
    errors = {}
    email_address = str(values.get("email_address") or "").strip()
    password = str(values.get("password") or "")
    if email_address == "":
        errors["email_address"] = "E-mailadres is verplicht."
    if require_password and password.strip() == "":
        errors["password"] = "Standaard wachtwoord is verplicht."

    return errors


def _values_from_user(user: User) -> dict[str, object]:
    return {
        "email_address": user.email_address,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "is_active": user.is_active,
    }


def _application_access_rows(
    user_id: int,
    applications_repository: ApplicationsRepository,
    roles_repository: RolesRepository,
    access_repository: UserApplicationAccessRepository,
) -> list[dict[str, object]]:
    roles = roles_repository.list_roles(active_only=True)
    rows = []
    for application in applications_repository.list_applications():
        access = access_repository.get_user_application_access(
            user_id=user_id,
            application_id=application.id,
        )
        assigned_role_ids = set()
        if access is not None:
            assigned_role_ids = {
                role.id
                for role in access_repository.list_user_application_roles(access.id)
            }

        rows.append(
            {
                "application": application,
                "access": access,
                "roles": roles,
                "assigned_role_ids": assigned_role_ids,
            }
        )

    return rows


def _update_application_access_from_form(
    user_id: int,
    form_data,
    applications_repository: ApplicationsRepository,
    roles_repository: RolesRepository,
    access_repository: UserApplicationAccessRepository,
) -> None:
    roles_by_id = {
        role.id: role for role in roles_repository.list_roles(active_only=True)
    }
    for application in applications_repository.list_applications():
        application_enabled = form_data.get(f"application_{application.id}") == "on"
        access = access_repository.get_user_application_access(
            user_id=user_id,
            application_id=application.id,
        )
        if not application_enabled:
            if access is not None:
                access_repository.revoke_application_access(access.id)
            continue

        if access is None:
            access = access_repository.grant_application_access(
                user_id=user_id,
                application_id=application.id,
            )
        else:
            access = access_repository.update_application_access(
                access.id,
                is_active=True,
            )

        _sync_application_roles(
            access.id, application.id, form_data, roles_by_id, access_repository
        )


def _sync_application_roles(
    access_id: int,
    application_id: int,
    form_data,
    roles_by_id: dict[int, object],
    access_repository: UserApplicationAccessRepository,
) -> None:
    selected_role_ids = {
        role_id
        for role_id in roles_by_id
        if form_data.get(f"role_{application_id}_{role_id}") == "on"
    }
    existing_roles = access_repository.list_user_application_roles(access_id)
    existing_role_ids = {role.id for role in existing_roles}
    for role_id in selected_role_ids - existing_role_ids:
        access_repository.grant_application_role(access_id=access_id, role_id=role_id)
    for role_id in existing_role_ids - selected_role_ids:
        access_repository.revoke_application_role(access_id=access_id, role_id=role_id)
