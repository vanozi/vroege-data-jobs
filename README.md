## Data jobs

Run data jobs from the repository root with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m <module>
```

Apply database migrations before running jobs that write to the database. Use
`--dry-run` first when validating credentials or checking a new command.

### Klauwscore

The Klauwscore job logs in to `klauwscore.nl`, reads the stallijst table at
`/veepedicure/stallijst`, parses hoof treatment notes, deduplicates rows by
`behandeldatum`, `eartag_short`, and `notatie`, then persists them to
`klauw_behandelingen`.

Required configuration:

```env
KLAUWSCORE_USERNAME=...
KLAUWSCORE_PASSWORD=...
```

Optional configuration:

```env
KLAUWSCORE_BASE_URL=http://klauwscore.nl
KLAUWSCORE_LOGIN_PATH=/login
KLAUWSCORE_STALLIJST_PATH=/veepedicure/stallijst
KLAUWSCORE_HEADLESS=true
KLAUWSCORE_DEFAULT_LIMIT=
```

The Klauwscore config loader reads the repository root `.env` first, then
`data_jobs/klauwscore/.env`. Values in the job-specific `.env` override root
values.

Recommended commands:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.scripts.collect_klauwscore --summary --dry-run
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.scripts.collect_klauwscore --limit 2 --dry-run --summary
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.scripts.collect_klauwscore --limit 1 --flat --dry-run
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.scripts.collect_klauwscore --summary
```

Expected `--summary --dry-run` output uses stallijst terms:

```text
source=stallijst
stallijst_cows=<unique cow/date rows>
flat_notitie_rows=<one row per note after splitting Laatste notaties>
deduped_notitie_rows=<rows after deduplication>
duplicate_notitie_rows=<removed duplicates>
failures=0
saved_klauw_behandelingen=<rows that would be written>
dry_run=True
```

Useful options:

- `--dry-run`: collect and validate without database writes.
- `--summary`: print counts instead of JSON records.
- `--flat`: print one row per notitie. If one cow has three values in
  `Laatste notaties`, this prints three rows with the same `eartag_short` and
  `behandeldatum`.
- `--limit N`: process only the first `N` stallijst cows.
- `--headless` / `--no-headless`: control browser visibility.

The older PDF agenda settings and flags are still present in code for
compatibility, but the normal collection path uses `/veepedicure/stallijst`.

Compatibility command:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.klauwscore.main --summary --dry-run
```

`data_jobs.klauwscore.main` is currently a wrapper around the new CLI entrypoint.

### Tank Terminal

The Tank Terminal job logs in to the diesel tank terminal, reads the
transactions table, normalizes fill-up rows, deduplicates them by transaction
number, and persists them to `tank_transactions`.

Required configuration:

```env
TANK_TERMINAL_BASE_URL=http://82.197.193.195:8080
TANK_TERMINAL_USERNAME=...
TANK_TERMINAL_PASSWORD=...
```

Optional configuration:

```env
TANK_TERMINAL_HEADLESS=true
TANK_TERMINAL_DEFAULT_LIMIT=
```

Recommended commands:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.tank_terminal.scripts.collect_tank_terminal --summary --dry-run
.\.venv\Scripts\python.exe -m data_jobs.tank_terminal.scripts.collect_tank_terminal --summary
```

## Dashboard portal

The dashboard portal is a small Flask app in [`dashboard_portal/`](dashboard_portal/).
It is the central authenticated homepage for applications and dashboards. The
root route `/` shows application links from the shared auth database after
login; without a session it redirects to `/login`.

Current portal routes:

- `/`: application overview, protected by session.
- `/login`: login page.
- `/logout`: logout endpoint.
- `/admin/users`: user administration for users with the
  `user_administration` application and `admin` role.
- `/auth/verify`: Traefik ForwardAuth endpoint with application-aware path
  checks.
- `/healthz`: healthcheck.

Portal login users are stored in the shared auth tables. Run migrations and the
`auth-bootstrap` tool before relying on `/login`. The `PORTAL_ADMIN_USERNAME`
and `PORTAL_ADMIN_PASSWORD_HASH` settings are legacy and no longer used; do not
add them to new deployments.

Run the Flask portal locally from the repository root:

```powershell
.\.venv\Scripts\python.exe -m flask --app dashboard_portal.app:create_app run --host 127.0.0.1 --port 10000
```

