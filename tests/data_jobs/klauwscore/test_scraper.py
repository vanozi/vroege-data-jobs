from datetime import date

import pytest

from data_jobs.klauwscore import scraper
from data_jobs.klauwscore.config import KlauwscoreConfig
from data_jobs.klauwscore.scraper import KlauwscorePdfDownloadError


PDF_HREF = "http://klauwscore.nl/pdfs/export.pdf"


def test_login_fills_credentials_and_waits_for_networkidle():
    page = FakePage()
    config = build_config()

    scraper.login(page, config)

    assert page.visited_urls == ["http://klauwscore.nl/login"]
    assert page.filled == [
        ('//input[@id="username"]', "user"),
        ('//input[@id="password"]', "secret"),
    ]
    assert page.clicked == ['//input[@id="_submit"]']
    assert page.waited_states == ["networkidle"]


def test_load_agenda_html_loads_configured_agenda_url():
    page = FakePage()
    config = build_config()

    agenda_html = scraper.load_agenda_html(page, config)

    assert page.visited_urls == ["http://klauwscore.nl/veehouder/agenda"]
    assert agenda_html == page.agenda_html


def test_load_stallijst_html_loads_configured_stallijst_url():
    page = FakePage()
    config = build_config()

    stallijst_html = scraper.load_stallijst_html(page, config)

    assert page.visited_urls == ["http://klauwscore.nl/veepedicure/stallijst"]
    assert page.waited_states == ["networkidle"]
    assert stallijst_html == page.stallijst_html


def test_load_zoeken_html_loads_configured_zoeken_url():
    page = FakePage()
    config = build_config()

    zoeken_html = scraper.load_zoeken_html(page, config)

    assert page.visited_urls == ["http://klauwscore.nl/veepedicure/zoeken"]
    assert page.waited_states == ["networkidle"]
    assert zoeken_html == page.zoeken_html


def test_download_pdf_retries_failed_responses_and_returns_body(monkeypatch):
    config = build_config(download_attempts=3)
    page = FakePage(
        request_results=[
            FakeResponse(ok=False, status=502, body=b""),
            FakeResponse(ok=True, status=200, body=b"%PDF"),
        ]
    )
    logger = FakeLogger()
    monkeypatch.setattr(scraper, "logger", logger)

    pdf_bytes = scraper.download_pdf(page, PDF_HREF, config)

    assert pdf_bytes == b"%PDF"
    assert page.context.request.calls == [
        (PDF_HREF, 120_000),
        (PDF_HREF, 120_000),
    ]
    assert logger.warnings[0][0] == "PDF download attempt %s/%s failed for %s: HTTP %s"
    assert logger.warnings[0][1] == (1, 3, PDF_HREF, 502)


def test_download_pdf_retries_request_exceptions_and_returns_body(monkeypatch):
    config = build_config(download_attempts=2)
    page = FakePage(
        request_results=[
            RuntimeError("network unavailable"),
            FakeResponse(ok=True, status=200, body=b"%PDF"),
        ]
    )
    logger = FakeLogger()
    monkeypatch.setattr(scraper, "logger", logger)

    pdf_bytes = scraper.download_pdf(page, PDF_HREF, config)

    assert pdf_bytes == b"%PDF"
    assert len(page.context.request.calls) == 2
    assert logger.warnings[0][0] == "PDF download attempt %s/%s failed for %s: %s"
    assert str(logger.warnings[0][1][3]) == "network unavailable"


def test_download_pdf_empty_body_remains_failure():
    config = build_config(download_attempts=2)
    page = FakePage(
        request_results=[
            FakeResponse(ok=True, status=200, body=b""),
            FakeResponse(ok=True, status=200, body=b""),
        ]
    )

    with pytest.raises(KlauwscorePdfDownloadError) as error:
        scraper.download_pdf(page, PDF_HREF, config)

    assert error.value.href == PDF_HREF
    assert error.value.attempts == 2
    assert error.value.context == "empty PDF body"


def test_scrape_agenda_links_uses_browser_lifecycle(monkeypatch):
    playwright = FakePlaywright()
    monkeypatch.setattr(scraper, "sync_playwright", lambda: playwright)

    links = scraper.scrape_agenda_links(build_config())

    assert playwright.entered is True
    assert playwright.exited is True
    assert playwright.chromium.launched_headless_values == [True]
    assert playwright.chromium.browser.closed is True
    assert len(links) == 2
    assert links[0].behandeldatum == date(2026, 5, 19)
    assert links[0].href == "http://klauwscore.nl/pdfs/export.pdf"


