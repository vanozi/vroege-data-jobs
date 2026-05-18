# Uniform Agri Refactor Plan

## Goal

Refactor the Uniform Agri data collection code into a coherent, maintainable data job that follows `AGENTS.md` conventions and fits the current repository structure.

The refactor should make it clear how scripts:

- authenticate with the Uniform Agri API,
- collect API data,
- transform API responses into database models,
- persist data through repositories,
- log progress and failures,
- support future scripts for additional API endpoints.

This plan is implementation-only guidance. Do not start code changes until this plan is reviewed.

## Current State

Relevant files:

- `data_jobs/uniform_agri/api_client.py`
- `data_jobs/uniform_agri/services/uniform_service.py`
- `data_jobs/uniform_agri/scripts/koe_data.py`
- `data_jobs/logger.py`
- `database/database.py`
- `database/models/koe.py`
- `database/models/melking.py`
- `database/repositories/koe_repository.py`
- `database/repositories/koe_detail_repository.py`
- `database/repositories/melkingen_repository.py`

Observed issues:

- `koe_data.py` mixes orchestration, filtering, persistence, printing, and error handling.
- `koe_data.py` imports `KoeRepository` from `repositories`, which does not match the current `database.repositories` package.
- `koe_data.py` imports `data_jobs.uniform_agri.utils.logger`, but the staged structure has shared logging in `data_jobs/logger.py`.
- `api_client.py` writes refreshed tokens back to `.env`, which couples runtime execution to local file mutation.
- `api_client.py` and `uniform_service.py` use `requests` synchronously, while `AGENTS.md` asks to use `async/await` for asynchronous operations.
- Several type hints use `List`, `Dict`, and `type | None` style inconsistently with `AGENTS.md`.
- The service layer both calls endpoints and mutates raw payloads into SQLModel objects.
- API payload construction is embedded in long methods, which makes future endpoints harder to add.
- Error handling exists, but it is broad and mostly logs per-animal failures in the script layer.
- The project has a shared `data_jobs` package, but Uniform Agri does not yet use one consistent job runner pattern.

## Target Structure

Keep the implementation Python-first and function-oriented. Use small modules with narrow responsibility.

Proposed package layout:

```text
data_jobs/uniform_agri/
  __init__.py
  api_client.py
  config.py
  exceptions.py
  payloads.py
  schemas.py
  transforms.py
  collectors/
    __init__.py
    herd_registration.py
    animal_details.py
    milk_recordings.py
  scripts/
    __init__.py
    collect_koeien.py
    collect_melkingen.py
    collect_all.py
```

Responsibilities:

- `config.py`: read and validate environment variables such as base URL, credentials, client ID, herd ID, timeouts, and retry settings.
- `exceptions.py`: define API, configuration, transformation, and collection exceptions.
- `api_client.py`: own HTTP transport, authentication, retry behavior, token refresh, and JSON response handling.
- `payloads.py`: build Uniform Agri request payloads with named functions.
- `schemas.py`: optional Pydantic DTOs for API response fragments when direct SQLModel validation is too coupled to external API shape.
- `transforms.py`: convert API response dictionaries or DTOs into database model input.
- `collectors/`: orchestrate endpoint-level collection and return database-shaped records or SQLModel instances.
- `scripts/`: thin command-line entry points that parse arguments, call collectors, persist results, and report status.

## Implementation Steps

### 1. Preserve Behavior Before Refactoring

1. Check for a virtual environment named `venv` or `.venv`.
2. Confirm the intended execution command for current scripts, likely one of:
   - `uv run python -m data_jobs.uniform_agri.scripts.koe_data`
   - `.\venv\Scripts\python -m data_jobs.uniform_agri.scripts.koe_data`
3. Run a syntax-only or import-only check first if real API credentials or database access are not available.
4. Capture current behavior:
   - which endpoint is called first,
   - which animals are skipped,
   - which tables are written,
   - which failures should abort the run versus continue per animal.

Acceptance criteria:

- There is a short note in the implementation PR or change summary describing existing behavior.
- No behavior is intentionally changed before it is documented.

### 2. Fix Imports And Shared Utilities

1. Replace script imports with current package paths:
   - `database.repositories.koe_repository`
   - `database.repositories.koe_detail_repository`
   - `database.repositories.melkingen_repository`
   - `data_jobs.logger`
2. Remove or replace references to `data_jobs.uniform_agri.utils.logger` unless that package is intentionally restored.
3. Ensure internal function imports follow `AGENTS.md`:
   - use namespace imports for modules containing functions,
   - use direct imports for classes and exceptions.
