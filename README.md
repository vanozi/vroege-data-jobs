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

## Dashboard portal

The dashboard portal is a small Flask app in [`dashboard_portal/`](dashboard_portal/).
It is intended as the authenticated homepage for Marimo dashboards. The root
route `/` shows dashboard links after login; without a session it redirects to
`/login`.

Current portal routes:

- `/`: dashboard overview, protected by session.
- `/login`: login page.
- `/logout`: logout endpoint.
- `/auth/verify`: Traefik ForwardAuth endpoint.
- `/healthz`: healthcheck.

The first dashboard link is:

```text
/klauwgezondheid
```

That route is intended to be served by the Marimo klauwgezondheid dashboard
behind Traefik.

Create a password hash for `PORTAL_ADMIN_PASSWORD_HASH`:

```powershell
.\.venv\Scripts\python.exe -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('replace-with-password'))"
```

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
PORTAL_ADMIN_USERNAME=admin
PORTAL_ADMIN_PASSWORD_HASH=...
PORTAL_SESSION_HOURS=12
PORTAL_COOKIE_SECURE=false
```

Dashboard links come from `dashboard_portal.registry`. By default the portal
shows `Klauwgezondheid` at `/klauwgezondheid`. You can override the visible
dashboards with `PORTAL_DASHBOARDS_JSON`:

```env
PORTAL_DASHBOARDS_JSON=[{"name":"Klauwgezondheid","description":"Mortellaro en klauwgezondheid van de actieve koppel.","url":"/klauwgezondheid","status":"Productie"}]
```

### Docker Compose dashboards

The repository includes a standalone [`docker-compose.yml`](docker-compose.yml)
with its own Traefik proxy, Flask portal, and Marimo klauwgezondheid dashboard.
It does not depend on another Compose project.

The portal and Marimo services use separate Dockerfiles and dependency files:

- [`docker/portal/Dockerfile`](docker/portal/Dockerfile): Flask portal and
  Gunicorn only.
- [`docker/marimo/Dockerfile`](docker/marimo/Dockerfile): Marimo dashboard and
  dashboard data dependencies.
- [`docker/database/Dockerfile`](docker/database/Dockerfile): Alembic migration
  runner for the `database/` package.
- [`docker/datajobs/Dockerfile`](docker/datajobs/Dockerfile): Playwright-based
  datajob runner for Klauwscore and Uniform Agri.

Required deployment configuration:

Copy `.env.example` to `.env` for Compose-level settings:

```env
DASHBOARD_HOST=dashboards.gebroedersvroege.nl
TRAEFIK_ACME_EMAIL=admin@example.nl
```

Copy `deploy/dashboard.env.example` to `deploy/dashboard.env` for application
settings:

```env
PORTAL_SECRET_KEY=...
PORTAL_ADMIN_USERNAME=admin
PORTAL_ADMIN_PASSWORD_HASH=...
PORTAL_SESSION_HOURS=12
PORTAL_COOKIE_SECURE=true
DATABASE_URL=postgresql+psycopg://...
```

The Compose stack includes a PostgreSQL service named `postgres`. For services
inside this Compose network, use:

```env
DATABASE_URL=postgresql+psycopg://postgres:change-me@postgres:5432/gebroeders_vroege
```

For local Docker with PostgreSQL running outside Compose on the host machine,
use `host.docker.internal` as database host in `DATABASE_URL`. Inside a
container, `localhost` means the container itself, not your Windows host.

Keep `PORTAL_ADMIN_PASSWORD_HASH` in `deploy/dashboard.env`, not in the Compose
`.env` file. Werkzeug hashes can contain `$`, and Compose treats `$...` as
variable interpolation in `.env`. The Compose services read
`deploy/dashboard.env` with `env_file` format `raw` so password hashes are
passed to the containers unchanged.

Start the dashboard stack:

```powershell
docker compose up -d --build
```

Run database migrations against the Compose PostgreSQL service:

```powershell
docker compose --profile tools run --rm db-migrate
```

Run datajobs manually:

```powershell
docker compose --profile jobs run --rm datajob-uniform-agri
docker compose --profile jobs run --rm datajob-klauwscore
```

The default Uniform Agri job collects cows, details, and milkings. The default
Klauwscore job collects the stallijst and persists klauwbehandelingen.

Routes:

- `https://dashboards.gebroedersvroege.nl/`: Flask portal.
- `https://dashboards.gebroedersvroege.nl/klauwgezondheid`: Marimo dashboard.

Traefik protects `/klauwgezondheid` with the portal `/auth/verify` ForwardAuth
endpoint. Direct access to the Marimo route without a valid portal session
returns unauthorized. The Marimo web app manifest at
`/klauwgezondheid/manifest.json` is routed without ForwardAuth because browsers
may fetch manifests without session cookies; it does not expose dashboard data.

For local testing, use the HTTP-only override:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Run local database migrations:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile tools run --rm db-migrate
```

Run local datajobs manually:

```powershell
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-uniform-agri
docker compose --env-file .env.local.example -f docker-compose.yml -f docker-compose.local.yml --profile jobs run --rm datajob-klauwscore
```

For nightly production runs, prefer a host-level scheduler over a cron process
inside a container. A host cron or systemd timer can run:

```bash
deploy/run-nightly-datajobs.sh
```

That script runs migrations first, then Uniform Agri, then Klauwscore. This
keeps scheduling visible in the server, avoids long-running scheduler logic in
the application containers, and makes retries/logging easier to manage with the
host's normal tools.

Local routes:

- `http://dashboards.localhost/`: Flask portal.
- `http://dashboards.localhost/klauwgezondheid`: Marimo dashboard.
- `http://localhost/`: fallback Flask portal route.
- `http://localhost/klauwgezondheid`: fallback Marimo dashboard route.

The local override disables TLS and Let's Encrypt, uses port `80`, and sets
`PORTAL_COOKIE_SECURE=false`. If another local service already uses port `80`,
stop it first or change the local override port mapping. If
`dashboards.localhost` does not resolve on your machine, use `localhost` or add
`127.0.0.1 dashboards.localhost` to your hosts file.

### Uniform Agri

The Uniform Agri job authenticates with Uniform Agri, collects herd
registration data, skips excluded calf records, and persists active cows. It can
optionally fetch actual-tab cow details and milk recordings per animal.

Required configuration:

```env
UNIFORM_BASE_URL=...
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
