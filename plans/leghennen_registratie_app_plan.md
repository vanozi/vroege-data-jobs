# Leghennen Registratie App Plan

## Goal

Build a small Flask web application for a stable with 24,000 organic laying
hens. The app should replace the paper laying calendar and add structured
registrations for dead hens and floor/outside-nest eggs.

The first version should be simple, fast to enter on a phone or tablet, and
protected by a login screen. After login, the user should see an overview of
recent registrations and clear action buttons to add new entries.

This plan is for review before implementation. Do not start code changes until
the plan is approved.

## Source Form

The photo shows a paper laying calendar from Het Anker bv. For the first
version, flock/stable metadata is out of scope and can be added later. Important
daily fields on the visible form:

- Daily laying calendar rows:
  - day of week
  - `Aantal eieren`
    - `1e soort`
    - `2e soort`
    - `Dagtotaal`
  - `Uitval`
  - `Verbruik per dag`
    - `Water`
    - `Voer`
  - `Ontvangen voer`
  - `Opmerkingen`
- Weekly totals:
  - `Aantal hennen eind vd week`
  - `Eigewicht in gram`
  - `legpercentage`
  - `gem. dagprod.`

For the MVP, daily entry should focus on the values that are actually filled in
every day. Weekly calculated fields can be derived from daily rows where
possible.

## Functional Scope

### MVP Assumptions

- There is one house/stable for the first implementation.
- Feed and water are entered once per day, not per silo or water meter.
- Egg classes are exactly `1e soort` and `2e soort`.
- A shared admin login is sufficient for the first version.
- The app should support exports that match the paper calendar as closely as
  practical, preferably Excel first and PDF after that.

### 1. Authentication

Use a simple Flask session login flow, similar to the dashboard portal:

- Login page with username/password.
- Password stored as a Werkzeug hash in environment config.
- Session cookie:
  - `HttpOnly`
  - `SameSite=Lax`
  - `Secure` configurable for production/local.
- Logout button.
- All application pages require an authenticated session.

Recommended env variables:

```env
KIPPEN_APP_SECRET_KEY=
KIPPEN_APP_ADMIN_USERNAME=admin
KIPPEN_APP_ADMIN_PASSWORD_HASH=
KIPPEN_APP_SESSION_HOURS=12
KIPPEN_APP_COOKIE_SECURE=true
```

### 2. Main Dashboard

After login, show a work-focused overview page with:

- Today section:
  - date
  - whether the daily laying calendar has been filled in
  - total eggs today
  - dead hens today
  - outside-nest eggs today
- Action buttons:
  - `Dagregistratie invullen`
  - `Dode hen registreren`
  - `Buitennest ronde registreren`
  - `Weekoverzicht bekijken`
- Recent registrations:
  - last 7 daily calendar entries
  - latest dead hen registrations
  - latest outside-nest egg rounds

The app should be usable as the first screen, not a marketing/landing page.

### 3. Daily Laying Calendar Registration

Daily form fields:

- `registration_date`
- `weekday`
- `flock_id` or `house_id`
- `first_quality_eggs`
- `second_quality_eggs`
- `total_eggs`
- `dead_hens_count`
- `water_liters`
- `feed_kg`
- `notes`

Derived fields:

- `total_eggs = first_quality_eggs + second_quality_eggs`
- `dead_hens_count` is calculated from dead hen log entries for the same date.
- `laying_percentage = total_eggs / current_hen_count * 100`
- `current_hen_count` from flock start count minus cumulative mortality, unless
  manually corrected.

Validation:

- One daily registration per flock/house/date.
- Numeric values cannot be negative.
- `total_eggs` may be calculated by the app and should not need manual entry.
- `dead_hens_count` is read-only on the daily calendar and comes from detailed
  dead hen registrations.
- Date defaults to today.
- Weekday can be derived from the date.

### 4. Dead Hen Registration

Separate log for individual or grouped mortality observations.

Fields:

- `found_at` date/time
- `flock_id` or `house_id`
- `count`
- `stable_side`
- `section_number`
- `walkway`
- `found_place`
- `suspected_cause`
- `observations`
- `registered_by`