Useful checks:

```powershell
.\.venv\Scripts\python.exe -m flask --app dashboard_portal.app:create_app routes
```

Optional local configuration:

```env
PORTAL_SECRET_KEY=change-me
PORTAL_SESSION_HOURS=12
PORTAL_COOKIE_SECURE=false
```

Visible application links now come from `applications`,
`user_application_access`, and `user_application_roles`. Core applications and
roles are seeded by the shared auth bootstrap command.

### User administration

The central portal includes a small admin UI for shared users and application
authorization. Open `/admin/users` after logging in as a user that has access to
the `user_administration` application with the `admin` role.

From this screen an admin can:

- create users with a default password;
- edit username, name, and active status;
- reset a user's password;
- grant or revoke access to applications;
- assign one or more roles per application.

Users log in with a username without spaces, not with an email address. New
users receive `PORTAL_DEFAULT_USER_PASSWORD` and must choose their own password
on first login. Password reset in user administration sets the same default
password again and forces the user to change it at the next login.

Normal users without the `user_administration` admin role can still log in and
open the applications they have access to, but they receive `403 Forbidden` on
`/admin/users`.

### Docker Compose stack

The repository includes a standalone [`docker-compose.yml`](docker-compose.yml)
with its own Traefik proxy, PostgreSQL database, Flask portal, Marimo
klauwgezondheid dashboard, Kippen registratie app, Alembic migration runner,
and datajob containers. It does not depend on another Compose project.

The services use separate Dockerfiles and dependency files:

- [`docker/portal/Dockerfile`](docker/portal/Dockerfile): Flask portal and
  Gunicorn.
- [`docker/kippen/Dockerfile`](docker/kippen/Dockerfile): Kippen registratie
  Flask app and Gunicorn.
- [`docker/marimo/Dockerfile`](docker/marimo/Dockerfile): Marimo dashboard and
  dashboard data dependencies for Kippen, Klauwgezondheid, Tanken, and Moneybird.
- [`docker/database/Dockerfile`](docker/database/Dockerfile): Alembic migration
  runner for the `database/` package.
- [`docker/datajobs/Dockerfile`](docker/datajobs/Dockerfile): Playwright-based
  datajob runner for Klauwscore and Uniform Agri.

Traefik protects the Marimo dashboard paths with the portal `/auth/verify`
ForwardAuth endpoint. Direct access to `/kippen-dashboard`, `/klauwgezondheid`,
`/tank-terminal`, `/moneybird`, and their Marimo manifest routes without a valid shared
portal session and matching application access returns unauthorized.
The Kippen registratie app at `/kippen` uses the shared portal session and
requires active `kippen` application access.

### Local quickstart

Local Docker uses [`docker-compose.local.yml`](docker-compose.local.yml) as an
HTTP-only override. It disables TLS and Let's Encrypt, binds Traefik to port
`80`, and sets `PORTAL_COOKIE_SECURE=false`.

Create local application configuration:

```powershell
Copy-Item deploy\dashboard.env.example deploy\dashboard.env
```

Set at least these values in `deploy/dashboard.env`:

```env
PORTAL_SECRET_KEY=change-me
PORTAL_DEFAULT_USER_PASSWORD=welkom123
AUTH_BOOTSTRAP_USERNAME=admin
AUTH_BOOTSTRAP_PASSWORD=replace-with-temporary-password
AUTH_BOOTSTRAP_FIRST_NAME=Admin
AUTH_BOOTSTRAP_LAST_NAME=
AUTH_BOOTSTRAP_RESET_PASSWORD=false
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/gebroeders_vroege
KLAUWSCORE_USERNAME=...
KLAUWSCORE_PASSWORD=...
UNIFORM_BASE_URL=https://eu.myherdmanagement.com/restapi
UNIFORM_USERNAME=...
UNIFORM_PASSWORD=...
UNIFORM_CLIENT_ID=...
TANK_TERMINAL_BASE_URL=http://82.197.193.195:8080
TANK_TERMINAL_USERNAME=...
TANK_TERMINAL_PASSWORD=...
```

Do not wrap values in quotes in `deploy/dashboard.env`. Compose reads this file
with `format: raw`, so quotes would be passed into the containers as literal
characters.

