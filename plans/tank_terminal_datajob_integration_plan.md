# Tank Terminal Datajob Integration Plan

## Goal

Integrate the old Tank Terminal scraper as a first-class datajob in this
repository. The target result is a containerized job that logs into the diesel
tank terminal, collects transaction rows, normalizes them, and persists them to
the shared PostgreSQL database through the existing model/repository/persistence
patterns.

This plan is for review before implementation. Do not start code changes until
the plan is approved.

## Current State

The old project has been added under `data_jobs/tank-terminal/`.

Important files:

- `data_jobs/tank-terminal/transactions.py`
- `data_jobs/tank-terminal/page_objects/`
- `data_jobs/tank-terminal/table.html`
- `data_jobs/tank-terminal/requirements.txt`
- `data_jobs/tank-terminal/Dockerfile`

Current behavior:

- Starts Playwright at module execution time.
- Opens `http://82.197.193.195:8080/cgi-bin/index.php`.
- Selects English.
- Logs in with generic env vars `USERNAME` and `PASSWORD`.
- Opens the transactions list.
- Extracts the transaction table HTML.
- Parses rows using hardcoded row indexes `range(3, 28)`.
- Normalizes quantity and meter fields.
- Posts each transaction to an external API at `BASE_URL_API + "/tank_transactions/"`.

Main issues before integration:

- Directory name uses a hyphen, so it is not a normal Python package import path.
- The script has top-level side effects and cannot be imported safely in tests.
- Config names are too generic for this repo.
- It posts to another API instead of writing through this repo's database layer.
- It has its own Dockerfile and runs the scraper at image build time with
  `RUN python /app/transactions.py`; collection must happen at container runtime.
- Parsing depends on fixed table row indexes instead of table structure.

## Target Structure

Use the existing datajob style from `data_jobs/klauwscore/` and
`data_jobs/uniform_agri/`.

Suggested package layout:

```text
data_jobs/tank_terminal/
  __init__.py
  config.py
  collectors.py
  parsers.py
  serializers.py
  page_objects/
    __init__.py
    base_page.py
    login_page.py
    overview_page.py
    transactions_page.py
  scripts/
    __init__.py
    collect_tank_terminal.py
```

The old `data_jobs/tank-terminal/` folder should be removed after the new
package is working.

## Configuration

Add explicit Tank Terminal settings to `deploy/dashboard.env.example`:

```env
TANK_TERMINAL_BASE_URL=http://82.197.193.195:8080
TANK_TERMINAL_USERNAME=
TANK_TERMINAL_PASSWORD=
TANK_TERMINAL_HEADLESS=true
TANK_TERMINAL_DEFAULT_LIMIT=
```

Create `data_jobs/tank_terminal/config.py` with:

- `TankTerminalConfig` dataclass.
- `load_tank_terminal_config()`.
- Required validation for base URL, username, and password.
- Boolean parsing for `TANK_TERMINAL_HEADLESS`.
- Optional integer parsing for `TANK_TERMINAL_DEFAULT_LIMIT`.

Avoid generic names like `USERNAME`, `PASSWORD`, and `BASE_URL_API`.

## Collection

Move the Playwright flow into import-safe functions.

Suggested API:

```python
def collect_tank_terminal_rows(
    config: TankTerminalConfig,
    limit: Optional[int] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> TankTerminalCollectionResult:
    ...
```

Collection steps:

1. Open the login page from `config.base_url`.
2. Select English if the language dropdown exists.
3. Fill username and password.
4. Click confirm.
5. Click continue if the session warning/intermediate screen appears.
6. Navigate to transactions.
7. Extract the transaction table HTML.
8. Parse and normalize rows.
9. Deduplicate rows in memory by transaction number before persistence.

Use Playwright's sync API to match the current Klauwscore approach unless there
is a specific reason to use async.

## Parsing

Move HTML parsing into `data_jobs/tank_terminal/parsers.py`.

The parser should:

- Accept a table HTML string.
- Use `lxml.html`.
- Read row cells by table structure, not by hardcoded row numbers.
- Ignore header/separator/filter rows.
- Produce normalized dictionaries or typed records.

Fields to parse:

- `vehicle`
- `driver`
- `transaction_type`
- `acquisition_mode`
- `transaction_status`
- `start_date_time`
- `transaction_number`
- `product`
- `quantity_liters`
- `transaction_duration`
- `meter_value`
- `meter_type`

Normalization rules:

- Convert `87.47 L` to `quantity_liters=87.47`.
- Convert `271 h` to `meter_value=271`, `meter_type="h"`.
- Convert `370187 km` to `meter_value=370187`, `meter_type="km"`.
- Empty meter should become `None` values.
- Parse `23/08/2022 10:30:38` to a Python `datetime`.
- Normalize non-breaking spaces and unexpected encoding artifacts.

The included `data_jobs/tank-terminal/table.html` should become a parser test
fixture.

## Database

Add a SQLModel table for tank transactions.

Suggested model:

```text
database/models/tank_transaction.py
```

Suggested fields:

- `id`: integer primary key.
- `transaction_number`: string, required, unique.
- `vehicle`: string, nullable.
- `driver`: string, nullable.
- `transaction_type`: string, nullable.
- `acquisition_mode`: string, nullable.
- `transaction_status`: string, nullable.
- `start_date_time`: datetime, required, indexed.
- `product`: string, nullable.
- `quantity_liters`: float, required.
- `transaction_duration`: string or integer seconds.
- `meter_value`: float or integer, nullable.
- `meter_type`: string, nullable, expected values `h` or `km`.
- `created_at` / `updated_at` via existing mixins.