def test_scrape_alle_notaties_pdfs_downloads_limited_documents(monkeypatch):
    playwright = FakePlaywright()
    playwright.chromium.browser.page.context.request.results = [
        FakeResponse(ok=True, status=200, body=b"first"),
    ]
    monkeypatch.setattr(scraper, "sync_playwright", lambda: playwright)
    progress_messages = []

    documents = scraper.scrape_alle_notaties_pdfs(
        build_config(),
        limit=1,
        progress_callback=progress_messages.append,
    )

    assert documents == [
        {
            "behandeldatum": date(2026, 5, 19),
            "aantal_koeien": 24,
            "href": "http://klauwscore.nl/pdfs/export.pdf",
            "pdf_bytes": b"first",
        }
    ]
    assert playwright.chromium.browser.closed is True
    assert any(
        "Limiting run to first 1 PDFs." in message for message in progress_messages
    )


def test_scrape_alle_notaties_pdfs_skips_existing_dates_before_download(monkeypatch):
    playwright = FakePlaywright()
    playwright.chromium.browser.page.context.request.results = [
        FakeResponse(ok=True, status=200, body=b"second"),
    ]
    monkeypatch.setattr(scraper, "sync_playwright", lambda: playwright)
    progress_messages = []

    documents = scraper.scrape_alle_notaties_pdfs(
        build_config(),
        existing_behandeldatums={date(2026, 5, 19)},
        progress_callback=progress_messages.append,
    )

    assert documents == [
        {
            "behandeldatum": date(2026, 5, 20),
            "aantal_koeien": 8,
            "href": "http://klauwscore.nl/pdfs/second.pdf",
            "pdf_bytes": b"second",
        }
    ]
    assert playwright.chromium.browser.page.context.request.calls == [
        ("http://klauwscore.nl/pdfs/second.pdf", 120_000)
    ]
    assert "Skipping 1 PDFs with dates already stored in the database." in (
        progress_messages
    )


def test_scrape_stallijst_rows_uses_browser_lifecycle(monkeypatch):
    playwright = FakePlaywright()
    monkeypatch.setattr(scraper, "sync_playwright", lambda: playwright)

    rows = scraper.scrape_stallijst_rows(build_config(), limit=1)

    assert playwright.chromium.browser.closed is True
    assert rows == [
        {
            "eartag_short": "8186",
            "behandeldatum": date(2026, 5, 12),
            "notatie": "Rechtsachter Tyloom",
        },
        {
            "eartag_short": "8186",
            "behandeldatum": date(2026, 5, 12),
            "notatie": "Vierkant",
        },
    ]


def test_scrape_zoekresultaten_rows_reuses_one_login_and_page(monkeypatch):
    playwright = FakePlaywright()
    monkeypatch.setattr(scraper, "sync_playwright", lambda: playwright)
    cows = [{"eartag_short": "8186"}, {"eartag_short": "8011"}]

    rows = scraper.scrape_zoekresultaten_rows_for_cows(build_config(), cows)

    page = playwright.chromium.browser.page
    assert playwright.chromium.browser.closed is True
    assert page.visited_urls == [
        "http://klauwscore.nl/login",
        "http://klauwscore.nl/veepedicure/zoeken",
    ]
    assert page.filled[-4:] == [
        ("#veehouderZoeken", ""),
        ("#veehouderZoeken", "8186"),
        ("#veehouderZoeken", ""),
        ("#veehouderZoeken", "8011"),
    ]
    assert page.pressed == [
        ("#veehouderZoeken", "Enter"),
        ("#veehouderZoeken", "Enter"),
    ]
    assert len(page.evaluated_scripts) == 2
    assert rows == [
        {
            "eartag_short": "8186",
            "behandeldatum": date(2025, 12, 15),
            "notatie": "Vierkant",
        },
        {
            "eartag_short": "8011",
            "behandeldatum": date(2025, 6, 2),
            "notatie": "Rechtsachter Verband",
        },
    ]


def test_search_koe_behandelingen_clears_old_table_before_search():
    playwright = FakePlaywright()
    page = playwright.chromium.browser.page
    page.goto("http://klauwscore.nl/veepedicure/zoeken")

    rows = scraper.search_koe_behandelingen(page, "8186")

    assert len(page.evaluated_scripts) == 1
    assert rows == [
        {
            "eartag_short": "8186",
            "behandeldatum": date(2025, 12, 15),
            "notatie": "Vierkant",
        }
    ]


