"""Flask app factory for the kippen registratie app."""

from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

from flask import Flask, abort, current_app, flash, redirect, render_template
from flask import request, session, url_for

from database import database
from database.repositories.laying_hens_repository import (
    DailyLayingRegistrationsRepository,
)
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
from database.repositories.laying_hens_repository import OutsideNestEggRoundsRepository
from kippen_app import auth
from kippen_app import config
from kippen_app import daily
from kippen_app import dead_hens


def create_app(session_factory=None) -> Flask:
    """Create and configure the kippen registratie application."""
    app_config = config.load_kippen_app_config()
    if session_factory is None:
        session_factory = database.get_session

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=app_config.secret_key,
        KIPPEN_SESSION_FACTORY=session_factory,
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
        repositories = _repositories()
        today = date.today()
        today_registration = repositories.daily.get_by_house_and_date(today)
        return render_template(
            "dashboard.html",
            today=today,
            today_registration=today_registration,
            dead_hens_today=repositories.dead_hens.count_for_date(today),
            recent_daily_registrations=repositories.daily.list_recent(limit=7),
            recent_dead_hens=repositories.dead_hens.list_recent(limit=5),
            recent_outside_nest_rounds=repositories.outside_nest_rounds.list_recent(
                limit=5,
            ),
        )

    @app.get("/kippen/daily/new")
    @login_required
    def daily_new():
        registration_date = _get_requested_date()
        return render_template(
            "daily_form.html",
            title="Dagregistratie invullen",
            values=daily.default_values(registration_date),
            errors={},
            action_url=url_for("daily_new_post"),
            submit_label="Opslaan",
            dead_hens_count=_repositories().dead_hens.count_for_date(registration_date),
        )

    @app.post("/kippen/daily/new")
    @login_required
    def daily_new_post():
        repositories = _repositories()
        registration, errors, values = daily.build_daily_registration_from_form(
            request.form,
            created_by=session.get("kippen_username"),
        )
        if errors or registration is None:
            return (
                render_template(
                    "daily_form.html",
                    title="Dagregistratie invullen",
                    values=values,
                    errors=errors,
                    action_url=url_for("daily_new_post"),
                    submit_label="Opslaan",
                    dead_hens_count=_dead_hens_count_for_values(
                        repositories.dead_hens,
                        values,
                    ),
                ),
                400,
            )

        repositories.daily.upsert_daily_registration(registration)
        flash("Dagregistratie opgeslagen.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/kippen/daily/<int:registration_id>/edit")
    @login_required
    def daily_edit(registration_id: int):
        repositories = _repositories()
        registration = repositories.daily.get_daily_registration_by_id(registration_id)
        if registration is None:
            abort(404)

        return render_template(
            "daily_form.html",
            title="Dagregistratie aanpassen",
            values=daily.values_from_registration(registration),
            errors={},
            action_url=url_for("daily_edit_post", registration_id=registration.id),
            submit_label="Wijzigingen opslaan",
            dead_hens_count=repositories.dead_hens.count_for_date(
                registration.registration_date,
                house_id=registration.house_id,
            ),
        )

    @app.post("/kippen/daily/<int:registration_id>/edit")
    @login_required
    def daily_edit_post(registration_id: int):
        repositories = _repositories()
        existing_registration = repositories.daily.get_daily_registration_by_id(
            registration_id,
        )
        if existing_registration is None:
            abort(404)

        registration, errors, values = daily.build_daily_registration_from_form(
            request.form,
            created_by=session.get("kippen_username"),
            existing_registration=existing_registration,
        )
        if errors or registration is None:
            return (
                render_template(
                    "daily_form.html",
                    title="Dagregistratie aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for(
                        "daily_edit_post",
                        registration_id=registration_id,
                    ),
                    submit_label="Wijzigingen opslaan",
                    dead_hens_count=_dead_hens_count_for_values(
                        repositories.dead_hens,
                        values,
                    ),
                ),
                400,
            )

        saved_registration = repositories.daily.update_daily_registration(
            registration_id,
            registration,
        )
        if saved_registration is None:
            abort(404)

        flash("Dagregistratie aangepast.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/kippen/dead-hens/new")
    @login_required
    def dead_hens_new():
        return render_template(
            "dead_hen_form.html",
            values=dead_hens.default_values(datetime.now()),
            errors={},
            stable_sides=dead_hens.STABLE_SIDES,
            walkways=dead_hens.WALKWAYS,
            found_places=dead_hens.FOUND_PLACES,
            action_url=url_for("dead_hens_new_post"),
        )

    @app.post("/kippen/dead-hens/new")
    @login_required
    def dead_hens_new_post():
        repositories = _repositories()
        registration, errors, values = dead_hens.build_dead_hen_registration_from_form(
            request.form,
            registered_by=session.get("kippen_username"),
        )
        if errors or registration is None:
            return (
                render_template(
                    "dead_hen_form.html",
                    values=values,
                    errors=errors,
                    stable_sides=dead_hens.STABLE_SIDES,
                    walkways=dead_hens.WALKWAYS,
                    found_places=dead_hens.FOUND_PLACES,
                    action_url=url_for("dead_hens_new_post"),
                ),
                400,
            )

        repositories.dead_hens.create_dead_hen_registration(registration)
        flash("Dode hen registratie opgeslagen.", "success")
        return redirect(url_for("dead_hens_list"))

    @app.get("/kippen/dead-hens")
    @login_required
    def dead_hens_list():
        return render_template(
            "dead_hens.html",
            registrations=_repositories().dead_hens.list_recent(limit=100),
        )

    @app.post("/kippen/dead-hens/<int:registration_id>/delete")
    @login_required
    def dead_hens_delete(registration_id: int):
        deleted = _repositories().dead_hens.delete_dead_hen_registration(
            registration_id,
        )
        if not deleted:
            abort(404)

        flash("Dode hen registratie verwijderd.", "success")
        return redirect(url_for("dead_hens_list"))

    @app.get("/kippen/week")
    @login_required
    def week_current():
        iso_year, iso_week, _ = date.today().isocalendar()
        return redirect(url_for("week_overview", year=iso_year, week=iso_week))

    @app.get("/kippen/week/<int:year>/<int:week>")
    @login_required
    def week_overview(year: int, week: int):
        week_days = _week_days(year, week)
        if week_days is None:
            abort(404)

        repositories = _repositories()
        registrations = repositories.daily.list_between(week_days[0], week_days[-1])
        registrations_by_date = {
            registration.registration_date: registration
            for registration in registrations
        }
        rows = []
        for day in week_days:
            registration = registrations_by_date.get(day)
            rows.append(
                {
                    "date": day,
                    "weekday": daily.DUTCH_WEEKDAYS[day.weekday()],
                    "registration": registration,
                    "dead_hens_count": repositories.dead_hens.count_for_date(day),
                }
            )

        return render_template(
            "week.html",
            year=year,
            week=week,
            previous_week=_offset_week(year, week, -1),
            next_week=_offset_week(year, week, 1),
            rows=rows,
            totals=_week_totals(rows),
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


class LayingHensRepositories:
    """Small container for laying hens repositories."""

    def __init__(self, session_factory):
        self.daily = DailyLayingRegistrationsRepository(session_factory)
        self.dead_hens = DeadHenRegistrationsRepository(session_factory)
        self.outside_nest_rounds = OutsideNestEggRoundsRepository(session_factory)


def _repositories() -> LayingHensRepositories:
    return LayingHensRepositories(current_app.config["KIPPEN_SESSION_FACTORY"])


def _get_requested_date() -> date:
    raw_date = request.args.get("date", "")
    if raw_date == "":
        return date.today()

    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return date.today()


def _dead_hens_count_for_values(
    repository: DeadHenRegistrationsRepository,
    values: dict[str, str],
) -> int:
    try:
        registration_date = date.fromisoformat(values.get("registration_date", ""))
    except ValueError:
        return 0

    return repository.count_for_date(
        registration_date,
        house_id=values.get("house_id", "main") or "main",
    )


def _week_days(year: int, week: int) -> Optional[list[date]]:
    try:
        first_day = date.fromisocalendar(year, week, 1)
    except ValueError:
        return None

    return [first_day + timedelta(days=offset) for offset in range(7)]


def _offset_week(year: int, week: int, offset: int) -> tuple[int, int]:
    first_day = date.fromisocalendar(year, week, 1)
    target_day = first_day + timedelta(weeks=offset)
    target_year, target_week, _ = target_day.isocalendar()
    return target_year, target_week


def _week_totals(rows: list[dict[str, object]]) -> dict[str, float]:
    totals = {
        "first_quality_eggs": 0,
        "second_quality_eggs": 0,
        "total_eggs": 0,
        "dead_hens_count": 0,
        "water_liters": 0.0,
        "feed_kg": 0.0,
    }
    for row in rows:
        registration = row["registration"]
        totals["dead_hens_count"] += int(row["dead_hens_count"])
        if registration is None:
            continue

        totals["first_quality_eggs"] += registration.first_quality_eggs
        totals["second_quality_eggs"] += registration.second_quality_eggs
        totals["total_eggs"] += registration.total_eggs
        totals["water_liters"] += registration.water_liters or 0
        totals["feed_kg"] += registration.feed_kg or 0

    return totals
