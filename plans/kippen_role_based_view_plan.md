# Implementation Plan: Role-Aware Kippen UI for Admin vs Worker

## Goal

Give the Kippen app a role-aware presentation layer on top of the existing
shared-auth role model. A user with the `kippen` `admin` role keeps the full
view they have today. A user with only the `kippen` `worker` role sees a
trimmed view focused on daily registration, the week overview, and the
history of past registrations. `Leeggoed beheren` (packaging weights) and
`Koppels beheren` (flocks) must be admin-only — not just blocked at the
route, but hidden from the UI for workers. Workers may edit and delete
**their own** registrations only.

## Current State

Route-level enforcement is already in place in
[kippen_app/app.py](kippen_app/app.py):

- `KIPPEN_ADMIN_PREFIXES` blocks `/kippen/flocks`, `/kippen/packaging-weights`,
  `/kippen/week`, `/kippen/export` for non-admins (403).
- `KIPPEN_WORKER_PREFIXES` allows `/kippen/eggs`, `/kippen/feed-water`,
  `/kippen/dead-hens`, `/kippen/outside-nest-rounds`, `/kippen/pallet-weights`
  for both admin and worker.
- Enforcement uses [SharedAuthService.user_has_application_role](shared_auth/service.py#L95)
  and `user_has_any_application_role` against the `kippen` application key.

Ownership data already exists on the registration models: `created_by`
(eggs, feed/water, pallet weights) and `registered_by` (dead hens,
outside-nest rounds) are populated from `_current_username()` at create
time. They are plain strings, not user FKs.

What is missing today:

- The templates render the **same UI for everybody**. A worker who lands on
  `/kippen/dashboard` sees buttons for `Leeggoed beheren`, `Koppels beheren`,
  all CSV export buttons, and the active flock pill links to admin-only
  `flocks_detail`. Clicking any of those returns a raw 403 instead of a
  coherent worker experience.
- The week overview lives under the admin prefix today, so workers cannot
  open it. The new scope says workers must be able to see it.
- Registration list templates (e.g. [egg_registrations.html](kippen_app/templates/egg_registrations.html))
  always show edit/delete actions for every row. Workers can therefore
  modify entries created by other users.
- The dashboard mixes recent-history summaries (worker-relevant) with admin
  shortcuts (`Leeggoed beheren`, `Koppels beheren`, raw CSV exports).
- There is no friendly 403 page; Flask's default error page is shown.

## Scope

In scope:

- Move `/kippen/week` (and its xlsx/pdf exports) out of admin-only and into
  the worker-accessible set, so workers can open the week overview.
- Expose the active user's Kippen role(s) and identity to all Kippen
  templates.
- Hide admin-only entry points (`Leeggoed beheren`, `Koppels beheren`, CSV
  exports under `/kippen/export`) from worker views.
- Adjust the dashboard so a worker sees a registration-focused layout (plus
  the week overview link).
- Restrict the per-row `Bewerken` / `Verwijderen` buttons and the matching
  POST routes so workers can edit and delete their own registrations only.
  Admins keep full edit/delete on every row.
- Add a small role badge in the header showing the logged-in user and
  whether they are viewing as Beheerder or Medewerker.
- Add a friendly 403 page so a worker who follows or types an admin URL
  gets a useful screen with a link back to their dashboard.
- Keep route-level access checks intact as defence-in-depth.

Out of scope:

- Adding new roles, changing role keys, or changing the access model.
- Changing what an admin can see — admin view stays as-is.
- Restructuring URLs (`/kippen/...` paths stay the same).
- Editing the central portal tiles. The portal already shows the `kippen`
  tile based on application access; no change needed there.
- Migrating `created_by` / `registered_by` from string to user FK. See the
  risks section for why this is acceptable for v1.

## Target Behaviour

### Worker view

A user whose only `kippen` role is `worker`:

- Dashboard (`/kippen/dashboard`) shows:
  - The header, role badge, and "Vandaag" stat cards.
  - Action buttons for: `Eieren registreren`, `Water en voer registreren`,
    `Dode hen registreren`, `Buitennest ronde registreren`,
    `Palletgewicht registreren`, `Weekoverzicht bekijken`.
  - Recent-registration summary tables (eggs, feed/water, dead hens,
    outside-nest, pallet weights) with links to the worker-accessible
    list pages.
  - The active-flock pill renders as text, not as a link (flock detail is
    admin-only).
- The following are **not rendered** anywhere on the worker dashboard or
  registration list pages: `Leeggoed beheren`, `Koppels beheren`, the CSV
  export buttons, any link to `/kippen/flocks/*`,
  `/kippen/packaging-weights/*`, or `/kippen/export/*`.
- On registration list pages (`/kippen/eggs`, `/kippen/feed-water`,
  `/kippen/dead-hens`, `/kippen/outside-nest-rounds`,
  `/kippen/pallet-weights`):
  - All entries are visible (workers need full context).
  - The `Bewerken` and `Verwijderen` buttons are only rendered for rows
    whose `created_by` / `registered_by` matches the worker's current
    username. Other rows show no row actions.
- On the week overview (`/kippen/week`, `/kippen/week/<year>/<week>`):
  - Workers may open the page.
  - Workers may also download the xlsx/pdf week exports under
    `/kippen/week/.../export.xlsx` and `.../export.pdf`. These are
    presentation exports of the week page; treating them differently
    would be inconsistent.
- If a worker types an admin URL by hand, the existing `before_request`
  check still 403s. The 403 page is the new friendly template.

### Admin view

A user with the `kippen` `admin` role keeps the current experience exactly,
plus the role badge in the header. If a user has both `admin` and `worker`,
admin wins — they see the full UI and can edit/delete any row.

### Role badge

A small element in the top-right of every Kippen page renders:

```text
{{ display_name }} · {{ "Beheerder" if is_admin else "Medewerker" }}
```

Placed in `base.html` so every Kippen page picks it up, including list and
form screens. Hidden when no user is logged in.

### Friendly 403

A `403.html` template under `kippen_app/templates/`, extending `base.html`,
explains in Dutch that the page is admin-only and links back to
`/kippen/dashboard`. Register a Flask error handler for `403` in
`create_app` that renders this template. Keep it limited to the Kippen app —
the portal has its own behaviour.

## Design

### Routing change for week overview

In [kippen_app/app.py](kippen_app/app.py):

- Remove `/kippen/week` from `KIPPEN_ADMIN_PREFIXES`.
- Add `/kippen/week` to `KIPPEN_WORKER_PREFIXES`.

`/kippen/export` (raw CSV exports) stays in `KIPPEN_ADMIN_PREFIXES`.

### Surface the role in templates

Add a single Flask `context_processor` in `create_app` that exposes a small
`kippen_user` view-model to every template:

```python
@app.context_processor
def inject_kippen_user():
    user = _current_user()
    if user is None:
        return {}
    auth_service = _auth_service()
    is_admin = auth_service.user_has_application_role(
        user.id, KIPPEN_APPLICATION_KEY, "admin",
    )
    is_worker = auth_service.user_has_application_role(
        user.id, KIPPEN_APPLICATION_KEY, "worker",
    )
    return {
        "kippen_user": {
            "id": user.id,
            "username": _current_username(),
            "display_name": _current_username(),
            "is_admin": is_admin,
            "is_worker": is_worker,
        },
    }
```

Notes:

- `is_admin` is the gate we care about. `is_worker` is included for symmetry.
- The username string surfaced here MUST match the value used at create
  time in `_current_username()` so the per-row ownership comparison works.
- Templates that may be rendered without a logged-in user must use
  `kippen_user|default(None)` or `kippen_user and kippen_user.is_admin`.

### Per-row ownership check

Add a small helper, used both by templates and routes:

```python
def _registration_owned_by_current_user(registration) -> bool:
    owner = getattr(registration, "created_by", None) or getattr(
        registration, "registered_by", None
    )
    if owner is None:
        return False
    return owner.strip() == _current_username().strip()
```

For template use, attach an `owned_by_current_user` flag per row before
rendering each list, or expose a Jinja global wrapping the helper. The
plan recommends computing the flag in the route and passing
`registrations=[(item, owned), ...]` to keep the template clean — but a
Jinja global is acceptable too. Either choice is local to the list views;
pick one during implementation and keep it consistent.

### Route-level ownership enforcement

For the edit and delete POST routes for the five worker-accessible
registration types — eggs, feed/water, dead hens, outside-nest rounds,
pallet weights — add a check at the top of each route:

```python
if not auth_service.user_has_application_role(
    user.id, KIPPEN_APPLICATION_KEY, "admin",
):
    if not _registration_owned_by_current_user(existing_registration):
        abort(403)
```

Concretely this applies to:

- `egg_registrations_edit`, `egg_registrations_edit_post`,
  `egg_registrations_delete`
- `feed_water_registrations_edit`, `feed_water_registrations_edit_post`,
  `feed_water_registrations_delete`
- `dead_hens_delete` (no edit route exists today)
- `outside_nest_rounds_delete` (no edit route exists today)
- `pallet_weights_edit`, `pallet_weights_edit_post`,
  `pallet_weights_delete`

This is the security boundary for ownership; the template-level button
hiding is cosmetic.

### Template changes

1. [kippen_app/templates/dashboard.html](kippen_app/templates/dashboard.html)
   - Wrap the `Leeggoed beheren`, `Koppels beheren`, and `Palletgewichten`
     admin-shortcut buttons in `{% if kippen_user and kippen_user.is_admin %}`
     blocks.
   - Leave `Weekoverzicht bekijken` visible for both roles.
   - Wrap the entire CSV-export `<div class="buttons are-small">` in the
     same admin gate.
   - Wrap the `<a href="...flocks_detail...">` inside the "Actief koppel"
     notification so workers see the flock name and placement date as
     plain text.

2. [kippen_app/templates/egg_registrations.html](kippen_app/templates/egg_registrations.html),
   [feed_water_registrations.html](kippen_app/templates/feed_water_registrations.html),
   [dead_hens.html](kippen_app/templates/dead_hens.html),
   [outside_nest_rounds.html](kippen_app/templates/outside_nest_rounds.html),
   [pallet_weights.html](kippen_app/templates/pallet_weights.html)
   - For each row, render the `Bewerken` / `Verwijderen` buttons only when
     `kippen_user.is_admin` OR the row is owned by the current user.
   - The `Nieuwe ...` header button and `Overzicht` link stay as is for
     both roles.

3. [kippen_app/templates/base.html](kippen_app/templates/base.html)
   - Add a top-right role badge:
     `{{ kippen_user.display_name }} · {{ "Beheerder" if kippen_user.is_admin else "Medewerker" }}`,
     rendered only when `kippen_user` is present.
   - Keep markup minimal — Bulma `navbar` or a simple `tag is-light` chip
     above the section container.

4. New `kippen_app/templates/403.html`
   - Extends `base.html`.
   - Title: `Geen toegang | Kippen Registratie`.
   - Body: short Dutch explanation that the requested page is for
     admins only, plus a `is-link` button back to
     `url_for("dashboard")`.

5. `flocks.html`, `flock_detail.html`, `flock_form.html`,
   `packaging_weights.html`, `packaging_weight_form.html`, `week.html`
   - `week.html` no longer needs to assume admin-only context. Audit any
     links inside it; if it links to admin-only pages (e.g. flock detail),
     gate those links the same way as the dashboard does. The week page
     itself stays usable for workers.
   - The other admin-only templates are unchanged.

### Defence-in-depth, unchanged

`KIPPEN_ADMIN_PREFIXES` and `KIPPEN_WORKER_PREFIXES` stay as the path-level
gate. The new ownership check inside the worker-prefixed edit/delete routes
adds a second gate. The UI gating only hides links.

## Files to Touch

- [kippen_app/app.py](kippen_app/app.py)
  - Move `/kippen/week` from `KIPPEN_ADMIN_PREFIXES` to
    `KIPPEN_WORKER_PREFIXES`.
  - Add `inject_kippen_user` context processor.
  - Add `_registration_owned_by_current_user` helper.
  - Add ownership checks at the top of the worker-accessible edit/delete
    routes listed above.
  - Register a 403 error handler that renders the new template.

- [kippen_app/templates/base.html](kippen_app/templates/base.html)
  - Role badge.

- [kippen_app/templates/dashboard.html](kippen_app/templates/dashboard.html)
  - Gate admin buttons, gate CSV export block, gate the flock-detail link.
    Keep week overview button visible to workers.

- The five registration list templates listed above
  - Gate per-row edit/delete buttons by ownership-or-admin.

- [kippen_app/templates/week.html](kippen_app/templates/week.html)
  - Audit and gate any admin-only links it embeds.

- New `kippen_app/templates/403.html`.

## Tests

Extend [tests/kippen_app/test_routes.py](tests/kippen_app/test_routes.py).
The existing fixture creates `admin` and `worker` users — reuse them and
add a second worker to test the cross-worker ownership case.

Add cases:

1. `test_worker_dashboard_hides_admin_shortcuts`
   - Worker GET `/kippen/dashboard`.
   - Body does NOT contain `"Leeggoed beheren"`, `"Koppels beheren"`,
     `"Eieren CSV"`.
   - Body DOES contain the five registration buttons and
     `"Weekoverzicht bekijken"`.

2. `test_admin_dashboard_shows_admin_shortcuts`
   - Admin GET `/kippen/dashboard`.
   - Body contains all admin shortcuts as today.

3. `test_worker_dashboard_active_flock_is_not_a_link`
   - With an active flock seeded, worker response does not contain
     `href="/kippen/flocks/<id>"`, admin response does.

4. `test_worker_can_open_week_overview`
   - Worker GET `/kippen/week` and `/kippen/week/<year>/<week>`: 200.

5. `test_worker_can_edit_own_registration`
   - Seed an egg registration with `created_by` matching the worker's
     username. Worker POST edit succeeds (302 + flash).

6. `test_worker_cannot_edit_other_users_registration`
   - Seed an egg registration with `created_by="someone_else"`. Worker
     POST edit returns 403.

7. `test_worker_cannot_delete_other_users_registration`
   - Same setup, POST delete returns 403, row still present.

8. `test_admin_can_edit_any_registration`
   - Seed an egg registration with `created_by="someone_else"`. Admin POST
     edit succeeds.

9. `test_registration_list_hides_buttons_for_other_users`
   - Seed two egg rows: one owned by the worker, one by another user.
     Worker GET `/kippen/eggs`. Response contains the edit URL for the
     owned row but not for the other row.

10. `test_friendly_403_page_on_admin_route`
    - Worker GET `/kippen/flocks`. Status 403. Body contains the
      friendly message and a link to `/kippen/dashboard`.

11. Keep existing `test_worker_role_is_denied_for_admin_routes` and
    `test_worker_role_can_open_daily_registration_routes` as the
    server-side safety net. Update the first one if it asserted that
    `/kippen/week` returns 403 for workers (it must now return 200).

## Risks and Trade-offs

- **String-based ownership.** `created_by` and `registered_by` store the
  display name / username string at create time. If a user's username
  changes, prior rows would no longer match and would become read-only
  for that worker. Username changes are rare in this app — there is no
  self-service rename — so the trade-off is acceptable for v1. If
  rename becomes a feature later, migrate these columns to user FKs and
  update the ownership helper.
- **`_current_username()` returns `display_name` when set.** The
  helper uses `session["display_name"]` if present, else
  `user.username`. The template-side ownership check must use the same
  string. The plan funnels both through `_current_username()` to keep
  them in sync.
- **Double role lookup per request.** The context processor calls
  `user_has_application_role` twice. Negligible at current scale; cache
  on `flask.g` later if it becomes a problem.
- **Template drift.** New templates also need to gate admin-only links.
  Add a one-liner reminder to `AGENTS.md` or the Kippen `README`.
- **Hidden ≠ secure.** Workers can hit admin URLs by hand. The
  `before_request` check rejects them and the new 403 page handles the
  presentation. The ownership check inside edit/delete routes is the
  real boundary for per-row protection.
- **Both roles assigned.** A user with both `admin` and `worker` gets
  the admin view and can edit any row. This matches the current
  bootstrap behaviour.

## Decisions (confirmed)

- Workers can edit and delete **their own** registrations only. Admins
  can edit/delete any row.
- A role badge is rendered in the Kippen header.
- A friendly 403 page is rendered when a worker hits an admin URL.
- The week overview (`/kippen/week`) is accessible to workers, including
  its xlsx and pdf exports. Raw CSV exports under `/kippen/export` stay
  admin-only.

## Implementation Phases

### Phase 1: Routing and role plumbing

- Move `/kippen/week` to `KIPPEN_WORKER_PREFIXES`.
- Add `inject_kippen_user` context processor.
- Add `_registration_owned_by_current_user` helper.
- Add the 403 error handler stub returning a placeholder string.

### Phase 2: Friendly 403 and role badge

- Create `kippen_app/templates/403.html`.
- Wire the error handler to render it.
- Add the role badge to `base.html`.

### Phase 3: Gate the dashboard

- Update `dashboard.html` admin button block, CSV export block, and the
  active-flock-link wrapper. Keep the week button visible.
- Add `test_worker_dashboard_hides_admin_shortcuts`,
  `test_admin_dashboard_shows_admin_shortcuts`,
  `test_worker_dashboard_active_flock_is_not_a_link`,
  `test_worker_can_open_week_overview`,
  `test_friendly_403_page_on_admin_route`.

### Phase 4: Per-row ownership

- Update each worker-accessible edit/delete route with the ownership
  guard.
- Update the five list templates to gate per-row buttons by
  ownership-or-admin.
- Audit `week.html` for embedded admin-only links and gate them.
- Add `test_worker_can_edit_own_registration`,
  `test_worker_cannot_edit_other_users_registration`,
  `test_worker_cannot_delete_other_users_registration`,
  `test_admin_can_edit_any_registration`,
  `test_registration_list_hides_buttons_for_other_users`.

### Phase 5: Verification

- `ruff format` and `ruff check --fix` on `kippen_app/app.py`.
- `pytest tests/kippen_app/test_routes.py`.
- Manual: log in as admin -> confirm unchanged; log in as worker ->
  confirm dashboard is trimmed, week overview is reachable, list pages
  show edit/delete only for own rows, admin URLs render the friendly
  403 page.