Location should be structured enough for later analysis, but not too slow to
enter. The stable is split into two sides:

- `Albering kant`
- `Ziekenboeg kant`

Each side has four sections from front to back:

- `1`
- `2`
- `3`
- `4`

Each section has three walkways:

- `Links`
- `Midden`
- `Rechts`

The found place should be one of:

- `In de stelling`
- `Op de stelling`
- `Onder de stelling`
- `In het gangpad`
- `Onbekend`

This gives a structured location like:

```text
Albering kant, vak 2, gangpad Midden, onder de stelling
```

The daily calendar `dead_hens_count` must be calculated from the detailed dead
hen log entries for the same date.

### 5. Outside-Nest Egg Rounds

Log each stable round where outside-nest/floor eggs are collected.

Fields:

- `round_at` date/time
- `flock_id` or `house_id`
- `egg_count`
- `notes`
- `registered_by`, taken from the logged-in user

Validation:

- `egg_count` cannot be negative.
- Date/time defaults to now.
- Multiple rounds per day are allowed.

Dashboard summaries:

- total outside-nest eggs today
- rounds today
- outside-nest eggs per week
- trend by time of day if enough data exists

## Data Model

Use PostgreSQL through SQLModel/Alembic if this app is integrated into the
current repository's database style.

### `daily_laying_registrations`

One row per flock/house/date.

Fields:

- `id`
- `flock_id`
- `registration_date`
- `weekday`
- `age_weeks`
- `first_quality_eggs`
- `second_quality_eggs`
- `total_eggs`
- `water_liters`
- `feed_kg`
- `notes`
- `created_by`
- `created_at`
- `updated_at`

Do not store `dead_hens_count` on this table in the MVP. Calculate it from
`dead_hen_registrations` for the same flock/house/date.

Indexes/constraints:

- unique: `(flock_id, registration_date)`
- index: `registration_date`

### `dead_hen_registrations`

Detailed mortality log.

Fields:

- `id`
- `flock_id`
- `found_at`
- `count`
- `stable_side`
- `section_number`
- `walkway`
- `found_place`
- `suspected_cause`
- `observations`
- `registered_by`
- `created_at`
- `updated_at`

Indexes:

- `found_at`
- `flock_id`

### `outside_nest_egg_rounds`

Outside-nest egg collection rounds.

Fields:

- `id`
- `flock_id`
- `round_at`
- `egg_count`
- `notes`
- `registered_by`
- `created_at`
- `updated_at`

Indexes:

- `round_at`
- `flock_id`

## Flask Structure

Suggested package:

```text
kippen_app/
  __init__.py
  app.py
  auth.py
  config.py
  forms.py
  services.py
  templates/
    base.html
    login.html
    dashboard.html
    daily_form.html
    dead_hen_form.html
    outside_nest_round_form.html
    week_overview.html
  static/
    app.css
```

Database files can follow the existing repo style:

```text
database/models/laying_hens.py
database/repositories/laying_hens_repository.py
database/persistence/laying_hens.py
database/migrations/versions/<revision>_add_laying_hens_registration_tables.py
```

## Routes

Authentication:

- `GET /login`
- `POST /login`
- `POST /logout`

Main:

- `GET /`
- `GET /dashboard`

Daily laying calendar:

- `GET /daily/new`
- `POST /daily/new`
- `GET /daily/<id>/edit`
- `POST /daily/<id>/edit`
- `POST /daily/<id>/delete`

Dead hens:

- `GET /dead-hens/new`
- `POST /dead-hens/new`
- `GET /dead-hens`
- `GET /dead-hens/<id>/edit`
- `POST /dead-hens/<id>/edit`
- `POST /dead-hens/<id>/delete`

Outside-nest eggs:

- `GET /outside-nest-rounds/new`
- `POST /outside-nest-rounds/new`
- `GET /outside-nest-rounds`
- `GET /outside-nest-rounds/<id>/edit`
- `POST /outside-nest-rounds/<id>/edit`
- `POST /outside-nest-rounds/<id>/delete`

