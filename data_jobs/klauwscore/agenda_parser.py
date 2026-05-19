from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin

import lxml.html as lh


DUTCH_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


class KlauwscoreAgendaParseError(ValueError):
    """Raised when Klauwscore agenda HTML cannot be parsed."""


@dataclass(frozen=True)
class AgendaPdfLink:
    behandeldatum: date
    aantal_koeien: int
    href: str

    def as_dict(self) -> dict[str, object]:
        return {
            "behandeldatum": self.behandeldatum,
            "aantal_koeien": self.aantal_koeien,
            "href": self.href,
        }


def parse_agenda_date(row: Any) -> date:
    """Parse the Dutch agenda date cell into a date."""
    day_text = row.xpath("normalize-space(.//*[contains(@class, 'dayofmonth')])")
    month_year_text = row.xpath("normalize-space(.//*[contains(@class, 'shortdate')])")
    month_year_parts = month_year_text.replace(",", " ").split()

    if not day_text:
        raise KlauwscoreAgendaParseError(
            f"Could not parse agenda day from row: {_short_row_context(row)}"
        )

    if len(month_year_parts) < 2:
        raise KlauwscoreAgendaParseError(
            "Could not parse agenda month/year from row: "
            f"{month_year_text!r}; {_short_row_context(row)}"
        )

    month_name = month_year_parts[0].lower()
    if month_name not in DUTCH_MONTHS:
        raise KlauwscoreAgendaParseError(
            f"Unknown Dutch month {month_name!r} in row: {_short_row_context(row)}"
        )

    try:
        return date(
            int(month_year_parts[1]),
            DUTCH_MONTHS[month_name],
            int(day_text),
        )
    except ValueError as error:
        raise KlauwscoreAgendaParseError(
            f"Invalid agenda date in row: {_short_row_context(row)}"
        ) from error


def parse_aantal_koeien(row: Any) -> int:
    """Parse the cow count from the registration row."""
    count_text = row.xpath("normalize-space(.//*[contains(@class, 'agenda-time')])")
    if not count_text:
        raise KlauwscoreAgendaParseError(
            f"Could not parse agenda cow count from row: {_short_row_context(row)}"
        )

    try:
        return int(count_text.split()[0])
    except (IndexError, ValueError) as error:
        raise KlauwscoreAgendaParseError(
            f"Invalid agenda cow count {count_text!r} in row: {_short_row_context(row)}"
        ) from error


def parse_registratielijst(html_or_table: Any, base_url: str) -> list[AgendaPdfLink]:
    """Parse registration rows and return the Alle notaties PDF links."""
    table = _coerce_table(html_or_table)
    rows = table.xpath(".//tbody/tr") or table.xpath(".//tr[td]")
    notatie_links: list[AgendaPdfLink] = []

    for row in rows:
        alle_notaties_href = row.xpath(
            ".//a[normalize-space(.) = 'Alle notaties']/@href"
        )
        if not alle_notaties_href:
            continue

        notatie_links.append(
            AgendaPdfLink(
                behandeldatum=parse_agenda_date(row),
                aantal_koeien=parse_aantal_koeien(row),
                href=urljoin(base_url, alle_notaties_href[0]),
            )
        )

    return notatie_links


def _coerce_table(html_or_table: Any) -> Any:
    if isinstance(html_or_table, str):
        return lh.fragment_fromstring(html_or_table)

    return html_or_table


def _short_row_context(row: Any) -> str:
    text = " ".join(row.xpath(".//text()"))
    return " ".join(text.split())[:240]
