# Implementation Plan: Central App Portal Authentication and Authorization

## Goal

Build one central portal for all Gebroeders Vroege applications and dashboards.

Production target:

```text
https://app.gebroedersvroege.nl
```

This replaces the current `dashboards.gebroedersvroege.nl` concept. Users log in
once at:

```text
/login
```

After login, the root route shows the applications and dashboards that the user
may access:

```text
/
```

Admin users see an additional application tile, for example **User
Administration**, where they can manage users, application access, and
authorization.

## Scope

This plan is about shared authentication and authorization for all applications.

It is split into two broad stages:

1. Build the shared authentication/authorization structure first.
2. Refactor the current portal, Kippen app, and dashboard protection to use one
   general login and one root application overview.

This plan does not implement detailed Kippen business permissions yet. It only
creates the shared access/role model that Kippen, dashboards, and future apps
can use.

## Current State

- The dashboard portal has its own Flask login/session flow.
- The Kippen app has its own Flask login/session flow.
- Marimo dashboards are protected through Traefik ForwardAuth against the
  dashboard portal.
- Authentication is currently configured through environment variables and
  password hashes.
- The current production portal host is dashboard-focused.
- There is no shared user table.
- There is no shared application table.
- There is no shared per-application access or role model.

Relevant files:

- `dashboard_portal/`
- `kippen_app/`
- `database/models/`
- `database/repositories/`
- `database/migrations/versions/`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `deploy/dashboard.env.example`
- `tests/dashboard_portal/`
- `tests/kippen_app/`

## Target Portal Behavior

### Public Routes

- `GET /login`
- `POST /login`
- `GET /healthz`

### Authenticated Routes

- `GET /`
  - Shows app/dashboard tiles the logged-in user has access to.
- `POST /logout`
  - Clears the shared session.

### Admin Routes

Admin users see a **User Administration** application tile on `/`.

Suggested route group:

- `GET /admin/users`
- `GET /admin/users/new`
- `POST /admin/users/new`
- `GET /admin/users/<id>/edit`
- `POST /admin/users/<id>/edit`
- `POST /admin/users/<id>/reset-password`
- `GET /admin/applications`
- `GET /admin/users/<id>/access`
- `POST /admin/users/<id>/access`

The exact route names can change during implementation, but all user and access
management should live under the central portal, not inside Kippen.

## Proposed Data Model

Use shared users, application access, and roles scoped to each application.

This is granular enough for the current project while avoiding a full
permission matrix too early.

### `users`

Shared identity table.

Fields:

- `id`
- `email_address`
- `first_name`
- `last_name`
- `password_hash`
- `is_active`
- `created_at`
- `updated_at`

Constraints:

- `email_address` is required.
- `email_address` is unique.
- `password_hash` is required.
- inactive users cannot log in.

### `applications`

Applications and dashboards that can appear on the portal root page.

Fields:

- `id`
- `key`
- `name`
- `description`
- `url`
- `category`
- `is_active`
- `display_order`
- `created_at`
- `updated_at`

Example application keys:

- `kippen`
- `dashboard_klauwgezondheid`
- `dashboard_tank_terminal`
- `user_administration`

Example categories:

- `app`
- `dashboard`
- `admin`

Constraints:

- `key` is required.
- `key` is unique.
- `name` is required.
- `url` is required.
- inactive applications do not show on `/` and cannot be accessed.

### `roles`

Roles are stored as data, not fixed strings in code.

Fields:

- `id`
- `key`
- `name`
- `description`
- `is_active`
- `created_at`
- `updated_at`

Initial role keys:

- `admin`
- `worker`
- `viewer`

Constraints:

- `key` is required.
- `key` is unique.
- inactive roles cannot be granted for new access.

### `user_application_access`

Access assignment for one user in one application.

Fields:

- `id`
- `user_id`
- `application_id`
- `is_active`
- `created_at`
- `updated_at`

Constraints:

- One access row per user/application pair.
- inactive access means the user cannot access that application.

