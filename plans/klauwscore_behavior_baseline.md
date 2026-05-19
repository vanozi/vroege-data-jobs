# Klauwscore Behavior Baseline

Captured before refactoring the Klauwscore data job.

## Validation Environment

- Workspace virtual environment found: `.venv`
- Validation interpreter:
  `.\.venv\Scripts\python.exe`
- Python version: `Python 3.13.7`

Credentials were not present in the current process:

- `KLAUWSCORE_USERNAME`: not present
- `KLAUWSCORE_PASSWORD`: not present

Because credentials were unavailable, the real scraping and database-writing
commands were not executed. Validation was limited to syntax, import, and CLI
help checks.

## Current Commands

Current Klauwscore job command:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --summary
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --flat
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --upsert-db
```

Current parser command:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.pdf_parser <pdf_path>
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.pdf_parser <pdf_path> --flat
```

Observed `main` options:

- `--limit LIMIT`
- `--flat`
- `--summary`
- `--upsert-db`

Observed `pdf_parser` options:

- positional `pdf_path`
- `--flat`

## Validation Checks Run

Syntax check:

```powershell
.\.venv\Scripts\python.exe -m py_compile data_jobs\klauwscore\main.py data_jobs\klauwscore\pdf_parser.py database\models\behandeling.py database\repositories\behandelingen_repository.py
```

Result: passed.

Import check:

```powershell
.\.venv\Scripts\python.exe -c "import data_jobs.klauwscore.main; import data_jobs.klauwscore.pdf_parser; import database.models.behandeling; import database.repositories.behandelingen_repository; print('klauwscore imports ok')"
```

Result: passed.

CLI help checks:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --help
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.pdf_parser --help
```

Result: both passed.

## Configuration Behavior

The job currently loads environment variables at module import time.

Load order:

1. Repo root `.env`
2. `data_jobs/klauwscore/.env`

Both calls use `override=True`, so values from `data_jobs/klauwscore/.env`
override matching values from the repo root `.env`.

Required variables:

- `KLAUWSCORE_USERNAME`
- `KLAUWSCORE_PASSWORD`

If either variable is missing, the scraping functions raise:

```text
RuntimeError: Missing KLAUWSCORE_USERNAME or KLAUWSCORE_PASSWORD
```

## Browser And Scraping Behavior

Current constants:

- Base URL: `http://klauwscore.nl`
- Login URL: `http://klauwscore.nl/login`
- Agenda URL: `http://klauwscore.nl/veehouder/agenda`

Login behavior:

1. Navigate to the login URL.
2. Fill `#username`.
3. Fill `#password`.
4. Click `#_submit`.
5. Wait for `networkidle`.

Agenda behavior:

1. Navigate to the agenda URL after login.
2. Read HTML from `//div[@class='account-wrapper']`.
3. Parse that HTML with `lxml.html.fragment_fromstring`.
4. Select agenda rows from `.//tbody/tr`, or `.//tr[td]` as a fallback.

`Alle notaties` link behavior:

1. For each row, select links whose visible normalized text is exactly
   `Alle notaties`.
2. Skip rows without such a link.
3. Parse the treatment date from elements containing class `dayofmonth` and
   `shortdate`.
4. Parse the agenda cow count from the first integer in the element containing
   class `agenda-time`.
5. Join the link href to `http://klauwscore.nl`.

Dutch month names are parsed with a local mapping for:

- `januari`
- `februari`
- `maart`
- `april`
- `mei`
- `juni`
- `juli`
- `augustus`
- `september`
- `oktober`
- `november`
- `december`

If the agenda date text cannot be parsed, the current code raises `ValueError`.

## PDF Download Behavior

PDFs are downloaded through the authenticated Playwright context.

Defaults:

- attempts: `3`
- timeout: `120000` milliseconds

For each attempt:

1. `page.context.request.get(href, timeout=timeout_ms)` is called.
2. Exceptions are logged as warnings and retried.
3. Non-OK HTTP responses are logged as warnings and retried.
4. Empty response bodies are logged as warnings and retried.

If all attempts fail, the current code raises:

```text
RuntimeError: Failed to download PDF after <attempts> attempts: <href>
```

