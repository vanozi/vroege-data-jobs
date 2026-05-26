"""Route tests for the kippen registratie app."""

from werkzeug import security

from kippen_app.app import create_app


def _client(monkeypatch):
    monkeypatch.setenv("KIPPEN_APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("KIPPEN_APP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "KIPPEN_APP_ADMIN_PASSWORD_HASH",
        security.generate_password_hash("correct-password"),
    )
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_redirects_to_dashboard(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/kippen")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"


def test_dashboard_redirects_to_login_without_session(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/kippen/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/login"


def test_login_with_wrong_credentials_fails(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/kippen/login",
        data={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "onjuist" in response.text


def test_login_with_correct_credentials_allows_dashboard(monkeypatch):
    client = _client(monkeypatch)

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
    client = _client(monkeypatch)
    client.post(
        "/kippen/login",
        data={"username": "admin", "password": "correct-password"},
    )

    response = client.get("/kippen/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/dashboard"


def test_logout_clears_session(monkeypatch):
    client = _client(monkeypatch)
    client.post(
        "/kippen/login",
        data={"username": "admin", "password": "correct-password"},
    )

    response = client.post("/kippen/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/kippen/login"
    assert client.get("/kippen/dashboard").status_code == 302


def test_healthz(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/kippen/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