Reports:

- `GET /week`
- `GET /week/<year>/<week>`
- `GET /week/<year>/<week>/export.xlsx`
- `GET /week/<year>/<week>/export.pdf`

## UI Guidance

Use Bulma, matching the user's preference and the existing portal style.

Main dashboard layout:

- Top bar:
  - app name
  - active flock/house
  - logout button
- KPI tiles:
  - eggs today
  - laying percentage
  - dead hens today
  - outside-nest eggs today
- Action buttons with clear labels.
- Tables for recent entries.

Form design:

- Large touch-friendly inputs.
- Date/time defaults to today/now.
- Numeric fields use number inputs.
- Save button fixed near the bottom.
- After save, redirect back to dashboard with a success message.

Avoid making the app card-heavy. It should feel like an operational tool for
fast repeated daily entry.

## Weekly Overview

Create a week table that resembles the paper calendar:

Columns:

- day
- date
- first-quality eggs
- second-quality eggs
- total eggs
- dead hens
- water
- feed
- notes

Show calculated weekly totals:

- total first-quality eggs
- total second-quality eggs
- total eggs
- total dead hens
- total water
- total feed
- end hen count
- average laying percentage

## Implementation Phases

### Phase 1: Foundation

- Add Flask app package under `kippen_app/`.
- Add config/auth/session handling.
- Add Bulma base layout.
- Add Docker service if this app runs next to the existing dashboards.
- Add tests for login/logout/session protection.

### Phase 2: Database

- Add SQLModel models.
- Add repositories/persistence helpers.
- Add Alembic migration.
- Add tests for create/update and unique daily registration behavior.

### Phase 3: Daily Registration

- Build dashboard page.
- Build daily form.
- Add validation and computed totals.
- Add week overview.

### Phase 4: Dead Hen Log

- Add dead hen form.
- Add recent mortality list.
- Make daily `dead_hens_count` display calculated totals from the detailed log.

### Phase 5: Outside-Nest Egg Rounds

- Add outside-nest round form.
- Add recent rounds list.
- Add daily/weekly totals.

### Phase 6: Polish and Deployment

- Add README section.
- Add production deployment instructions.
- Add backups/export.
- Add Excel export for the weekly laying calendar.
- Add PDF export for the weekly laying calendar.
- Add optional CSV export for raw records.
- Add responsive checks on phone-sized viewport.

## Testing Plan

Unit tests:

- auth credential validation
- config loading
- daily total calculations
- daily dead hen total calculation from detailed log entries
- laying percentage calculations
- hen count calculations

Repository tests:

- daily registration upsert/update by flock/date
- dead hen registration create/list
- outside-nest round create/list
- delete behavior for daily registrations, dead hen registrations, and
  outside-nest rounds

Route tests:

- unauthenticated users redirect to login
- authenticated users can open dashboard
- successful form posts create records
- invalid form posts return validation errors
- delete endpoints require authentication and remove the selected record
- Excel/PDF export endpoints require authentication

Manual checks:

- login/logout
- enter today's laying calendar
- register dead hens
- register outside-nest round
- delete an incorrectly entered registration
- view week overview on mobile
- export a week to Excel
- export a week to PDF

## Open Decisions

- None for the MVP.

Resolved MVP choices:

- Use one house/stable for now. Keep the model extensible enough to add multiple
  houses later.
- Enter feed and water per day only.
- Use only two egg classes: `1e soort` and `2e soort`.
- Use one shared admin login for now.
- Add weekly Excel/PDF export matching the paper calendar.

## MVP Acceptance Criteria

- User can log in.
- User sees a dashboard with today's status and action buttons.
- User can create/update one daily laying registration per date.
- User can register dead hens with location, date/time, count, and observations.
- User can register outside-nest egg rounds with date/time and egg count.
- User can delete incorrect registrations.
- Daily dead hen count is calculated from dead hen registrations.
- User can see recent registrations.
- User can open a weekly overview similar to the paper calendar.
- User can export a week overview to Excel/PDF.
- Database schema is managed through Alembic.
- The app can run locally through Docker Compose.
