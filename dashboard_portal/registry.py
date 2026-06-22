"""Dashboard registry for the Flask portal."""

from dataclasses import dataclass
import json
import os
from typing import Any


@dataclass(frozen=True)
class DashboardLink:
    """A dashboard shown on the portal homepage."""

    name: str
    description: str
    url: str
    status: str


DEFAULT_DASHBOARDS = [
    DashboardLink(
        name="Kippen dashboard",
        description="Analyse en trends van leghennenproductie per koppel.",
        url="/kippen-dashboard",
        status="Productie",
    ),
    DashboardLink(
        name="Klauwgezondheid",
        description="Mortellaro en klauwgezondheid van de actieve koppel.",
        url="/klauwgezondheid",
        status="Productie",
    ),
    DashboardLink(
        name="Tanken",
        description="Dieseltransacties per voertuig, chauffeur en CSV-import.",
        url="/tank-terminal",
        status="Concept",
    ),
    DashboardLink(
        name="Moneybird",
        description="Boekhoudkundig overzicht van facturen, rapporten en bankmutaties.",
        url="/moneybird",
        status="Concept",
    ),
]


def get_dashboard_links() -> list[DashboardLink]:
    """Return dashboards that should be visible on the portal homepage."""
    raw_dashboards = os.getenv("PORTAL_DASHBOARDS_JSON", "").strip()
    if not raw_dashboards:
        return list(DEFAULT_DASHBOARDS)

    parsed_dashboards = json.loads(raw_dashboards)
    if not isinstance(parsed_dashboards, list):
        raise ValueError("PORTAL_DASHBOARDS_JSON must be a JSON list")

    return [_dashboard_from_mapping(item) for item in parsed_dashboards]


def _dashboard_from_mapping(item: Any) -> DashboardLink:
    if not isinstance(item, dict):
        raise ValueError("Each configured dashboard must be a JSON object")

    return DashboardLink(
        name=_required_str(item, "name"),
        description=_required_str(item, "description"),
        url=_required_dashboard_url(item),
        status=str(item.get("status") or "Concept"),
    )


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configured dashboard is missing {key}")

    return value.strip()


def _required_dashboard_url(item: dict[str, Any]) -> str:
    url = _required_str(item, "url")
    if not url.startswith("/"):
        raise ValueError("Configured dashboard url must start with /")

    return url
