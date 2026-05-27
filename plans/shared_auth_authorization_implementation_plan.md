# Implementation Plan: Shared Authentication and Authorization

## Goal

Build a shared authentication and authorization foundation for multiple apps in
this project.

The first target applications are:

- Kippen registration app.
- Dashboard portal.
- Marimo dashboards behind the portal/ForwardAuth flow.

This plan is intentionally limited to the shared auth flow and data model. It
does not implement detailed Kippen-specific permissions beyond proving that
application access and per-application roles can be checked.

## Current State

- The dashboard portal has its own Flask login/session flow.
- The Kippen app has its own Flask login/session flow.
- Marimo dashboards are protected through Traefik ForwardAuth against the
  dashboard portal.
- Authentication is currently configured through environment variables and
  password hashes.
- There is no shared user table.
- There is no shared application-access model.
- There is no shared per-application role model.

Relevant files:

- `dashboard_portal/`
- `kippen_app/`
- `database/models/`
- `database/repositories/`
- `database/migrations/versions/`
- `tests/kippen_app/`

## Proposed Model

Use shared users and application access with a role scoped to each application.

This gives enough control for the current project without immediately building a
fine-grained permission system.

### `users`

Shared identity table.

Fields:

- `id`
- `last_name`
- `email_address` 
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

Registered applications that can be protected by shared auth.

Fields:

- `id`
- `key`
- `name`
- `description`
- `is_active`
- `created_at`
- `updated_at`

Example application keys:

- `portal`
- `kippen`
- `klauwgezondheid`
- `tank-terminal`

Constraints:

- `key` is required.
- `key` is unique.
- inactive applications cannot be accessed.

### `user_application_access`

Access and role assignment for one user in one application.

Fields:

- `id`
- `user_id`
- `application_id`
- `role`
- `is_active`
- `created_at`
- `updated_at`

Suggested first roles:

- `admin`
- `worker`
- `viewer`

Constraints:

- One active access row per user/application pair.
- `role` is required.
- inactive access means the user cannot access that application.

## Authorization Rules

Authentication answers:

```text
Is this username/password valid for an active user?
```

Application access answers:

```text
Can this active user access application X?
```

Role authorization answers:

```text
Does this user have role Y, or one of roles A/B/C, in application X?
```

The shared layer should not decide every app-specific business rule. It should
provide simple helpers that apps can call.

Examples:

- Kippen worker can access daily registration forms.
- Kippen admin can access Kippen admin screens.
- Portal viewer can access allowed dashboard links.
- Portal/ForwardAuth can deny a Marimo dashboard when the user has no access to
  that dashboard application key.

## Repository and Service Layer

Add a shared auth repository/service area instead of putting this only inside
Kippen.

Suggested files:

- `database/models/auth.py`
- `database/repositories/auth_repository.py`
- `auth_service/` or `shared_auth/`

Repository methods:

- `create_user`
- `update_user`
- `get_user_by_id`
- `get_user_by_username`
- `set_user_active`
- `set_user_password_hash`
- `create_application`
- `get_application_by_key`
- `list_applications`
- `grant_application_access`
- `update_application_role`
- `revoke_application_access`
- `get_user_application_access`
- `list_user_applications`

Service/helper methods:

- `verify_user_password`
- `authenticate_user`
- `user_can_access_application`
- `user_has_application_role`
- `require_application_access`
- `require_application_role`

## Session Model

Keep Flask sessions simple.

After login, store:

- `user_id`
- `email_address`

Do not store passwords or password hashes in the session.

Each app should load/check the user's access and role for its own application
key.

For Kippen:

```text
application_key = "kippen"
```

For the dashboard portal:

```text
application_key = "portal"
```

For Marimo dashboards behind the portal:

```text
application_key = "dashboard_klauwgezondheid"
application_key = "dashboard_tank_terminal"
```

## Bootstrap Strategy

The system needs a way to create the first admin user.

Suggested approach:

1. Keep the existing environment variables temporarily:
   - `PORTAL_ADMIN_USERNAME`
   - `PORTAL_ADMIN_PASSWORD_HASH`
   - `KIPPEN_APP_ADMIN_USERNAME`
   - `KIPPEN_APP_ADMIN_PASSWORD_HASH`
2. Add a bootstrap command or migration-safe startup helper that creates:
   - a shared admin user if no users exist.
   - core applications if missing.
   - admin access rows for that first user.
3. Prefer an explicit CLI/admin command over hidden writes on every request.

Possible command:

```powershell
.\.venv\Scripts\python.exe -m shared_auth.scripts.bootstrap_admin
```

Docker equivalent:

```powershell
docker compose --profile tools run --rm auth-bootstrap
```