Decision needed:

- Store `transaction_duration` as raw text such as `00:01:07`, or normalize to
  seconds. Prefer seconds if dashboards or reporting will aggregate duration.

Add the model to `database/models/__init__.py` so Alembic sees it.

## Repository And Persistence

Add:

```text
database/repositories/tank_transactions_repository.py
database/persistence/tank_terminal.py
```

Repository behavior:

- Inherit from `BaseRepository`.
- Add `upsert_tank_transaction()`.
- Upsert by `transaction_number`.

Persistence behavior:

- `save_tank_transactions(rows, repository, dry_run=False, logger=None) -> int`.
- Return number of rows processed.
- Log dry-run and saved counts.
- Raise if `repository is None` and `dry_run=False`.

## Migration

Add a new Alembic migration in `database/migrations/versions/`.

Migration should:

- Create `tank_transactions`.
- Add a unique index or constraint on `transaction_number`.
- Add an index on `start_date_time`.
- Use the same migration style as existing files.

Run:

```bash
docker compose --profile tools run --rm db-migrate
```

For local testing:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile tools run --rm db-migrate
```

## CLI

Add:

```text
data_jobs/tank_terminal/scripts/collect_tank_terminal.py
```

Target command:

```bash
python -m data_jobs.tank_terminal.scripts.collect_tank_terminal --summary --dry-run
```

Suggested flags:

- `--limit N`
- `--summary`
- `--dry-run`
- `--headless` / `--no-headless`

CLI responsibilities:

- Load config.
- Apply CLI overrides.
- Run collector.
- Persist rows unless `--dry-run`.
- Print concise summary counts.
- Return non-zero exit code on config or collection failures.

Example summary output:

```text
dry_run=True
collected_transactions=25
deduped_transactions=25
saved_tank_transactions=25
failures=0
```

## Docker Compose

Use the shared `docker/datajobs/Dockerfile`; do not keep the old Tank Terminal
Dockerfile.

Add a Compose service:

```yaml
datajob-tank-terminal:
  <<: *datajob-base
  command:
    - python
    - -m
    - data_jobs.tank_terminal.scripts.collect_tank_terminal
    - --summary
```

Local dry run:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-tank-terminal python -m data_jobs.tank_terminal.scripts.collect_tank_terminal --summary --dry-run
```

Local write:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-tank-terminal
```

Production manual run:

```bash
docker compose --profile jobs run --rm datajob-tank-terminal
```

## Nightly Scheduling

If Tank Terminal should run nightly, update `deploy/run-nightly-datajobs.sh`.

Suggested order:

1. Run migrations.
2. Run Uniform Agri.
3. Run Klauwscore.
4. Run Tank Terminal.

Tank Terminal is independent from the cow data, so it can also run before or in
parallel later. Keep it sequential at first for simpler logging and failure
diagnosis.

## Tests

Add focused tests before or alongside implementation:

- Config tests:
  - missing required vars fail clearly;
  - booleans and optional limits parse correctly;
  - base URL requires `http://` or `https://`.
- Parser tests:
  - parse `table.html`;
  - quantity normalization;
  - meter `h`, `km`, and empty values;
  - date/time parsing;
  - no hardcoded row count dependency.
- Persistence tests:
  - dry-run returns count without repository;
  - upsert uses `transaction_number`;
  - duplicate transaction updates rather than inserts.
- CLI tests:
  - dry-run path with mocked collector;
  - summary output;
  - config error returns non-zero.

## Documentation

Update README:

- Add Tank Terminal config vars to local and production setup.
- Add local dry-run and write commands.
- Add production manual run command.
- Mention nightly job if added to `deploy/run-nightly-datajobs.sh`.

## Implementation Phases

### Phase 1. Preserve Parsing Behavior

Create parser tests from the existing `table.html`, then move parsing into
`data_jobs/tank_terminal/parsers.py`.

Definition of done:

- Parser extracts the same transaction fields as the old script.
- No dependency on fixed row indexes.

### Phase 2. Add Config And Collector

Create config loading and a Playwright collector that returns rows instead of
posting to an API.

Definition of done:

- Importing modules does not start Playwright.
- Dry-run CLI can collect and print summary without database writes.

### Phase 3. Add Database Persistence

Create model, repository, persistence module, and migration.

Definition of done:

- Migration creates `tank_transactions`.
- CLI can upsert collected transactions by `transaction_number`.

### Phase 4. Compose Integration

Add `datajob-tank-terminal` to `docker-compose.yml` using the shared datajob
image.

Definition of done:

- Local dry-run works through Docker Compose.
- Local write works after migrations.

### Phase 5. Scheduling And Docs

Add the job to nightly scheduling if desired and update README.

Definition of done:

- README documents local and production usage.
- Nightly script includes Tank Terminal if approved.

## Open Questions

- Should `transaction_duration` be stored as raw text, seconds, or both?
- Should `vehicle` eventually link to a machine/equipment table?
- Are `transaction_number` values globally stable and unique across the tank
  terminal lifetime?
- Should the job collect only the first page/latest rows, or page through older
  transactions until it reaches already-saved transaction numbers?
- Should non-diesel products be stored or filtered out?
