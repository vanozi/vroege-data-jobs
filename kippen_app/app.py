"""Flask app factory for the kippen registratie app."""

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from typing import Optional

from flask import Flask, abort, current_app, flash, redirect, render_template
from flask import request, session, url_for
from flask import send_file

from database import database
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
from database.repositories.laying_hens_repository import (
    EggPackagingWeightConfigsRepository,
)
from database.repositories.laying_hens_repository import (
    EggPalletWeightRegistrationsRepository,
)
from database.repositories.laying_hens_repository import EggRegistrationsRepository
from database.repositories.laying_hens_repository import (
    FeedWaterRegistrationsRepository,
)
from database.repositories.laying_hens_repository import FlocksRepository
from database.repositories.laying_hens_repository import OutsideNestEggRoundsRepository
from kippen_app import config
from kippen_app import dead_hens
from kippen_app import eggs
from kippen_app import exports
from kippen_app import feed_water
from kippen_app import flock_age
from kippen_app import flocks
from kippen_app import outside_nest
from kippen_app import packaging_weights
from kippen_app import pallet_weights
from kippen_app import weekdays
from shared_auth.service import SharedAuthService


KIPPEN_APPLICATION_KEY = "kippen"
KIPPEN_ADMIN_PREFIXES = (
    "/kippen/flocks",
    "/kippen/packaging-weights",
    "/kippen/export",
)
KIPPEN_WORKER_PREFIXES = (
    "/kippen/eggs",
    "/kippen/feed-water",
    "/kippen/dead-hens",
    "/kippen/outside-nest-rounds",
    "/kippen/pallet-weights",
    "/kippen/week",
)


