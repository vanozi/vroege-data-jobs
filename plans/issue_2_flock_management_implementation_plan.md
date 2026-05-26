# Issue #2 Implementation Plan: Flock Management

GitHub issue: https://github.com/vanozi/vroege-data-jobs/issues/2

## Goal

Introduce flock management for the Kippen registratie app so operational
registrations can be tied to a production batch of laying hens. The first
implementation should keep the existing registration flows recognizable while
adding flock selection, flock lifecycle metadata, and bird-age calculations.

## Current State

- The Kippen app currently assumes one implicit house/flock via `house_id="main"`.
- Daily laying registrations, dead hen registrations, and outside-nest rounds
  exist as separate tables.
- There is no flock table and no explicit relation from registrations to a
  flock.
- Weekly reporting is based on ISO calendar weeks.
- Business rule: only one flock can be active in one house at the same time.
  For the current implementation there is one house, so there can be only one
  active flock globally.

## Proposed Data Model

Add a new SQLModel table: `flocks`.

Fields:

- `id`
- `flock_name`
- `date_of_birth`
- `placement_date`
- `end_date`
- `bird_count`
- `breed`
- `house_id`
- `is_active`
- `archived_at`
- `notes`
- `created_at`
- `updated_at`

Add nullable `flock_id` foreign keys to existing Kippen tables:

- `daily_laying_registrations.flock_id`
- `dead_hen_registrations.flock_id`
- `outside_nest_egg_rounds.flock_id`

Keep `house_id` for now so existing records and current UI behavior remain
compatible. `flock_id` should become the preferred link for new registrations.

`end_date` represents the date on which the hens leave the house. A flock is
considered active when:

- `placement_date <= target_date`
- `end_date` is empty or `target_date <= end_date`
- `archived_at` is empty

For the first version, there is only one house: `house_id="main"`. Enforce
that only one flock can be active for that house. Future multi-house support
must keep this rule scoped per house: flocks in different houses may have
overlapping active date ranges.

## Bird Age Rules

Bird age is calculated from `date_of_birth`.

Definitions:

- Bird age in days: `(target_date - date_of_birth).days + 1`
- Production week: `((bird_age_days - 1) // 7) + 1`
- Production day: `((bird_age_days - 1) % 7) + 1`

Examples:

- Hatch date `2026-01-01`, target `2026-01-01`: week 1, day 1
- Hatch date `2026-01-01`, target `2026-01-08`: week 2, day 1
- Hatch date `2026-01-01`, target `2026-01-10`: week 2, day 3

If `target_date` is before `date_of_birth`, show no age and reject new
registrations for that flock/date.

## Repository and Persistence

Add:

- `database/models/flock.py` or extend `database/models/laying_hens.py`
  if keeping the poultry domain in one model file is preferred.
- `FlocksRepository` with:
  - `create_flock`
  - `update_flock`
  - `get_flock_by_id`
  - `list_flocks`
  - `list_active_flocks`
  - `archive_flock`
  - `get_current_active_flock`
  - `get_active_flock_for_date`
  - `ensure_no_overlapping_active_flock`

Update existing repositories:

- Allow creating/updating daily registrations with `flock_id`.
- Allow creating dead hen registrations with `flock_id`.
- Allow creating outside-nest egg rounds with `flock_id`.
- Add list/count helpers that can filter by `flock_id` while keeping current
  `house_id` behavior as a fallback.
- Registration form helpers should assign the current active flock
  automatically. Users should not be able to create new registrations for an
  inactive or ended flock.

## Migration Plan

Create one Alembic migration:

1. Create `flocks`.
2. Add nullable `flock_id` columns to Kippen registration tables.
3. Add foreign keys and indexes.
4. Add an index on `house_id`, `placement_date`, and `end_date` to support
   active-flock lookup.
5. Optionally create one default flock only if required by application startup.

Recommendation: do not auto-create flock data in the migration unless the
business values are known. Instead, the UI should guide the user to create the
first flock, and existing records can remain unlinked until assigned later.

Database-level overlap prevention for date ranges is awkward across database
engines, so enforce "one active flock per house" in repository/application
logic first. The overlap check must always include `house_id`; overlapping
date ranges are allowed when they belong to different houses. If this becomes
high-risk later, add a PostgreSQL exclusion constraint or trigger scoped by
`house_id`.

## UI Routes

Flock management:

