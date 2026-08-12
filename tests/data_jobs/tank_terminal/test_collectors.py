from datetime import datetime
from pathlib import Path

from database.models.tank_transaction import TankTransaction
from data_jobs.tank_terminal import collectors
from data_jobs.tank_terminal.collectors import TankTerminalCollectionResult
from data_jobs.tank_terminal.page_objects.export_transactions_page import (
    ExportTransactionsPage,
)
from data_jobs.tank_terminal.page_objects.overview_page import OverviewPage


def test_build_export_date_range_uses_day_before_latest_and_tomorrow():
    date_range = collectors._build_export_date_range(
        datetime(2026, 8, 5, 14, 20, 0),
        now=datetime(2026, 8, 7, 11, 0, 0),
    )

    assert date_range.start_date_time == "04/08/2026 00:00:00"
    assert date_range.end_date_time == "08/08/2026 00:00:00"


def test_build_export_date_range_leaves_fields_empty_without_database_timestamp():
    date_range = collectors._build_export_date_range(
        None,
        now=datetime(2026, 8, 7, 11, 0, 0),
    )

    assert date_range.start_date_time is None
    assert date_range.end_date_time is None


def test_export_page_objects_define_navigation_and_form_selectors():
    assert "Administration" in OverviewPage.administration_links[0]
    assert "Export" in OverviewPage.export_links[0]
    assert "Transactions" in OverviewPage.export_transaction_links[0]
    assert ExportTransactionsPage.template_option_name == "Export before purge"
    assert ExportTransactionsPage.start_date_inputs
    assert ExportTransactionsPage.end_date_inputs
    assert ExportTransactionsPage.export_buttons


def test_collection_result_summary_counts_exported_models_without_deduping():
    result = TankTerminalCollectionResult(
        rows=[
            TankTransaction(
                transaction_number="001",
                start_date_time=datetime(2026, 8, 4, 9, 0, 0),
                quantity_liters=12.5,
            )
        ]
    )

    assert result.summary_counts() == {
        "transactions": 1,
        "deduped_transactions": 1,
        "duplicate_transactions": 0,
    }


def test_fill_export_filters_fills_dates_when_database_has_transactions():
    page = FakePage()
    date_range = collectors.TankTerminalExportDateRange(
        start_date_time="04/08/2026 00:00:00",
        end_date_time="08/08/2026 00:00:00",
    )

    collectors._fill_export_filters(page, date_range)

    fill_calls = [call for call in page.calls if call[0] == "fill"]
    assert fill_calls[0][2] == "04/08/2026 00:00:00"
    assert fill_calls[1][2] == "08/08/2026 00:00:00"


def test_fill_export_filters_clears_dates_when_database_is_empty():
    page = FakePage()
    date_range = collectors.TankTerminalExportDateRange(
        start_date_time=None,
        end_date_time=None,
    )

    collectors._fill_export_filters(page, date_range)

    fill_calls = [call for call in page.calls if call[0] == "fill"]
    assert fill_calls[0][2] == ""
    assert fill_calls[1][2] == ""


def test_download_transactions_csv_reads_downloaded_file():
    csv_path = Path(__file__).parent / "fixtures" / "minimal_export.csv"
    page = FakePage(csv_path)

    csv_text = collectors._download_transactions_csv(page)

    assert csv_text == "Transaction number;Start date-time;Quantity\n"
    assert any(call[0] == "click" for call in page.calls)


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=None):
        self.page.calls.append(("wait_for", self.selector, state, timeout))

    def click(self, timeout=None):
        self.page.calls.append(("click", self.selector, timeout))

    def fill(self, value):
        self.page.calls.append(("fill", self.selector, value))

    def select_option(self, label=None, value=None):
        self.page.calls.append(("select_option", self.selector, label, value))

    def count(self):
        return 1

    def is_visible(self):
        return True


class FakeDownload:
    def __init__(self, path):
        self._path = path

    def path(self):
        return self._path


class FakeDownloadContext:
    def __init__(self, download):
        self.value = download

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakePage:
    def __init__(self, csv_path=None):
        self.calls = []
        self.csv_path = csv_path

    def locator(self, selector):
        return FakeLocator(self, selector)

    def wait_for_load_state(self, state):
        self.calls.append(("wait_for_load_state", state))

    def expect_download(self):
        return FakeDownloadContext(FakeDownload(self.csv_path))
