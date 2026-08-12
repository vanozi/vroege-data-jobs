"""Collect Tank Terminal diesel transaction rows."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from database.models.tank_transaction import TankTransaction
from data_jobs.tank_terminal import csv_parsers
from data_jobs.tank_terminal.config import TankTerminalConfig
from data_jobs.tank_terminal.page_objects.export_transactions_page import (
    ExportTransactionsPage,
)
from data_jobs.tank_terminal.page_objects.login_page import LoginPage
from data_jobs.tank_terminal.page_objects.overview_page import OverviewPage


@dataclass(frozen=True)
class TankTerminalCollectionResult:
    """Collected and deduplicated Tank Terminal transactions."""

    rows: list[TankTransaction]
    duplicate_count: int = 0

    def summary_counts(self) -> dict[str, int]:
        """Return counts for CLI output and logging."""
        return {
            "transactions": len(self.rows) + self.duplicate_count,
            "deduped_transactions": len(self.rows),
            "duplicate_transactions": self.duplicate_count,
        }


@dataclass(frozen=True)
class TankTerminalExportDateRange:
    """Date-time filter values for the ProFleet transaction export."""

    start_date_time: Optional[str]
    end_date_time: Optional[str]


def collect_tank_terminal_rows(
    config: TankTerminalConfig,
    limit: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    latest_start_date_time: Optional[datetime] = None,
) -> TankTerminalCollectionResult:
    """Collect normalized transactions from the Tank Terminal CSV export."""
    date_range = _build_export_date_range(latest_start_date_time)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        try:
            page = browser.new_page()
            _log(progress_callback, "Opening Tank Terminal login page.")
            page.goto(f"{config.base_url}/cgi-bin/index.php")
            _login(page, config)
            _open_export_transactions(page)
            _select_export_template(page)
            _fill_export_filters(page, date_range)
            csv_text = _download_transactions_csv(page)
        finally:
            browser.close()

    rows = csv_parsers.parse_tank_transactions_csv_text(csv_text)
    if limit is not None:
        rows = rows[:limit]

    _log(
        progress_callback,
        f"Collected Tank Terminal transactions from CSV export: rows={len(rows)}",
    )
    return TankTerminalCollectionResult(rows=rows)


def _build_export_date_range(
    latest_start_date_time: Optional[datetime],
    now: Optional[datetime] = None,
) -> TankTerminalExportDateRange:
    if latest_start_date_time is None:
        return TankTerminalExportDateRange(
            start_date_time=None,
            end_date_time=None,
        )

    current_datetime = now if now is not None else datetime.now()
    start_date = latest_start_date_time.date() - timedelta(days=1)
    end_date = current_datetime.date() + timedelta(days=1)
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.min)

    return TankTerminalExportDateRange(
        start_date_time=start_datetime.strftime("%d/%m/%Y %H:%M:%S"),
        end_date_time=end_datetime.strftime("%d/%m/%Y %H:%M:%S"),
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


def _open_export_transactions(page: Page) -> None:
    _click_first_visible(page, OverviewPage.administration_link)
    _click_first_visible(page, OverviewPage.reports_exports_link)
    _click_first_visible(page, OverviewPage.export_link)
    page.locator(ExportTransactionsPage.export_transactions_page_title).first.wait_for(state="visible")


def _select_export_template(page: Page) -> None:
    page.locator(ExportTransactionsPage.template_select).first.select_option(
        ExportTransactionsPage.template_option_value
    )
    page.wait_for_load_state("networkidle")


def _fill_export_filters(page: Page, date_range: TankTerminalExportDateRange) -> None:
    page.wait_for_load_state("networkidle")
    _fill_first_available(
        page,
        ExportTransactionsPage.start_date_input,
        date_range.start_date_time,
    )
    _fill_first_available(
        page,
        ExportTransactionsPage.end_date_input,
        date_range.end_date_time,
    )


def _download_transactions_csv(page: Page) -> str:
    with page.expect_download() as download_info:
        _click_first_visible(page, ExportTransactionsPage.export_button)

    download = download_info.value
    download_path = download.path()
    if download_path is None:
        raise ValueError("Tank Terminal export did not produce a local download path.")

    return Path(download_path).read_text(encoding="utf-8-sig")


def _fill_first_available(
    page: Page,
    selectors: list[str],
    value: Optional[str],
) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=2_000)
        except PlaywrightTimeoutError:
            continue

        locator.fill(value or "")
        return

    raise ValueError(f"Could not find Tank Terminal export input: {selectors}")


def _click_first_visible(page: Page, selectors: list[str]) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError:
            continue

        locator.click(timeout=5_000)
        page.wait_for_load_state("networkidle")
        return

    raise ValueError(f"Could not find Tank Terminal export target: {selectors}")


def _log(
    progress_callback: Optional[Callable[[str], None]],
    message: str,
) -> None:
    if progress_callback is None:
        return

    progress_callback(message)
