# Uniform Agri Collection Progress Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report regular, concise progress while collecting Uniform Agri cow details and milk recordings.

**Architecture:** Add an optional callback to each per-animal collector. The CLI supplies a logging callback, preserving collector reuse and leaving existing callers unchanged. The callback is invoked before collection, at each 50-cow boundary, and once after the final cow.

**Tech Stack:** Python 3.12+, pytest, standard-library logging.

## Global Constraints

- Progress messages use `INFO` and never include credentials.
- The standard progress interval is exactly 50 cows.
- Existing callers without a callback retain current results and error handling.
- Run `ruff format` and `ruff check --fix` on edited Python files.

---

### Task 1: Expose progress from per-animal collectors

**Files:**
- Modify: `data_jobs/uniform_agri/collectors/animal_details.py`
- Modify: `data_jobs/uniform_agri/collectors/milk_recordings.py`
- Test: `tests/data_jobs/uniform_agri/test_animal_details.py`
- Test: `tests/data_jobs/uniform_agri/test_milk_recordings.py`

**Interfaces:**
- Consumes: the existing `Koe` lists, service objects, and `continue_on_animal_error` flag.
- Produces: optional `progress_callback(processed: int, total: int)` calls before processing, at each 50-cow boundary, and after processing.

- [ ] **Step 1: Write failing collector tests**

```python
progress = []

collect_animal_details(
    service,
    "herd-id",
    koeien,
    progress_callback=lambda processed, total: progress.append((processed, total)),
)

assert progress == [(0, 51), (50, 51), (51, 51)]
```

Repeat the assertion for `collect_milk_recordings`.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/data_jobs/uniform_agri/test_animal_details.py tests/data_jobs/uniform_agri/test_milk_recordings.py -q`

Expected: FAIL because the collectors do not accept `progress_callback`.

- [ ] **Step 3: Add the optional callback and invoke it**

```python
progress_callback: Optional[Callable[[int, int], None]] = None

if progress_callback:
    progress_callback(0, len(koeien))

for processed, koe in enumerate(koeien, start=1):
    # Existing request and error-handling logic.
    if progress_callback and (processed % 50 == 0 or processed == len(koeien)):
        progress_callback(processed, len(koeien))
```

- [ ] **Step 4: Run collector tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/data_jobs/uniform_agri/test_animal_details.py tests/data_jobs/uniform_agri/test_milk_recordings.py -q`

Expected: PASS.

### Task 2: Log CLI stage progress

**Files:**
- Modify: `data_jobs/uniform_agri/scripts/koe_data.py`
- Test: `tests/data_jobs/uniform_agri/test_koe_data_cli.py`

**Interfaces:**
- Consumes: collector `progress_callback(processed, total)` calls from Task 1.
- Produces: an `INFO` log at stage start, every 50 cows, and stage completion.

- [ ] **Step 1: Write a failing CLI logging test**

```python
with caplog.at_level(logging.INFO, logger=logger.name):
    koe_data.run(args, logger)

assert "Collecting cow details: 0/2" in caplog.text
assert "Collecting cow details: 2/2" in caplog.text
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run: `./venv/bin/python -m pytest tests/data_jobs/uniform_agri/test_koe_data_cli.py -q`

Expected: FAIL because no progress callback is passed or logged.

- [ ] **Step 3: Add a logging callback factory and pass it to both collectors**

```python
def build_progress_logger(logger: logging.Logger, stage: str):
    def log_progress(processed: int, total: int) -> None:
        logger.info("Collecting %s: %s/%s", stage, processed, total)
    return log_progress
```

Pass `build_progress_logger(logger, "cow details")` to the details collector and
`build_progress_logger(logger, "milk recordings")` to the milkings collector.

- [ ] **Step 4: Run formatting, linting, and focused tests**

Run:

```bash
./venv/bin/ruff format data_jobs/uniform_agri/collectors/animal_details.py data_jobs/uniform_agri/collectors/milk_recordings.py data_jobs/uniform_agri/scripts/koe_data.py tests/data_jobs/uniform_agri/test_animal_details.py tests/data_jobs/uniform_agri/test_milk_recordings.py tests/data_jobs/uniform_agri/test_koe_data_cli.py
./venv/bin/ruff check --fix data_jobs/uniform_agri/collectors/animal_details.py data_jobs/uniform_agri/collectors/milk_recordings.py data_jobs/uniform_agri/scripts/koe_data.py tests/data_jobs/uniform_agri/test_animal_details.py tests/data_jobs/uniform_agri/test_milk_recordings.py tests/data_jobs/uniform_agri/test_koe_data_cli.py
./venv/bin/python -m pytest tests/data_jobs/uniform_agri -q
```

Expected: all commands succeed.
