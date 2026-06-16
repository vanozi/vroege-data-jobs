from datetime import date

import pytest

from data_jobs.klauwscore import zoekresultaten_parser
from data_jobs.klauwscore.zoekresultaten_parser import (
    KlauwscoreZoekresultatenParseError,
)


def test_parse_zoekresultaten_rows_extracts_multiple_notities_per_date():
    rows = zoekresultaten_parser.parse_zoekresultaten_rows(
        """
        <table>
          <tr><th>Datum</th><th>Notaties</th></tr>
          <tr>
            <td>2025-12-15</td>
            <td>- Rechtsachter Verband<br>- Vierkant</td>
          </tr>
          <tr>
            <td>2025-06-02</td>
            <td>- Vierkant</td>
          </tr>
        </table>
        """,
        eartag_short="1234",
    )

    assert rows == [
        {
            "eartag_short": "1234",
            "behandeldatum": date(2025, 12, 15),
            "notatie": "Rechtsachter Verband",
        },
        {
            "eartag_short": "1234",
            "behandeldatum": date(2025, 12, 15),
            "notatie": "Vierkant",
        },
        {
            "eartag_short": "1234",
            "behandeldatum": date(2025, 6, 2),
            "notatie": "Vierkant",
        },
    ]


def test_parse_zoekresultaten_rows_returns_empty_for_no_table_rows():
    assert (
        zoekresultaten_parser.parse_zoekresultaten_rows(
            "<p>Geen behandelingen gevonden</p>",
            eartag_short="1234",
        )
        == []
    )


def test_parse_zoekresultaten_rows_raises_for_invalid_date():
    with pytest.raises(KlauwscoreZoekresultatenParseError):
        zoekresultaten_parser.parse_zoekresultaten_rows(
            """
            <table>
              <tr><td>15-12-2025</td><td>- Vierkant</td></tr>
            </table>
            """,
            eartag_short="1234",
        )
