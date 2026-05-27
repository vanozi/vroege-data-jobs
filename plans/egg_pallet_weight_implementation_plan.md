# Implementation Plan: Egg Pallet Weight Registrations

## Goal

Add a Kippen workflow for registering egg pallet weights and empty-packaging
weights so the app can calculate average egg weight in grams.

Calculation:

```text
egg_weight_grams = (pallet_weight_kg - empty_packaging_weight_kg) / 10800 * 1000
```

The default egg count per pallet is `10800`.

## Current State

- The Kippen app is a Flask app under `kippen_app/`.
- Kippen database models live in `database/models/laying_hens.py`.
- Kippen repositories live in `database/repositories/laying_hens_repository.py`.
- Current registration workflows use:
  - SQLModel models.
  - Alembic migrations.
  - repository classes.
  - small form-helper modules.
  - Bulma templates.
  - route tests in `tests/kippen_app/test_routes.py`.
- Existing Kippen workflows require an active flock for registration dates.
- Current split daily workflows are:
  - egg counts in `egg_registrations`
  - feed/water in `feed_water_registrations`

## Proposed Data Model

### `egg_packaging_weight_configs`

Stores empty-packaging weights by supplier/eierhandel and active date range.

Fields:

- `id`
- `supplier_name`
- `empty_packaging_weight_kg`
- `start_date`
- `end_date`
- `notes`
- `created_at`
- `updated_at`

Constraints:

- `supplier_name` is required.
- `empty_packaging_weight_kg` must be non-negative.
- `start_date` is required.
- `end_date` is optional.
- `end_date` cannot be before `start_date`.
- Active ranges for the same supplier should not overlap.

Implementation note:

- Use a numeric type that preserves decimal precision. Prefer `Decimal` in
  Python and an Alembic `Numeric` column in PostgreSQL.

### `egg_pallet_weight_registrations`

Stores pallet-weight measurements and the calculated average egg weight.

Fields:

- `id`
- `house_id`
- `flock_id`
- `registration_date`
- `weekday`
- `packaging_weight_config_id`
- `supplier_name`
- `pallet_weight_kg`
- `empty_packaging_weight_kg`
- `egg_count`
- `egg_weight_grams`
- `notes`
- `created_by`
- `created_at`
- `updated_at`

Constraints:

- `flock_id` is required.
- `registration_date` is required.
- `packaging_weight_config_id` is required.
- `pallet_weight_kg` must be non-negative.
- `empty_packaging_weight_kg` must be non-negative.
- `pallet_weight_kg` should be greater than or equal to
  `empty_packaging_weight_kg`.
- `egg_count` defaults to `10800` and must be greater than zero.
- `egg_weight_grams` is calculated from the saved weights.

Historical correctness:

- Store both `packaging_weight_config_id` and the actual
  `empty_packaging_weight_kg` copied from the selected config at save time.
- Store `supplier_name` copied from the selected config at save time.
- This prevents old pallet registrations from changing when a supplier's
  empty-packaging config changes later.

## Calculation Rules

Use:

```text
net_egg_weight_kg = pallet_weight_kg - empty_packaging_weight_kg
egg_weight_grams = net_egg_weight_kg / egg_count * 1000
```

Example:

```text
pallet_weight_kg = 700
empty_packaging_weight_kg = 50
egg_count = 10800
egg_weight_grams = (700 - 50) / 10800 * 1000 = 60.185185...
```

Display:

- Show `egg_weight_grams` rounded to a practical number of decimals in the UI.
- Store enough precision for later reporting. Suggested storage precision:
  `Numeric(10, 4)` for grams.

## Repository Layer

Add repositories:

- `EggPackagingWeightConfigsRepository`
- `EggPalletWeightRegistrationsRepository`

### Packaging Config Repository

Methods:

- `create_packaging_weight_config`
- `update_packaging_weight_config`
- `get_packaging_weight_config_by_id`
- `list_packaging_weight_configs`
- `list_active_for_date`
- `get_active_for_supplier_and_date`
- `delete_packaging_weight_config`

Validation:

- Reject invalid date ranges.
- Reject overlapping date ranges for the same supplier.
- Prevent deletion if pallet registrations already reference the config, or
  make the delete route archive/deactivate instead of hard-delete.

### Pallet Weight Repository

Methods:

- `create_pallet_weight_registration`
- `update_pallet_weight_registration`
- `get_pallet_weight_registration_by_id`
- `list_recent`
- `list_between`
- `list_all`
- `delete_pallet_weight_registration`

Validation:

- Reject writes without `flock_id`.
- Reject writes without `packaging_weight_config_id`.
- Keep active-flock lookup and user-facing errors in the Flask route layer.

## Form Helpers

Add helper modules:

- `kippen_app/packaging_weights.py`
- `kippen_app/pallet_weights.py`

### Packaging Weight Form

Fields:

- `supplier_name`
- `empty_packaging_weight_kg`
- `start_date`
- `end_date`
- `notes`

Parsing:

- Accept decimal numbers for weights.
- Support comma input by normalizing `12,5` to `12.5`.
- Reject negative weights.
- Validate date order.

### Pallet Weight Form

Fields:

- `registration_date`
- `house_id`
- `packaging_weight_config_id`
- `pallet_weight_kg`
- `egg_count`
- `notes`

