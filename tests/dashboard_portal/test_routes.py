"""Route tests for the dashboard portal."""

from werkzeug import security

from dashboard_portal.app import create_app


def _client(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET_KEY", "test-secret")
    monkeypatch.setenv("PORTAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "PORTAL_ADMIN_PASSWORD_HASH",
        security.generate_password_hash("correct-password"),
    )
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_redirects_to_login_without_session(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_login_with_wrong_credentials_fails(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "onjuist" in response.text


def test_login_with_correct_credentials_allows_index(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/login",
        data={"username": "admin", "password": "correct-password"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "Klauwgezondheid" in index_response.text


def test_logout_clears_session(monkeypatch):
    client = _client(monkeypatch)
    client.post("/login", data={"username": "admin", "password": "correct-password"})

    response = client.post("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert client.get("/").status_code == 302


def test_auth_verify_requires_session(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/auth/verify")

    assert response.status_code == 401


def test_auth_verify_accepts_session(monkeypatch):
    client = _client(monkeypatch)
    client.post("/login", data={"username": "admin", "password": "correct-password"})

    response = client.get("/auth/verify")

    assert response.status_code == 204
