from typing import Callable, Optional

from playwright.sync_api import sync_playwright

from data_jobs import logger as job_logger
from data_jobs.klauwscore import agenda_parser
from data_jobs.klauwscore import stallijst_parser
from data_jobs.klauwscore.agenda_parser import AgendaPdfLink
from data_jobs.klauwscore.config import KlauwscoreConfig


logger = job_logger.get_job_logger(__file__)


class KlauwscoreScrapeError(RuntimeError):
    """Raised when Klauwscore browser scraping fails."""


class KlauwscorePdfDownloadError(KlauwscoreScrapeError):
    """Raised when a Klauwscore PDF cannot be downloaded."""

    def __init__(
        self,
        href: str,
        attempts: int,
        context: str,
    ):
        self.href = href
        self.attempts = attempts
        self.context = context
        super().__init__(
            f"Failed to download PDF after {attempts} attempts: {href}; {context}"
        )


def login(page, config: KlauwscoreConfig) -> None:
    """Log in to Klauwscore."""
    page.goto(config.login_url)
    page.locator('//input[@id="username"]').fill(config.username)
    page.locator('//input[@id="password"]').fill(config.password)
    page.locator('//input[@id="_submit"]').click()
    page.wait_for_load_state("networkidle")


def load_agenda_html(page, config: KlauwscoreConfig) -> str:
    """Load the Klauwscore agenda and return the account-wrapper HTML."""
    page.goto(config.agenda_url)
    return page.inner_html("//div[@class='account-wrapper']")


def load_stallijst_html(page, config: KlauwscoreConfig) -> str:
    """Load the Klauwscore stallijst and return the full page HTML."""
    page.goto(config.stallijst_url)
    page.wait_for_load_state("networkidle")
    return page.content()


def download_pdf(page, href: str, config: KlauwscoreConfig) -> bytes:
    """Download a PDF through the authenticated Playwright context."""
    last_context = "no response"

    for attempt in range(1, config.download_attempts + 1):
        try:
            response = page.context.request.get(
                href,
                timeout=config.download_timeout_ms,
            )
        except Exception as error:
            last_context = str(error)
            logger.warning(
                "PDF download attempt %s/%s failed for %s: %s",
                attempt,
                config.download_attempts,
                href,
                error,
            )
            continue

        if not response.ok:
            last_context = f"HTTP {response.status}"
            logger.warning(
                "PDF download attempt %s/%s failed for %s: HTTP %s",
                attempt,
                config.download_attempts,
                href,
                response.status,
            )
            continue

        body = response.body()
        if body:
            return body

        last_context = "empty PDF body"
        logger.warning(
            "PDF download attempt %s/%s returned an empty body for %s",
            attempt,
            config.download_attempts,
            href,
        )

    raise KlauwscorePdfDownloadError(
        href=href,
        attempts=config.download_attempts,
        context=last_context,
    )


def scrape_agenda_links(config: KlauwscoreConfig) -> list[AgendaPdfLink]:
    """Scrape all Alle notaties PDF links from the registration list."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        try:
            page = browser.new_page()
            login(page, config)
            agenda_html = load_agenda_html(page, config)
        finally:
            browser.close()

    return agenda_parser.parse_registratielijst(agenda_html, config.base_url)


def scrape_alle_notaties_pdfs(
    config: KlauwscoreConfig,
    limit: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    continue_on_document_error: bool = False,
    failure_callback: Optional[Callable[[AgendaPdfLink, Exception], None]] = None,
) -> list[dict[str, object]]:
    """Download all Alle notaties PDFs and return metadata plus PDF bytes."""
    pdf_documents: list[dict[str, object]] = []

    with sync_playwright() as playwright:
        _report(progress_callback, "Starting browser and logging in to Klauwscore...")
        browser = playwright.chromium.launch(headless=config.headless)
        try:
            page = browser.new_page()
            login(page, config)

            _report(progress_callback, "Loading Klauwscore agenda...")
            agenda_html = load_agenda_html(page, config)
            notatie_links = agenda_parser.parse_registratielijst(
                agenda_html,
                config.base_url,
            )
            _report(
                progress_callback,
                f"Found {len(notatie_links)} Alle notaties PDFs.",
            )

            if limit is not None:
                notatie_links = notatie_links[:limit]
                _report(
                    progress_callback,
                    f"Limiting run to first {len(notatie_links)} PDFs.",
                )

            for index, notatie_link in enumerate(notatie_links, start=1):
                _report(
                    progress_callback,
                    "Downloading PDF "
                    f"{index}/{len(notatie_links)} for date "
                    f"{notatie_link.behandeldatum}: {notatie_link.href}",
                )
                try:
                    pdf_bytes = download_pdf(page, notatie_link.href, config)
                except Exception as error:
                    if not continue_on_document_error:
                        raise

                    if failure_callback is not None:
                        failure_callback(notatie_link, error)
                    continue

                pdf_documents.append(
                    {
                        **notatie_link.as_dict(),
                        "pdf_bytes": pdf_bytes,
                    }
                )
        finally:
            browser.close()
            _report(
                progress_callback,
                "Finished downloading Klauwscore PDFs.",
            )

    return pdf_documents


def scrape_stallijst_rows(
    config: KlauwscoreConfig,
    limit: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[dict[str, object]]:
    """Scrape Klauwscore stallijst rows from the authenticated table page."""
    with sync_playwright() as playwright:
        _report(progress_callback, "Starting browser and logging in to Klauwscore...")
        browser = playwright.chromium.launch(headless=config.headless)
        try:
            page = browser.new_page()
            login(page, config)

            _report(progress_callback, "Loading Klauwscore stallijst...")
            stallijst_html = load_stallijst_html(page, config)
        finally:
            browser.close()

    rows = stallijst_parser.parse_stallijst_rows(stallijst_html, limit=limit)
    _report(progress_callback, f"Parsed {len(rows)} notitie rows from stallijst.")
    return rows


def _report(
    progress_callback: Optional[Callable[[str], None]],
    message: str,
) -> None:
    if progress_callback is None:
        return

    progress_callback(message)