### `user_application_roles`

Role assignments for one user/application access row.

Fields:

- `id`
- `user_application_access_id`
- `role_id`
- `created_at`
- `updated_at`

Constraints:

- One role can be assigned once per access row.
- A user can have multiple roles within the same application.
- Removing all roles can leave application access intact, but app-level
  authorization checks should deny role-specific actions.

## Authorization Rules

Authentication answers:

```text
Is this email/password valid for an active user?
```

Application access answers:

```text
Can this active user access application X?
```

Role authorization answers:

```text
Does this user have role Y, or one of roles A/B/C, in application X?
```

The shared layer should expose simple checks. Each app can later interpret roles
more specifically.

A user can have multiple roles in one application. For example, a user can be
both `admin` and `worker` in `kippen`.

Examples:

- A user with `kippen` access can open the Kippen app.
- A user with `dashboard_klauwgezondheid` access can open that dashboard.
- A user with `user_administration` role `admin` can manage users.
- A user with `kippen` role `worker` can do daily Kippen registrations.
- A user with both `kippen` roles `admin` and `worker` can do daily work and
  manage Kippen admin screens.
- A user without `dashboard_tank_terminal` access cannot open that dashboard.

## Application Registry

Applications should be stored in the database, but initial core applications can
be bootstrapped.

Initial records:

```text
key: kippen
name: Kippen
url: /kippen
category: app

key: dashboard_klauwgezondheid
name: Klauwgezondheid
url: /klauwgezondheid
category: dashboard

key: dashboard_tank_terminal
name: Tanken
url: /tank-terminal
category: dashboard

key: user_administration
name: User Administration
url: /admin/users
category: admin
```

The old `PORTAL_DASHBOARDS_JSON` can be removed or deprecated once the
database-backed application registry is in place.

Initial role records:

```text
key: admin
name: Admin

key: worker
name: Worker

key: viewer
name: Viewer
```

## Repository and Service Layer

Add shared auth model/repository/service code outside of Kippen.

Suggested files:

- `database/models/auth.py`
- `database/repositories/auth_repository.py`
- `shared_auth/`

Repository methods:

- `create_user`
- `update_user`
- `get_user_by_id`
- `get_user_by_email`
- `list_users`
- `set_user_active`
- `set_user_password_hash`
- `create_application`
- `update_application`
- `get_application_by_key`
- `list_applications`
- `create_role`
- `get_role_by_key`
- `list_roles`
- `grant_application_access`
- `update_application_access`
- `revoke_application_access`
- `get_user_application_access`
- `grant_application_role`
- `revoke_application_role`
- `list_user_application_roles`
- `list_user_applications`

Service/helper methods:

- `hash_password`
- `verify_user_password`
- `authenticate_user`
- `user_can_access_application`
- `user_has_application_role`
- `user_has_any_application_role`
- `list_accessible_applications`
- `require_application_access`
- `require_application_role`

## Shared Session Model

Keep Flask sessions simple.

After login, store:

- `user_id`
- `email_address`
- optionally `display_name`

Do not store passwords or password hashes in the session.

All portal and application access checks should reload the user/access from the
database.

## Host and Routing Model

Production should move to:

```text
APP_HOST=app.gebroedersvroege.nl
```

Routes under that host:

- `/`: central app overview.
- `/login`: central login.
- `/logout`: central logout.
- `/kippen`: Kippen app.
- `/klauwgezondheid`: Marimo klauwgezondheid dashboard.
- `/tank-terminal`: Marimo tank terminal dashboard.
- `/admin/users`: user administration.

Traefik should route all of these under `APP_HOST`.

The old `DASHBOARD_HOST=dashboards.gebroedersvroege.nl` should be removed
immediately. Do not keep a temporary redirect.

Future applications should use paths under the same `APP_HOST`. Do not add
separate application subdomains in the first version. For example, Kippen stays
under:

```text
https://app.gebroedersvroege.nl/kippen
```

## Portal Integration

The current `dashboard_portal/` should become the central app portal.

