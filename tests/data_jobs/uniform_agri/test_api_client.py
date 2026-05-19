from pathlib import Path
import shutil

import httpx
import pytest

from data_jobs.uniform_agri import api_client
from data_jobs.uniform_agri.config import UniformAgriConfig
from data_jobs.uniform_agri.exceptions import (
    UniformAgriApiError,
    UniformAgriAuthenticationError,
)


def build_config(access_token: str = "initial-token") -> UniformAgriConfig:
    return UniformAgriConfig(
        base_url="https://uniform.example.test",
        username="user",
        password="password",
        client_id="client-id",
        herd_id="herd-id",
        access_token=access_token,
        request_timeout_seconds=7,
        max_retries=1,
    )


def test_request_attaches_bearer_token():
    seen_authorization = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://uniform.example.test",
        transport=transport,
    )
    client = api_client.ApiClient(
        config=build_config(),
        http_client=http_client,
    )

    assert client.get("/resource") == {"ok": True}
    assert seen_authorization == "Bearer initial-token"


def test_request_refreshes_token_once_after_unauthorized_response():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            (request.method, request.url.path, request.headers.get("authorization"))
        )

        if request.url.path == "/resource" and len(calls) == 1:
            return httpx.Response(401, json={"error": "expired"})

        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "fresh-token"})

        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://uniform.example.test",
        transport=transport,
    )
    client = api_client.ApiClient(
        config=build_config(),
        http_client=http_client,
    )

    assert client.get("/resource") == {"ok": True}
    assert calls == [
        ("GET", "/resource", "Bearer initial-token"),
        ("POST", "/oauth2/token", None),
        ("GET", "/resource", "Bearer fresh-token"),
    ]
    assert client.token == "fresh-token"


def test_runtime_token_refresh_does_not_mutate_env_file(monkeypatch):
    env_dir = Path("plans_api_client_env_test").resolve()
    env_dir.mkdir(exist_ok=True)
    env_file = env_dir / ".env"
    original_env = 'UNIFORM_ACCESS_TOKEN="old-token"\n'
    env_file.write_text(original_env, encoding="utf-8")
    monkeypatch.chdir(env_dir)

    try:

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/resource":
                authorization = request.headers.get("authorization")
                if authorization == "Bearer old-token":
                    return httpx.Response(401, json={"error": "expired"})

                return httpx.Response(200, json={"ok": True})

            return httpx.Response(200, json={"access_token": "fresh-token"})

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(
            base_url="https://uniform.example.test",
            transport=transport,
        )
        client = api_client.ApiClient(
            config=build_config(access_token="old-token"),
            http_client=http_client,
        )

        assert client.get("/resource") == {"ok": True}
        assert Path(".env").read_text(encoding="utf-8") == original_env
    finally:
        monkeypatch.chdir(Path(__file__).resolve().parents[3])
        shutil.rmtree(env_dir)


def test_api_error_includes_endpoint_status_and_short_response_context():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="x" * 700)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://uniform.example.test",
        transport=transport,
    )
    client = api_client.ApiClient(
        config=build_config(),
        http_client=http_client,
    )

    with pytest.raises(UniformAgriApiError) as error:
        client.get("/broken")

    assert error.value.endpoint == "/broken"
    assert error.value.status_code == 500
    assert len(error.value.response_text) == 500


def test_request_retries_transient_server_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(502, text="temporary")

        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://uniform.example.test",
        transport=transport,
    )
    client = api_client.ApiClient(
        config=build_config(),
        http_client=http_client,
    )

    assert client.get("/resource") == {"ok": True}
    assert calls == ["/resource", "/resource"]


def test_authentication_error_when_token_response_has_no_access_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"missing": "token"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://uniform.example.test",
        transport=transport,
    )
    client = api_client.ApiClient(
        config=build_config(access_token=""),
        token="bootstrap-token",
        http_client=http_client,
    )

    with pytest.raises(UniformAgriAuthenticationError) as error:
        client.get_access_token()

    assert error.value.endpoint == "/oauth2/token"
