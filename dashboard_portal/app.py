"""Flask app factory for the central application portal."""

from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse

from flask import Flask, redirect, render_template, request, session, url_for

from dashboard_portal import config
from database import database
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
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
    auth_service = _create_auth_service(session_factory or database.get_session)

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

    return app


def application_key_for_path(path: str) -> Optional[str]:
    """Return the application key that owns a request path."""
    normalized_path = _normalize_path(path)
    for prefix, application_key in PATH_APPLICATION_KEYS:
        if normalized_path == prefix or normalized_path.startswith(f"{prefix}/"):
            return application_key

    return None


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
