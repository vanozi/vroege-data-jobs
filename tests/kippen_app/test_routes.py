"""Route tests for the kippen registratie app."""

from datetime import date
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from werkzeug import security

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import Flock
from database.models.laying_hens import OutsideNestEggRound
from kippen_app.app import create_app


def _client(monkeypatch):
    monkeypatch.setenv("KIPPEN_APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("KIPPEN_APP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "KIPPEN_APP_ADMIN_PASSWORD_HASH",
        security.generate_password_hash("correct-password"),
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    app = create_app(lambda: Session(engine, expire_on_commit=False))
    app.config.update(TESTING=True)
    return app.test_client(), engine


def _login(client):
    return client.post(
        "/kippen/login",
        data={"username": "admin", "password": "correct-password"},
    )


def _create_active_flock(
    client,
    *,
    flock_name: str = "Actief koppel",
    placement_date: str = "2026-01-01",
    end_date: str = "2035-12-31",
):
    return client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": flock_name,
            "house_id": "main",
            "date_of_birth": "2025-10-01",
            "placement_date": placement_date,
            "end_date": end_date,
            "bird_count": "24000",
        },
    )


def test_index_redirects_to_dashboard(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/kippen")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"


def test_root_redirects_to_kippen(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen"


def test_dashboard_redirects_to_login_without_session(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/kippen/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/login"


def test_login_with_wrong_credentials_fails(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.post(
        "/kippen/login",
        data={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "onjuist" in response.text


def test_login_with_correct_credentials_allows_dashboard(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.post(
        "/kippen/login",
        data={"username": "admin", "password": "correct-password"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"
    dashboard_response = client.get("/kippen/dashboard")
    assert dashboard_response.status_code == 200
    assert "Kippen Registratie" in dashboard_response.text
    assert "Dagregistratie invullen" in dashboard_response.text
    assert "Dode hen registreren" in dashboard_response.text
    assert "Buitennest ronde registreren" in dashboard_response.text
    assert "Koppels beheren" in dashboard_response.text


def test_login_page_redirects_to_dashboard_when_already_logged_in(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.get("/kippen/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"


def test_logout_clears_session(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post("/kippen/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/login"
    assert client.get("/kippen/dashboard").status_code == 302


def test_healthz(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/kippen/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_flocks_list_requires_login(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/kippen/flocks")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/login"


def test_flock_new_form_renders_for_logged_in_user(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.get("/kippen/flocks/new")

    assert response.status_code == 200
    assert "Koppel toevoegen" in response.text
    assert 'name="flock_name"' in response.text
    assert 'name="bird_count"' in response.text


def test_flock_new_post_saves_flock(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Koppel 2026",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "bird_count": "24000",
            "breed": "Bio leghen",
            "notes": "Eerste koppel",
        },
    )

    assert response.status_code == 302
    with Session(engine) as session:
        flock = session.exec(select(Flock)).one()

    assert response.headers["Location"] == f"/kippen/flocks/{flock.id}"
    assert flock.flock_name == "Koppel 2026"
    assert flock.house_id == "main"
    assert flock.bird_count == 24000
    assert flock.is_active is True


def test_flock_new_post_validates_required_values(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "",
            "house_id": "main",
            "date_of_birth": "2026-05-01",
            "placement_date": "2026-04-01",
            "bird_count": "-1",
        },
    )

    assert response.status_code == 400
    assert "Koppelnaam is verplicht." in response.text
    assert "Opzetdatum kan niet voor geboortedatum liggen." in response.text
    assert "Aantal hennen mag niet negatief zijn." in response.text


def test_flock_new_post_rejects_overlapping_active_flock(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Koppel 1",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "bird_count": "24000",
        },
    )

    response = client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Koppel 2",
            "house_id": "main",
            "date_of_birth": "2026-02-01",
            "placement_date": "2026-06-01",
            "bird_count": "23000",
        },
    )

    assert response.status_code == 400
    assert "overlaps with another flock" in response.text


def test_flock_detail_and_list_show_saved_flock(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Koppel detail",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "bird_count": "24000",
        },
    )
    with Session(engine) as session:
        flock = session.exec(select(Flock)).one()

    list_response = client.get("/kippen/flocks")
    detail_response = client.get(f"/kippen/flocks/{flock.id}")

    assert list_response.status_code == 200
    assert "Koppel detail" in list_response.text
    assert detail_response.status_code == 200
    assert "Koppel detail" in detail_response.text
    assert "Einddatum instellen" in detail_response.text


def test_flock_edit_updates_existing_flock(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Oude naam",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "bird_count": "24000",
        },
    )
    with Session(engine) as session:
        flock = session.exec(select(Flock)).one()

    response = client.post(
        f"/kippen/flocks/{flock.id}/edit",
        data={
            "flock_name": "Nieuwe naam",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "end_date": "2027-06-01",
            "bird_count": "23800",
            "breed": "Wit",
            "notes": "Aangepast",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"/kippen/flocks/{flock.id}"
    with Session(engine) as session:
        updated_flock = session.get(Flock, flock.id)

    assert updated_flock.flock_name == "Nieuwe naam"
    assert updated_flock.end_date == date(2027, 6, 1)
    assert updated_flock.bird_count == 23800
    assert updated_flock.notes == "Aangepast"


def test_flock_set_end_date(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Koppel einddatum",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "bird_count": "24000",
        },
    )
    with Session(engine) as session:
        flock = session.exec(select(Flock)).one()

    response = client.post(
        f"/kippen/flocks/{flock.id}/end-date",
        data={"end_date": "2027-05-15"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"/kippen/flocks/{flock.id}"
    with Session(engine) as session:
        updated_flock = session.get(Flock, flock.id)

    assert updated_flock.end_date == date(2027, 5, 15)


def test_flock_archive_marks_flock_inactive(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/flocks/new",
        data={
            "flock_name": "Koppel archief",
            "house_id": "main",
            "date_of_birth": "2026-01-01",
            "placement_date": "2026-05-01",
            "bird_count": "24000",
        },
    )
    with Session(engine) as session:
        flock = session.exec(select(Flock)).one()

    response = client.post(f"/kippen/flocks/{flock.id}/archive")

    assert response.status_code == 302
    assert response.headers["Location"] == f"/kippen/flocks/{flock.id}"
    with Session(engine) as session:
        archived_flock = session.get(Flock, flock.id)

    assert archived_flock.is_active is False
    assert archived_flock.archived_at is not None


def test_daily_new_form_renders_for_logged_in_user(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)

    response = client.get("/kippen/daily/new?date=2026-05-26")

    assert response.status_code == 200
    assert "Dagregistratie invullen" in response.text
    assert "2026-05-26" in response.text
    assert "Dinsdag" in response.text
    assert "Actief koppel" in response.text
    assert "33 weken en 5 dagen" in response.text


def test_daily_new_post_saves_registration_with_computed_total(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)

    response = client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "20530",
            "second_quality_eggs": "19",
            "water_ml": "199555",
            "feed_grams": "109255",
            "notes": "Normale dag",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"
    with Session(engine) as session:
        registration = session.exec(select(DailyLayingRegistration)).one()

    assert registration.registration_date == date(2026, 5, 26)
    assert registration.weekday == "Dinsdag"
    assert registration.total_eggs == 20549
    assert registration.water_ml == 199555
    assert registration.feed_grams == 109255
    assert registration.created_by == "admin"
    assert registration.flock_id is not None


def test_daily_new_post_requires_active_flock_for_date(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "20530",
            "second_quality_eggs": "19",
        },
    )

    assert response.status_code == 400
    assert "Geen actief koppel gevonden" in response.text


def test_daily_new_post_validates_negative_values(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "-1",
            "second_quality_eggs": "0",
        },
    )

    assert response.status_code == 400
    assert "mag niet negatief" in response.text


def test_daily_edit_updates_existing_registration(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
        },
    )
    with Session(engine) as session:
        registration = session.exec(select(DailyLayingRegistration)).one()

    response = client.post(
        f"/kippen/daily/{registration.id}/edit",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "120",
            "second_quality_eggs": "6",
            "water_ml": "255",
            "feed_grams": "805",
            "notes": "Aangepast",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"
    with Session(engine) as session:
        registrations = session.exec(select(DailyLayingRegistration)).all()

    assert len(registrations) == 1
    assert registrations[0].total_eggs == 126
    assert registrations[0].water_ml == 255
    assert registrations[0].feed_grams == 805
    assert registrations[0].notes == "Aangepast"


def test_daily_edit_form_formats_water_and_feed_as_whole_units(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
            "water_ml": "200",
            "feed_grams": "800",
        },
    )
    with Session(engine) as session:
        registration = session.exec(select(DailyLayingRegistration)).one()

    response = client.get(f"/kippen/daily/{registration.id}/edit")

    assert response.status_code == 200
    assert 'name="water_ml"' in response.text
    assert 'step="1"' in response.text
    assert 'value="200"' in response.text
    assert 'name="feed_grams"' in response.text
    assert 'value="800"' in response.text


def test_week_overview_shows_saved_registration_and_totals(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
            "water_ml": "10123",
            "feed_grams": "20456",
        },
    )

    response = client.get("/kippen/week/2026/22")

    assert response.status_code == 200
    assert "Week 22" in response.text
    assert "2026-05-26" in response.text
    assert "Actief koppel" in response.text
    assert "33 weken en 5 dagen" in response.text
    assert "105" in response.text


def test_dead_hen_new_form_renders_for_logged_in_user(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)

    response = client.get("/kippen/dead-hens/new")

    assert response.status_code == 200
    assert "Dode hen registreren" in response.text
    assert "Albering kant" in response.text
    assert "Ziekenboeg kant" in response.text
    assert "Actief koppel" in response.text


def test_dead_hen_post_saves_registration(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)

    response = client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T08:30",
            "count": "2",
            "stable_side": "Albering kant",
            "section_number": "2",
            "walkway": "Midden",
            "found_place": "Onder de stelling",
            "suspected_cause": "Onbekend",
            "observations": "Gevonden tijdens ochtendronde",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dead-hens"
    with Session(engine) as session:
        registration = session.exec(select(DeadHenRegistration)).one()

    assert registration.count == 2
    assert registration.stable_side == "Albering kant"
    assert registration.section_number == 2
    assert registration.walkway == "Midden"
    assert registration.found_place == "Onder de stelling"
    assert registration.registered_by == "admin"
    assert registration.flock_id is not None


def test_dead_hen_post_requires_active_flock_for_date(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T08:30",
            "count": "2",
            "stable_side": "Albering kant",
            "section_number": "2",
            "walkway": "Midden",
            "found_place": "Onder de stelling",
        },
    )

    assert response.status_code == 400
    assert "Geen actief koppel gevonden" in response.text


def test_dead_hen_post_validates_count(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T08:30",
            "count": "0",
            "stable_side": "Albering kant",
            "section_number": "2",
            "walkway": "Midden",
            "found_place": "Onder de stelling",
        },
    )

    assert response.status_code == 400
    assert "Aantal moet minimaal 1 zijn." in response.text


def test_dead_hen_list_shows_recent_registrations(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T08:30",
            "count": "1",
            "stable_side": "Ziekenboeg kant",
            "section_number": "4",
            "walkway": "Rechts",
            "found_place": "In het gangpad",
            "observations": "Bij achterste vak",
        },
    )

    response = client.get("/kippen/dead-hens")

    assert response.status_code == 200
    assert "Ziekenboeg kant" in response.text
    assert "In het gangpad" in response.text
    assert "Bij achterste vak" in response.text


def test_dead_hen_counts_are_visible_in_daily_dashboard_and_week(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T08:30",
            "count": "2",
            "stable_side": "Albering kant",
            "section_number": "2",
            "walkway": "Midden",
            "found_place": "Onder de stelling",
        },
    )
    client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T15:45",
            "count": "1",
            "stable_side": "Ziekenboeg kant",
            "section_number": "4",
            "walkway": "Rechts",
            "found_place": "In het gangpad",
        },
    )

    daily_response = client.get("/kippen/daily/new?date=2026-05-26")
    week_response = client.get("/kippen/week/2026/22")

    assert daily_response.status_code == 200
    assert 'id="dead_hens_count"' in daily_response.text
    assert 'value="3"' in daily_response.text
    assert week_response.status_code == 200
    assert "Week totaal" in week_response.text
    assert ">3<" in week_response.text


def test_outside_nest_round_new_form_renders_for_logged_in_user(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)

    response = client.get("/kippen/outside-nest-rounds/new")

    assert response.status_code == 200
    assert "Buitennest ronde registreren" in response.text
    assert "Aantal eieren" in response.text
    assert "Actief koppel" in response.text


def test_outside_nest_round_post_saves_round(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)

    response = client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T10:30",
            "egg_count": "12",
            "notes": "Ochtendronde",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/outside-nest-rounds"
    with Session(engine) as session:
        egg_round = session.exec(select(OutsideNestEggRound)).one()

    assert egg_round.egg_count == 12
    assert egg_round.notes == "Ochtendronde"
    assert egg_round.registered_by == "admin"
    assert egg_round.flock_id is not None


def test_outside_nest_round_post_requires_active_flock_for_date(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T10:30",
            "egg_count": "12",
        },
    )

    assert response.status_code == 400
    assert "Geen actief koppel gevonden" in response.text


def test_outside_nest_round_post_validates_negative_egg_count(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T10:30",
            "egg_count": "-1",
        },
    )

    assert response.status_code == 400
    assert "Aantal eieren mag niet negatief zijn." in response.text


