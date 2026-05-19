# Klauwscore Refactor Plan

## Goal

Refactor the Klauwscore data job into a coherent, testable workflow that follows
`AGENTS.md` and the structure now used by the Uniform Agri job.

The refactor should make it clear how the job:

- loads Klauwscore credentials and runtime options,
- logs in and collects agenda/PDF data,
- parses PDFs into raw records,
- transforms parsed records into database-shaped rows or SQLModel objects,
- validates document counts and duplicate rows,
- persists rows through the repository boundary,
- supports dry-run and repeatable CLI execution.

This plan is for review before implementation. Do not start code changes until
the plan is approved.

## Current State

Relevant files:

- `data_jobs/klauwscore/main.py`
- `data_jobs/klauwscore/pdf_parser.py`
- `data_jobs/klauwscore/Dockerfile`
- `database/models/behandeling.py`
- `database/repositories/behandelingen_repository.py`
- `database/migrations/versions/20260510_01_add_timestamps_to_klauw_behandelingen.py`
- `database/migrations/versions/20260511_01_change_klauw_behandeldatum_to_date.py`
- `database/migrations/versions/20260512_01_fix_klauw_behandelingen_id_sequence.py`

Observed issues:

- `main.py` mixes configuration, Playwright browser automation, scraping,
  parsing orchestration, flattening, deduplication, JSON serialization, CLI
  output, and database writes.
- Environment variables are loaded at import time through `load_klauwscore_env()`.
- `os.getenv()` is called inside scraping functions instead of loading a single
  validated config object at the edge.
- The script mutates `sys.path` so it can import from the repo root.
- Progress reporting uses `print_progress()` and direct `print()` calls instead
  of consistent job logging.
- Database persistence is embedded in the script and creates its repository
  directly.
- The Playwright scraping code is synchronous. That is acceptable if retained
  initially, but it should be isolated so an async migration or browser-context
  test strategy is possible later.
- `pdf_parser.py` is mostly focused and reusable, but it uses `int | None`,
  which conflicts with `AGENTS.md`.
- `database/models/behandeling.py` uses `str | None`, has formatting drift, and
  could use a closer review against current SQLModel conventions in the repo.
- There is no visible test coverage for Klauwscore parsing, agenda extraction,
  deduplication, persistence, or CLI behavior.

## Target Structure

Keep the implementation Python-first and function-oriented. Use small modules
with one responsibility each.

Proposed package layout:

```text
data_jobs/klauwscore/
  __init__.py
  config.py
  exceptions.py
  models.py
  scraper.py
  agenda_parser.py
  pdf_parser.py
  transforms.py
  collectors.py
  serializers.py
  scripts/
    __init__.py
    collect_klauwscore.py

database/
  persistence/
    klauwscore.py
```

Responsibilities:

- `config.py`: load and validate environment variables and runtime defaults.
- `exceptions.py`: define configuration, scraping, parsing, and collection
  exceptions.
- `models.py`: define small dataclasses such as `AgendaPdfLink`,
  `ParsedKlauwscoreDocument`, `KlauwscoreCollectionResult`, and
  `DocumentCountMismatch`.
- `scraper.py`: own Playwright login, agenda page loading, and authenticated PDF
  download.
- `agenda_parser.py`: parse agenda HTML rows into `AgendaPdfLink` objects.
- `pdf_parser.py`: keep text extraction and PDF text parsing focused and pure.
- `transforms.py`: convert parsed PDF records into `KlauwBehandeling` objects or
  database-shaped dictionaries.
- `collectors.py`: orchestrate agenda collection, PDF downloads, PDF parsing,
  count validation, and duplicate handling without database writes.
- `serializers.py`: produce grouped and flattened JSON output.
- `database/persistence/klauwscore.py`: save rows through
  `KlauwBehandelingenRepository`, return write counts, and support dry-run.
- `scripts/collect_klauwscore.py`: thin CLI entrypoint.

## Implementation Phases

### 1. Preserve Behavior Before Refactoring

1. Check for `.venv` or `venv` and use that interpreter for all validation.
2. Confirm the current execution commands, likely:
   - `.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --summary`
   - `.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --flat`
   - `.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --upsert-db`
   - `.\.venv\Scripts\python.exe -m data_jobs.klauwscore.pdf_parser <pdf_path>`