## Flask Integration

### Kippen App

Replace Kippen-only static credential verification with shared auth.

Add decorators/helpers:

- `login_required`
- `application_access_required("kippen")`
- `application_role_required("kippen", {"admin"})`

First integration scope:

- Daily registration routes require access to `kippen`.
- Kippen admin routes require `admin` role in `kippen`.
- Detailed Kippen permissions can be refined later.

### Dashboard Portal

Use shared auth for portal login.

Portal routes:

- `/login`: authenticates shared user.
- `/auth/verify`: verifies session and application access.

For portal dashboard links:

- Only show dashboards for which the user has access.
- Check app key mapped to each dashboard entry.

### Marimo Dashboards

Do not redesign Marimo app internals in the first version.

Use the portal/ForwardAuth layer:

- map `/klauwgezondheid` to application key `klauwgezondheid`.
- map `/tank-terminal` to application key `tank-terminal`.
- deny access when the logged-in user lacks access to that dashboard key.

## Admin UI Scope

This feature can include a minimal shared user admin UI, but only if kept small.

Recommended first admin screens:

- user list
- create user with default password
- edit display name / active status
- reset password
- manage application access and role per user

Keep the user management UI in one place, preferably the dashboard portal, so it
can administer access across all applications.

## Security Requirements

- Store passwords only as Werkzeug password hashes.
- Never store or log raw passwords.
- Reject inactive users at login.
- Reject inactive applications during access checks.
- Reject inactive access rows during access checks.
- Use POST for password reset and access changes.
- Keep session cookies HTTP-only.
- Keep existing secure-cookie behavior configurable for local vs production.

## Tests

Add tests for:

- user creation.
- username uniqueness.
- password verification.
- inactive user login rejection.
- application creation and lookup by key.
- granting and revoking application access.
- per-application role lookup.
- user with access to one app denied for another app.
- Kippen app login/access through shared auth.
- Kippen admin-only route denial for non-admin user.
- Portal dashboard link filtering by application access.
- ForwardAuth allows/denies dashboard routes based on application access.

Likely files:

- `tests/database/test_auth_repository.py`
- `tests/shared_auth/test_auth_service.py`
- `tests/kippen_app/test_auth.py`
- `tests/dashboard_portal/test_auth.py`

## README Updates

Document:

- shared auth model.
- how to bootstrap the first admin.
- application keys.
- role meanings.
- how to grant app access.
- local and production auth setup.

## Implementation Phases

### Phase 1: Data Model and Repository

- Add `User` model.
- Add `Application` model.
- Add `UserApplicationAccess` model.
- Add Alembic migration.
- Add repository methods.
- Add repository tests.

### Phase 2: Shared Auth Service

- Add password verification helpers.
- Add login/authenticate helper.
- Add application access checks.
- Add per-application role checks.
- Add service tests.

### Phase 3: Bootstrap

- Add bootstrap script or command for first admin user.
- Seed core application keys.
- Grant first admin access to core apps.
- Add README instructions.
- Add tests where practical.

### Phase 4: Kippen Integration

- Switch Kippen login to shared auth.
- Store shared user session.
- Require `kippen` application access.
- Protect Kippen admin routes with `admin` role.
- Keep daily operational routes available to users with `kippen` access.
- Add route tests.

### Phase 5: Portal and Dashboard Integration

- Switch portal login to shared auth.
- Filter dashboard tiles by application access.
- Update ForwardAuth to check dashboard application keys.
- Add route tests for portal and dashboard access.

### Phase 6: Admin User Management UI

- Add admin-only user list.
- Add create user form with default password.
- Add edit user form.
- Add password reset action.
- Add application access and role management.
- Add route tests.

### Phase 7: Documentation and Verification

- Update README.
- Run `ruff format`.
- Run `ruff check --fix`.
- Run `pytest`.
- Run Docker build and migrations locally.
- Verify Kippen and portal login flows with Playwright.
- Verify dashboard access filtering with Playwright.

## Open Decisions

- Should users have one role per application, or multiple roles per
  application?
- Should the first admin be created by a CLI command, migration seed, or manual
  database insert?
- Should user management live in the dashboard portal, Kippen, or a separate
  admin app?
- Should roles be fixed strings in code, or stored in a `roles` table?
- Should application access be enough for Marimo dashboards, or do dashboards
  need internal role awareness later?

## Recommendation

Start with:

- one role per user/application.
- fixed role strings: `admin`, `worker`, `viewer`.
- user management in the dashboard portal.
- explicit bootstrap command for the first admin.
- portal/ForwardAuth as the gatekeeper for Marimo dashboards.

This keeps the first implementation practical while preserving room for finer
permissions later.
