from datetime import date
from typing import Optional

from lxml import html


class KlauwscoreStallijstParseError(ValueError):
    """Raised when the Klauwscore stallijst table cannot be parsed."""


def parse_stallijst_rows(
    html_text: str,
    limit: Optional[int] = None,
) -> list[dict[str, object]]:
    """Parse the Klauwscore stallijst table to one row per notitie."""
    document = html.fromstring(html_text)
    table_rows = document.xpath("//table//tr[td]")
    parsed_rows: list[dict[str, object]] = []
    parsed_cows = 0

    for table_row in table_rows:
        cells = table_row.xpath("./td")
        if len(cells) < 3:
            continue

        if limit is not None and parsed_cows >= limit:
            break

        eartag_short = _cell_text(cells[0])
        behandeldatum = _parse_date(_cell_text(cells[1]))
        notities = _parse_notities(cells[2])
        if not eartag_short or behandeldatum is None:
            continue

        parsed_cows += 1
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


def _parse_date(raw_value: str) -> date | None:
    if not raw_value:
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise KlauwscoreStallijstParseError(
            f"Could not parse stallijst behandeldatum: {raw_value}"
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