def test_outside_nest_rounds_list_shows_recent_rounds(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T10:30",
            "egg_count": "12",
            "notes": "Ochtendronde",
        },
    )

    response = client.get("/kippen/outside-nest-rounds")

    assert response.status_code == 200
    assert "26-05-2026 10:30" in response.text
    assert "Ochtendronde" in response.text


def test_outside_nest_round_counts_are_visible_in_dashboard_and_week(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T10:30",
            "egg_count": "12",
        },
    )
    client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T15:00",
            "egg_count": "8",
        },
    )

    dashboard_response = client.get("/kippen/dashboard")
    week_response = client.get("/kippen/week/2026/22")

    assert dashboard_response.status_code == 200
    assert "Buitennest eieren vandaag" in dashboard_response.text
    assert ">20<" in dashboard_response.text
    assert week_response.status_code == 200
    assert "Buitennest" in week_response.text
    assert ">20<" in week_response.text


def test_week_excel_export_downloads_xlsx(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
            "water_ml": "10123",
            "feed_grams": "20456",
        },
    )

    response = client.get("/kippen/week/2026/22/export.xlsx")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "legkalender-week-2026-22.xlsx" in response.headers["Content-Disposition"]
    assert response.data.startswith(b"PK")
    workbook = load_workbook(BytesIO(response.data))
    worksheet = workbook.active
    headers = [cell.value for cell in worksheet[3]]
    row = [cell.value for cell in worksheet[5]]
    assert "Koppel" in headers
    assert "Leeftijd" in headers
    assert "Actief koppel" in row
    assert "33 weken en 5 dagen" in row
    assert "10123" in row
    assert "20456" in row


