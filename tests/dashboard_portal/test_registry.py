"""Tests for dashboard portal registry."""

import json

import pytest

from dashboard_portal import registry


@pytest.fixture(autouse=True)
def clear_dashboard_registry_env(monkeypatch):
    monkeypatch.delenv("PORTAL_DASHBOARDS_JSON", raising=False)


def test_dashboard_registry_contains_default_dashboards():
    dashboards = registry.get_dashboard_links()

    assert len(dashboards) == 2
    assert dashboards[0].name == "Klauwgezondheid"
    assert dashboards[0].url == "/klauwgezondheid"
    assert dashboards[1].name == "Tanken"
    assert dashboards[1].url == "/tank-terminal"


def test_dashboard_registry_can_be_configured_from_environment(monkeypatch):
    monkeypatch.setenv(
        "PORTAL_DASHBOARDS_JSON",
        json.dumps(
            [
                {
                    "name": "Melkproductie",
                    "description": "Melkproductie dashboard.",
                    "url": "/melkproductie",
                    "status": "Concept",
                },
                {
                    "name": "Vruchtbaarheid",
                    "description": "Vruchtbaarheid dashboard.",
                    "url": "/vruchtbaarheid",
                },
            ]
        ),
    )

    dashboards = registry.get_dashboard_links()

    assert [dashboard.name for dashboard in dashboards] == [
        "Melkproductie",
        "Vruchtbaarheid",
    ]
    assert dashboards[0].url == "/melkproductie"
    assert dashboards[1].status == "Concept"


def test_dashboard_registry_rejects_non_list_json(monkeypatch):
    monkeypatch.setenv("PORTAL_DASHBOARDS_JSON", json.dumps({"name": "invalid"}))

    with pytest.raises(ValueError, match="JSON list"):
        registry.get_dashboard_links()


def test_dashboard_registry_rejects_url_without_leading_slash(monkeypatch):
    monkeypatch.setenv(
        "PORTAL_DASHBOARDS_JSON",
        json.dumps(
            [
                {
                    "name": "Melkproductie",
                    "description": "Melkproductie dashboard.",
                    "url": "melkproductie",
                }
            ]
        ),
    )

    with pytest.raises(ValueError, match="must start with /"):
        registry.get_dashboard_links()
