import httpx
import pytest

from data_jobs.moneybird.api_client import MoneybirdClient
from data_jobs.moneybird.config import MoneybirdConfig
from data_jobs.moneybird.exceptions import (
    MoneybirdAuthenticationError,
    MoneybirdRateLimitError,
)


def build_config(**overrides) -> MoneybirdConfig:
    values = {
        "access_token": "secret-token",
        "base_url": "https://moneybird.example.test/api/v2",
        "time_zone": "Europe/Amsterdam",
        "request_timeout_seconds": 5,
        "max_retries": 1,
        "retry_backoff_seconds": 0,
    }
    values.update(overrides)
    return MoneybirdConfig(**values)


def test_list_administrations_sends_auth_and_timezone_headers():
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json=[{"id": "123", "name": "Gebroeders vroege cv"}],
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        transport=transport,
        base_url="https://moneybird.example.test/api/v2",
    )
    client = MoneybirdClient(config=build_config(), http_client=http_client)

    administrations = client.list_administrations()

    assert administrations == [{"id": "123", "name": "Gebroeders vroege cv"}]
    assert captured_request is not None
    assert captured_request.url.path == "/api/v2/administrations.json"
    assert captured_request.headers["Authorization"] == "Bearer secret-token"
    assert captured_request.headers["Time-Zone"] == "Europe/Amsterdam"
    assert captured_request.headers["Accept"] == "application/json"


def test_get_paginated_follows_link_header():
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_pages.append(request.url.params.get("page"))
        if request.url.params.get("page") == "1":
            return httpx.Response(
                200,
                headers={
                    "Link": (
                        "<https://moneybird.example.test/api/v2/123/contacts.json"
                        '?page=2&per_page=100>; rel="next"'
                    )
                },
                json=[{"id": "contact-1"}],
            )

        return httpx.Response(200, json=[{"id": "contact-2"}])

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://moneybird.example.test/api/v2",
    )
    client = MoneybirdClient(config=build_config(), http_client=http_client)

    rows = client.get_paginated("/123/contacts.json")

    assert requested_pages == ["1", "2"]
    assert rows == [{"id": "contact-1"}, {"id": "contact-2"}]


def test_get_paginated_increments_page_when_no_link_and_page_is_full():
    requested_pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        requested_pages.append(page)
        if page == "1":
            return httpx.Response(200, json=[{"id": str(index)} for index in range(2)])
        return httpx.Response(200, json=[{"id": "last"}])

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://moneybird.example.test/api/v2",
    )
    client = MoneybirdClient(config=build_config(), http_client=http_client)

    rows = client.get_paginated("/123/sales_invoices.json", params={"per_page": "2"})

    assert requested_pages == ["1", "2"]
    assert rows == [{"id": "0"}, {"id": "1"}, {"id": "last"}]


def test_rate_limit_retries_with_retry_after_header():
    calls = 0
    sleep_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0.25"}, json={})
        return httpx.Response(200, json={"ok": True})

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://moneybird.example.test/api/v2",
    )
    client = MoneybirdClient(
        config=build_config(max_retries=2),
        http_client=http_client,
        sleep=sleep_calls.append,
    )

    response = client.get_json("/123/reports/profit_loss.json")

    assert response == {"ok": True}
    assert calls == 2
    assert sleep_calls == [0.25]


def test_rate_limit_raises_after_retry_exhaustion_without_leaking_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            text="too many requests for secret-token",
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://moneybird.example.test/api/v2",
    )
    client = MoneybirdClient(
        config=build_config(max_retries=0),
        http_client=http_client,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(MoneybirdRateLimitError) as error:
        client.get_json("/123/reports/profit_loss.json")

    assert "secret-token" not in str(error.value)
    assert error.value.response_text == "too many requests for [REDACTED]"


def test_authentication_error_message_does_not_leak_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid token")

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://moneybird.example.test/api/v2",
    )
    client = MoneybirdClient(config=build_config(), http_client=http_client)

    with pytest.raises(MoneybirdAuthenticationError) as error:
        client.list_administrations()

    assert "secret-token" not in str(error.value)
    assert "401" in str(error.value)