def test_week_pdf_export_downloads_pdf(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.get("/kippen/week/2026/22/export.pdf")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/pdf")
    assert "legkalender-week-2026-22.pdf" in response.headers["Content-Disposition"]
    assert response.data.startswith(b"%PDF")


def test_raw_daily_csv_export_downloads_csv(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
        },
    )

    response = client.get("/kippen/export/daily.csv")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "kippen-daily.csv" in response.headers["Content-Disposition"]
    csv_text = response.data.decode("utf-8-sig")
    assert "registration_date" in csv_text
    assert "flock_name" in csv_text
    assert "flock_age_weeks" in csv_text
    assert "flock_age_days" in csv_text
    assert "Actief koppel" in csv_text
    assert "2026-05-26" in csv_text


def test_raw_dead_hens_csv_export_includes_flock_context(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/dead-hens/new",
        data={
            "found_at": "2026-05-26T08:30",
            "count": "1",
            "stable_side": "Albering kant",
            "section_number": "2",
            "walkway": "Midden",
            "found_place": "Onder de stelling",
        },
    )

    response = client.get("/kippen/export/dead-hens.csv")

    assert response.status_code == 200
    csv_text = response.data.decode("utf-8-sig")
    assert "flock_name" in csv_text
    assert "flock_age_weeks" in csv_text
    assert "Actief koppel" in csv_text


def test_raw_outside_nest_csv_export_includes_flock_context(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    _create_active_flock(client)
    client.post(
        "/kippen/outside-nest-rounds/new",
        data={
            "round_at": "2026-05-26T10:30",
            "egg_count": "12",
        },
    )

    response = client.get("/kippen/export/outside-nest-rounds.csv")

    assert response.status_code == 200
    csv_text = response.data.decode("utf-8-sig")
    assert "flock_name" in csv_text
    assert "flock_age_weeks" in csv_text
    assert "Actief koppel" in csv_text
