"""Flask app factory for the kippen registratie app."""

from datetime import date, timedelta
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for

from kippen_app import auth
from kippen_app import config


def create_app() -> Flask:
    """Create and configure the kippen registratie application."""
    app_config = config.load_kippen_app_config()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=app_config.secret_key,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=app_config.session_hours),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app_config.cookie_secure,
    )

    @app.get("/kippen")
    def index():
        return redirect(url_for("dashboard"))

    @app.get("/kippen/dashboard")
    @login_required
    def dashboard():
        return render_template(
            "dashboard.html",
            today=date.today(),
            recent_daily_registrations=[],
            recent_dead_hens=[],
            recent_outside_nest_rounds=[],
        )

    @app.get("/kippen/login")
    def login():
        if session.get("kippen_authenticated"):
            return redirect(url_for("dashboard"))

        return render_template("login.html", error=None)

    @app.post("/kippen/login")
    def login_post():
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if not auth.verify_credentials(username, password, app_config):
            return (
                render_template(
                    "login.html",
                    error="Gebruikersnaam of wachtwoord is onjuist.",
                ),
                401,
            )

        session.clear()
        session.permanent = True
        session["kippen_authenticated"] = True
        session["kippen_username"] = username
        return redirect(url_for("dashboard"))

    @app.post("/kippen/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/kippen/healthz")
    def healthz():
        return {"status": "ok"}

    return app


def login_required(view_func):
    """Require a kippen app login session before serving a route."""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("kippen_authenticated"):
            return redirect(url_for("login"))

        return view_func(*args, **kwargs)

    return wrapped_view
