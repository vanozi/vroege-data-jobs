# Uniform Agri Behavior Baseline

This note captures the current behavior before refactoring. No runtime behavior was changed while gathering this baseline.

## Environment Check

- Workspace virtual environment found: `.venv`
- `venv` directory found: no
- `.venv` Python version: `Python 3.13.7`
- `uv` is installed at `C:\Users\woute\.local\bin\uv.exe`
- `uv run python --version` currently fails because uv cannot open `C:\Users\woute\AppData\Local\uv\cache\sdists-v9\.git` due to access denied.
- `.venv` currently has no `pip` module available.

## Current Script Command

Likely intended command:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.uniform_agri.scripts.koe_data
```

The script does not currently define an argument parser, so `--help` is not supported yet.

Attempted command:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.uniform_agri.scripts.koe_data --help
```

Observed result:

- The command fails during import because `requests` is not installed in `.venv`.

## Syntax And Import Checks

Syntax check:

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  data_jobs\uniform_agri\api_client.py `
  data_jobs\uniform_agri\services\uniform_service.py `
  data_jobs\uniform_agri\scripts\koe_data.py
```

Observed result:

- Syntax compilation succeeds for the current Uniform Agri files.

Import checks:

```powershell
.\.venv\Scripts\python.exe -c "import data_jobs.uniform_agri.api_client"
.\.venv\Scripts\python.exe -c "import data_jobs.uniform_agri.scripts.koe_data"
```

Observed result:

- Imports fail at `data_jobs.uniform_agri.api_client` because `requests` is missing.

Additional likely blockers after dependencies are available:

- `data_jobs/uniform_agri/scripts/koe_data.py` imports `init_db` from `database.database`, but no `init_db` function currently exists in `database/database.py`.
- `data_jobs/uniform_agri/scripts/koe_data.py` imports `KoeRepository` from a bare `repositories` package instead of `database.repositories.koe_repository`.
- `data_jobs/uniform_agri/scripts/koe_data.py` imports `data_jobs.uniform_agri.utils.logger.get_logger`, but shared job logging currently lives in `data_jobs/logger.py`.

## Current Behavior From Source Review

### Authentication

- `data_jobs/uniform_agri/api_client.py` loads environment variables through `load_dotenv()`.
- `get_access_token()` reads:
  - `UNIFORM_USERNAME`
  - `UNIFORM_PASSWORD`
  - `UNIFORM_BASE_URL`
  - `UNIFORM_CLIENT_ID`
- It posts credentials to:

```text
{UNIFORM_BASE_URL}/oauth2/token
```

- `ApiClient` first uses an explicit token if provided.
- If no explicit token is provided, it uses `UNIFORM_ACCESS_TOKEN`.
- If `UNIFORM_ACCESS_TOKEN` is missing, it requests a token and writes it back to `.env` as `UNIFORM_ACCESS_TOKEN`.
- API requests retry once after HTTP 401 by requesting a new token and updating `.env`.

### First API Endpoint Called

The first data endpoint called by `koe_data.py` is herd registration through `UniformService.get_herd_registration()`.

Endpoint:

```text
/herd/{herd_id}/management/form/herd/herdregistration
```

The current script hard-codes this herd id:

```text
c670836f-7732-43a1-ac5a-70c4f63435f4
```

### Follow-Up API Endpoint

For each retained cow, the script calls `UniformService.get_actual_tab_data()`.

Endpoint:

```text
/herd/{herd_id}/management/form/animalrecord/{animal_id}/tab/actual
```

### Available But Not Currently Used By Script

`UniformService.get_milk_recordings()` exists, but `koe_data.py` does not call it.

Endpoint:

```text
/herd/{herd_id}/management/form/animalrecord/{animal_id}/tab/milkrecording
```

### Animals Skipped

The script skips animals whose names start with:

- `VAARSKALF`
- `STIERKALF`

Current condition:

```python
if koe.name and koe.name.upper().startswith("VAARSKALF") or koe.name.upper().startswith("STIERKALF"):
    continue
```

Important observation:

- Because of operator precedence, `koe.name.upper().startswith("STIERKALF")` is evaluated even when `koe.name` is falsey. This can raise an error if `koe.name` is `None`.

### Tables Written

The script currently intends to write:

- `koeien`, through `KoeRepository.upsert_koe()`
- `koe_details`, through `KoeDetailRepository.upsert_koe_detail()`

The script then marks missing animals as no longer in the current herd:

- updates `koeien.in_current_herd` through `KoeRepository.mark_all_not_in_herd()`

The script does not currently write:

- `melkingen`, even though `MelkingenRepository` is imported and `UniformService.get_milk_recordings()` exists.

### Failure Behavior

Current behavior by phase:

- If herd registration fetch fails, the script prints an error and returns immediately.
- If a single cow upsert fails, the error is logged and the script continues with the next animal.
- If a single cow detail fetch or detail upsert fails, the error is logged and the script continues with the next animal.
- If marking missing animals as not in the current herd fails, the error is logged and the script still prints `Data collection completed!`.

### Output Behavior

- The script prints coarse progress messages to stdout.
- The script logs per-animal success and failure messages through `get_logger(__name__)`.
- The intended logger import path is currently stale relative to the shared `data_jobs.logger` module.

## Refactor Constraints From Baseline

- Preserve the current high-level collection order unless a later step intentionally changes it:
  1. fetch herd registration,
  2. upsert retained cows,
  3. fetch and upsert cow details,
  4. mark missing cows as not in current herd.
- Keep the current abort behavior for herd registration failure unless explicitly changed.
- Keep per-animal failures non-fatal unless explicitly changed.
- Treat milk recording collection as an existing capability that is not part of the current `koe_data.py` behavior.
