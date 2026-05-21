from datetime import date

import pytest

from data_jobs.klauwscore import stallijst_parser
from data_jobs.klauwscore.stallijst_parser import KlauwscoreStallijstParseError


def test_parse_stallijst_rows_returns_one_row_per_notitie():
    rows = stallijst_parser.parse_stallijst_rows(
        """
        <table>
          <tr>
            <th>Koenummer</th>
            <th>Laatste behandeldatum</th>
            <th>Laatste notaties</th>
          </tr>
          <tr>
            <td>8186</td>
            <td>2026-05-12</td>
            <td>
              - Rechtsachter Tyloom<br>
              - Linksachter Mortelaro<br>
              - Vierkant
            </td>
          </tr>
          <tr>
            <td>0253</td>
            <td>2026-05-12</td>
            <td>- Vierkant</td>
          </tr>
        </table>
        """
    )

    assert rows == [
        {
            "eartag_short": "8186",
            "behandeldatum": date(2026, 5, 12),
            "notatie": "Rechtsachter Tyloom",
        },
        {
            "eartag_short": "8186",
            "behandeldatum": date(2026, 5, 12),
            "notatie": "Linksachter Mortelaro",
        },
        {
            "eartag_short": "8186",
            "behandeldatum": date(2026, 5, 12),
            "notatie": "Vierkant",
        },
        {
            "eartag_short": "0253",
            "behandeldatum": date(2026, 5, 12),
            "notatie": "Vierkant",
        },
    ]


def test_parse_stallijst_rows_limit_applies_to_cows_not_notities():
    rows = stallijst_parser.parse_stallijst_rows(
        """
        <table>
          <tr><td>8186</td><td>2026-05-12</td><td>- A<br>- B</td></tr>
          <tr><td>8011</td><td>2026-05-12</td><td>- C</td></tr>
        </table>
        """,
        limit=1,
    )

    assert [row["notatie"] for row in rows] == ["A", "B"]


def test_parse_stallijst_rows_rejects_invalid_dates():
    with pytest.raises(KlauwscoreStallijstParseError, match="behandeldatum"):
        stallijst_parser.parse_stallijst_rows(
            """
            <table>
              <tr><td>8186</td><td>12-05-2026</td><td>- Vierkant</td></tr>
            </table>
            """
        )
