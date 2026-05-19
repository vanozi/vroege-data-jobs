from datetime import date

import lxml.html as lh
import pytest

from data_jobs.klauwscore import agenda_parser
from data_jobs.klauwscore.agenda_parser import KlauwscoreAgendaParseError


def test_parse_registratielijst_returns_alle_notaties_links_with_joined_urls():
    links = agenda_parser.parse_registratielijst(
        """
        <table>
          <tbody>
            <tr>
              <td><span class="dayofmonth">19</span></td>
              <td><span class="shortdate">mei, 2026</span></td>
              <td><span class="agenda-time">24 koeien</span></td>
              <td><a href="/pdfs/alle-notaties-1.pdf">Alle notaties</a></td>
            </tr>
            <tr>
              <td><span class="dayofmonth">20</span></td>
              <td><span class="shortdate">mei, 2026</span></td>
              <td><span class="agenda-time">5 koeien</span></td>
              <td><a href="/pdfs/other.pdf">Andere link</a></td>
            </tr>
          </tbody>
        </table>
        """,
        "http://klauwscore.nl",
    )

    assert len(links) == 1
    assert links[0].behandeldatum == date(2026, 5, 19)
    assert links[0].aantal_koeien == 24
    assert links[0].href == "http://klauwscore.nl/pdfs/alle-notaties-1.pdf"
    assert links[0].as_dict() == {
        "behandeldatum": date(2026, 5, 19),
        "aantal_koeien": 24,
        "href": "http://klauwscore.nl/pdfs/alle-notaties-1.pdf",
    }


def test_parse_registratielijst_accepts_lxml_table():
    table = lh.fragment_fromstring(
        """
        <table>
          <tr>
            <td><span class="dayofmonth">1</span></td>
            <td><span class="shortdate">januari, 2026</span></td>
            <td><span class="agenda-time">1 koe</span></td>
            <td><a href="https://cdn.example/export.pdf">Alle notaties</a></td>
          </tr>
        </table>
        """
    )

    links = agenda_parser.parse_registratielijst(table, "http://klauwscore.nl")

    assert links[0].behandeldatum == date(2026, 1, 1)
    assert links[0].href == "https://cdn.example/export.pdf"


def test_parse_agenda_date_raises_project_error_for_malformed_date():
    row = parse_row(
        """
        <tr>
          <td><span class="dayofmonth">19</span></td>
          <td><span class="shortdate">not-a-month, 2026</span></td>
          <td><span class="agenda-time">24 koeien</span></td>
          <td><a href="/pdf">Alle notaties</a></td>
        </tr>
        """
    )

    with pytest.raises(KlauwscoreAgendaParseError, match="Unknown Dutch month"):
        agenda_parser.parse_agenda_date(row)


def test_parse_aantal_koeien_raises_project_error_for_missing_count():
    row = parse_row(
        """
        <tr>
          <td><span class="dayofmonth">19</span></td>
          <td><span class="shortdate">mei, 2026</span></td>
          <td><a href="/pdf">Alle notaties</a></td>
        </tr>
        """
    )

    with pytest.raises(KlauwscoreAgendaParseError, match="cow count"):
        agenda_parser.parse_aantal_koeien(row)


def test_parse_aantal_koeien_raises_project_error_for_invalid_count():
    row = parse_row(
        """
        <tr>
          <td><span class="dayofmonth">19</span></td>
          <td><span class="shortdate">mei, 2026</span></td>
          <td><span class="agenda-time">geen koeien</span></td>
          <td><a href="/pdf">Alle notaties</a></td>
        </tr>
        """
    )

    with pytest.raises(KlauwscoreAgendaParseError, match="Invalid agenda cow count"):
        agenda_parser.parse_aantal_koeien(row)


def parse_row(html: str):
    return lh.fragment_fromstring(html)