Responsibilities:

- render `/login`.
- authenticate users through shared auth.
- store shared login session.
- render `/` with only applications the user can access.
- expose `/auth/verify` for Traefik ForwardAuth.
- host user administration for admin users.

`/auth/verify` should:

1. Verify the session user exists and is active.
2. Determine which application key matches the requested path.
3. Check the user has active access to that application.
4. Return authorized or unauthorized.

Path-to-application mapping examples:

```text
/kippen -> kippen
/klauwgezondheid -> dashboard_klauwgezondheid
/tank-terminal -> dashboard_tank_terminal
/admin/users -> user_administration
```

## Kippen Integration

Kippen should stop owning the primary login flow.

Target behavior:

- User authenticates at `/login` on the central portal.
- User opens `/kippen` from the portal root.
- Kippen checks the shared session and requires access to `kippen`.
- Kippen can still apply app-specific role checks internally.

First integration scope:

- Any Kippen access requires active `kippen` application access.
- Kippen admin routes require role `admin` for `kippen`.
- Daily registration routes can allow role `worker` or `admin`.
- Existing Kippen-specific login page can be removed or redirected to `/login`.

## Marimo Dashboard Integration

Do not redesign Marimo dashboard internals in the first version.

Use Traefik ForwardAuth through the central portal:

- `/klauwgezondheid` requires `dashboard_klauwgezondheid` access.
- `/tank-terminal` requires `dashboard_tank_terminal` access.

If later a Marimo dashboard needs internal role awareness, it can read headers
from ForwardAuth or call shared auth helpers, but that is not part of the first
version.

## User Administration Application

This is an admin-only application shown on `/` only when the user has access to
`user_administration` with role `admin`.

First screens:

- user list.
- create user with default password.
- edit user name/email/active status.
- reset password.
- manage application access and role per user.

No public registration page should exist.

## Bootstrap Strategy

The system needs a safe first-admin creation path.

Recommended approach:

1. Add an explicit bootstrap command.
2. The command creates core applications when missing.
3. The command creates core roles when missing.
4. The command creates the first admin user when no users exist.
5. The command grants first admin access to:
   - `user_administration` with role `admin`.
   - `kippen` with roles `admin` and `worker`.
   - dashboard apps with role `viewer`.

Possible local command:

```powershell
.\.venv\Scripts\python.exe -m shared_auth.scripts.bootstrap_admin
```

Possible Docker command:

```powershell
docker compose --profile tools run --rm auth-bootstrap
```

Both the local CLI command and Docker tool service should be supported.

Temporary environment variables can be used for bootstrap only:

```env
AUTH_BOOTSTRAP_EMAIL=...
AUTH_BOOTSTRAP_PASSWORD=...
AUTH_BOOTSTRAP_FIRST_NAME=...
AUTH_BOOTSTRAP_LAST_NAME=...
```

## Security Requirements

- Store passwords only as Werkzeug password hashes.
- Never store or log raw passwords.
- Reject inactive users at login.
- Reject inactive applications during access checks.
- Reject inactive access rows during access checks.
- Use POST for password reset and access changes.
- Keep session cookies HTTP-only.
- Keep secure-cookie behavior configurable for local vs production.
- Prefer one central session cookie for `app.gebroedersvroege.nl`.

## Tests

Add tests for:

- user creation.
- unique email addresses.
- password hashing and verification.
- inactive user login rejection.
- application creation and lookup by key.
- role creation and lookup by key.
- user with access to one application denied for another application.
- assigning multiple roles for one user/application.
- role lookup per application.
- accessible application list for the root portal page.
- admin user can see User Administration tile.
- normal user cannot see User Administration tile.
- ForwardAuth allows/denies dashboard routes based on application access.
- Kippen access requires shared session and `kippen` application access.
- Kippen role checks distinguish `admin` and `worker`.

Likely files:

- `tests/database/test_auth_repository.py`
- `tests/shared_auth/test_auth_service.py`
- `tests/dashboard_portal/test_auth.py`
- `tests/dashboard_portal/test_routes.py`
- `tests/kippen_app/test_auth.py`
- `tests/kippen_app/test_routes.py`

## README Updates

Document:

- central app host: `app.gebroedersvroege.nl`.
- local app portal route.
- shared auth model.
- how to bootstrap the first admin.
- application keys.
- role table and role meanings.
- how to grant app access.
- how to grant multiple roles in one app.
- how Kippen and dashboards are protected.
- removal of the old dashboard host.

## Implementation Phases

### Phase 1: Shared Auth Data Model

- Add `User` model.
- Add `Application` model.
- Add `UserApplicationAccess` model.
- Add `Role` model.
- Add `UserApplicationRole` model.
- Add Alembic migration.
- Add repository methods.
- Add repository tests.

### Phase 2: Shared Auth Service

- Add password hashing and verification helpers.
- Add authentication helper.
- Add application access checks.
- Add per-application role checks.
- Add accessible application listing.
- Add service tests.

### Phase 3: Bootstrap and Core Applications

- Add bootstrap command for first admin user.
- Seed core application keys.
- Seed core roles.
- Grant first admin access to core apps.
- Add Docker tool service.
- Add README instructions.
- Add tests where practical.

### Phase 4: Central Portal Refactor

- Refactor `dashboard_portal/` into the central app portal.
- Move login to shared auth.
- Render `/` from database-backed application access.
- Add User Administration tile for admin users.
- Keep `/auth/verify`, but make it application-aware.
- Add portal route tests.

### Phase 5: Routing and Host Refactor

- Replace `DASHBOARD_HOST` with `APP_HOST`.
- Route portal, Kippen, and dashboards under `app.gebroedersvroege.nl`.
- Update local override routes.
- Remove old dashboard host routing; do not add redirect.
- Keep all apps under `APP_HOST` path prefixes, including `/kippen`.
- Update `.env.example` and `deploy/dashboard.env.example`.
- Add Docker Compose validation.

### Phase 6: Kippen Integration

- Remove or redirect Kippen-specific login to `/login`.
- Require shared session for Kippen.
- Require `kippen` application access.
- Restrict Kippen admin routes to role `admin`.
- Allow daily registration routes for roles `worker` and `admin`.
- Add route tests.

### Phase 7: Marimo Dashboard Integration

- Map dashboard paths to application keys.
- Enforce dashboard access in ForwardAuth.
- Filter root portal dashboard tiles by access.
- Add ForwardAuth route tests.

### Phase 8: User Administration UI

- Add admin-only user list.
- Add create user form with default password.
- Add edit user form.
- Add password reset action.
- Add application access and role management.
- Add route tests.

### Phase 9: Documentation and Verification

- Update README.
- Run `ruff format`.
- Run `ruff check --fix`.
- Run `pytest`.
- Run Docker build and migrations locally.
- Verify central login and root app overview with Playwright.
- Verify Kippen access from the portal.
- Verify dashboard access filtering with Playwright.
- Verify normal user cannot open User Administration.

## Decisions

- Users can have multiple roles in one application.
- Roles are stored in a separate `roles` table.
- Remove `dashboards.gebroedersvroege.nl` immediately. Do not add a temporary
  redirect.
- Keep all applications under `app.gebroedersvroege.nl` path prefixes. Kippen
  stays under `/kippen`.
- Provide both a local CLI bootstrap command and a Docker tool service for
  first-admin bootstrap.

## Recommendation

Start with:

- multiple roles per user/application.
- database-backed roles seeded with `admin`, `worker`, and `viewer`.
- central portal hosted at `app.gebroedersvroege.nl`.
- user management in the central portal as the `user_administration`
  application.
- explicit CLI and Docker bootstrap paths for the first admin.
- portal/ForwardAuth as the gatekeeper for Marimo dashboards.
- Kippen using the shared session instead of its own login.

This keeps the first implementation practical while preserving room for finer
permissions and future applications later.
