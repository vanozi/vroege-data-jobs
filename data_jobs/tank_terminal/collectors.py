"""Collect Tank Terminal diesel transaction rows."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from data_jobs.tank_terminal.config import TankTerminalConfig
from data_jobs.tank_terminal.page_objects.login_page import LoginPage
from data_jobs.tank_terminal.page_objects.overview_page import OverviewPage
from data_jobs.tank_terminal.page_objects.transactions_page import TransactionsPage
from data_jobs.tank_terminal.parsers import ParsedTankTransaction
from data_jobs.tank_terminal.parsers import parse_transactions_table


@dataclass(frozen=True)
class TankTerminalCollectionResult:
    """Collected and deduplicated Tank Terminal transactions."""

    rows: list[ParsedTankTransaction]
    duplicate_count: int = 0

    def summary_counts(self) -> dict[str, int]:
        """Return counts for CLI output and logging."""
        return {
            "transactions": len(self.rows) + self.duplicate_count,
            "deduped_transactions": len(self.rows),
            "duplicate_transactions": self.duplicate_count,
        }


def collect_tank_terminal_rows(
    config: TankTerminalConfig,
    limit: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> TankTerminalCollectionResult:
    """Collect normalized transactions from the Tank Terminal web UI."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        try:
            page = browser.new_page()
            _log(progress_callback, "Opening Tank Terminal login page.")
            page.goto(f"{config.base_url}/cgi-bin/index.php")
            _login(page, config)
            _open_transactions(page)
            rows = _parse_visible_transactions(page)
        finally:
            browser.close()

    if limit is not None:
        rows = rows[:limit]

    deduped_rows, duplicate_count = _dedupe_transactions(rows)
    _log(
        progress_callback,
        (
            "Collected Tank Terminal transactions: "
            f"rows={len(rows)} deduped={len(deduped_rows)} duplicates={duplicate_count}"
        ),
    )
    return TankTerminalCollectionResult(
        rows=deduped_rows,
        duplicate_count=duplicate_count,
    )


def _login(page: Page, config: TankTerminalConfig) -> None:
    language_select = page.locator(LoginPage.language_select)
    if language_select.count() > 0:
        language_select.select_option("English")

    page.locator(LoginPage.username_input).fill(config.username)
    page.locator(LoginPage.password_input).fill(config.password)
    page.locator(LoginPage.confirm_button).click()
    page.wait_for_load_state("networkidle")

    continue_button = page.locator(LoginPage.continue_button)
    if continue_button.count() > 0 and continue_button.is_visible():
        continue_button.click()
        page.wait_for_load_state("networkidle")

    username_input = page.locator(LoginPage.username_input)
    if username_input.count() > 0 and username_input.is_visible():
        raise ValueError(
            "Tank Terminal login did not complete; check "
            "TANK_TERMINAL_USERNAME and TANK_TERMINAL_PASSWORD."
        )


def _open_transactions(page: Page) -> None:
    for selector in OverviewPage.transaction_links:
        link = page.locator(selector).first
        try:
            link.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError:
            continue

        link.click(timeout=5_000)
        page.wait_for_load_state("networkidle")
        break

    page.locator(TransactionsPage.transaction_tables).first.wait_for(state="visible")


def _parse_visible_transactions(page: Page) -> list[ParsedTankTransaction]:
    transaction_tables = page.locator(TransactionsPage.transaction_tables)
    table_count = transaction_tables.count()
    table_previews = []

    for index in range(table_count):
        table = transaction_tables.nth(index)
        try:
            table.wait_for(state="visible", timeout=2_000)
        except PlaywrightTimeoutError:
            continue

        table_previews.append(_preview_text(table.inner_text(timeout=2_000)))
        rows = parse_transactions_table(table.inner_html())
        if rows:
            return rows

    page_html = page.content()
    rows = parse_transactions_table(page_html)
    if rows:
        return rows

    raise ValueError(
        "Could not find Tank Terminal transaction rows on the transactions page. "
        f"candidate_tables={table_count} previews={table_previews[:5]}"
    )


def _preview_text(value: str) -> str:
    return " ".join(value.split())[:300]


def _dedupe_transactions(
    rows: list[ParsedTankTransaction],
) -> tuple[list[ParsedTankTransaction], int]:
    seen_transaction_numbers = set()
    deduped_rows = []

    for row in rows:
        if row.transaction_number in seen_transaction_numbers:
            continue

        seen_transaction_numbers.add(row.transaction_number)
        deduped_rows.append(row)

    return deduped_rows, len(rows) - len(deduped_rows)


def _log(
    progress_callback: Optional[Callable[[str], None]],
    message: str,
) -> None:
    if progress_callback is None:
        return

    progress_callback(message)
