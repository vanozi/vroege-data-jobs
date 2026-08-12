# Tank Terminal CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Tank Terminal datajob to download the ProFleet `Export before purge` transactions CSV, parse it, and store parsed transactions in the database.

**Architecture:** Keep login and Playwright orchestration in `data_jobs.tank_terminal.collectors`, move export-specific selectors into page objects, reuse `csv_parsers` for CSV mapping, and persist `TankTransaction` models through the existing persistence helper. Add a repository query for latest stored transaction timestamp so date filters can be computed before navigation.

**Tech Stack:** Python, Playwright sync API, SQLModel, pytest, Ruff.

## Global Constraints

- Use Python and latest project style.
- Use `Optional[type]` rather than `type | None`.
- Use namespace imports for internal project functions and direct imports for classes/exceptions.
- Use `pathlib.Path` for path operations.
- Run `ruff format` and `ruff check --fix` on edited Python files.
- Run focused pytest tests for edited behavior.
- Do not repeatedly log in to the live ProFleet portal during development; prefer mocked Playwright tests and reuse one logged-in browser session if manual testing is needed.
- Do not commit changes from this plan; provide a commit message at the end.

---

## File Structure

- Modify `database/repositories/tank_transactions_repository.py`: add `get_latest_start_date_time() -> Optional[datetime]`.
- Modify or create `tests/database/test_tank_transactions_repository.py`: cover latest timestamp query.
- Modify `data_jobs/tank_terminal/collectors.py`: replace table scraping collection with CSV export collection and date-range calculation.
- Modify `data_jobs/tank_terminal/page_objects/overview_page.py`: add robust selectors for `Administratien`, `Export`, and `Transactions` navigation targets.
- Create `data_jobs/tank_terminal/page_objects/export_transactions_page.py`: selectors for template dropdown, filter fields, export button, and fallback matching.
- Modify `data_jobs/tank_terminal/scripts/collect_tank_terminal.py`: wire repository latest timestamp into collection and persist parsed models by `start_date_time`.
- Modify `tests/data_jobs/tank_terminal/test_collect_tank_terminal_cli.py`: update CLI test expectations for model collection and persistence path.
- Create or modify `tests/data_jobs/tank_terminal/test_collectors.py`: cover date-range formatting and export download behavior with fakes.
- Existing `data_jobs/tank_terminal/csv_parsers.py` remains the CSV source of truth.

## Task 1: Repository Latest Timestamp Query

**Files:**
- Modify: `database/repositories/tank_transactions_repository.py`
- Create: `tests/database/test_tank_transactions_repository.py`

**Interfaces:**
- Produces: `TankTransactionsRepository.get_latest_start_date_time() -> Optional[datetime]`
- Consumes: `TankTransaction.start_date_time`

- [ ] **Step 1: Write the failing repository tests**

Add `tests/database/test_tank_transactions_repository.py`:

```python
from datetime import datetime

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database.models.tank_transaction import TankTransaction
from database.repositories.tank_transactions_repository import (
    TankTransactionsRepository,
)


def test_get_latest_start_date_time_returns_none_when_empty():
    engine = _create_engine()
    repository = TankTransactionsRepository(_session_factory(engine))

    latest = repository.get_latest_start_date_time()

    assert latest is None


def test_get_latest_start_date_time_returns_maximum_timestamp():
    engine = _create_engine()
    repository = TankTransactionsRepository(_session_factory(engine))

    repository.upsert_tank_transaction(
        _transaction("001", datetime(2026, 8, 4, 9, 30, 0))
    )
    repository.upsert_tank_transaction(
        _transaction("002", datetime(2026, 8, 6, 7, 15, 0))
    )
    repository.upsert_tank_transaction(
        _transaction("003", datetime(2026, 8, 5, 18, 45, 0))
    )

    latest = repository.get_latest_start_date_time()

    assert latest == datetime(2026, 8, 6, 7, 15, 0)


def _transaction(transaction_number: str, start_date_time: datetime) -> dict[str, object]:
    return {
        "transaction_number": transaction_number,
        "start_date_time": start_date_time,
        "quantity_liters": 10.0,
    }


def _create_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _session_factory(engine):
    def factory():
        return Session(engine)

    return factory
```

- [ ] **Step 2: Run the failing repository test**