4. Keep this step behavior-neutral.

Acceptance criteria:

- `python -m data_jobs.uniform_agri.scripts.koe_data --help` works after CLI support exists, or module import succeeds before CLI support is added.
- No stale imports remain in Uniform Agri scripts.

### 3. Add Configuration Module

Create `data_jobs/uniform_agri/config.py`.

Planned functions and data:

- `load_uniform_config() -> UniformAgriConfig`
- `UniformAgriConfig` as a small Pydantic model or dataclass.
- Required fields:
  - `base_url`
  - `username`
  - `password`
  - `client_id`
  - `herd_id`
- Optional fields:
  - `access_token`
  - `request_timeout_seconds`
  - `max_retries`

Rules:

- Load `.env` once at the edge.
- Fail fast with a clear configuration error when required values are missing.
- Do not call `os.getenv()` throughout the codebase after this module exists.
- Prefer `pathlib.Path` when referencing `.env` or repo paths.

Acceptance criteria:

- Missing credentials produce one clear exception before any API or database work starts.
- Scripts no longer hard-code `herd_id`.

### 4. Refactor API Client

Refactor `ApiClient` around an explicit config object.

Recommended approach:

- Prefer `httpx.AsyncClient` for async API calls if adding `httpx` as a dependency is acceptable.
- If keeping `requests` initially, isolate synchronous transport so an async migration can happen in a follow-up step.

Required behavior:

- Authenticate with Uniform Agri OAuth.
- Attach bearer token to requests.
- Refresh token once on HTTP 401.
- Raise project-specific exceptions with endpoint, status code, and short response context.
- Support configurable timeout.
- Do not write refreshed tokens back into `.env` unless explicitly desired.

Suggested dependency decision:

- Add `httpx` to runtime dependencies when converting to async.
- Remove duplicate dependency lines from `requirements.txt` while keeping current project dependency approach intact.

Acceptance criteria:

- API client can be unit tested with mocked HTTP responses.
- Token refresh behavior is covered by a test.
- Runtime token refresh does not mutate `.env` by default.

### 5. Split Payload Builders

Create `data_jobs/uniform_agri/payloads.py`.

Move request payloads out of service methods into named functions:

- `build_herd_registration_payload(herd_id: str, date: Optional[datetime] = None) -> dict`
- `build_animal_actual_payload(herd_id: str) -> dict`
- `build_milk_recordings_payload(herd_id: str) -> dict`

Rules:

- Keep payload functions pure.
- Use guarding clauses for invalid inputs.
- Avoid large inline dictionaries in endpoint orchestration methods after this step.

Acceptance criteria:

- Payloads can be tested without API or database dependencies.
- Endpoint methods are short enough to scan quickly.

### 6. Separate API Collection From Transformation

Replace or slim down `UniformService`.

Target responsibilities:

- API methods fetch raw Uniform Agri response data.
- Transform functions convert raw response data into model-shaped dictionaries or SQLModel instances.
- Collectors decide which endpoint calls to make and in what sequence.

Suggested functions:

- `fetch_herd_registration(client, herd_id, date) -> list[dict]`
- `fetch_animal_actual(client, herd_id, animal_id) -> dict`
- `fetch_milk_recordings(client, herd_id, animal_id) -> list[dict]`
- `koe_from_registration(raw: dict) -> Koe`
- `koe_detail_from_actual(raw: dict) -> KoeDetail`
- `melking_from_recording(raw: dict) -> Melking`

Rules:

- Do not mutate raw API dictionaries in place.
- Keep UUID and datetime parsing in transform helpers.
- Use `Optional[type]` instead of `type | None`.
- Use builtin collection types such as `list[dict]`.

Acceptance criteria:

- Transform functions can be tested from static fixture dictionaries.
- Service/client functions can be tested separately from database writes.

### 7. Build Collector Modules

Create collector modules for repeatable workflows.

Suggested collector behavior:

- `collectors/herd_registration.py`
  - fetch herd registration,
  - transform records into `Koe`,
  - skip excluded calf records using a named predicate,
  - return active cow list.
- `collectors/animal_details.py`
  - fetch details per animal,
  - continue on per-animal API failure when configured,
  - return details plus failures.
- `collectors/milk_recordings.py`
  - fetch milk recordings per animal,
  - return milkings plus failures.

Add small result models if useful:

- `CollectionResult`
- `AnimalCollectionFailure`

Acceptance criteria:

- The orchestration flow is testable without a database.
- Per-animal failures are reported in a structured way, not only printed.

