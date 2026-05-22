"""Collect Tank Terminal diesel transaction rows."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, sync_playwright

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
            table_html = page.inner_html(TransactionsPage.transaction_table)
        finally:
            browser.close()

    rows = parse_transactions_table(table_html)
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


def _open_transactions(page: Page) -> None:
    page.locator(OverviewPage.transaction_list).click()
    page.wait_for_load_state("networkidle")
    page.locator(TransactionsPage.transaction_table).wait_for(state="visible")


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
