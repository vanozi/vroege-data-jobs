"""Flask app factory for the dashboard portal."""

from datetime import timedelta

from flask import Flask, redirect, render_template, request, session, url_for

from dashboard_portal import auth
from dashboard_portal import config
from dashboard_portal import registry


def create_app() -> Flask:
    """Create and configure the dashboard portal application."""
    portal_config = config.load_dashboard_portal_config()

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
        if not session.get("portal_authenticated"):
            return redirect(url_for("login"))

        return render_template(
            "dashboards.html",
            dashboards=registry.get_dashboard_links(),
        )

    @app.get("/login")
    def login():
        return render_template("login.html", error=None)

    @app.post("/login")
    def login_post():
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not auth.verify_credentials(username, password, portal_config):
            return (
                render_template(
                    "login.html",
                    error="Gebruikersnaam of wachtwoord is onjuist.",
                ),
                401,
            )

        session.clear()
        session.permanent = True
        session["portal_authenticated"] = True
        session["portal_username"] = username
        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/auth/verify")
    def verify_auth():
        if session.get("portal_authenticated"):
            return "", 204

        return "", 401

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app