def create_app(session_factory=None) -> Flask:
    """Create and configure the kippen registratie application."""
    app_config = config.load_kippen_app_config()
    if session_factory is None:
        session_factory = database.get_session

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=app_config.secret_key,
        KIPPEN_SESSION_FACTORY=session_factory,
        KIPPEN_AUTH_SERVICE=_create_auth_service(session_factory),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=app_config.session_hours),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app_config.cookie_secure,
    )

    @app.context_processor
    def inject_kippen_user():
        user = _current_user()
        if user is None:
            return {}

        auth_service = _auth_service()
        is_admin = auth_service.user_has_application_role(
            user.id,
            KIPPEN_APPLICATION_KEY,
            "admin",
        )
        is_worker = auth_service.user_has_application_role(
            user.id,
            KIPPEN_APPLICATION_KEY,
            "worker",
        )
        display_name = _current_username()
        return {
            "kippen_user": {
                "id": user.id,
                "username": display_name,
                "display_name": display_name,
                "is_admin": is_admin,
                "is_worker": is_worker,
            },
        }

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("403.html"), 403

    @app.before_request
    def require_shared_kippen_access():
        if not request.path.startswith("/kippen"):
            return None
        if request.path in {"/kippen/healthz", "/kippen/login"}:
            return None
        if request.path == "/kippen/logout":
            return None

        user = _current_user()
        if user is None:
            return redirect("/login")
        if user.must_change_password:
            return redirect("/change-password")

        auth_service = _auth_service()
        if not auth_service.user_can_access_application(
            user.id,
            KIPPEN_APPLICATION_KEY,
        ):
            abort(403)

        if _path_has_prefix(request.path, KIPPEN_ADMIN_PREFIXES):
            if not auth_service.user_has_application_role(
                user.id,
                KIPPEN_APPLICATION_KEY,
                "admin",
            ):
                abort(403)
            return None

        if _path_has_prefix(request.path, KIPPEN_WORKER_PREFIXES):
            if not auth_service.user_has_any_application_role(
                user.id,
                KIPPEN_APPLICATION_KEY,
                ["admin", "worker"],
            ):
                abort(403)
            return None

        return None

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
        yesterday = today - timedelta(days=1)
        yesterday_egg_registration = repositories.eggs.get_by_house_and_date(yesterday)
        yesterday_feed_water_registration = (
            repositories.feed_water.get_by_house_and_date(yesterday)
        )
        active_flock = repositories.flocks.get_current_active_flock()
        return render_template(
            "dashboard.html",
            today=today,
            yesterday=yesterday,
            yesterday_egg_registration=yesterday_egg_registration,
            yesterday_feed_water_registration=yesterday_feed_water_registration,
            active_flock=active_flock,
            active_flock_age=flock_age.flock_age_context(active_flock, today),
            dead_hens_yesterday=repositories.dead_hens.count_for_date(yesterday),
            outside_nest_eggs_yesterday=repositories.outside_nest_rounds.count_for_date(
                yesterday,
            ),
            recent_egg_registrations=repositories.eggs.list_recent(limit=5),
            recent_feed_water_registrations=repositories.feed_water.list_recent(
                limit=5,
            ),
            recent_dead_hens=repositories.dead_hens.list_recent(limit=5),
            recent_outside_nest_rounds=repositories.outside_nest_rounds.list_recent(
                limit=5,
            ),
            recent_pallet_weights=repositories.pallet_weights.list_recent(limit=5),
            yesterday_average_egg_weight_grams=_average_egg_weight_grams(
                repositories.pallet_weights.list_between(yesterday, yesterday),
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

    @app.get("/kippen/eggs")
    @login_required
    def egg_registrations_list():
        return render_template(
            "egg_registrations.html",
            registrations=_repositories().eggs.list_recent(limit=100),
        )

    @app.get("/kippen/eggs/new")
    @login_required
    def egg_registrations_new():
        repositories = _repositories()
        registration_date = _get_requested_date()
        active_flock = repositories.flocks.get_active_flock_for_date(
            registration_date,
        )
        return render_template(
            "egg_form.html",
            title="Eieren registreren",
            values=eggs.default_values(registration_date),
            errors={},
            action_url=url_for("egg_registrations_new_post"),
            submit_label="Opslaan",
            active_flock=active_flock,
            active_flock_age=flock_age.flock_age_context(
                active_flock,
                registration_date,
            ),
        )

    @app.post("/kippen/eggs/new")
    @login_required
    def egg_registrations_new_post():
        repositories = _repositories()
        registration, errors, values = eggs.build_egg_registration_from_form(
            request.form,
            created_by=_current_username(),
        )
        if errors or registration is None:
            return (
                render_template(
                    "egg_form.html",
                    title="Eieren registreren",
                    values=values,
                    errors=errors,
                    action_url=url_for("egg_registrations_new_post"),
                    submit_label="Opslaan",
                    active_flock=_active_flock_for_values(repositories.flocks, values),
                    active_flock_age=_active_flock_age_for_values(
                        repositories.flocks,
                        values,
                    ),
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
                    "egg_form.html",
                    title="Eieren registreren",
                    values=values,
                    errors=errors,
                    action_url=url_for("egg_registrations_new_post"),
                    submit_label="Opslaan",
                    active_flock=None,
                    active_flock_age=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
        repositories.eggs.upsert_egg_registration(registration)
        flash("Eiregistratie opgeslagen.", "success")
        return redirect(url_for("egg_registrations_list"))

    @app.get("/kippen/eggs/<int:registration_id>/edit")
    @login_required
    def egg_registrations_edit(registration_id: int):
        repositories = _repositories()
        registration = repositories.eggs.get_egg_registration_by_id(registration_id)
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.registration_date,
            house_id=registration.house_id,
        )
        return render_template(
            "egg_form.html",
            title="Eiregistratie aanpassen",
            values=eggs.values_from_registration(registration),
            errors={},
            action_url=url_for(
                "egg_registrations_edit_post",
                registration_id=registration.id,
            ),
            submit_label="Wijzigingen opslaan",
            active_flock=active_flock,
            active_flock_age=_flock_age_for_registration(
                repositories.flocks,
                registration,
            ),
        )

    @app.post("/kippen/eggs/<int:registration_id>/edit")
    @login_required
    def egg_registrations_edit_post(registration_id: int):
        repositories = _repositories()
        existing_registration = repositories.eggs.get_egg_registration_by_id(
            registration_id,
        )
        if existing_registration is None:
            abort(404)
        _require_admin_or_owner(existing_registration)

        registration, errors, values = eggs.build_egg_registration_from_form(
            request.form,
            created_by=_current_username(),
            existing_registration=existing_registration,
        )
        if errors or registration is None:
            return (
                render_template(
                    "egg_form.html",
                    title="Eiregistratie aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for(
                        "egg_registrations_edit_post",
                        registration_id=registration_id,
                    ),
                    submit_label="Wijzigingen opslaan",
                    active_flock=_active_flock_for_values(repositories.flocks, values),
                    active_flock_age=_active_flock_age_for_values(
                        repositories.flocks,
                        values,
                    ),
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
                    "egg_form.html",
                    title="Eiregistratie aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for(
                        "egg_registrations_edit_post",
                        registration_id=registration_id,
                    ),
                    submit_label="Wijzigingen opslaan",
                    active_flock=None,
                    active_flock_age=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
        saved_registration = repositories.eggs.update_egg_registration(
            registration_id,
            registration,
        )
        if saved_registration is None:
            abort(404)

        flash("Eiregistratie aangepast.", "success")
        return redirect(url_for("egg_registrations_list"))

    @app.post("/kippen/eggs/<int:registration_id>/delete")
    @login_required
    def egg_registrations_delete(registration_id: int):
        repositories = _repositories()
        registration = repositories.eggs.get_egg_registration_by_id(registration_id)
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)
        repositories.eggs.delete_egg_registration(registration_id)
        flash("Eiregistratie verwijderd.", "success")
        return redirect(url_for("egg_registrations_list"))

    @app.get("/kippen/feed-water")
    @login_required
    def feed_water_registrations_list():
        return render_template(
            "feed_water_registrations.html",
            registrations=_repositories().feed_water.list_recent(limit=100),
        )

    @app.get("/kippen/feed-water/new")
    @login_required
    def feed_water_registrations_new():
        repositories = _repositories()
        registration_date = _get_requested_date()
        active_flock = repositories.flocks.get_active_flock_for_date(
            registration_date,
        )
        return render_template(
            "feed_water_form.html",
            title="Water en voer registreren",
            values=feed_water.default_values(registration_date),
            errors={},
            action_url=url_for("feed_water_registrations_new_post"),
            submit_label="Opslaan",
            active_flock=active_flock,
            active_flock_age=flock_age.flock_age_context(
                active_flock,
                registration_date,
            ),
        )

    @app.post("/kippen/feed-water/new")
    @login_required
    def feed_water_registrations_new_post():
        repositories = _repositories()
        registration, errors, values = (
            feed_water.build_feed_water_registration_from_form(
                request.form,
                created_by=_current_username(),
            )
        )
        if errors or registration is None:
            return (
                render_template(
                    "feed_water_form.html",
                    title="Water en voer registreren",
                    values=values,
                    errors=errors,
                    action_url=url_for("feed_water_registrations_new_post"),
                    submit_label="Opslaan",
                    active_flock=_active_flock_for_values(repositories.flocks, values),
                    active_flock_age=_active_flock_age_for_values(
                        repositories.flocks,
                        values,
                    ),
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
                    "feed_water_form.html",
                    title="Water en voer registreren",
                    values=values,
                    errors=errors,
                    action_url=url_for("feed_water_registrations_new_post"),
                    submit_label="Opslaan",
                    active_flock=None,
                    active_flock_age=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
        repositories.feed_water.upsert_feed_water_registration(registration)
        flash("Water en voer registratie opgeslagen.", "success")
        return redirect(url_for("feed_water_registrations_list"))

    @app.get("/kippen/feed-water/<int:registration_id>/edit")
    @login_required
    def feed_water_registrations_edit(registration_id: int):
        repositories = _repositories()
        registration = repositories.feed_water.get_feed_water_registration_by_id(
            registration_id,
        )
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.registration_date,
            house_id=registration.house_id,
        )
        return render_template(
            "feed_water_form.html",
            title="Water en voer registratie aanpassen",
            values=feed_water.values_from_registration(registration),
            errors={},
            action_url=url_for(
                "feed_water_registrations_edit_post",
                registration_id=registration.id,
            ),
            submit_label="Wijzigingen opslaan",
            active_flock=active_flock,
            active_flock_age=_flock_age_for_registration(
                repositories.flocks,
                registration,
            ),
        )

    @app.post("/kippen/feed-water/<int:registration_id>/edit")
    @login_required
    def feed_water_registrations_edit_post(registration_id: int):
        repositories = _repositories()
        existing_registration = (
            repositories.feed_water.get_feed_water_registration_by_id(
                registration_id,
            )
        )
        if existing_registration is None:
            abort(404)
        _require_admin_or_owner(existing_registration)

        registration, errors, values = (
            feed_water.build_feed_water_registration_from_form(
                request.form,
                created_by=_current_username(),
                existing_registration=existing_registration,
            )
        )
        if errors or registration is None:
            return (
                render_template(
                    "feed_water_form.html",
                    title="Water en voer registratie aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for(
                        "feed_water_registrations_edit_post",
                        registration_id=registration_id,
                    ),
                    submit_label="Wijzigingen opslaan",
                    active_flock=_active_flock_for_values(repositories.flocks, values),
                    active_flock_age=_active_flock_age_for_values(
                        repositories.flocks,
                        values,
                    ),
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
                    "feed_water_form.html",
                    title="Water en voer registratie aanpassen",
                    values=values,
                    errors=errors,
                    action_url=url_for(
                        "feed_water_registrations_edit_post",
                        registration_id=registration_id,
                    ),
                    submit_label="Wijzigingen opslaan",
                    active_flock=None,
                    active_flock_age=None,
                ),
                400,
            )

        registration.flock_id = active_flock.id
        saved_registration = repositories.feed_water.update_feed_water_registration(
            registration_id,
            registration,
        )
        if saved_registration is None:
            abort(404)

        flash("Water en voer registratie aangepast.", "success")
        return redirect(url_for("feed_water_registrations_list"))

    @app.post("/kippen/feed-water/<int:registration_id>/delete")
    @login_required
    def feed_water_registrations_delete(registration_id: int):
        repositories = _repositories()
        registration = repositories.feed_water.get_feed_water_registration_by_id(
            registration_id,
        )
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)
        repositories.feed_water.delete_feed_water_registration(registration_id)
        flash("Water en voer registratie verwijderd.", "success")
        return redirect(url_for("feed_water_registrations_list"))

    @app.get("/kippen/dead-hens/new")
    @login_required
    def dead_hens_new():
        today = date.today()
        active_flock = _repositories().flocks.get_active_flock_for_date(today)
        return render_template(
            "dead_hen_form.html",
            values=dead_hens.default_values(datetime.now()),
            errors={},
            stable_sides=dead_hens.STABLE_SIDES,
            walkways=dead_hens.WALKWAYS,
            found_places=dead_hens.FOUND_PLACES,
            action_url=url_for("dead_hens_new_post"),
            active_flock=active_flock,
            active_flock_age=flock_age.flock_age_context(active_flock, today),
        )

    @app.post("/kippen/dead-hens/new")
    @login_required
    def dead_hens_new_post():
        repositories = _repositories()
        registration, errors, values = dead_hens.build_dead_hen_registration_from_form(
            request.form,
            registered_by=_current_username(),
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
                    active_flock_age=_active_flock_age_for_datetime_values(
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
                    active_flock_age=None,
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
        repositories = _repositories()
        registration = repositories.dead_hens.get_dead_hen_registration_by_id(
            registration_id,
        )
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)
        repositories.dead_hens.delete_dead_hen_registration(registration_id)
        flash("Dode hen registratie verwijderd.", "success")
        return redirect(url_for("dead_hens_list"))

    @app.get("/kippen/outside-nest-rounds/new")
    @login_required
    def outside_nest_rounds_new():
        today = date.today()
        active_flock = _repositories().flocks.get_active_flock_for_date(today)
        return render_template(
            "outside_nest_round_form.html",
            values=outside_nest.default_values(datetime.now()),
            errors={},
            action_url=url_for("outside_nest_rounds_new_post"),
            active_flock=active_flock,
            active_flock_age=flock_age.flock_age_context(active_flock, today),
        )

    @app.post("/kippen/outside-nest-rounds/new")
    @login_required
    def outside_nest_rounds_new_post():
        repositories = _repositories()
        egg_round, errors, values = outside_nest.build_outside_nest_round_from_form(
            request.form,
            registered_by=_current_username(),
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
                    active_flock_age=_active_flock_age_for_datetime_values(
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
                    active_flock_age=None,
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
        repositories = _repositories()
        round_obj = repositories.outside_nest_rounds.get_outside_nest_egg_round_by_id(
            round_id,
        )
        if round_obj is None:
            abort(404)
        _require_admin_or_owner(round_obj)
        repositories.outside_nest_rounds.delete_outside_nest_egg_round(round_id)
        flash("Buitennest ronde verwijderd.", "success")
        return redirect(url_for("outside_nest_rounds_list"))

    @app.get("/kippen/packaging-weights")
    @login_required
    def packaging_weights_list():
        return render_template(
            "packaging_weights.html",
            configs=_repositories().packaging_weights.list_packaging_weight_configs(),
        )

    @app.get("/kippen/packaging-weights/new")
    @login_required
    def packaging_weights_new():
        return render_template(
            "packaging_weight_form.html",
            title="Leeggoed configuratie toevoegen",
            values=packaging_weights.default_values(date.today()),
            errors={},
            action_url=url_for("packaging_weights_new_post"),
            submit_label="Configuratie opslaan",
        )

    @app.post("/kippen/packaging-weights/new")
    @login_required
    def packaging_weights_new_post():
        repositories = _repositories()
        config_model, errors, values = (
            packaging_weights.build_packaging_weight_config_from_form(request.form)
        )
        if errors or config_model is None:
            return _render_packaging_weight_form(
                title="Leeggoed configuratie toevoegen",
                values=values,
                errors=errors,
                action_url=url_for("packaging_weights_new_post"),
                submit_label="Configuratie opslaan",
                status_code=400,
            )

        try:
            repositories.packaging_weights.create_packaging_weight_config(config_model)
        except ValueError as exc:
            errors["form"] = str(exc)
            return _render_packaging_weight_form(
                title="Leeggoed configuratie toevoegen",
                values=values,
                errors=errors,
                action_url=url_for("packaging_weights_new_post"),
                submit_label="Configuratie opslaan",
                status_code=400,
            )

        flash("Leeggoed configuratie opgeslagen.", "success")
        return redirect(url_for("packaging_weights_list"))

    @app.get("/kippen/packaging-weights/<int:config_id>/edit")
    @login_required
    def packaging_weights_edit(config_id: int):
        config_model = (
            _repositories().packaging_weights.get_packaging_weight_config_by_id(
                config_id,
            )
        )
        if config_model is None:
            abort(404)

        return render_template(
            "packaging_weight_form.html",
            title="Leeggoed configuratie aanpassen",
            values=packaging_weights.values_from_config(config_model),
            errors={},
            action_url=url_for("packaging_weights_edit_post", config_id=config_id),
            submit_label="Wijzigingen opslaan",
        )

    @app.post("/kippen/packaging-weights/<int:config_id>/edit")
    @login_required
    def packaging_weights_edit_post(config_id: int):
        repositories = _repositories()
        existing_config = (
            repositories.packaging_weights.get_packaging_weight_config_by_id(
                config_id,
            )
        )
        if existing_config is None:
            abort(404)

        config_model, errors, values = (
            packaging_weights.build_packaging_weight_config_from_form(
                request.form,
                existing_config=existing_config,
            )
        )
        if errors or config_model is None:
            return _render_packaging_weight_form(
                title="Leeggoed configuratie aanpassen",
                values=values,
                errors=errors,
                action_url=url_for("packaging_weights_edit_post", config_id=config_id),
                submit_label="Wijzigingen opslaan",
                status_code=400,
            )

        try:
            saved_config = (
                repositories.packaging_weights.update_packaging_weight_config(
                    config_id,
                    config_model,
                )
            )
        except ValueError as exc:
            errors["form"] = str(exc)
            return _render_packaging_weight_form(
                title="Leeggoed configuratie aanpassen",
                values=values,
                errors=errors,
                action_url=url_for("packaging_weights_edit_post", config_id=config_id),
                submit_label="Wijzigingen opslaan",
                status_code=400,
            )

        if saved_config is None:
            abort(404)

        flash("Leeggoed configuratie aangepast.", "success")
        return redirect(url_for("packaging_weights_list"))

    @app.post("/kippen/packaging-weights/<int:config_id>/archive")
    @login_required
    def packaging_weights_archive(config_id: int):
        archived_config = (
            _repositories().packaging_weights.archive_packaging_weight_config(config_id)
        )
        if archived_config is None:
            abort(404)

        flash("Leeggoed configuratie gearchiveerd.", "success")
        return redirect(url_for("packaging_weights_list"))

    @app.get("/kippen/pallet-weights")
    @login_required
    def pallet_weights_list():
        return render_template(
            "pallet_weights.html",
            registrations=_repositories().pallet_weights.list_recent(limit=100),
        )

    @app.get("/kippen/pallet-weights/new")
    @login_required
    def pallet_weights_new():
        repositories = _repositories()
        registration_date = _get_requested_date()
        return render_template(
            "pallet_weight_form.html",
            title="Palletgewicht registreren",
            values=pallet_weights.default_values(registration_date),
            errors={},
            action_url=url_for("pallet_weights_new_post"),
            submit_label="Opslaan",
            active_flock=repositories.flocks.get_active_flock_for_date(
                registration_date,
            ),
            active_flock_age=flock_age.flock_age_context(
                repositories.flocks.get_active_flock_for_date(registration_date),
                registration_date,
            ),
            packaging_configs=repositories.packaging_weights.list_active_for_date(
                registration_date,
            ),
        )

    @app.post("/kippen/pallet-weights/new")
    @login_required
    def pallet_weights_new_post():
        repositories = _repositories()
        selected_config = _packaging_config_from_form(repositories, request.form)
        registration, errors, values = (
            pallet_weights.build_pallet_weight_registration_from_form(
                request.form,
                packaging_config=selected_config,
                created_by=_current_username(),
            )
        )
        if errors or registration is None:
            return _render_pallet_weight_form(
                repositories,
                title="Palletgewicht registreren",
                values=values,
                errors=errors,
                action_url=url_for("pallet_weights_new_post"),
                submit_label="Opslaan",
                selected_config=selected_config,
                status_code=400,
            )

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.registration_date,
            house_id=registration.house_id,
        )
        if active_flock is None:
            errors["form"] = _missing_active_flock_message(registration.house_id)
            return _render_pallet_weight_form(
                repositories,
                title="Palletgewicht registreren",
                values=values,
                errors=errors,
                action_url=url_for("pallet_weights_new_post"),
                submit_label="Opslaan",
                selected_config=selected_config,
                status_code=400,
            )

        if not _packaging_config_is_active_for_registration(
            repositories,
            registration,
        ):
            errors["packaging_weight_config_id"] = (
                "Leeggoed configuratie is niet actief op deze datum."
            )
            return _render_pallet_weight_form(
                repositories,
                title="Palletgewicht registreren",
                values=values,
                errors=errors,
                action_url=url_for("pallet_weights_new_post"),
                submit_label="Opslaan",
                selected_config=selected_config,
                status_code=400,
            )

        registration.flock_id = active_flock.id
        repositories.pallet_weights.create_pallet_weight_registration(registration)
        flash("Palletgewicht opgeslagen.", "success")
        return redirect(url_for("pallet_weights_list"))

    @app.get("/kippen/pallet-weights/<int:registration_id>/edit")
    @login_required
    def pallet_weights_edit(registration_id: int):
        repositories = _repositories()
        registration = repositories.pallet_weights.get_pallet_weight_registration_by_id(
            registration_id,
        )
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)

        selected_config = (
            repositories.packaging_weights.get_packaging_weight_config_by_id(
                registration.packaging_weight_config_id,
            )
        )
        return render_template(
            "pallet_weight_form.html",
            title="Palletgewicht aanpassen",
            values=pallet_weights.values_from_registration(registration),
            errors={},
            action_url=url_for(
                "pallet_weights_edit_post",
                registration_id=registration.id,
            ),
            submit_label="Wijzigingen opslaan",
            active_flock=_flock_for_registration_by_id(
                repositories.flocks,
                registration.flock_id,
            ),
            active_flock_age=_flock_age_for_registration(
                repositories.flocks,
                registration,
            ),
            packaging_configs=_packaging_configs_for_values(
                repositories,
                pallet_weights.values_from_registration(registration),
                selected_config,
            ),
        )

    @app.post("/kippen/pallet-weights/<int:registration_id>/edit")
    @login_required
    def pallet_weights_edit_post(registration_id: int):
        repositories = _repositories()
        existing_registration = (
            repositories.pallet_weights.get_pallet_weight_registration_by_id(
                registration_id,
            )
        )
        if existing_registration is None:
            abort(404)
        _require_admin_or_owner(existing_registration)

        selected_config = _packaging_config_from_form(repositories, request.form)
        registration, errors, values = (
            pallet_weights.build_pallet_weight_registration_from_form(
                request.form,
                packaging_config=selected_config,
                created_by=_current_username(),
                existing_registration=existing_registration,
            )
        )
        if errors or registration is None:
            return _render_pallet_weight_form(
                repositories,
                title="Palletgewicht aanpassen",
                values=values,
                errors=errors,
                action_url=url_for(
                    "pallet_weights_edit_post",
                    registration_id=registration_id,
                ),
                submit_label="Wijzigingen opslaan",
                selected_config=selected_config,
                status_code=400,
            )

        active_flock = repositories.flocks.get_active_flock_for_date(
            registration.registration_date,
            house_id=registration.house_id,
        )
        if active_flock is None:
            errors["form"] = _missing_active_flock_message(registration.house_id)
            return _render_pallet_weight_form(
                repositories,
                title="Palletgewicht aanpassen",
                values=values,
                errors=errors,
                action_url=url_for(
                    "pallet_weights_edit_post",
                    registration_id=registration_id,
                ),
                submit_label="Wijzigingen opslaan",
                selected_config=selected_config,
                status_code=400,
            )

        registration.flock_id = active_flock.id
        saved_registration = (
            repositories.pallet_weights.update_pallet_weight_registration(
                registration_id,
                registration,
            )
        )
        if saved_registration is None:
            abort(404)

        flash("Palletgewicht aangepast.", "success")
        return redirect(url_for("pallet_weights_list"))

    @app.post("/kippen/pallet-weights/<int:registration_id>/delete")
    @login_required
    def pallet_weights_delete(registration_id: int):
        repositories = _repositories()
        registration = repositories.pallet_weights.get_pallet_weight_registration_by_id(
            registration_id,
        )
        if registration is None:
            abort(404)
        _require_admin_or_owner(registration)
        repositories.pallet_weights.delete_pallet_weight_registration(registration_id)
        flash("Palletgewicht verwijderd.", "success")
        return redirect(url_for("pallet_weights_list"))

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
        flocks_by_id = _flocks_by_id(repositories.flocks)
        if record_type == "eggs":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "flock_name",
                    "flock_date_of_birth",
                    "flock_age_weeks",
                    "flock_age_days",
                    "registration_date",
                    "weekday",
                    "first_quality_eggs",
                    "second_quality_eggs",
                    "total_eggs",
                    "notes",
                    "created_by",
                ],
                [
                    [
                        item.id,
                        item.house_id,
                        item.flock_id,
                        *_raw_flock_context_values(
                            flocks_by_id,
                            item.flock_id,
                            item.registration_date,
                        ),
                        item.registration_date,
                        item.weekday,
                        item.first_quality_eggs,
                        item.second_quality_eggs,
                        item.total_eggs,
                        item.notes,
                        item.created_by,
                    ]
                    for item in repositories.eggs.list_all()
                ],
            )
        elif record_type == "feed-water":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "flock_name",
                    "flock_date_of_birth",
                    "flock_age_weeks",
                    "flock_age_days",
                    "registration_date",
                    "weekday",
                    "water_ml",
                    "feed_grams",
                    "notes",
                    "created_by",
                ],
                [
                    [
                        item.id,
                        item.house_id,
                        item.flock_id,
                        *_raw_flock_context_values(
                            flocks_by_id,
                            item.flock_id,
                            item.registration_date,
                        ),
                        item.registration_date,
                        item.weekday,
                        item.water_ml,
                        item.feed_grams,
                        item.notes,
                        item.created_by,
                    ]
                    for item in repositories.feed_water.list_all()
                ],
            )
        elif record_type == "dead-hens":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "flock_name",
                    "flock_date_of_birth",
                    "flock_age_weeks",
                    "flock_age_days",
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
                        *_raw_flock_context_values(
                            flocks_by_id,
                            item.flock_id,
                            item.found_at.date(),
                        ),
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
                    "flock_name",
                    "flock_date_of_birth",
                    "flock_age_weeks",
                    "flock_age_days",
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
                        *_raw_flock_context_values(
                            flocks_by_id,
                            item.flock_id,
                            item.round_at.date(),
                        ),
                        item.round_at,
                        item.egg_count,
                        item.notes,
                        item.registered_by,
                    ]
                    for item in repositories.outside_nest_rounds.list_all()
                ],
            )
        elif record_type == "pallet-weights":
            output = exports.records_csv(
                [
                    "id",
                    "house_id",
                    "flock_id",
                    "flock_name",
                    "flock_date_of_birth",
                    "flock_age_weeks",
                    "flock_age_days",
                    "registration_date",
                    "weekday",
                    "supplier_name",
                    "pallet_weight_kg",
                    "empty_packaging_weight_kg",
                    "egg_count_per_pallet",
                    "egg_weight_grams",
                    "notes",
                    "created_by",
                ],
                [
                    [
                        item.id,
                        item.house_id,
                        item.flock_id,
                        *_raw_flock_context_values(
                            flocks_by_id,
                            item.flock_id,
                            item.registration_date,
                        ),
                        item.registration_date,
                        item.weekday,
                        item.supplier_name,
                        item.pallet_weight_kg,
                        item.empty_packaging_weight_kg,
                        item.egg_count_per_pallet,
                        item.egg_weight_grams,
                        item.notes,
                        item.created_by,
                    ]
                    for item in repositories.pallet_weights.list_all()
                ],
            )
        elif record_type == "packaging-weights":
            output = exports.records_csv(
                [
                    "id",
                    "supplier_name",
                    "empty_packaging_weight_kg",
                    "egg_count_per_pallet",
                    "start_date",
                    "end_date",
                    "is_active",
                    "archived_at",
                    "notes",
                ],
                [
                    [
                        item.id,
                        item.supplier_name,
                        item.empty_packaging_weight_kg,
                        item.egg_count_per_pallet,
                        item.start_date,
                        item.end_date,
                        item.is_active,
                        item.archived_at,
                        item.notes,
                    ]
                    for item in repositories.packaging_weights.list_packaging_weight_configs()
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
        return redirect("/login")

    @app.post("/kippen/login")
    def login_post():
        return redirect("/login", code=303)

    @app.post("/kippen/logout")
    def logout():
        return redirect("/logout", code=303)

    @app.get("/kippen/healthz")
    def healthz():
        return {"status": "ok"}

    return app


def login_required(view_func):
    """Require shared portal access to the Kippen application."""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user = _current_user()
        if user is None:
            return redirect("/login")
        if not _auth_service().user_can_access_application(
            user.id,
            KIPPEN_APPLICATION_KEY,
        ):
            abort(403)

        return view_func(*args, **kwargs)

    return wrapped_view


class LayingHensRepositories:
    """Small container for laying hens repositories."""

    def __init__(self, session_factory):
        self.flocks = FlocksRepository(session_factory)
        self.eggs = EggRegistrationsRepository(session_factory)
        self.feed_water = FeedWaterRegistrationsRepository(session_factory)
        self.dead_hens = DeadHenRegistrationsRepository(session_factory)
        self.outside_nest_rounds = OutsideNestEggRoundsRepository(session_factory)
        self.packaging_weights = EggPackagingWeightConfigsRepository(session_factory)
        self.pallet_weights = EggPalletWeightRegistrationsRepository(session_factory)


def _repositories() -> LayingHensRepositories:
    return LayingHensRepositories(current_app.config["KIPPEN_SESSION_FACTORY"])


def _create_auth_service(session_factory) -> SharedAuthService:
    return SharedAuthService(
        users_repository=UsersRepository(session_factory),
        applications_repository=ApplicationsRepository(session_factory),
        roles_repository=RolesRepository(session_factory),
        access_repository=UserApplicationAccessRepository(session_factory),
    )


def _auth_service() -> SharedAuthService:
    return current_app.config["KIPPEN_AUTH_SERVICE"]


def _current_user():
    return _auth_service().get_active_user(session.get("user_id"))


def _current_username() -> str:
    user = _current_user()
    if user is None:
        return ""

    display_name = session.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()

    return user.username


def _registration_owned_by_current_user(registration) -> bool:
    owner = getattr(registration, "created_by", None) or getattr(
        registration,
        "registered_by",
        None,
    )
    if owner is None:
        return False

    current_username = _current_username()
    if current_username == "":
        return False

    return owner.strip() == current_username.strip()


def _require_admin_or_owner(registration) -> None:
    user = _current_user()
    if user is None:
        abort(403)
    if _auth_service().user_has_application_role(
        user.id,
        KIPPEN_APPLICATION_KEY,
        "admin",
    ):
        return
    if not _registration_owned_by_current_user(registration):
        abort(403)


def _path_has_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _get_requested_date() -> date:
    raw_date = request.args.get("date", "")
    if raw_date == "":
        return date.today()

    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return date.today()


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


def _active_flock_age_for_values(
    repository: FlocksRepository,
    values: dict[str, str],
):
    try:
        registration_date = date.fromisoformat(values.get("registration_date", ""))
    except ValueError:
        return None

    active_flock = repository.get_active_flock_for_date(
        registration_date,
        house_id=values.get("house_id", "main") or "main",
    )
    return flock_age.flock_age_context(active_flock, registration_date)


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


def _active_flock_age_for_datetime_values(
    repository: FlocksRepository,
    values: dict[str, str],
    field_name: str,
):
    try:
        registration_datetime = datetime.fromisoformat(values.get(field_name, ""))
    except ValueError:
        return None

    active_flock = repository.get_active_flock_for_date(
        registration_datetime.date(),
        house_id=values.get("house_id", "main") or "main",
    )
    return flock_age.flock_age_context(active_flock, registration_datetime.date())


def _flock_age_for_registration(
    repository: FlocksRepository,
    registration,
):
    if registration.flock_id is None:
        return None

    active_flock = repository.get_flock_by_id(registration.flock_id)
    if active_flock is None:
        return None

    return flock_age.flock_age_context(active_flock, registration.registration_date)


def _flock_for_registration_by_id(
    repository: FlocksRepository,
    flock_id: Optional[int],
):
    if flock_id is None:
        return None

    return repository.get_flock_by_id(flock_id)


def _render_packaging_weight_form(
    *,
    title: str,
    values: dict[str, str],
    errors: dict[str, str],
    action_url: str,
    submit_label: str,
    status_code: int,
):
    return (
        render_template(
            "packaging_weight_form.html",
            title=title,
            values=values,
            errors=errors,
            action_url=action_url,
            submit_label=submit_label,
        ),
        status_code,
    )


def _render_pallet_weight_form(
    repositories: LayingHensRepositories,
    *,
    title: str,
    values: dict[str, str],
    errors: dict[str, str],
    action_url: str,
    submit_label: str,
    selected_config,
    status_code: int,
):
    return (
        render_template(
            "pallet_weight_form.html",
            title=title,
            values=values,
            errors=errors,
            action_url=action_url,
            submit_label=submit_label,
            active_flock=_active_flock_for_values(repositories.flocks, values),
            active_flock_age=_active_flock_age_for_values(
                repositories.flocks,
                values,
            ),
            packaging_configs=_packaging_configs_for_values(
                repositories,
                values,
                selected_config,
            ),
        ),
        status_code,
    )


def _packaging_config_from_form(
    repositories: LayingHensRepositories,
    form_data,
):
    try:
        config_id = int(form_data.get("packaging_weight_config_id", ""))
    except ValueError:
        return None

    return repositories.packaging_weights.get_packaging_weight_config_by_id(config_id)


def _packaging_configs_for_values(
    repositories: LayingHensRepositories,
    values: dict[str, str],
    selected_config,
):
    try:
        registration_date = date.fromisoformat(values.get("registration_date", ""))
    except ValueError:
        registration_date = date.today()

    configs = repositories.packaging_weights.list_active_for_date(registration_date)
    if selected_config is None or selected_config.id is None:
        return configs

    if any(config.id == selected_config.id for config in configs):
        return configs

    return [selected_config, *configs]


def _packaging_config_is_active_for_registration(
    repositories: LayingHensRepositories,
    registration,
) -> bool:
    configs = repositories.packaging_weights.list_active_for_date(
        registration.registration_date,
    )
    return any(
        config.id == registration.packaging_weight_config_id for config in configs
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
    egg_registrations = repositories.eggs.list_between(week_days[0], week_days[-1])
    feed_water_registrations = repositories.feed_water.list_between(
        week_days[0],
        week_days[-1],
    )
    pallet_weight_registrations = repositories.pallet_weights.list_between(
        week_days[0],
        week_days[-1],
    )
    egg_registrations_by_date = {
        registration.registration_date: registration
        for registration in egg_registrations
    }
    feed_water_registrations_by_date = {
        registration.registration_date: registration
        for registration in feed_water_registrations
    }
    pallet_weight_registrations_by_date = _group_by_registration_date(
        pallet_weight_registrations,
    )
    flocks_by_id = _flocks_by_id(repositories.flocks)
    rows = []
    for day in week_days:
        egg_registration = egg_registrations_by_date.get(day)
        feed_water_registration = feed_water_registrations_by_date.get(day)
        pallet_weight_registrations_for_day = pallet_weight_registrations_by_date.get(
            day,
            [],
        )
        active_flock = _flock_for_week_row(
            repositories.flocks,
            flocks_by_id,
            day,
            egg_registration,
            feed_water_registration,
        )
        rows.append(
            {
                "date": day,
                "weekday": weekdays.DUTCH_WEEKDAYS[day.weekday()],
                "registration": egg_registration,
                "egg_registration": egg_registration,
                "feed_water_registration": feed_water_registration,
                "pallet_weight_registrations": pallet_weight_registrations_for_day,
                "average_egg_weight_grams": _average_egg_weight_grams(
                    pallet_weight_registrations_for_day,
                ),
                "flock": active_flock,
                "flock_age": flock_age.flock_age_context(active_flock, day),
                "dead_hens_count": repositories.dead_hens.count_for_date(day),
                "outside_nest_egg_count": (
                    repositories.outside_nest_rounds.count_for_date(day)
                ),
            }
        )

    return rows


def _flocks_by_id(repository: FlocksRepository):
    return {
        flock.id: flock for flock in repository.list_flocks() if flock.id is not None
    }


def _flock_for_week_row(
    repository: FlocksRepository,
    flocks_by_id: dict[int, object],
    target_date: date,
    egg_registration,
    feed_water_registration=None,
):
    for registration in (egg_registration, feed_water_registration):
        if registration is not None and registration.flock_id is not None:
            return flocks_by_id.get(registration.flock_id)

    return repository.get_active_flock_for_date(target_date)


def _raw_flock_context_values(
    flocks_by_id: dict[int, object],
    flock_id: Optional[int],
    target_date: date,
) -> list[object]:
    if flock_id is None:
        return ["", "", "", ""]

    flock = flocks_by_id.get(flock_id)
    if flock is None:
        return ["", "", "", ""]

    age_context = flock_age.flock_age_context(flock, target_date)
    if age_context is None:
        return [flock.flock_name, flock.date_of_birth, "", ""]

    return [
        flock.flock_name,
        flock.date_of_birth,
        age_context["weeks"],
        age_context["days"],
    ]


def _group_by_registration_date(registrations) -> dict[date, list[object]]:
    grouped: dict[date, list[object]] = {}
    for registration in registrations:
        grouped.setdefault(registration.registration_date, []).append(registration)

    return grouped


def _average_egg_weight_grams(registrations) -> Optional[Decimal]:
    values = [
        registration.egg_weight_grams
        for registration in registrations
        if registration.egg_weight_grams is not None
    ]
    if not values:
        return None

    return (sum(values) / Decimal(len(values))).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )


def _week_totals(rows: list[dict[str, object]]) -> dict[str, object]:
    totals = {
        "first_quality_eggs": 0,
        "second_quality_eggs": 0,
        "total_eggs": 0,
        "dead_hens_count": 0,
        "outside_nest_egg_count": 0,
        "water_ml": 0,
        "feed_grams": 0,
        "average_egg_weight_grams": None,
    }
    pallet_weight_registrations = []
    for row in rows:
        egg_registration = row["egg_registration"]
        feed_water_registration = row["feed_water_registration"]
        pallet_weight_registrations.extend(row["pallet_weight_registrations"])
        totals["dead_hens_count"] += int(row["dead_hens_count"])
        totals["outside_nest_egg_count"] += int(row["outside_nest_egg_count"])
        if egg_registration is not None:
            totals["first_quality_eggs"] += egg_registration.first_quality_eggs
            totals["second_quality_eggs"] += egg_registration.second_quality_eggs
            totals["total_eggs"] += egg_registration.total_eggs

        if feed_water_registration is not None:
            totals["water_ml"] += feed_water_registration.water_ml
            totals["feed_grams"] += feed_water_registration.feed_grams

    totals["average_egg_weight_grams"] = _average_egg_weight_grams(
        pallet_weight_registrations,
    )
    return totals
