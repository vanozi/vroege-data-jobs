from datetime import date
from typing import Optional

from lxml import html


class KlauwscoreZoekresultatenParseError(ValueError):
    """Raised when Klauwscore search results cannot be parsed."""


def parse_zoekresultaten_rows(
    html_text: str,
    eartag_short: str,
) -> list[dict[str, object]]:
    """Parse Klauwscore cow search results to one row per notitie."""
    document = html.fromstring(html_text)
    table_rows = document.xpath("//table//tr[td]")
    parsed_rows: list[dict[str, object]] = []

    for table_row in table_rows:
        cells = table_row.xpath("./td")
        if len(cells) < 2:
            continue

        behandeldatum = _parse_date(_cell_text(cells[0]))
        notities = _parse_notities(cells[1])
        if behandeldatum is None:
            continue

        for notitie in notities:
            parsed_rows.append(
                {
                    "eartag_short": eartag_short,
                    "behandeldatum": behandeldatum,
                    "notatie": notitie,
                }
            )

    return parsed_rows


def _cell_text(cell) -> str:
    return " ".join(cell.text_content().strip().split())


def _parse_date(raw_value: str) -> Optional[date]:
    if not raw_value:
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise KlauwscoreZoekresultatenParseError(
            f"Could not parse zoekresultaten behandeldatum: {raw_value}"
        ) from error


def _parse_notities(cell) -> list[str]:
    notities: list[str] = []
    for raw_text in cell.xpath(".//text()"):
        notitie = " ".join(raw_text.strip().split())
        if not notitie:
            continue

        if notitie.startswith("-"):
            notitie = notitie[1:].strip()

        if notitie:
            notities.append(notitie)

    return notities