Run: `pytest tests/database/test_tank_transactions_repository.py -v`

Expected: FAIL with `AttributeError` for `get_latest_start_date_time`.

- [ ] **Step 3: Implement the repository method**

In `database/repositories/tank_transactions_repository.py`, import `datetime`, `Optional`, `func`, and `select`, then add:

```python
    def get_latest_start_date_time(self) -> Optional[datetime]:
        """Return the latest stored Tank Terminal transaction timestamp."""
        with self.get_session() as session:
            statement = select(func.max(TankTransaction.start_date_time))
            return session.exec(statement).one()
```

Keep the existing `Union` import.

- [ ] **Step 4: Verify repository tests pass**

Run: `pytest tests/database/test_tank_transactions_repository.py -v`

Expected: PASS.

## Task 2: Export Date Range Calculation

**Files:**
- Modify: `data_jobs/tank_terminal/collectors.py`
- Create or modify: `tests/data_jobs/tank_terminal/test_collectors.py`

**Interfaces:**
- Consumes: latest timestamp as `Optional[datetime]`
- Produces: `TankTerminalExportDateRange(start_date_time: Optional[str], end_date_time: Optional[str])`
- Produces: `_build_export_date_range(latest_start_date_time: Optional[datetime], now: Optional[datetime] = None) -> TankTerminalExportDateRange`

- [ ] **Step 1: Write failing date-range tests**

Add to `tests/data_jobs/tank_terminal/test_collectors.py`:

```python
from datetime import datetime

from data_jobs.tank_terminal import collectors


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
```

- [ ] **Step 2: Run the failing date-range tests**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py -v`

Expected: FAIL with `AttributeError` for `_build_export_date_range`.

- [ ] **Step 3: Implement date-range helper**

In `data_jobs/tank_terminal/collectors.py`, add imports:

```python
from datetime import datetime, time, timedelta
```

Add near `TankTerminalCollectionResult`:

```python
@dataclass(frozen=True)
class TankTerminalExportDateRange:
    """Date-time filter values for the ProFleet transaction export."""

    start_date_time: Optional[str]
    end_date_time: Optional[str]
```

Add helper:

```python
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
```

- [ ] **Step 4: Verify date-range tests pass**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py -v`

Expected: PASS.

## Task 3: Export Page Selectors

**Files:**
- Modify: `data_jobs/tank_terminal/page_objects/overview_page.py`
- Create: `data_jobs/tank_terminal/page_objects/export_transactions_page.py`

**Interfaces:**
- Produces: `OverviewPage.administration_links`, `OverviewPage.export_links`, `OverviewPage.export_transaction_links`
- Produces: `ExportTransactionsPage.template_select`, `ExportTransactionsPage.template_option_name`, `ExportTransactionsPage.filters_tab`, `ExportTransactionsPage.start_date_inputs`, `ExportTransactionsPage.end_date_inputs`, `ExportTransactionsPage.export_buttons`

- [ ] **Step 1: Write a failing selector contract test**

Add to `tests/data_jobs/tank_terminal/test_collectors.py`:

```python
from data_jobs.tank_terminal.page_objects.export_transactions_page import (
    ExportTransactionsPage,
)
from data_jobs.tank_terminal.page_objects.overview_page import OverviewPage


def test_export_page_objects_define_navigation_and_form_selectors():
    assert "Administration" in OverviewPage.administration_links[0]
    assert "Export" in OverviewPage.export_links[0]
    assert "Transactions" in OverviewPage.export_transaction_links[0]
    assert ExportTransactionsPage.template_option_name == "Export before purge"
    assert ExportTransactionsPage.start_date_inputs
    assert ExportTransactionsPage.end_date_inputs
    assert ExportTransactionsPage.export_buttons
```

- [ ] **Step 2: Run the failing selector test**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py::test_export_page_objects_define_navigation_and_form_selectors -v`

Expected: FAIL because `export_transactions_page.py` does not exist or selectors are missing.

- [ ] **Step 3: Add selector definitions**

In `data_jobs/tank_terminal/page_objects/overview_page.py`, add:

```python
    administration_links = [
        "//a[descendant::span[contains(normalize-space(), 'Administration')]]",
        "//a[contains(normalize-space(), 'Administration')]",
        "//span[contains(normalize-space(), 'Administration')]",
    ]
    export_links = [
        "//a[descendant::span[contains(normalize-space(), 'Export')]]",
        "//a[contains(normalize-space(), 'Export')]",
        "//span[contains(normalize-space(), 'Export')]",
    ]
    export_transaction_links = [
        "//a[descendant::span[contains(normalize-space(), 'Transactions')]]",
        "//a[contains(normalize-space(), 'Transactions')]",
        "//span[contains(normalize-space(), 'Transactions')]",
    ]