Start the local stack:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Run database migrations:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile tools run --rm db-migrate
```

Bootstrap the shared auth registry and first admin user:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile tools run --rm auth-bootstrap
```

The bootstrap command creates the core application keys (`kippen`,
`dashboard_kippen`, `dashboard_klauwgezondheid`,
`dashboard_tank_terminal`, `dashboard_moneybird`, and `user_administration`), the core roles
(`admin`, `worker`, `viewer`), and grants the bootstrap admin access to those
apps. If users already exist and
`AUTH_BOOTSTRAP_USERNAME` is empty, it only refreshes the core apps and roles.

Load the lay-curve norm seed after migrations:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile tools run --rm kippen-norms-seed
```

The Kippen migrations create the `flocks` table, require `flock_id` on new
registrations, and split the old combined daily table into
`egg_registrations` and `feed_water_registrations`. Run migrations before
opening the Kippen app after pulling changes.

Run dry runs before writing data:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-uniform-agri python -m data_jobs.uniform_agri.scripts.koe_data --dry-run --include-details --include-milkings --limit 10
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-klauwscore python -m data_jobs.klauwscore.scripts.collect_klauwscore --summary --dry-run
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-tank-terminal python -m data_jobs.tank_terminal.scripts.collect_tank_terminal --summary --dry-run
```

Fill the local database. Run Uniform Agri first, then Klauwscore, because the
dashboard joins klauwbehandelingen to the active cow data. Tank Terminal is
independent and can run after those jobs:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-uniform-agri
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-klauwscore
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-tank-terminal
```

Local routes:

- `http://localhost/`: Flask portal.
- `http://localhost/admin/users`: user administration for portal admins.
- `http://localhost/kippen`: Kippen registratie app.
- `http://localhost/kippen-dashboard`: Kippen Marimo dashboard.
- `http://localhost/klauwgezondheid`: Marimo dashboard.
- `http://localhost/tank-terminal`: Tanken Marimo dashboard.
- `http://localhost/moneybird`: Moneybird Marimo dashboard.
- `http://localhost:8080`: Adminer database editor.

Adminer login for the local stack:

- System: `PostgreSQL`
- Server: `postgres`
- Username: `postgres`
- Password: `postgres`
- Database: `gebroeders_vroege`

Useful local checks:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml ps
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml logs -f traefik portal marimo-kippen-dashboard
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml logs --tail=100 marimo-kippen-dashboard
```

If port `80` is already in use, stop the other service or change the local
override port mapping. Use `http://localhost` for local testing; do not use
`https://localhost` with the local override.

### Production server setup

Production routes:

- `https://app.gebroedersvroege.nl/`: central Flask portal.
- `https://app.gebroedersvroege.nl/admin/users`: user administration for portal
  admins.
- `https://app.gebroedersvroege.nl/kippen`: Kippen registratie app.
- `https://app.gebroedersvroege.nl/kippen-dashboard`: Kippen Marimo dashboard.
- `https://app.gebroedersvroege.nl/klauwgezondheid`: Marimo dashboard.
- `https://app.gebroedersvroege.nl/tank-terminal`: Tanken Marimo dashboard.
- `https://app.gebroedersvroege.nl/moneybird`: Moneybird Marimo dashboard.

Clone the repository somewhere owned by the deploy user, for example:

```bash
cd /opt
sudo git clone git@github.com:vanozi/vroege-data-jobs.git vroege-data-jobs
sudo chown -R "$USER:$USER" /opt/vroege-data-jobs
cd /opt/vroege-data-jobs
```

Create the Compose-level configuration:

```bash
cp .env.example .env
```

Set at least these values in `.env`:

```env
APP_HOST=app.gebroedersvroege.nl
TRAEFIK_ACME_EMAIL=admin@example.nl
POSTGRES_DB=gebroeders_vroege
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
```

Create the application configuration:

```bash
cp deploy/dashboard.env.example deploy/dashboard.env
```

Set at least these values in `deploy/dashboard.env`:

```env
PORTAL_SECRET_KEY=change-me
PORTAL_SESSION_HOURS=12
PORTAL_COOKIE_SECURE=true
PORTAL_DEFAULT_USER_PASSWORD=welkom123
AUTH_BOOTSTRAP_USERNAME=admin
AUTH_BOOTSTRAP_PASSWORD=replace-with-temporary-password
AUTH_BOOTSTRAP_FIRST_NAME=Admin
AUTH_BOOTSTRAP_LAST_NAME=
AUTH_BOOTSTRAP_RESET_PASSWORD=false
KIPPEN_APP_SESSION_HOURS=12
KIPPEN_APP_COOKIE_SECURE=true
DATABASE_URL=postgresql+psycopg://postgres:change-me@postgres:5432/gebroeders_vroege
KLAUWSCORE_USERNAME=...
KLAUWSCORE_PASSWORD=...
UNIFORM_BASE_URL=https://eu.myherdmanagement.com/restapi
UNIFORM_USERNAME=...
UNIFORM_PASSWORD=...
UNIFORM_CLIENT_ID=...
TANK_TERMINAL_BASE_URL=http://82.197.193.195:8080
TANK_TERMINAL_USERNAME=...
TANK_TERMINAL_PASSWORD=...
```

Do not wrap values in quotes in `deploy/dashboard.env`. Compose reads this file
with `format: raw`, so quotes would be passed into the containers as literal
characters.

Validate, migrate, and start the production stack:

```bash
docker compose config --quiet
docker compose up -d postgres
docker compose --profile tools run --rm db-migrate
docker compose --profile tools run --rm auth-bootstrap
docker compose --profile tools run --rm kippen-norms-seed
docker compose up -d --build
```

For shared auth bootstrap, `AUTH_BOOTSTRAP_PASSWORD` is only used to create a
new bootstrap user. It is not logged. If the bootstrap user already exists,
passwords are not reset unless `AUTH_BOOTSTRAP_RESET_PASSWORD=true` is set
explicitly for that run.

`kippen-norms-seed` loads `database/seeds/dekalb_white_norms.csv` into
`flock_lay_curve_norms` with idempotent upserts on `(breed_key, age_weeks)`.

Run production datajobs manually:

```bash
docker compose --profile jobs run --rm datajob-uniform-agri
docker compose --profile jobs run --rm datajob-klauwscore
docker compose --profile jobs run --rm datajob-tank-terminal
```

Useful production checks:

```bash
docker compose ps
docker compose logs -f traefik portal marimo-kippen-dashboard
docker compose logs -f postgres
docker compose logs --tail=100 marimo-kippen-dashboard
```

### Nightly datajobs

For nightly production runs, prefer a host-level scheduler over a cron process
inside a container. The repository includes
[`deploy/run-nightly-datajobs.sh`](deploy/run-nightly-datajobs.sh). It runs
migrations first, then Uniform Agri, Klauwscore, and Tank Terminal.

Make the script executable:

```bash
chmod +x deploy/run-nightly-datajobs.sh
```

Example cron entry:

```cron
30 2 * * * cd /opt/vroege-data-jobs && /bin/sh deploy/run-nightly-datajobs.sh >> /var/log/vroege-datajobs.log 2>&1
```

This keeps scheduling visible on the server, avoids long-running scheduler
logic in the application containers, and makes retries/logging easier to manage
with the host's normal tools.

### Deploy changes

Bring changes to production by committing and pushing locally, then pulling on
the server:

```bash
cd /opt/vroege-data-jobs
git pull
docker compose build
docker compose --profile tools run --rm db-migrate
docker compose up -d --force-recreate
```

For a dashboard-only code or dependency change, rebuilding only Marimo is often
enough:

```bash
docker compose build marimo-kippen-dashboard
docker compose up -d --force-recreate marimo-kippen-dashboard
```

Restart Traefik after label or routing changes:

```bash
docker compose restart traefik
```

### PostgreSQL backup

Create a compressed backup:

```bash
mkdir -p /opt/backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > /opt/backups/vroege-datajobs-$(date +%F).sql.gz
```

Restore only after checking the target database:

```bash
gunzip -c /opt/backups/vroege-datajobs-YYYY-MM-DD.sql.gz | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

### Kippen registratie app

The Kippen registratie app is served by the `kippen-app` service. Production
uses `APP_HOST=app.gebroedersvroege.nl`; Traefik routes `/kippen` on that host
to the app.

Access requires a shared portal session and active `kippen` application access.
The app enforces two roles within the `kippen` application:

| Role | What a user can do |
|---|---|
| `worker` | Daily registration (eggs, water/voer, dead hens, outside-nest rounds, pallet weights), week overview (read-only), registration list pages with edit/delete on own entries only. |
| `admin` | Everything a worker can do, plus: Leeggoed beheren, Koppels beheren, CSV exports, edit/delete any row regardless of who created it. |

A user with both `admin` and `worker` roles gets the admin view. The bootstrap
admin is automatically granted both roles for `kippen`. Grant only `worker` to
farm employees who should do daily registrations but not manage flocks or
packaging configurations.

The header badge shows **Beheerder** or **Medewerker** so users know which view
they are in. Workers who navigate to an admin-only URL see a friendly Dutch 403
page with a link back to the dashboard rather than a bare error.

Useful routes:

- `/kippen/dashboard`: overview after login.
- `/kippen/flocks`: flock management.
- `/kippen/flocks/new`: create a flock.
- `/kippen/eggs/new`: register `1e soort` and `2e soort` eggs.
- `/kippen/feed-water/new`: register daily water in milliliters and feed in
  grams.
- `/kippen/packaging-weights`: manage empty-packaging weight configurations per
  supplier.
- `/kippen/packaging-weights/new`: create a supplier empty-packaging
  configuration.
- `/kippen/pallet-weights/new`: register a weighed egg pallet.
- `/kippen/pallet-weights`: recent pallet weight registrations.
- `/kippen/eggs`: recent egg registrations.
- `/kippen/feed-water`: recent water/feed registrations.
- `/kippen/dead-hens/new`: dead hen registration.
- `/kippen/outside-nest-rounds/new`: outside-nest egg round.
- `/kippen/week`: redirect to the current flock age week.
- `/kippen/week/<flock_week>`: week overview for flock age week N (e.g. `17` for the week the flock is 17w0d–17w6d old).

Flock workflow:

1. Run database migrations before using the Kippen app.
2. Log in to `/kippen`.
3. Open **Koppels beheren**.
4. Create the active flock with a name, date of birth, placement date, and bird
   count.
5. Leave `Einddatum` empty while the flock is still active.
6. Enter egg registrations and water/feed registrations separately.
7. Enter dead-hen registrations and outside-nest rounds as needed.
8. Add empty-packaging configurations before registering pallet weights.
9. Enter pallet weights to calculate average egg weight in grams.

Registrations are only accepted when there is an active flock in the same house
for the registration date. For now the app uses one house, `main`. Future houses
can have overlapping flock dates, but one house cannot have overlapping active
flocks. When a flock leaves the house, set its `Einddatum` from the flock detail
page. Use **Koppel archiveren** only when the flock should no longer be used for
new registrations.

The dashboard and registration pages show the active flock plus bird age in
weeks, days, and total days. Weekly overviews and exports include flock context
and age for each day.

### Kippen dashboard

The Kippen Marimo dashboard is served by the `marimo-kippen-dashboard` service
at `/kippen-dashboard`. Access requires a shared portal session and active
`dashboard_kippen` application access. The bootstrap admin receives the
`viewer` role on this dashboard by default.

The dashboard is read-only and compares flock performance against seeded
lay-curve norms from `flock_lay_curve_norms`.

To add a new norm CSV for another breed:

1. Add the CSV under `database/seeds/`.
2. Run `python -m database.seeds.load_lay_curve_norms --csv path/to/file.csv`.
3. Set `flocks.breed` to a value that normalizes to the CSV `breed_key`, or add
   an alias in `dashboard/kippen_transforms.py`.

Egg pallet weight workflow:

1. Open **Leeggoed beheren**.
2. Create a configuration for the eierhandel/leverancier.
3. Enter the empty-packaging weight in kilograms.
4. Leave `Eieren per pallet` at `10800` unless that supplier uses a different
   pallet setup.
5. Set the active date range for that configuration.
6. Open **Palletgewicht registreren**.
7. Select the date and active empty-packaging configuration.
8. Enter the weighed pallet weight including empty packaging.

The app calculates average egg weight in grams with:

```text
(palletgewicht kg - leeggoed kg) / eieren per pallet * 1000
```

Pallet registrations copy the supplier name, empty-packaging weight, and
egg-count-per-pallet from the selected configuration. This keeps historical
registrations stable when a supplier's empty-packaging configuration changes
later. Weekly overviews show the average egg weight per day. When multiple
pallets are registered on the same day, the day shows the average of those
pallet egg-weight values. The weekly total row shows the average across all
pallet registrations in that week.

Weekly exports:

- `/kippen/week/<flock_week>/export.xlsx`: Excel laying calendar export for flock age week N.
- `/kippen/week/<flock_week>/export.pdf`: PDF laying calendar export for flock age week N.

Raw CSV exports:

- `/kippen/export/eggs.csv`: egg registrations.
- `/kippen/export/feed-water.csv`: water/feed registrations.
- `/kippen/export/dead-hens.csv`: dead hen registrations.
- `/kippen/export/outside-nest-rounds.csv`: outside-nest egg rounds.
- `/kippen/export/pallet-weights.csv`: pallet weight registrations including
  calculated egg weight.
- `/kippen/export/packaging-weights.csv`: supplier empty-packaging
  configurations.

Raw CSV exports include `flock_id`, `flock_name`, `flock_date_of_birth`,
`flock_age_weeks`, and `flock_age_days`.

Example (flock age week 19):

```text
https://app.gebroedersvroege.nl/kippen/week/19/export.xlsx
```

Backups are database-level. The PostgreSQL backup command above includes the
Kippen tables (`flocks`, `egg_registrations`, `feed_water_registrations`,
`dead_hen_registrations`, `outside_nest_egg_rounds`,
`egg_packaging_weight_configs`, and `egg_pallet_weight_registrations`). For
operational exports that can be opened directly in Excel, use the weekly Excel
export and raw CSV links in the app.

### Uniform Agri

The Uniform Agri job authenticates with Uniform Agri, collects herd
registration data, skips excluded calf records, and persists active cows. It can
optionally fetch actual-tab cow details and milk recordings per animal.

Required configuration:

```env
UNIFORM_BASE_URL=https://eu.myherdmanagement.com/restapi
UNIFORM_USERNAME=...
UNIFORM_PASSWORD=...
UNIFORM_CLIENT_ID=...
```

Optional configuration:

```env
UNIFORM_HERD_ID=c670836f-7732-43a1-ac5a-70c4f63435f4
UNIFORM_ACCESS_TOKEN=
UNIFORM_REQUEST_TIMEOUT_SECONDS=60
UNIFORM_MAX_RETRIES=1
```

If `UNIFORM_HERD_ID` is not set, the default herd id is
`c670836f-7732-43a1-ac5a-70c4f63435f4`. A refreshed runtime token is kept in
memory and is not written back to `.env`.

Recommended commands:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.uniform_agri.scripts.koe_data --dry-run
.\.venv\Scripts\python.exe -m data_jobs.uniform_agri.scripts.koe_data --dry-run --include-details --limit 5
.\.venv\Scripts\python.exe -m data_jobs.uniform_agri.scripts.koe_data --dry-run --include-details --include-milkings --limit 5
.\.venv\Scripts\python.exe -m data_jobs.uniform_agri.scripts.koe_data --include-details
```