Derived fields:

- `weekday`
- `supplier_name`
- `empty_packaging_weight_kg`
- `egg_weight_grams`
- `created_by`

Parsing:

- Accept decimal numbers for weights.
- Default `egg_count` to `10800`.
- Reject `egg_count <= 0`.
- Reject `pallet_weight_kg < empty_packaging_weight_kg`.

## Flask Routes

### Packaging Weights

- `GET /kippen/packaging-weights`
- `GET /kippen/packaging-weights/new`
- `POST /kippen/packaging-weights/new`
- `GET /kippen/packaging-weights/<id>/edit`
- `POST /kippen/packaging-weights/<id>/edit`
- `POST /kippen/packaging-weights/<id>/delete`

### Pallet Weights

- `GET /kippen/pallet-weights`
- `GET /kippen/pallet-weights/new`
- `POST /kippen/pallet-weights/new`
- `GET /kippen/pallet-weights/<id>/edit`
- `POST /kippen/pallet-weights/<id>/edit`
- `POST /kippen/pallet-weights/<id>/delete`

Route behavior:

- All routes require Kippen login.
- Pallet registrations require an active flock for the selected date.
- The pallet form should show active flock and age context.
- The pallet form should only allow packaging configs active on the selected
  registration date.
- After successful save, redirect to the relevant list page.

## Templates

Add templates:

- `packaging_weight_form.html`
- `packaging_weights.html`
- `pallet_weight_form.html`
- `pallet_weights.html`

Update:

- `dashboard.html`
  - Add action buttons for pallet weights and packaging weights.
  - Add a recent pallet weights section or link.
- Consider adding pallet-weight links to week/report pages in a later phase.

UI display:

- Show pallet weight kg.
- Show empty-packaging weight kg.
- Show egg count.
- Show calculated egg weight in grams.
- Show supplier/eierhandel.

## Reporting and Exports

Initial scope:

- Add raw CSV exports:
  - `/kippen/export/pallet-weights.csv`
  - `/kippen/export/packaging-weights.csv`

CSV fields for pallet weights:

- `id`
- `house_id`
- `flock_id`
- `flock_name`
- `flock_date_of_birth`
- `flock_age_weeks`
- `flock_age_days`
- `registration_date`
- `weekday`
- `supplier_name`
- `pallet_weight_kg`
- `empty_packaging_weight_kg`
- `egg_count`
- `egg_weight_grams`
- `notes`
- `created_by`

CSV fields for packaging weights:

- `id`
- `supplier_name`
- `empty_packaging_weight_kg`
- `start_date`
- `end_date`
- `notes`

Non-goal for first implementation:

- Do not change the weekly laying calendar PDF/Excel unless explicitly needed.

## Tests

Add/update tests for:

- SQLModel model creation.
- Alembic migration creation.
- Repository CRUD for packaging configs.
- Repository overlap validation for packaging configs.
- Repository CRUD for pallet weights.
- Egg-weight calculation.
- Form validation for decimal weights and invalid values.
- Login-protected routes.
- Pallet form active-flock enforcement.
- Pallet form active packaging config selection.
- Delete behavior.
- Raw CSV exports.
- README route/export documentation.

Likely files:

- `tests/database/test_laying_hens_repository.py`
- `tests/database/test_laying_hens_persistence.py`
- `tests/kippen_app/test_routes.py`
- Optional focused tests:
  - `tests/kippen_app/test_pallet_weights.py`
  - `tests/kippen_app/test_packaging_weights.py`

## README Updates

Update the Kippen app section with:

- Packaging weight setup workflow.
- Pallet weight registration workflow.
- Calculation formula.
- New routes.
- New CSV exports.

## Implementation Phases

### Phase 1: Data Model and Migration

- Add packaging config model.
- Add pallet weight registration model.
- Add Alembic migration.
- Add repository classes.
- Add repository tests.

### Phase 2: Calculation and Form Helpers

- Add decimal parsing helpers.
- Add egg-weight calculation helper.
- Add packaging config form helper.
- Add pallet weight form helper.
- Add helper tests.

### Phase 3: CRUD Routes and Templates

- Add packaging config CRUD routes.
- Add pallet weight CRUD routes.
- Add Bulma templates.
- Add route tests.

### Phase 4: Dashboard and Exports

- Add dashboard navigation/status links.
- Add raw CSV exports.
- Add export tests.

### Phase 5: Documentation and Verification

- Update README.
- Run ruff format/check.
- Run pytest.
- Run Docker build and migrations locally.
- Verify with Playwright desktop and mobile.

## Risks

- Decimal handling needs care; floats can introduce rounding errors.
- Historical correctness can be lost if pallet rows only reference a packaging
  config instead of copying the used empty-packaging weight.
- Overlap validation for packaging configs must be scoped by supplier.
- Existing local databases may have old Kippen data; migration must be additive
  and should not touch existing egg/feed/water tables.

## Open Questions

- Should `egg_count` always be locked at `10800`, or should the form allow a
  manual override for partial pallets?
- Should packaging configs be hard-deleted when unused, or archived with an
  inactive flag?
- Should pallet weights be included in weekly reports now, or only as a
  separate list/export in the first version?
- Should supplier/eierhandel names be free text, or managed as a separate
  supplier table later?
