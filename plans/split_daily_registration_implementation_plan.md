# Implementation Plan: Split Daily Registration

## Goal

Split the current Kippen `Dagregistratie` into two separate workflows:

- Egg registration for `1e soort eieren` and `2e soort eieren`.
- Feed/water registration for `water_ml` and `feed_grams`.

Both workflows must keep the active-flock requirement and continue to support
dashboard summaries, week overview, Excel/PDF exports, and raw CSV exports.

## Current State

- The Kippen app has one combined daily registration flow.
- `DailyLayingRegistration` currently stores:
  - `registration_date`
  - `first_quality_eggs`
  - `second_quality_eggs`
  - `total_eggs`
  - `water_ml`
  - `feed_grams`
  - `flock_id`
  - `house_id`
  - notes/user metadata
- New registrations require an active flock for the selected date.
- Water is stored as milliliters.
- Feed is stored as grams.
- Weekly reports read from the combined daily table.

## Proposed Data Model

Create two separate tables:

### `egg_registrations`

Fields:

- `id`
- `house_id`
- `flock_id`
- `registration_date`
- `weekday`
- `first_quality_eggs`
- `second_quality_eggs`
- `total_eggs`
- `notes`
- `created_by`
- `created_at`
- `updated_at`

Constraints:

- Unique key on `house_id` + `registration_date`.
- `flock_id` required.
- Egg counts must be non-negative integers.

### `feed_water_registrations`

Fields:

- `id`
- `house_id`
- `flock_id`
- `registration_date`
- `weekday`
- `water_ml`
- `feed_grams`
- `notes`
- `created_by`
- `created_at`
- `updated_at`

Constraints:

- Unique key on `house_id` + `registration_date`.
- `flock_id` required.
- `water_ml` and `feed_grams` must be non-negative integers.

## Migration Strategy

Add an Alembic migration that:

1. Creates `egg_registrations`.
2. Creates `feed_water_registrations`.
3. Copies existing values from `daily_laying_registrations`:
   - Egg fields into `egg_registrations`.
   - Feed/water fields into `feed_water_registrations`.
4. Keeps `flock_id`, `house_id`, `registration_date`, `weekday`, and metadata.
5. Drops or archives the old combined `daily_laying_registrations` table.

Recommended approach:

- Prefer creating the new tables and copying the data first.
- Drop the old table only after the copy is complete in the same migration.
- Downgrade can recreate `daily_laying_registrations` and merge values back from
  the two new tables.

Migration decision:

- For every existing `daily_laying_registrations` row, create both new rows:
  - one `egg_registrations` row
  - one `feed_water_registrations` row
- If values are missing in the old row, carry them over as the new model's
  default empty value. Use `0` for missing numeric counts/usage values unless
  implementation reveals a strong reason to preserve `NULL`.

## Repository Layer

Add repositories:

- `EggRegistrationsRepository`
- `FeedWaterRegistrationsRepository`

Each repository should support:

- create/upsert by `house_id` + `registration_date`
- update by id
- get by id
- get by house/date
- list recent
- list between dates
- list all
- delete by id

Validation rules:

- Reject writes without `flock_id`.
- Keep active-flock lookup in the Flask route layer so error messages are
  user-facing and consistent.

## Form Helpers

Replace or split `kippen_app/daily.py` into focused modules:

- `kippen_app/eggs.py`
- `kippen_app/feed_water.py`

### Egg Form

Fields:

- `registration_date`
- `house_id`
- `first_quality_eggs`
- `second_quality_eggs`
- `total_eggs` computed/read-only
- `notes`

### Feed/Water Form

Fields:

- `registration_date`
- `house_id`
- `water_ml`
- `feed_grams`
- `notes`

Parsing:

- Egg counts: integer, `>= 0`
- Water/feed: integer, `>= 0`
- Keep comma/decimal parsing out of feed/water because these are whole units.

## Flask Routes

Add route groups:

### Egg registrations

- `GET /kippen/eggs/new`
- `POST /kippen/eggs/new`
- `GET /kippen/eggs/<id>/edit`
- `POST /kippen/eggs/<id>/edit`
- `POST /kippen/eggs/<id>/delete`
- `GET /kippen/eggs`

### Feed/water registrations