```

Create `data_jobs/tank_terminal/page_objects/export_transactions_page.py`:

```python
"""Transactions export page selectors for the Tank Terminal web UI."""

from data_jobs.tank_terminal.page_objects.base_page import BasePage


class ExportTransactionsPage(BasePage):
    """Selectors for the ProFleet transactions export screen."""

    template_option_name = "Export before purge"
    template_select = (
        "//select[option[contains(normalize-space(), 'Export before purge')]]"
    )
    filters_tab = (
        "//a[contains(normalize-space(), 'Filters')]"
        " | //span[contains(normalize-space(), 'Filters')]"
        " | //td[contains(normalize-space(), 'Filters')]"
    )
    start_date_inputs = [
        "//tr[descendant::*[contains(normalize-space(), 'Start date-time')]]//input",
        "//input[contains(@name, 'start') or contains(@id, 'start')]",
    ]
    end_date_inputs = [
        "//tr[descendant::*[contains(normalize-space(), 'End date-time')]]//input",
        "//input[contains(@name, 'end') or contains(@id, 'end')]",
    ]
    export_buttons = [
        "//input[@type='submit' and contains(@value, 'Export')]",
        "//button[contains(normalize-space(), 'Export')]",
        "//a[contains(normalize-space(), 'Export')]",
    ]
```

- [ ] **Step 4: Verify selector test passes**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py::test_export_page_objects_define_navigation_and_form_selectors -v`

Expected: PASS.

## Task 4: CSV Export Collector With Mocked Playwright

**Files:**
- Modify: `data_jobs/tank_terminal/collectors.py`
- Modify: `tests/data_jobs/tank_terminal/test_collectors.py`

**Interfaces:**
- Modifies: `TankTerminalCollectionResult.rows` becomes `list[TankTransaction]`
- Modifies: `collect_tank_terminal_rows(config: TankTerminalConfig, limit: Optional[int] = None, progress_callback: Optional[Callable[[str], None]] = None, latest_start_date_time: Optional[datetime] = None) -> TankTerminalCollectionResult`
- Produces: `_open_export_transactions(page: Page) -> None`
- Produces: `_select_export_template(page: Page) -> None`
- Produces: `_fill_export_filters(page: Page, date_range: TankTerminalExportDateRange) -> None`
- Produces: `_download_transactions_csv(page: Page) -> str`

- [ ] **Step 1: Update the result-summary test first**

In `tests/data_jobs/tank_terminal/test_collectors.py`, add:

```python
from datetime import datetime

from database.models.tank_transaction import TankTransaction
from data_jobs.tank_terminal.collectors import TankTerminalCollectionResult


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
```

- [ ] **Step 2: Run result-summary test**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py::test_collection_result_summary_counts_exported_models_without_deduping -v`

Expected: PASS if the existing dataclass remains compatible, otherwise fix type annotations only.

- [ ] **Step 3: Write focused tests for export helpers using fakes**

Add fake locator/page classes in `tests/data_jobs/tank_terminal/test_collectors.py`:

```python
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
```

Then add tests:

```python
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