### 8. Refactor Persistence Flow

Keep database writes in scripts or a small persistence module, not in the API client.

Recommended functions:

- `save_koeien(koeien, koe_repository) -> int`
- `save_koe_details(details, koe_detail_repository) -> int`
- `save_melkingen(melkingen, melkingen_repository) -> int`
- `mark_missing_koeien_not_in_current_herd(current_animal_ids, koe_repository) -> int`

Rules:

- Repositories remain the database boundary.
- Do not call `init_db()` as a substitute for Alembic migrations unless the project explicitly keeps runtime table creation.
- Prefer Alembic for schema changes.

Acceptance criteria:

- Collection can be run in dry-run mode without database writes.
- Database write counts are returned and logged.

### 9. Replace Script With Thin CLI Entrypoints

Refactor `koe_data.py` into a thin CLI or replace it with `collect_koeien.py`.

Recommended CLI options:

- `--herd-id`
- `--date`
- `--include-details`
- `--include-milkings`
- `--dry-run`
- `--continue-on-animal-error`
- `--limit`

Behavior:

- Load config.
- Create logger with `data_jobs.logger.get_job_logger(__file__)`.
- Create API client.
- Run collectors.
- Persist results unless `--dry-run` is set.
- Log summary counts and failures.

Acceptance criteria:

- The script file contains minimal business logic.
- The script can be invoked with `python -m ...`.
- Progress goes through logging instead of scattered `print()` calls, except for intentional CLI summary output.

### 10. Add Focused Tests

Add pytest coverage around the refactor.

Suggested test files:

```text
tests/data_jobs/uniform_agri/test_config.py
tests/data_jobs/uniform_agri/test_payloads.py
tests/data_jobs/uniform_agri/test_transforms.py
tests/data_jobs/uniform_agri/test_api_client.py
tests/data_jobs/uniform_agri/test_collectors.py
```

Priority tests:

- config fails clearly when required environment variables are missing,
- payload builders produce expected keys,
- UUID and datetime parsing works for known API shapes,
- calf skip predicate handles missing names safely,
- API client refreshes token once on 401,
- collectors continue or abort based on configuration,
- persistence helpers call repositories with expected model instances.

Acceptance criteria:

- Tests do not require live Uniform Agri credentials.
- Tests do not require a live PostgreSQL database unless explicitly marked as integration tests.

### 11. Apply Formatting And Linting

After Python files are changed:

1. Run `ruff format` on edited Python files.
2. Run `ruff check --fix` on edited Python files.
3. Run the focused pytest suite.
4. Run an import or dry-run command for the CLI.

Use the repository virtual environment if present:

- prefer `.venv` or `venv`,
- use `uv run` where appropriate,
- do not use `pip install`; use `uv pip install` if dependencies must be installed.

Acceptance criteria:

- Ruff format passes.
- Ruff check passes or remaining warnings are documented.
- Focused tests pass.

### 12. Documentation Update

Update `README.md` or add a small Uniform Agri section after implementation.

Include:

- required environment variables,
- example dry-run command,
- example database write command,
- note that Alembic manages schema changes,
- expected log location under `data_jobs/logs/`.

Acceptance criteria:

- A developer can run the Uniform Agri job without reading source code first.

## Suggested Implementation Order

1. Import cleanup and shared logger adoption.
2. Config and exceptions.
3. Payload builders.
4. Transform helpers with tests.
5. API client cleanup.
6. Collector modules.
7. Persistence helpers.
8. Thin CLI scripts.
9. Tests and documentation.

This order keeps the riskiest behavior changes isolated and allows each phase to be reviewed independently.

## Risk Areas

- The current code may depend on `.env` token persistence. Removing it should be tested with token refresh scenarios.
- Uniform Agri API responses may contain optional or missing fields not represented in current models.
- The current `KoeDetail` model may require fields that are sometimes absent from `actual` tab responses.
- Long per-animal runs need predictable failure handling so one bad animal does not invalidate a whole collection.
- Async conversion may require dependency updates and careful test mocking.

## Definition Of Done

- Uniform Agri jobs use a consistent package structure under `data_jobs/uniform_agri`.
- API, transform, collection, and persistence responsibilities are separated.
- Scripts are thin, runnable with `python -m`, and support dry-run behavior.
- Logging uses `data_jobs.logger`.
- Configuration is validated before work starts.
- No runtime code mutates `.env` by default.
- Focused pytest coverage exists for config, payloads, transforms, client retry behavior, and collectors.
- Edited Python files pass `ruff format` and `ruff check --fix`.