Useful options:

- `--herd-id HERD_ID`: override the configured/default herd id for one run.
- `--date YYYY-MM-DD`: collect herd registration for a specific date.
- `--include-details`: fetch and persist actual-tab cow details.
- `--include-milkings`: fetch and persist milk recordings.
- `--dry-run`: collect and log write counts without database writes.
- `--continue-on-animal-error` / `--no-continue-on-animal-error`: control
  per-animal failure handling for details and milk recordings.
- `--limit N`: process only the first `N` cows after filtering.

The command prints summary counts such as saved cows, marked missing cows,
detail failures, milking failures, and cows without milk recordings.

## Database migrations

Alembic is configured under [`database/`](database/) and is the only supported
way to create or evolve the database schema.

Install dependencies first, then run migrations from the repository root.

Recommended PostgreSQL connection format:

```env
DATABASE_URL=postgresql+psycopg://postgres:change-me@localhost:5432/gebroeders-vroege
```

Create a new revision:

```powershell
alembic -c database/alembic.ini revision --autogenerate -m "describe change"
```

Apply all migrations:

```powershell
alembic -c database/alembic.ini upgrade head
```

Roll back one revision:

```powershell
alembic -c database/alembic.ini downgrade -1
```

Show the current database revision:

```powershell
alembic -c database/alembic.ini current
```

For a fresh database, the initial schema is included in
`database/migrations/versions/20260507_01_initial_schema.py`.