def test_download_transactions_csv_reads_downloaded_file(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    csv_path.write_text("Transaction number;Start date-time;Quantity\n", encoding="utf-8")
    page = FakePage(csv_path)

    csv_text = collectors._download_transactions_csv(page)

    assert csv_text == "Transaction number;Start date-time;Quantity\n"
    assert any(call[0] == "click" for call in page.calls)
```

- [ ] **Step 4: Run failing export helper tests**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py -v`

Expected: FAIL for missing helper functions.

- [ ] **Step 5: Implement export helpers**

In `data_jobs/tank_terminal/collectors.py`, import:

```python
from pathlib import Path

from database.models.tank_transaction import TankTransaction
from data_jobs.tank_terminal import csv_parsers
from data_jobs.tank_terminal.page_objects.export_transactions_page import (
    ExportTransactionsPage,
)
```

Change the result row type to:

```python
    rows: list[TankTransaction]
```

Add:

```python
def _open_export_transactions(page: Page) -> None:
    _click_first_visible(page, OverviewPage.administration_links)
    _click_first_visible(page, OverviewPage.export_links)
    _click_first_visible(page, OverviewPage.export_transaction_links)
    page.locator(ExportTransactionsPage.template_select).first.wait_for(state="visible")


def _select_export_template(page: Page) -> None:
    page.locator(ExportTransactionsPage.template_select).first.select_option(
        label=ExportTransactionsPage.template_option_name
    )
    page.wait_for_load_state("networkidle")


def _fill_export_filters(page: Page, date_range: TankTerminalExportDateRange) -> None:
    filter_tab = page.locator(ExportTransactionsPage.filters_tab).first
    filter_tab.click(timeout=5_000)
    page.wait_for_load_state("networkidle")
    _fill_first_available(page, ExportTransactionsPage.start_date_inputs, date_range.start_date_time)
    _fill_first_available(page, ExportTransactionsPage.end_date_inputs, date_range.end_date_time)


def _download_transactions_csv(page: Page) -> str:
    with page.expect_download() as download_info:
        _click_first_visible(page, ExportTransactionsPage.export_buttons)

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

    raise ValueError(f"Could not find Tank Terminal export navigation target: {selectors}")
```

Format long lines with Ruff.

- [ ] **Step 6: Replace table scrape flow with CSV export flow**

Update `collect_tank_terminal_rows`:

```python
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
```

Keep `_login`, `_preview_text`, `_dedupe_transactions`, `_open_transactions`, and `_parse_visible_transactions` only if tests still require them. If no production or test code uses the table-scrape helpers, remove them in the refactor step after green tests.

- [ ] **Step 7: Verify collector tests pass**

Run: `pytest tests/data_jobs/tank_terminal/test_collectors.py tests/data_jobs/tank_terminal/test_csv_parsers.py -v`

Expected: PASS.

## Task 5: CLI Uses Latest Timestamp And Model Persistence

**Files:**
- Modify: `data_jobs/tank_terminal/scripts/collect_tank_terminal.py`
- Modify: `tests/data_jobs/tank_terminal/test_collect_tank_terminal_cli.py`
- Modify: `data_jobs/tank_terminal/serializers.py` only if current summary code requires changed type hints.

**Interfaces:**
- Consumes: `TankTransactionsRepository.get_latest_start_date_time() -> Optional[datetime]`
- Consumes: `collect_tank_terminal_rows(..., latest_start_date_time: Optional[datetime])`
- Consumes: `save_tank_transaction_models_by_start_date_time(models, repository, dry_run=False) -> int`

- [ ] **Step 1: Update CLI test to use `TankTransaction` models**

Replace the parsed-row setup in `tests/data_jobs/tank_terminal/test_collect_tank_terminal_cli.py` with:

```python
from database.models.tank_transaction import TankTransaction
```

Then create:

```python
    row = TankTransaction(
        transaction_number="001012235085",
        start_date_time=datetime(2022, 8, 23, 10, 30, 38),
        transaction_date=datetime(2022, 8, 23, 10, 30, 38).date(),
        transaction_hour="10:30:38",
        vehicle="Siloking",
        driver="Jeffrey",
        transaction_type="Dispensing",
        acquisition_mode="Normal",
        transaction_status="Normal",
        product="Diesel",
        quantity_liters=87.47,
        quantity_units="L",
        meter_value=271,
        meter_type="h",
    )
```

- [ ] **Step 2: Update CLI monkeypatches to assert latest timestamp is passed**

Use:

```python
    expected_latest = datetime(2022, 8, 22, 10, 0, 0)

    class FakeRepository:
        def __init__(self):
            self.models_by_start_date_time = []

        def get_latest_start_date_time(self):
            return expected_latest

        def upsert_tank_transaction_by_start_date_time(self, model):
            self.models_by_start_date_time.append(model)

    fake_repository = FakeRepository()

    def fake_collect(config, limit, progress_callback, latest_start_date_time):
        assert latest_start_date_time == expected_latest
        return TankTerminalCollectionResult([row])

    monkeypatch.setattr(
        collect_tank_terminal.collectors,
        "collect_tank_terminal_rows",
        fake_collect,
    )
    monkeypatch.setattr(
        collect_tank_terminal,
        "_build_repository",
        lambda: fake_repository,
    )
```

The dry-run case should still avoid database writes, but `_build_repository()` is needed to read the latest timestamp. Add a second test for `dry_run=True` if this behavior should be explicit.

- [ ] **Step 3: Run the failing CLI test**

Run: `pytest tests/data_jobs/tank_terminal/test_collect_tank_terminal_cli.py -v`

Expected: FAIL because `collect_tank_terminal_rows` is called without `latest_start_date_time` and persistence uses the old helper.

- [ ] **Step 4: Update CLI run flow**

In `data_jobs/tank_terminal/scripts/collect_tank_terminal.py`, update `run`:

```python
    repository = _build_repository()
    latest_start_date_time = repository.get_latest_start_date_time()
    result = collectors.collect_tank_terminal_rows(
        config,
        limit=limit,
        progress_callback=logger.info,
        latest_start_date_time=latest_start_date_time,
    )
    saved_count = _persist_rows(result, repository=repository, dry_run=args.dry_run)
```

Update `_persist_rows` signature:

```python
def _persist_rows(
    result: collectors.TankTerminalCollectionResult,
    repository,
    dry_run: bool,
) -> int:
    return tank_terminal_persistence.save_tank_transaction_models_by_start_date_time(
        result.rows,
        repository,
        dry_run=dry_run,
    )
```

- [ ] **Step 5: Verify CLI tests pass**

Run: `pytest tests/data_jobs/tank_terminal/test_collect_tank_terminal_cli.py -v`

Expected: PASS.

## Task 6: Cleanup, Formatting, And Focused Verification

**Files:**
- Modify: `data_jobs/tank_terminal/collectors.py`
- Modify: any touched test files if imports are now unused.

**Interfaces:**
- Keeps public CLI command unchanged: `python -m data_jobs.tank_terminal.scripts.collect_tank_terminal`

- [ ] **Step 1: Remove unused table-scrape imports and helpers**

In `data_jobs/tank_terminal/collectors.py`, remove imports and helpers that are no longer used:

```python
from dataclasses import asdict
from data_jobs.tank_terminal.page_objects.transactions_page import TransactionsPage
from data_jobs.tank_terminal.parsers import ParsedTankTransaction
from data_jobs.tank_terminal.parsers import parse_transactions_table
```

Remove `_open_transactions`, `_parse_visible_transactions`, `_preview_text`, and `_dedupe_transactions` if no test imports them. If existing parser tests still cover table parsing directly, leave `data_jobs/tank_terminal/parsers.py` and its tests untouched.

- [ ] **Step 2: Run Ruff format**

Run: `ruff format data_jobs/tank_terminal database/repositories tests/data_jobs/tank_terminal tests/database/test_tank_transactions_repository.py`

Expected: files formatted without errors.

- [ ] **Step 3: Run Ruff check with fixes**

Run: `ruff check --fix data_jobs/tank_terminal database/repositories tests/data_jobs/tank_terminal tests/database/test_tank_transactions_repository.py`

Expected: no remaining lint errors.

- [ ] **Step 4: Run focused pytest suite**

Run: `pytest tests/data_jobs/tank_terminal tests/database/test_tank_transactions_repository.py -v`

Expected: PASS.

- [ ] **Step 5: Optional single live Playwright verification**

Only run this if credentials are configured and login-rate limits allow it:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.tank_terminal.scripts.collect_tank_terminal --summary --dry-run --no-headless
```

Expected: one browser session logs in, opens the export page, downloads CSV, prints summary, and exits `0`. Do not repeat this command while tuning selectors; inspect and adjust from one logged-in session where possible.

## Self-Review

- Spec coverage: the plan covers export navigation, template selection, date filter rules, empty-database blank fields, CSV parsing, model persistence by `start_date_time`, clear error handling through helper failures, and login-rate testing constraints.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `TankTerminalCollectionResult.rows` is consistently `list[TankTransaction]`; `latest_start_date_time` is consistently `Optional[datetime]`; the repository method returns `Optional[datetime]`.