def build_config(download_attempts: int = 3) -> KlauwscoreConfig:
    return KlauwscoreConfig(
        username="user",
        password="secret",
        download_attempts=download_attempts,
    )


class FakeResponse:
    def __init__(self, ok: bool, status: int, body: bytes):
        self.ok = ok
        self.status = status
        self._body = body

    def body(self) -> bytes:
        return self._body


class FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append((message, args))


class FakeRequest:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def get(self, href, timeout):
        self.calls.append((href, timeout))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result

        return result


class FakeContext:
    def __init__(self, request_results=None):
        self.request = FakeRequest(request_results)


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def fill(self, value):
        self.page.filled.append((self.selector, value))
        self.page.current_search_value = value

    def click(self):
        self.page.clicked.append(self.selector)

    def press(self, key):
        self.page.pressed.append((self.selector, key))

    def inner_text(self, timeout):
        return self.page.table_text()


class FakePage:
    def __init__(self, request_results=None):
        self.context = FakeContext(request_results)
        self.visited_urls = []
        self.filled = []
        self.clicked = []
        self.pressed = []
        self.waited_states = []
        self.waited_selectors = []
        self.waited_functions = []
        self.evaluated_scripts = []
        self.current_search_value = ""
        self.agenda_html = """
        <table>
          <tr>
            <td><span class="dayofmonth">19</span></td>
            <td><span class="shortdate">mei, 2026</span></td>
            <td><span class="agenda-time">24 koeien</span></td>
            <td><a href="/pdfs/export.pdf">Alle notaties</a></td>
          </tr>
          <tr>
            <td><span class="dayofmonth">20</span></td>
            <td><span class="shortdate">mei, 2026</span></td>
            <td><span class="agenda-time">8 koeien</span></td>
            <td><a href="/pdfs/second.pdf">Alle notaties</a></td>
          </tr>
        </table>
        """
        self.stallijst_html = """
        <table>
          <tr>
            <th>Koenummer</th>
            <th>Laatste behandeldatum</th>
            <th>Laatste notaties</th>
          </tr>
          <tr>
            <td>8186</td>
            <td>2026-05-12</td>
            <td>- Rechtsachter Tyloom<br>- Vierkant</td>
          </tr>
          <tr>
            <td>8011</td>
            <td>2026-05-12</td>
            <td>- Vierkant</td>
          </tr>
        </table>
        """
        self.zoekresultaten_by_eartag_short = {
            "8186": """
            <table>
              <tr><th>Datum</th><th>Notaties</th></tr>
              <tr><td>2025-12-15</td><td>- Vierkant</td></tr>
            </table>
            """,
            "8011": """
            <table>
              <tr><th>Datum</th><th>Notaties</th></tr>
              <tr><td>2025-06-02</td><td>- Rechtsachter Verband</td></tr>
            </table>
            """,
        }
        self.zoeken_html = self.zoekresultaten_by_eartag_short["8186"]

    def goto(self, url):
        self.visited_urls.append(url)

    def locator(self, selector):
        return FakeLocator(self, selector)

    def wait_for_load_state(self, state):
        self.waited_states.append(state)

    def wait_for_selector(self, selector, timeout):
        self.waited_selectors.append((selector, timeout))

    def wait_for_function(self, script, timeout, arg=None):
        self.waited_functions.append(arg)

    def evaluate(self, script):
        self.evaluated_scripts.append(script)

    def inner_html(self, selector):
        assert selector == "//div[@class='account-wrapper']"
        return self.agenda_html

    def content(self):
        if self.visited_urls and self.visited_urls[-1].endswith("/zoeken"):
            if not self.current_search_value:
                return self.zoeken_html

            return self.zoekresultaten_by_eartag_short.get(
                self.current_search_value,
                "<table></table>",
            )

        return self.stallijst_html

    def table_text(self):
        return " ".join(
            self.content()
            .replace("<table>", " ")
            .replace("</table>", " ")
            .replace("<tr>", " ")
            .replace("</tr>", " ")
            .replace("<th>", " ")
            .replace("</th>", " ")
            .replace("<td>", " ")
            .replace("</td>", " ")
            .split()
        )


class FakeBrowser:
    def __init__(self):
        self.page = FakePage()
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self):
        self.browser = FakeBrowser()
        self.launched_headless_values = []

    def launch(self, headless):
        self.launched_headless_values.append(headless)
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.exited = True