An empty PDF body is treated as a download failure, not as an empty document.

## PDF Parsing Behavior

`pdf_parser.py` uses `pypdf.PdfReader`.

Text extraction behavior:

- File path parser reads a local PDF file.
- Byte parser reads PDF bytes through `BytesIO`.
- Page text is joined with newline separators.

Parsing behavior:

1. Find the inspection date with pattern `op DD-MM-YYYY`.
2. Convert it to a `date`.
3. Treat a line containing only digits as a cow collar number.
4. Treat following non-skipped lines as notities for that cow until the next
   collar number is found.
5. Skip empty lines, lines starting with `Registratie van`, and footer lines
   matching the Rundvee Pedicure email/footer pattern.

If no inspection date is found, the parser raises:

```text
ValueError: Could not find inspection date in PDF text.
```

Flattening behavior:

- Grouped parser records contain one row per cow with `notities: list[str]`.
- Flattening emits one dictionary per notitie with:
  - `behandeldatum`
  - `halsbandnummer`
  - `notatie`

## Collection Behavior

`scrape_alle_notaties_records(limit=None)`:

1. Validates credentials.
2. Starts Chromium through synchronous Playwright in headless mode.
3. Logs in.
4. Loads the agenda page.
5. Parses all `Alle notaties` links.
6. Applies `limit` by slicing from the beginning of the link list.
7. Downloads each PDF sequentially.
8. Parses each PDF into cow records.
9. Appends each parsed document to a list.
10. Closes the browser after the loop.

Per-document download or parse failures currently abort the run. There is no
structured per-document failure result yet.

Progress is printed to stderr through `print_progress()`.

## Count Mismatch Behavior

`validate_document_counts(parsed_documents)` compares:

- agenda cow count: `document["aantal_koeien"]`
- parsed cow count: `len(document["records"])`

Mismatches are returned as dictionaries containing:

- `behandeldatum`
- `href`
- `aantal_koeien`
- `parsed_count`

Summary output prints:

- `documents=<count>`
- `cow_records=<count>`
- `notitie_rows=<count>`
- `count_mismatches=<count>`

The first 10 mismatches are printed as:

```text
count_mismatch=<date> agenda=<agenda_count> parsed=<parsed_count> <href>
```

Count mismatches do not abort the run.

## Duplicate Row Behavior

`dedupe_klauwbehandeling_rows(rows)` removes duplicate flattened rows by this
identity:

```text
(behandeldatum, halsbandnummer, notatie)
```

The first row for each identity is kept. Later duplicates are skipped.

If duplicates are removed, the duplicate count is printed to stderr through
`print_progress()`.

## Database Write Behavior

Database writes happen only when `--upsert-db` is passed.

The script:

1. Flattens parsed documents.
2. Deduplicates flattened rows.
3. Creates `KlauwBehandelingenRepository(get_session)`.
4. Groups rows by `behandeldatum`.
5. Upserts each row through `repository.upsert_klauw_behandeling(...)`.

Only these fields are passed to the repository:

- `halsbandnummer`
- `behandeldatum`
- `notatie`

The repository writes to table:

```text
klauw_behandelingen
```

The repository upsert identity is:

```text
["halsbandnummer", "behandeldatum", "notatie"]
```

After database upsert, stdout prints:

```text
upserted_klauw_behandelingen=<count>
```

There is no dry-run mode yet.

## Output Behavior

Without `--summary`, `--flat`, or `--upsert-db`:

- The script prints grouped JSON documents to stdout.

With `--flat`:

- The script prints flattened JSON rows to stdout.

With `--summary`:

- The script prints summary counts to stdout.

With `--upsert-db` and without `--flat`:

- The script prints only the upsert count to stdout and returns.

With `--upsert-db --flat`:

- The script upserts deduplicated rows, then prints flattened JSON to stdout.

## Known Refactor Constraints

- Preserve existing command compatibility until schedules or Docker commands are
  reviewed.
- Preserve current parse and dedupe behavior until tests document it.
- Keep real browser, network, and database actions out of unit tests.
- Move progress logging to `data_jobs.logger` in a later phase, but avoid
  changing output behavior before CLI compatibility is covered.