- `GET /kippen/feed-water/new`
- `POST /kippen/feed-water/new`
- `GET /kippen/feed-water/<id>/edit`
- `POST /kippen/feed-water/<id>/edit`
- `POST /kippen/feed-water/<id>/delete`
- `GET /kippen/feed-water`

Route behavior:

- Resolve the active flock for the selected date.
- Show active flock and curve-age context on both forms.
- Block saving when no active flock exists.
- Redirect to dashboard or the relevant list after successful save.

## Templates

Add templates:

- `egg_form.html`
- `egg_registrations.html`
- `feed_water_form.html`
- `feed_water_registrations.html`

Update existing templates:

- `dashboard.html`
  - Replace `Dagregistratie invullen` with separate buttons:
    - `Eieren registreren`
    - `Water en voer registreren`
  - Show today's egg total independently from today's water/feed status.
- `week.html`
  - Read egg totals and feed/water values from separate row context.

## Reporting and Exports

Update `_week_rows` so each row contains:

- date
- weekday
- active/current flock
- flock age
- egg registration for that date
- feed/water registration for that date
- dead hen count
- outside-nest egg count

Update `_week_totals`:

- Egg totals from egg registrations.
- Water/feed totals from feed/water registrations.
- Mortality and outside-nest totals unchanged.

Update exports:

- Weekly Excel/PDF should keep the same visible report columns.
- Raw CSV exports should become:
  - `/kippen/export/eggs.csv`
  - `/kippen/export/feed-water.csv`
  - existing dead-hens and outside-nest exports unchanged

Compatibility decision:

- Do not keep `/kippen/export/daily.csv`.
- It is not operationally used, so remove the combined daily export and document
  the replacement exports:
  - `/kippen/export/eggs.csv`
  - `/kippen/export/feed-water.csv`

## Tests

Add/update tests for:

- SQLModel models and migrations.
- Egg repository CRUD/upsert/delete.
- Feed/water repository CRUD/upsert/delete.
- Active-flock enforcement for both workflows.
- Egg form validation.
- Feed/water form validation.
- Dashboard display.
- Week overview row merging.
- Excel/PDF weekly exports.
- Raw CSV exports.
- Delete endpoints.

Existing test files likely affected:

- `tests/kippen_app/test_routes.py`
- `tests/database/test_laying_hens_repository.py`
- `tests/database/test_laying_hens_persistence.py`

Consider adding:

- `tests/kippen_app/test_eggs.py`
- `tests/kippen_app/test_feed_water.py`

## README Updates

Update Kippen documentation with:

- New workflow:
  - create active flock
  - register eggs
  - register feed/water
  - view week report
- New routes.
- New raw CSV exports.
- Migration note explaining that the old combined daily rows are split into two
  tables.

## Implementation Phases

### Phase 1: Data Model and Migration

- Add `EggRegistration` model.
- Add `FeedWaterRegistration` model.
- Add Alembic migration to split existing rows.
- Add repository classes.
- Add repository tests.

### Phase 2: Form Helpers and Routes

- Add egg form helper.
- Add feed/water form helper.
- Add CRUD routes for both workflows.
- Add route tests.

### Phase 3: Templates and Dashboard

- Add list/form templates.
- Update dashboard buttons and status blocks.
- Verify active flock and age display on both forms.

### Phase 4: Reporting and Exports

- Update week row merging.
- Update weekly totals.
- Update Excel/PDF exports.
- Add new raw CSV exports.
- Add export tests.

### Phase 5: Cleanup and Documentation

- Remove obsolete combined daily form/template/routes.
- Update README.
- Run Docker build and migrations locally.
- Verify with Playwright desktop and mobile.

## Risks

- Existing dashboard/week/export logic assumes one daily row per date.
- Migration must preserve existing operational data.
- Delete behavior should not accidentally remove data from the other workflow.
- Removing `/kippen/export/daily.csv` is a deliberate breaking change, but it is
  acceptable because that export is not operationally used.

## Open Questions

- Should `/kippen/daily/new` redirect to a choice page, to egg registration, or
  be removed?
- Should notes be separate for eggs and feed/water, or should only one workflow
  keep notes?
- Should missing feed/water values be shown as `-` or `0` in weekly reports?