3. Run syntax/import checks first if real Klauwscore credentials are not
   available.
4. Capture existing behavior in a short note:
   - which environment variables are required,
   - which `.env` files are loaded and in what order,
   - which page is opened after login,
   - how agenda rows are selected,
   - how `Alle notaties` links are parsed,
   - how many PDF download attempts are made,
   - what happens when a PDF has an empty body,
   - how agenda cow count mismatches are reported,
   - how duplicate notitie rows are removed,
   - which database table is written,
   - which failures abort the whole run.

Acceptance criteria:

- A short behavior baseline exists in `plans/` or the implementation summary.
- No intentional behavior changes are made before current behavior is
  documented.
- Import-only checks pass before files are moved or split.

### 2. Add Configuration Module

Create `data_jobs/klauwscore/config.py`.

Planned functions and data:

- `load_klauwscore_config() -> KlauwscoreConfig`
- `KlauwscoreConfig` as a small dataclass or Pydantic model.
- Required fields:
  - `username`
  - `password`
- Optional/defaulted fields:
  - `base_url`, default `http://klauwscore.nl`
  - `login_path`, default `/login`
  - `agenda_path`, default `/veehouder/agenda`
  - `headless`, default `True`
  - `download_attempts`, default `3`
  - `download_timeout_ms`, default `120000`
  - `default_limit`, default `None`

Rules:

- Load `.env` once at the CLI edge.
- Preserve current load order unless there is a documented reason to change it:
  repo root `.env`, then `data_jobs/klauwscore/.env`.
- Fail fast with one clear configuration exception when credentials are missing.
- Do not call `os.getenv()` throughout the codebase after this module exists.
- Use `pathlib.Path` for `.env` and repo path references.

Acceptance criteria:

- Missing credentials fail before Playwright starts.
- Configuration can be unit tested without invoking the browser.
- Runtime URLs are built from config, not module-level string constants.

### 3. Fix Imports And Package Boundaries

1. Remove `sys.path` mutation from `main.py`.
2. Ensure the job is invoked as a module from the repo root.
3. Follow `AGENTS.md` import style:
   - namespace imports for internal modules containing functions,
   - direct imports for classes and exceptions.
4. Keep `data_jobs.logger.get_job_logger(__file__)` as the logging entrypoint.
5. Replace `type | None` hints in Klauwscore code with `Optional[type]`.
6. Use builtin collection types such as `list[dict]`.

Acceptance criteria:

- `python -m data_jobs.klauwscore.main --help` still works during the transition.
- After the new CLI exists, `python -m data_jobs.klauwscore.scripts.collect_klauwscore --help` works.
- No Klauwscore module mutates `sys.path`.

### 4. Split Agenda Parsing From Browser Automation

Create `data_jobs/klauwscore/agenda_parser.py`.

Suggested functions:

- `parse_agenda_date(row) -> date`
- `parse_aantal_koeien(row) -> int`
- `parse_registratielijst(html_or_table, base_url: str) -> list[AgendaPdfLink]`

Rules:

- Keep parsing pure and independent from Playwright.
- Keep Dutch month parsing in this module.
- Raise a project-specific parse error with enough row context when a date or
  count cannot be parsed.
- Preserve current behavior of selecting links with visible text
  `Alle notaties`.

Acceptance criteria:

- Agenda parsing can be tested with static HTML fixtures.
- URL joining is covered by a test.
- Malformed dates and missing cow counts have explicit tests.

### 5. Isolate Playwright Scraping

Create `data_jobs/klauwscore/scraper.py`.

Suggested functions:

- `login(page, config: KlauwscoreConfig) -> None`
- `load_agenda_html(page, config: KlauwscoreConfig) -> str`
- `download_pdf(page, href: str, config: KlauwscoreConfig) -> bytes`
- `scrape_agenda_links(config: KlauwscoreConfig) -> list[AgendaPdfLink]`

Rules:

- Keep browser lifecycle in one place.
- Keep synchronous Playwright initially unless async migration is explicitly
  selected later.
- Continue retrying PDF downloads according to config.
- Raise typed scraping exceptions with URL, attempt count, and short failure
  context.
- Use logging for retry warnings.

Acceptance criteria:

- Browser automation is mockable in tests.
- Download retry behavior is covered by tests.
- Empty PDF bodies remain a failure unless explicitly reclassified later.

### 6. Keep PDF Parsing Pure

Refactor `data_jobs/klauwscore/pdf_parser.py` only where needed.

Rules:

- Keep PDF byte/text extraction separate from text parsing.
- Keep `parse_klauwscore_pdf_text(text)` pure.
- Keep `flatten_records(records)` pure or move flattening to `transforms.py`,
  but do not duplicate it.
- Replace `int | None` with `Optional[int]`.
- Add tests for:
  - date extraction,
  - cow number boundaries,
  - multiple notities per cow,
  - footer/header skipping,
  - missing inspection date.

Acceptance criteria:

- PDF parsing can be tested with static text strings.
- No database or browser dependency is needed for parser tests.
- Existing parser CLI still works or is intentionally replaced with a compatible
  module command.

### 7. Add Transform And Validation Modules

Create `data_jobs/klauwscore/transforms.py`.

Suggested functions:

- `klauw_behandeling_from_row(row: dict[str, object]) -> KlauwBehandeling`
- `flatten_documents(documents: list[ParsedKlauwscoreDocument]) -> list[dict[str, object]]`
- `dedupe_klauwbehandeling_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]`
- `validate_document_counts(documents: list[ParsedKlauwscoreDocument]) -> list[DocumentCountMismatch]`

Rules:

- Do not mutate raw parsed document dictionaries in place.
- Keep duplicate identity explicit:
  `(behandeldatum, halsbandnummer, notatie)`.
- Consider whether blank/whitespace notities should be skipped; preserve current
  behavior unless a behavior change is approved.
- Return structured mismatch objects, not only printed messages.

Acceptance criteria:

- Deduplication is covered by tests.
- Count mismatch validation is covered by tests.
- Transform functions can be tested without browser, PDFs, or database access.

### 8. Build Collector Flow

Create `data_jobs/klauwscore/collectors.py`.

Suggested functions:

- `collect_klauwscore_documents(config, limit: Optional[int] = None) -> KlauwscoreCollectionResult`
- `collect_klauwscore_rows(config, limit: Optional[int] = None) -> KlauwscoreCollectionResult`

Suggested result models:

- `AgendaPdfLink`
- `ParsedKlauwscoreDocument`
- `DocumentCollectionFailure`
- `DocumentCountMismatch`
- `KlauwscoreCollectionResult`

Collector responsibilities:

- load agenda links,
- apply `limit`,
- download each PDF,
- parse PDF records,
- continue or abort on per-document failures depending on CLI/config option,
- collect structured failures,
- validate agenda count mismatches,
- flatten and dedupe rows.

Acceptance criteria:

- Collection flow is testable without a database.
- Per-document failures are reported in a structured way.
- Summary counts are available without scraping logs:
  `documents`, `cow_records`, `notitie_rows`, `deduped_notitie_rows`,
  `duplicate_rows`, `count_mismatches`, and `failures`.

### 9. Move Persistence Into Database Package

Create `database/persistence/klauwscore.py`.

Recommended functions:

- `save_klauw_behandelingen(rows, repository, *, dry_run=False, logger=None) -> int`
- `save_klauw_behandeling_models(models, repository, *, dry_run=False, logger=None) -> int`

Rules:

- Repositories remain the database boundary.
- Do not call `init_db()` as a substitute for Alembic migrations.
- Keep schema changes in `database/migrations`.
- Return write counts and log them.
- Support dry-run with zero database writes.

Acceptance criteria:

- Persistence can be unit tested with a fake repository.
- Dry-run returns the number of rows that would be written.
- Database write counts are logged and surfaced in the CLI summary.

### 10. Replace Main Script With Thin CLI Entrypoint

Create `data_jobs/klauwscore/scripts/collect_klauwscore.py`.

Recommended CLI options:

- `--limit`
- `--flat`
- `--summary`
- `--dry-run`
- `--continue-on-document-error`
- `--headless` / `--no-headless`
- `--download-attempts`
- `--download-timeout-ms`

Behavior:

- Load config.
- Create logger with `data_jobs.logger.get_job_logger(__file__)`.
- Run collector.
- Persist deduplicated rows by default.
- Skip database writes only when `--dry-run` is set.
- Print intentional JSON or summary output to stdout.
- Send progress and diagnostic information through logging.
- Accept the old `--upsert-db` flag temporarily as a hidden no-op so existing
  scheduled commands do not fail during the transition.

Migration strategy:

1. Keep `data_jobs/klauwscore/main.py` temporarily as a compatibility wrapper.
2. Make it call the new CLI `main()` function.
3. Remove the wrapper later only after external schedules or Docker commands are
   updated.

Acceptance criteria:

- The CLI file contains minimal business logic.
- `python -m data_jobs.klauwscore.scripts.collect_klauwscore --help` works.
- Existing `python -m data_jobs.klauwscore.main --help` remains compatible during
  the transition.
- Progress uses logging, except for intentional JSON/summary stdout output.

### 11. Review Database Model And Repository Style

Review `database/models/behandeling.py` and
`database/repositories/behandelingen_repository.py`.

Potential cleanup:

- Format with Ruff.
- Replace `str | None` with `Optional[str]`.
- Ensure `id` typing and defaults match SQLModel conventions used elsewhere in
  the repo.
- Keep `behandeldatum` as `date`; it already has a migration.
- Keep the repository's unique fields as:
  `["halsbandnummer", "behandeldatum", "notatie"]`.
- Consider accepting `KlauwBehandeling` directly and using `model_dump()` only at
  the repository boundary.

Acceptance criteria:

- Model and repository pass Ruff.
- No schema change is introduced unless explicitly needed.
- Existing unique upsert behavior is preserved.

### 12. Add Focused Tests

Add test files:

- `tests/data_jobs/klauwscore/test_config.py`
- `tests/data_jobs/klauwscore/test_agenda_parser.py`
- `tests/data_jobs/klauwscore/test_pdf_parser.py`
- `tests/data_jobs/klauwscore/test_transforms.py`
- `tests/data_jobs/klauwscore/test_collectors.py`
- `tests/data_jobs/klauwscore/test_collect_klauwscore_cli.py`
- `tests/database/test_klauwscore_persistence.py`

Test strategy:

- Use static HTML snippets for agenda parsing.
- Use static PDF text strings for parser behavior.
- Mock browser/page/request behavior for scraper retry tests.
- Use fake repositories for persistence tests.
- Avoid real Klauwscore credentials, browser sessions, PDFs, and database writes
  in unit tests.

Acceptance criteria:

- Tests cover parser, transform, collector, persistence, and CLI behavior.
- Tests do not require network access.
- Tests can run with:
  `.\.venv\Scripts\python.exe -m pytest tests\data_jobs\klauwscore tests\database\test_klauwscore_persistence.py -p no:cacheprovider`

### 13. Docker And Scheduling Review

Review `data_jobs/klauwscore/Dockerfile` after the CLI split.

Rules:

- Keep the Docker command aligned with the supported module entrypoint.
- Ensure browser dependencies required by Playwright are still available.
- Do not bake credentials into the image.
- Confirm whether scheduled execution expects JSON output, summary output, or
  database upsert mode.

Acceptance criteria:

- Docker still runs the intended Klauwscore command.
- Required environment variables are documented.
- Any changed entrypoint is called out in the implementation summary.

### 14. Formatting, Linting, And Verification

For every implementation phase:

1. Run `ruff format` on edited Python files.
2. Run `ruff check --fix` on edited Python files.
3. Run focused pytest tests.
4. Run import/CLI help checks:
   - `python -m data_jobs.klauwscore.pdf_parser --help`
   - `python -m data_jobs.klauwscore.scripts.collect_klauwscore --help`
   - compatibility wrapper: `python -m data_jobs.klauwscore.main --help`

Acceptance criteria:

- Formatting and linting pass for edited files.
- Focused tests pass.
- Any test skipped because of missing browser dependencies or credentials is
  documented clearly.

## Suggested First Implementation Slice

Start with the lowest-risk behavior-preserving work:

1. Document current behavior.
2. Add config and exceptions modules.
3. Move agenda parsing into a pure module with tests.
4. Add parser tests and fix type hints in `pdf_parser.py`.
5. Add transform/dedupe/count-validation tests.

This gives a reliable safety net before moving Playwright scraping and the CLI.
