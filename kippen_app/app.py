"""Flask app factory for the kippen registratie app."""

from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

from flask import Flask, abort, current_app, flash, redirect, render_template
from flask import request, session, url_for
from flask import send_file

from database import database
from database.repositories.laying_hens_repository import (
    DailyLayingRegistrationsRepository,
)
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
from database.repositories.laying_hens_repository import FlocksRepository
from database.repositories.laying_hens_repository import OutsideNestEggRoundsRepository
from kippen_app import auth
from kippen_app import config
from kippen_app import daily
from kippen_app import dead_hens
from kippen_app import exports
from kippen_app import flocks
from kippen_app import outside_nest


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

    @app.get("/")
    def root_index():
        return redirect(url_for("index"))

    @app.get("/kippen/dashboard")
    @login_required
    def dashboard():
        repositories = _repositories()
        today = date.today()
        today_registration = repositories.daily.get_by_house_and_date(today)
        active_flock = repositories.flocks.get_current_active_flock()
        return render_template(
            "dashboard.html",
            today=today,
            today_registration=today_registration,
            active_flock=active_flock,
            dead_hens_today=repositories.dead_hens.count_for_date(today),
            outside_nest_eggs_today=repositories.outside_nest_rounds.count_for_date(
                today,
            ),
            recent_daily_registrations=repositories.daily.list_recent(limit=7),
            recent_dead_hens=repositories.dead_hens.list_recent(limit=5),
            recent_outside_nest_rounds=repositories.outside_nest_rounds.list_recent(
                limit=5,
            ),
        )

    @app.get("/kippen/flocks")
    @login_required
    def flocks_list():
        return render_template(
            "flocks.html",
            flocks=_repositories().flocks.list_flocks(),
        )

    @app.get("/kippen/flocks/new")
    @login_required
    def flocks_new():
        return render_template(
            "flock_form.html",
            title="Koppel toevoegen",
            values=flocks.default_values(),
            errors={},
            action_url=url_for("flocks_new_post"),
            submit_label="Koppel opslaan",
        )

    @app.post("/kippen/flocks/new")
    @login_required
    def flocks_new_post():
        repositories = _repositories()
        flock, errors, values = flocks.build_flock_from_form(request.form)
        if errors or flock is None:
            return (
                render_template(
                    "flock_form.html",
                    title="Koppel toevoegen",
                    values=values,
                    errors=errors,
                    action_url=url_for("flocks_new_post"),
                    submit_label="Koppel opslaan",
                ),
                400,
            )

        try:
            saved_flock = repositories.flocks.create_flock(flock)
        except ValueError as exc:
            errors["form"] = str(exc)
            return (
                render_template(
                    "flock_form.html",
                    title="Koppel toevoegen",
                    values=values,
                    errors=errors,
                    action_url=url_for("flocks_new_post"),
                    submit_label="Koppel opslaan",
                ),
                400,
            )

        flash("Koppel opgeslagen.", "success")
        return redirect(url_for("flocks_detail", flock_id=saved_flock.id))

    @app.get("/kippen/flocks/<int:flock_id>")
    @login_required
    def flocks_detail(flock_id: int):
        flock = _repositories().flocks.get_flock_by_id(flock_id)
        if flock is None:
            abort(404)

        return render_template("flock_detail.html", flock=flock, end_date_error=None)

    @app.get("/kippen/flocks/<int:flock_id>/edit")
    @login_required
    def flocks_edit(flock_id: int):
        flock = _repositories().flocks.get_flock_by_id(flock_id)
        if flock is None:
            abort(404)

        return render_template(
            "flock_form.html",
            title="Koppel aanpassen",
            values=flocks.values_from_flock(flock),
            errors={},
            action_url=url_for("flocks_edit_post", flock_id=flock.id),
            submit_label="Wijzigingen opslaan",
        )

    @app.post("/kippen/flocks/<int:flock_id>/edit")
    @login_required
    def flocks_edit_post(flock_id: int):
        repositories = _repositories()
        existing_flock = repositories.flocks.get_flock_by_id(flock_id)
        if existing_flock is None:
            abort(404)

        flock, errors, values = flocks.build_flock_from_form(
            request.form,
            existing_flock=existing_flock,
        )
        if errors or flock is None:
            return (
                render_template(
                    "flock_form.html",
                    title="Koppel aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for("flocks_edit_post", flock_id=flock_id),
                    submit_label="Wijzigingen opslaan",
                ),
                400,
            )

        try:
            saved_flock = repositories.flocks.update_flock(flock_id, flock)
        except ValueError as exc:
            errors["form"] = str(exc)
            return (
                render_template(
                    "flock_form.html",
                    title="Koppel aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for("flocks_edit_post", flock_id=flock_id),
                    submit_label="Wijzigingen opslaan",
                ),
                400,
            )

        if saved_flock is None:
            abort(404)

        flash("Koppel aangepast.", "success")
        return redirect(url_for("flocks_detail", flock_id=saved_flock.id))

    @app.post("/kippen/flocks/<int:flock_id>/archive")
    @login_required
    def flocks_archive(flock_id: int):
        flock = _repositories().flocks.archive_flock(flock_id)
        if flock is None:
            abort(404)

        flash("Koppel gearchiveerd.", "success")
        return redirect(url_for("flocks_detail", flock_id=flock.id))

    @app.post("/kippen/flocks/<int:flock_id>/end-date")
    @login_required
    def flocks_set_end_date(flock_id: int):
        repositories = _repositories()
        flock = repositories.flocks.get_flock_by_id(flock_id)
        if flock is None:
            abort(404)

        end_date, errors, _ = flocks.parse_end_date(request.form)
        if errors or end_date is None:
            return (
                render_template(
                    "flock_detail.html",
                    flock=flock,
                    end_date_error=errors.get("end_date"),
                ),
                400,
            )

        try:
            saved_flock = repositories.flocks.end_flock(flock_id, end_date)
        except ValueError as exc:
            return (
                render_template(
                    "flock_detail.html",
                    flock=flock,
                    end_date_error=str(exc),
                ),
                400,
            )

        if saved_flock is None:
            abort(404)

        flash("Einddatum opgeslagen.", "success")
        return redirect(url_for("flocks_detail", flock_id=saved_flock.id))

    @app.get("/kippen/daily/new")
    @login_required
    def daily_new():
        repositories = _repositories()
        registration_date = _get_requested_date()
        active_flock = repositories.flocks.get_active_flock_for_date(registration_date)
        return render_template(
            "daily_form.html",
            title="Dagregistratie invullen",
            values=daily.default_values(registration_date),
            errors={},
            action_url=url_for("daily_new_post"),
            submit_label="Opslaan",
            dead_hens_count=repositories.dead_hens.count_for_date(registration_date),
            active_flock=active_flock,
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
                    active_flock=_active_flock_for_values(repositories.flocks, values),
                ),
                400,
            )

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.registration_date,
            house_id=registration.house_id,
        )
        if active_flock is None:
            errors["form"] = _missing_active_flock_message(registration.house_id)
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
                    active_flock=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
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
            active_flock=repositories.flocks.get_active_flock_for_date(
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
                    active_flock=_active_flock_for_values(repositories.flocks, values),
                ),
                400,
            )

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.registration_date,
            house_id=registration.house_id,
        )
        if active_flock is None:
            errors["form"] = _missing_active_flock_message(registration.house_id)
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
                    active_flock=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
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
        active_flock = _repositories().flocks.get_active_flock_for_date(date.today())
        return render_template(
            "dead_hen_form.html",
            values=dead_hens.default_values(datetime.now()),
            errors={},
            stable_sides=dead_hens.STABLE_SIDES,
            walkways=dead_hens.WALKWAYS,
            found_places=dead_hens.FOUND_PLACES,
            action_url=url_for("dead_hens_new_post"),
            active_flock=active_flock,
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
                    active_flock=_active_flock_for_datetime_values(
                        repositories.flocks,
                        values,
                        "found_at",
                    ),
                ),
                400,
            )

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.found_at.date(),
            house_id=registration.house_id,
        )
        if active_flock is None:
            errors["form"] = _missing_active_flock_message(registration.house_id)
            return (
                render_template(
                    "dead_hen_form.html",
                    values=values,
                    errors=errors,
                    stable_sides=dead_hens.STABLE_SIDES,
                    walkways=dead_hens.WALKWAYS,
                    found_places=dead_hens.FOUND_PLACES,
                    action_url=url_for("dead_hens_new_post"),
                    active_flock=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
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

    @app.get("/kippen/outside-nest-rounds/new")
    @login_required
    def outside_nest_rounds_new():
        active_flock = _repositories().flocks.get_active_flock_for_date(date.today())
        return render_template(
            "outside_nest_round_form.html",
            values=outside_nest.default_values(datetime.now()),
            errors={},
            action_url=url_for("outside_nest_rounds_new_post"),
            active_flock=active_flock,
        )

    @app.post("/kippen/outside-nest-rounds/new")
    @login_required
    def outside_nest_rounds_new_post():
        repositories = _repositories()
        egg_round, errors, values = outside_nest.build_outside_nest_round_from_form(
            request.form,
            registered_by=session.get("kippen_username"),
        )
        if errors or egg_round is None:
            return (
                render_template(
                    "outside_nest_round_form.html",
                    values=values,
                    errors=errors,
                    action_url=url_for("outside_nest_rounds_new_post"),
                    active_flock=_active_flock_for_datetime_values(
                        repositories.flocks,
                        values,
                        "round_at",
                    ),
                ),
                400,
            )

        active_flock = repositories.flocks.get_active_flock_for_date(
            egg_round.round_at.date(),
            house_id=egg_round.house_id,
        )
        if active_flock is None:
            errors["form"] = _missing_active_flock_message(egg_round.house_id)
            return (
                render_template(
                    "outside_nest_round_form.html",
                    values=values,
                    errors=errors,
                    action_url=url_for("outside_nest_rounds_new_post"),
                    active_flock=None,
                ),
                400,
            )

        egg_round.flock_id = active_flock.id
        repositories.outside_nest_rounds.create_outside_nest_egg_round(egg_round)
        flash("Buitennest ronde opgeslagen.", "success")
        return redirect(url_for("outside_nest_rounds_list"))

    @app.get("/kippen/outside-nest-rounds")
    @login_required
    def outside_nest_rounds_list():
        return render_template(
            "outside_nest_rounds.html",
            rounds=_repositories().outside_nest_rounds.list_recent(limit=100),
        )

    @app.post("/kippen/outside-nest-rounds/<int:round_id>/delete")
    @login_required
    def outside_nest_rounds_delete(round_id: int):
        deleted = _repositories().outside_nest_rounds.delete_outside_nest_egg_round(
            round_id,
        )
        if not deleted:
            abort(404)

        flash("Buitennest ronde verwijderd.", "success")
        return redirect(url_for("outside_nest_rounds_list"))

    @app.get("/kippen/week")
    @login_required
    def week_current():
        iso_year, iso_week, _ = date.today().isocalendar()
        return redirect(url_for("week_overview", year=iso_year, week=iso_week))

    @app.get("/kippen/week/<int:year>/<int:week>")
    @login_required
    def week_overview(year: int, week: int):
        rows = _week_rows(year, week)

        return render_template(
            "week.html",
            year=year,
            week=week,
            previous_week=_offset_week(year, week, -1),
            next_week=_offset_week(year, week, 1),
            rows=rows,
            totals=_week_totals(rows),
        )

    @app.get("/kippen/week/<int:year>/<int:week>/export.xlsx")
    @login_required
    def week_export_xlsx(year: int, week: int):
        rows = _week_rows(year, week)
        output = exports.weekly_calendar_xlsx(
            year=year,
            week=week,
            rows=rows,
            totals=_week_totals(rows),
        )
        return send_file(
            output,
            as_attachment=True,
            download_name=f"legkalender-week-{year}-{week:02d}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    @app.get("/kippen/week/<int:year>/<int:week>/export.pdf")
    @login_required
    def week_export_pdf(year: int, week: int):
        rows = _week_rows(year, week)
        output = exports.weekly_calendar_pdf(
            year=year,
            week=week,
            rows=rows,
            totals=_week_totals(rows),
        )
        return send_file(
            output,
            as_attachment=True,
            download_name=f"legkalender-week-{year}-{week:02d}.pdf",
            mimetype="application/pdf",
        )

    @app.get("/kippen/export/<record_type>.csv")
    @login_required
    def raw_records_csv(record_type: str):
        repositories = _repositories()
        if record_type == "daily":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "registration_date",
                    "weekday",
                    "first_quality_eggs",
                    "second_quality_eggs",
                    "total_eggs",
                    "water_liters",
                    "feed_kg",
                    "notes",
                    "created_by",
                ],
                [
                    [
                        item.id,
                        item.house_id,
                        item.flock_id,
                        item.registration_date,
                        item.weekday,
                        item.first_quality_eggs,
                        item.second_quality_eggs,
                        item.total_eggs,
                        item.water_liters,
                        item.feed_kg,
                        item.notes,
                        item.created_by,
                    ]
                    for item in repositories.daily.list_all()
                ],
            )
        elif record_type == "dead-hens":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "found_at",
                    "count",
                    "stable_side",
                    "section_number",
                    "walkway",
                    "found_place",
                    "suspected_cause",
                    "observations",
                    "registered_by",
                ],
                [
                    [
                        item.id,
                        item.house_id,
                        item.flock_id,
                        item.found_at,
                        item.count,
                        item.stable_side,
                        item.section_number,
                        item.walkway,
                        item.found_place,
                        item.suspected_cause,
                        item.observations,
                        item.registered_by,
                    ]
                    for item in repositories.dead_hens.list_all()
                ],
            )
        elif record_type == "outside-nest-rounds":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "round_at",
                    "egg_count",
                    "notes",
                    "registered_by",
                ],
                [
                    [
                        item.id,
                        item.house_id,
                        item.flock_id,
                        item.round_at,
                        item.egg_count,
                        item.notes,
                        item.registered_by,
                    ]
                    for item in repositories.outside_nest_rounds.list_all()
                ],
            )
        else:
            abort(404)

        return send_file(
            output,
            as_attachment=True,
            download_name=f"kippen-{record_type}.csv",
            mimetype="text/csv",
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
        self.flocks = FlocksRepository(session_factory)
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


def _active_flock_for_values(
    repository: FlocksRepository,
    values: dict[str, str],
):
    try:
        registration_date = date.fromisoformat(values.get("registration_date", ""))
    except ValueError:
        return None

    return repository.get_active_flock_for_date(
        registration_date,
        house_id=values.get("house_id", "main") or "main",
    )


def _active_flock_for_datetime_values(
    repository: FlocksRepository,
    values: dict[str, str],
    field_name: str,
):
    try:
        registration_datetime = datetime.fromisoformat(values.get(field_name, ""))
    except ValueError:
        return None

    return repository.get_active_flock_for_date(
        registration_datetime.date(),
        house_id=values.get("house_id", "main") or "main",
    )


def _missing_active_flock_message(house_id: str) -> str:
    return (
        "Geen actief koppel gevonden voor deze datum in stal "
        f"{house_id}. Maak eerst een actief koppel aan."
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


def _week_rows(year: int, week: int) -> list[dict[str, object]]:
    week_days = _week_days(year, week)
    if week_days is None:
        abort(404)

    repositories = _repositories()
    registrations = repositories.daily.list_between(week_days[0], week_days[-1])
    registrations_by_date = {
        registration.registration_date: registration for registration in registrations
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
                "outside_nest_egg_count": (
                    repositories.outside_nest_rounds.count_for_date(day)
                ),
            }
        )

    return rows


def _week_totals(rows: list[dict[str, object]]) -> dict[str, float]:
    totals = {
        "first_quality_eggs": 0,
        "second_quality_eggs": 0,
        "total_eggs": 0,
        "dead_hens_count": 0,
        "outside_nest_egg_count": 0,
        "water_liters": 0.0,
        "feed_kg": 0.0,
    }
    for row in rows:
        registration = row["registration"]
        totals["dead_hens_count"] += int(row["dead_hens_count"])
        totals["outside_nest_egg_count"] += int(row["outside_nest_egg_count"])
        if registration is None:
            continue

        totals["first_quality_eggs"] += registration.first_quality_eggs
        totals["second_quality_eggs"] += registration.second_quality_eggs
        totals["total_eggs"] += registration.total_eggs
        totals["water_liters"] += registration.water_liters or 0
        totals["feed_kg"] += registration.feed_kg or 0

    return totals
