"""Route tests for the kippen registratie app."""

from datetime import date

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from werkzeug import security

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
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


def test_index_redirects_to_dashboard(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/kippen")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"


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


def test_daily_new_form_renders_for_logged_in_user(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.get("/kippen/daily/new?date=2026-05-26")

    assert response.status_code == 200
    assert "Dagregistratie invullen" in response.text
    assert "2026-05-26" in response.text
    assert "Dinsdag" in response.text


def test_daily_new_post_saves_registration_with_computed_total(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)

    response = client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "20530",
            "second_quality_eggs": "19",
            "water_liters": "199.55",
            "feed_kg": "109.25",
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
    assert registration.water_liters == 199.55
    assert registration.feed_kg == 109.25
    assert registration.created_by == "admin"


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
            "water_liters": "0,25",
            "feed_kg": "0,80",
            "notes": "Aangepast",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"
    with Session(engine) as session:
        registrations = session.exec(select(DailyLayingRegistration)).all()

    assert len(registrations) == 1
    assert registrations[0].total_eggs == 126
    assert registrations[0].water_liters == 0.25
    assert registrations[0].feed_kg == 0.80
    assert registrations[0].notes == "Aangepast"


def test_daily_edit_form_formats_water_and_feed_with_two_decimals(monkeypatch):
    client, engine = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
            "water_liters": "0.2",
            "feed_kg": "0.8",
        },
    )
    with Session(engine) as session:
        registration = session.exec(select(DailyLayingRegistration)).one()

    response = client.get(f"/kippen/daily/{registration.id}/edit")

    assert response.status_code == 200
    assert 'name="water_liters"' in response.text
    assert 'value="0.20"' in response.text
    assert 'name="feed_kg"' in response.text
    assert 'value="0.80"' in response.text


def test_week_overview_shows_saved_registration_and_totals(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)
    client.post(
        "/kippen/daily/new",
        data={
            "registration_date": "2026-05-26",
            "first_quality_eggs": "100",
            "second_quality_eggs": "5",
            "water_liters": "10",
            "feed_kg": "20",
        },
    )

    response = client.get("/kippen/week/2026/22")

    assert response.status_code == 200
    assert "Week 22" in response.text
    assert "2026-05-26" in response.text
    assert "105" in response.text


def test_dead_hen_new_form_renders_for_logged_in_user(monkeypatch):
    client, _ = _client(monkeypatch)
    _login(client)

    response = client.get("/kippen/dead-hens/new")

    assert response.status_code == 200
    assert "Dode hen registreren" in response.text
    assert "Albering kant" in response.text
    assert "Ziekenboeg kant" in response.text


def test_dead_hen_post_saves_registration(monkeypatch):
    client, engine = _client(monkeypatch)
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