- `GET /kippen/flocks`
- `GET /kippen/flocks/new`
- `POST /kippen/flocks/new`
- `GET /kippen/flocks/<id>`
- `GET /kippen/flocks/<id>/edit`
- `POST /kippen/flocks/<id>/edit`
- `POST /kippen/flocks/<id>/archive`
- `POST /kippen/flocks/<id>/delete` only if no registrations are linked
- `POST /kippen/flocks/<id>/end` to set the flock `end_date`

Registration changes:

- Daily form shows the current active flock as read-only context.
- Dead hen form shows the current active flock as read-only context.
- Outside-nest round form shows the current active flock as read-only context.
- Dashboard shows active flock, bird age, production week, and production day.
- Week overview can filter by flock.
- If no active flock exists for the registration date, block new registration
  creation and show a clear link to create or activate a flock.

## UX Notes

- Keep the first version simple: there is one house (`house_id="main"`) and
  therefore at most one active flock.
- If no flock exists, dashboard should show a clear action to create one.
- If a flock has an `end_date`, registrations after that date should no longer
  attach to it.
- When a new flock is created, reject it if its active date range overlaps with
  an existing non-archived flock in the same house. Do not reject overlapping
  date ranges for different houses.
- If a new flock starts after the previous flock leaves, the previous flock
  should have an `end_date` before the new `placement_date`.
- Do not block viewing old records that have no `flock_id`.
- In form labels use Dutch operational terms:
  - `Koppel`
  - `Geboortedatum`
  - `Opzetdatum`
  - `Aantal hennen`
  - `Ras`
  - `Productieweek`
  - `Productiedag`

## Export Updates

Add flock columns to exports:

- Weekly Excel/PDF: active flock name, production week/day in the header.
- Raw daily CSV: `flock_id`, `flock_name`.
- Raw dead hens CSV: `flock_id`, `flock_name`.
- Raw outside-nest CSV: `flock_id`, `flock_name`.
Export filters should default to the current active flock where applicable, but
historical exports must still support older ended flocks.

## Tests

Unit tests:

- Bird age calculation.
- Production week/day calculation.
- Reject target dates before hatch date.
- Active flock lookup for dates inside/outside the placement/end date range.
- Overlapping active flock validation.

Repository tests:

- Create/update/list/archive flocks.
- Delete only when no registrations are linked.
- End a flock with `end_date`.
- Reject a second active/overlapping flock in the same house.
- Allow active/overlapping flock date ranges in different houses.
- Allow a new flock after the previous flock `end_date`.
- Registration creation with `flock_id`.
- Registration creation attaches to the active flock for the registration date.
- Registration creation is rejected when no active flock exists.
- Existing unlinked registrations still load.

Route tests:

- Flock list/new/edit/detail routes require login.
- Create flock validation.
- Archive flock.
- Registration forms include flock selector.
- Registration forms show current active flock.
- Registration forms block save when no active flock exists for the date.
- Dashboard shows bird age and production week/day.
- Week overview can display flock context.

Migration checks:

- Alembic upgrade creates the new table/columns.
- Existing registration rows survive migration with `flock_id=NULL`.

## Implementation Phases

### Phase 1: Domain and Migration

- Add `Flock` model.
- Add `flock_id` to existing registration models.
- Add Alembic migration.
- Add repository methods and tests.
- Add overlap validation scoped by `house_id`; for now this means
  `house_id="main"`, but the validation must be ready for multiple houses.

### Phase 2: Flock UI

- Add flock list, detail, create, edit, archive routes.
- Add route/action for setting `end_date`.
- Add Bulma templates.
- Add route tests.

### Phase 3: Registration Integration

- Add active flock context to daily, dead hen, and outside-nest forms.
- Persist `flock_id` on new registrations.
- Only allow new registrations for the current active flock for the
  registration date.
- Keep fallback behavior for old rows.
- Add tests.

### Phase 4: Age and Reporting

- Add bird-age helper functions.
- Show age/week/day on dashboard and registration pages.
- Add flock context to weekly exports and raw CSV exports.
- Add tests.

### Phase 5: Polish and Deployment

- Update README with flock management instructions.
- Run Docker build and migrations locally.
- Verify with Playwright on desktop and mobile.

## Open Decisions

- Should existing historical records be bulk-assigned to the first flock, or
  left unlinked until manually corrected?
- Should deleting a flock be allowed at all, or should archive/end-date be the
  only production-safe operations?
- Should production week reports eventually replace ISO week reports, or live
  alongside them?
- Should `end_date` mean the last day registrations are allowed, or the first
  day registrations are no longer allowed? Current plan treats `end_date` as
  the last allowed registration date.
