# Moneybird Datajob Plan

## Goal

Build a read-only Moneybird datajob that collects bookkeeping data from the
Moneybird API, stores it in the shared PostgreSQL database, and makes the data
available for a bookkeeping dashboard.

The first version should focus on visibility, not mutations. It should not
create invoices, update contacts, register payments, or alter bookkeeping data
in Moneybird.

This plan is for review before implementation. Do not start code changes until
the plan is approved.

## API Context

Moneybird exposes a REST API under:

```text
https://moneybird.com/api/v2/{administration_id}/{resource}.json
```

Important API behavior:

- Authentication uses OAuth2 or a personal API token in the `Authorization:
  Bearer <token>` header.
- Personal API tokens can be limited by scopes.
- Relevant scopes for the dashboard are:
  - `sales_invoices`;
  - `documents`;
  - `bank`;
  - `settings` if ledger/account metadata requires it later.
- Most list endpoints use pagination with `page` and `per_page`.
- `per_page` has a maximum of 100.
- General API throttling is 150 requests per 5 minutes.
- `/reports/` endpoints have a stricter limit of 50 requests per 5 minutes.
- Moneybird IDs can be very large and should be stored as strings.
- Reports accept Moneybird period presets such as `this_month`, `this_quarter`,
  `this_year`, or explicit whole-month date ranges.

Primary documentation references:

- `https://developer.moneybird.com/introduction`
- `https://developer.moneybird.com/authentication`
- `https://developer.moneybird.com/api/administrations/`
- `https://developer.moneybird.com/api/sales-invoices/`
- `https://developer.moneybird.com/api/documents-purchase-invoices/`
- `https://developer.moneybird.com/api/financial-accounts/`
- `https://developer.moneybird.com/api/financial-mutations/`
- `https://developer.moneybird.com/api/reports/`
- `https://developer.moneybird.com/api/contacts/`
- `https://developer.moneybird.com/api/ledger-accounts/`

## Dashboard Data Requirements

The datajob should support a basic bookkeeping dashboard with these sections:

- **Overview**
  - revenue;
  - expenses;
  - gross profit;
  - operating profit;
  - net profit;
  - open receivables;
  - open payables;
  - bank accounts and balances when available.
- **Profit and loss**
  - revenue by ledger account;
  - direct costs by ledger account;
  - expenses by ledger account;
  - other income/expenses;
  - monthly/quarter/year comparisons.
- **Sales invoices**
  - invoice number/reference;
  - contact;
  - invoice date;
  - due date;
  - status;
  - total incl/excl tax;
  - paid amount;
  - unpaid amount;
  - late/uncollectible/dubious flags where available.
- **Purchase invoices**
  - supplier/contact;
  - reference;
  - date;
  - due date;
  - status;
  - total incl/excl tax;
  - paid date;
  - open payable amount where derivable.
- **Bank**
  - financial accounts;
  - recent financial mutations;
  - processed/unprocessed mutation counts;
  - open amount per mutation where available.
- **Relations**
  - contacts;
  - customer/supplier identification;
  - revenue/cost totals by contact when derivable from invoices.

## Target Structure

Use the existing datajob style in this repository.

Suggested package layout:

```text
data_jobs/moneybird/
  __init__.py
  api_client.py
  config.py
  exceptions.py
  serializers.py
  transforms.py
  collectors.py
  scripts/
    __init__.py
    collect_moneybird.py
```

Responsibilities:

- `config.py`
  - Load and validate Moneybird environment variables.
  - Parse booleans, integers, timeouts, periods, and optional defaults.
- `exceptions.py`
  - Define configuration, API, throttling, and transformation exceptions.
- `api_client.py`
  - Own HTTP transport, authorization headers, pagination, rate-limit handling,
    retries, and JSON parsing.
- `collectors.py`
  - Orchestrate endpoint-level collection.
  - Keep collection read-only.
  - Return normalized records or persistence-ready payloads.
- `transforms.py`
  - Convert Moneybird JSON into database-shaped dictionaries.
  - Parse dates, datetimes, decimal strings, states, and nested contact data.
- `serializers.py`
  - Optional JSON snapshot helpers for debugging and fixture generation.
- `scripts/collect_moneybird.py`
  - Thin CLI entry point for scheduled collection.

## Configuration

Add the following to `deploy/dashboard.env.example`:

```env
MONEYBIRD_ACCESS_TOKEN=
MONEYBIRD_ADMINISTRATION_ID=
MONEYBIRD_TIME_ZONE=Europe/Amsterdam
MONEYBIRD_DEFAULT_PERIOD=this_year
MONEYBIRD_REQUEST_TIMEOUT_SECONDS=30
MONEYBIRD_MAX_RETRIES=3
MONEYBIRD_RETRY_BACKOFF_SECONDS=2
MONEYBIRD_SYNC_REPORTS=true
MONEYBIRD_SYNC_INVOICES=true
MONEYBIRD_SYNC_BANK=true
MONEYBIRD_SYNC_CONTACTS=true
```

Configuration rules:

- `MONEYBIRD_ACCESS_TOKEN` is required.
- `MONEYBIRD_ADMINISTRATION_ID` can be required for scheduled jobs.
- If no administration ID is configured, the CLI can support
  `--list-administrations` to print available administrations.
- Store IDs as strings, not integers.
- Use `MONEYBIRD_TIME_ZONE` as the `Time-Zone` header.
- Treat the token as a secret; never print it or store it in logs.

## API Client Design

Suggested public API:

```python
def build_moneybird_client(config: MoneybirdConfig) -> MoneybirdClient:
    ...
```

```python
class MoneybirdClient:
    def get_json(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> object:
        ...

    def get_paginated(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> list[dict[str, object]]:
        ...
```

Implementation notes:

- Use `httpx`.
- Use explicit timeouts.
- Include:
  - `Authorization: Bearer <token>`;
  - `Content-Type: application/json`;
  - `Accept: application/json`;
  - `Time-Zone: Europe/Amsterdam` when configured.
- For paginated endpoints:
  - request `per_page=100`;
  - follow the `Link` header when present;
  - otherwise increment `page` until fewer than 100 rows are returned.
- For `429`:
  - respect `Retry-After` if present;
  - otherwise exponential backoff.
- Raise typed exceptions for:
  - 401/403 auth or scope problems;
  - 429 throttling after retry exhaustion;
  - malformed JSON;
  - unexpected response shapes.

## Collection Scope

### 1. Administrations

Endpoint:

```text
GET /administrations.json
```

Purpose:

- verify credentials;
- list accessible administrations;
- validate configured administration ID;
- persist administration metadata.

Fields:

- `id`;
- `name`;
- `language`;
- `currency`;
- `country`;
- `time_zone`;
- `access`;
- `period_locked_until`;
- `period_start_date`.

### 2. Reports

Endpoints:

```text
GET /{administration_id}/reports/profit_loss.json?period={period}
GET /{administration_id}/reports/balance_sheet.json?period={period}
```

Initial periods:

- `this_month`;
- `this_quarter`;
- `this_year`;
- optionally `prev_month`, `prev_quarter`, `prev_year`.

Profit/loss fields:

- `total_revenue`;
- `total_expenses`;
- `gross_profit`;
- `operating_profit`;
- `net_profit`;
- grouped revenue/direct costs/expenses/other by ledger account.

Persistence approach:

- Store one summary row per administration and period.
- Store raw report JSON alongside normalized summary values.
- Add report type: `profit_loss` or `balance_sheet`.

### 3. Sales Invoices

Endpoint:

```text
GET /{administration_id}/sales_invoices.json?filter=period:{period},state:all
```

Use pagination.

Fields:

- `id`;
- `invoice_id`;
- `contact_id`;
- contact display name;
- `state`;
- `invoice_date`;
- `due_date`;
- `paid_at`;
- `sent_at`;
- `currency`;
- `total_price_excl_tax`;
- `total_price_incl_tax`;
- `total_paid`;
- `total_unpaid`;
- `marked_dubious_on`;
- `marked_uncollectible_on`;
- `reminder_count`;
- `next_reminder`;
- `updated_at`;
- `version`.

Dashboard derivations:

- open receivables: sum `total_unpaid` for non-paid invoices;
- overdue receivables: open invoices where `due_date < today`;
- paid revenue by month: based on `paid_at`;
- invoice revenue by month: based on `invoice_date`.

### 4. Purchase Invoices

Endpoint:

```text
GET /{administration_id}/documents/purchase_invoices.json?filter=period:{period},state:all
```

Use pagination.

Fields:

- `id`;
- `contact_id`;
- contact display name;
- `reference`;
- `entry_number`;
- `state`;
- `date`;
- `due_date`;
- `paid_at`;
- `currency`;
- `total_price_excl_tax`;
- `total_price_incl_tax`;
- `total_price_excl_tax_base`;
- `total_price_incl_tax_base`;
- `updated_at`;
- `version`.

Dashboard derivations:

- open payables by status;
- overdue payables where `due_date < today` and not paid;
- purchases by month;
- purchases by supplier.

### 5. Financial Accounts

Endpoint:

```text
GET /{administration_id}/financial_accounts.json
```

Fields:

- `id`;
- `type`;
- `name`;
- `identifier`;
- `currency`;
- `provider`;
- `active`.

This endpoint does not by itself guarantee a live balance field in every API
shape. If balance is not present, derive balance from reports or financial
mutations only when reliable.

### 6. Financial Mutations

Endpoint for small/recent views:

```text
GET /{administration_id}/financial_mutations.json?filter=period:{period},state:all
```

Endpoint for robust synchronization:

```text
GET /{administration_id}/financial_mutations/synchronization.json?filter=period:{period},state:all
POST /{administration_id}/financial_mutations/synchronization.json
```

Use the synchronization endpoint for production-like jobs because the normal
list endpoint is limited to 100 mutations.

Fields:

- `id`;
- `financial_account_id`;
- `amount`;
- `amount_open`;
- `date`;
- `message`;
- `code`;
- `contra_account_name`;
- `contra_account_number`;
- `state`;
- `settlement_state`;
- `updated_at`;
- `version`.

Dashboard derivations:

- incoming/outgoing cash flow;
- unprocessed mutation count;
- recent bank transactions;
- unmatched/open amount.

### 7. Contacts

Endpoint:

```text
GET /{administration_id}/contacts.json
```

Fields:

- `id`;
- `company_name`;
- `firstname`;
- `lastname`;
- `customer_id`;
- `supplier_id` if present in response;
- `email`;
- `city`;
- `country`;
- `archived`;
- `updated_at`;
- `version`.

Use contacts as dimension data for invoice/contact aggregation.

### 8. Ledger Accounts

Endpoint:

```text
GET /{administration_id}/ledger_accounts.json
```

Fields:

- `id`;
- `name`;
- `account_type`;
- `account_id`;

Use this as lookup data for profit/loss grouped report rows.

## Database Design

Add Alembic migrations and SQLModel models for:

```text
moneybird_administrations
moneybird_contacts
moneybird_ledger_accounts
moneybird_sales_invoices
moneybird_purchase_invoices
moneybird_financial_accounts
moneybird_financial_mutations
moneybird_report_snapshots
moneybird_collection_runs
```

General columns for all Moneybird entity tables:

- `id`: local primary key if needed;
- `moneybird_id`: string, unique with `administration_id`;
- `administration_id`: string;
- `moneybird_version`: optional integer/string depending on endpoint;
- `raw_json`: JSON for traceability;
- `created_at`;
- `updated_at`;
- `synced_at`.

Money columns:

- Store as `Numeric(14, 2)` or appropriate precision.
- Parse Moneybird decimal strings with `Decimal`, not float.
- Keep currency as a separate string column.

Indexes:

- `(administration_id, moneybird_id)` unique where applicable.
- invoice status/state indexes.
- date indexes:
  - invoice date;
  - due date;
  - paid date;
  - mutation date.
- contact ID indexes for joins.

## Persistence Rules

- Upsert by `(administration_id, moneybird_id)`.
- Never delete local rows just because they are absent from a filtered sync.
- For full synchronization endpoints, consider marking stale rows only after an
  intentional full sync.
- Persist `raw_json` to reduce future migration risk.
- Persist one `moneybird_collection_runs` row per run:
  - started_at;
  - finished_at;
  - status;
  - administration_id;
  - requested period;
  - counts per entity;
  - error message when failed.

## CLI Design

Suggested command:

```powershell
.\.venv\Scripts\python.exe -m data_jobs.moneybird.scripts.collect_moneybird
```

Options:

```text
--list-administrations
--administration-id <id>
--period this_year
--sync-reports / --no-sync-reports
--sync-invoices / --no-sync-invoices
--sync-bank / --no-sync-bank
--sync-contacts / --no-sync-contacts
--dry-run
```

Behavior:

1. Load config.
2. Validate token by listing administrations.
3. Resolve administration ID.
4. Create collection run record.
5. Collect enabled resource groups.
6. Transform and persist data.
7. Mark collection run success or failure.

## Scheduling

Add a container/runtime command after implementation, similar to other datajobs.

Suggested schedule:

- reports: every morning;
- invoices: every morning and optionally every afternoon;
- bank mutations: every morning, optionally more often;
- contacts/ledger accounts: daily or weekly.

Keep report API calls conservative because `/reports/` has stricter throttling.

## Dashboard Implementation Plan

Create a separate dashboard after the datajob is reliable:

```text
dashboard/moneybird_dashboard.py
```

Dashboard tabs:

1. **Overzicht**
   - KPI cards;
   - monthly trend;
   - warnings.
2. **Resultaat**
   - profit/loss summary;
   - ledger account breakdown.
3. **Facturen**
   - sales invoice table;
   - open/late filters.
4. **Inkoop**
   - purchase invoice table;
   - due date filters.
5. **Bank**
   - financial account table;
   - mutation table;
   - unprocessed mutation counts.
6. **Relaties**
   - contact table;
   - revenue/cost by relation.

The first dashboard should read from the local database only. Do not call
Moneybird directly from the dashboard UI.

## Testing Plan

Unit tests:

- config validation;
- boolean/integer parsing;
- decimal parsing;
- date/datetime parsing;
- Link header pagination parsing;
- Moneybird error handling;
- transformation of:
  - sales invoices;
  - purchase invoices;
  - financial mutations;
  - reports;
  - contacts;
  - ledger accounts.

Integration-style tests with mocked HTTP:

- paginated endpoint collection;
- 429 retry handling;
- failed auth;
- synchronization endpoint batching with max 100 IDs per POST;
- partial failure updates collection run status.

Persistence tests:

- insert new entities;
- update existing entities by Moneybird ID;
- preserve raw JSON;
- store amounts as Decimal/Numeric;
- store IDs as strings.

CLI tests:

- `--list-administrations`;
- `--dry-run`;
- scoped sync flags;
- failed config exits with a useful message.

## Implementation Phases

### Phase 1: Read-only API client and config

- Add `data_jobs/moneybird/config.py`.
- Add `data_jobs/moneybird/api_client.py`.
- Add exceptions.
- Add unit tests for config, auth headers, pagination, retries.

Acceptance criteria:

- Can list administrations with a token.
- No token appears in logs or exceptions.
- Pagination works in tests.

### Phase 2: Models and migrations

- Add SQLModel models.
- Add Alembic migration.
- Add repositories or persistence functions following existing repo patterns.

Acceptance criteria:

- Migration upgrades/downgrades cleanly.
- Persistence tests pass for upsert behavior.

### Phase 3: Reports and invoice collection

- Collect profit/loss and balance sheet snapshots.
- Collect sales invoices.
- Collect purchase invoices.
- Persist normalized records.

Acceptance criteria:

- One command can collect dashboard-critical financial data.
- Re-running the command updates rows idempotently.

### Phase 4: Bank and dimension data

- Collect contacts.
- Collect ledger accounts.
- Collect financial accounts.
- Collect financial mutations through synchronization where needed.

Acceptance criteria:

- Bank tab data is locally available.
- Invoice tables can join contact names.
- Profit/loss account IDs can be mapped to account names.

### Phase 5: Dashboard

- Build `dashboard/moneybird_dashboard.py`.
- Add dashboard portal registration if needed.
- Keep dashboard read-only.

Acceptance criteria:

- Dashboard loads from local DB.
- No Moneybird token is needed in the dashboard runtime.
- Basic KPI cards, invoice tables, purchase tables, and report views are usable.

## Open Questions

Resolved choices:

- Use a personal API token for the first version.
  - Reason: this is an internal, read-only datajob with one administration. A
    personal API token is simpler to configure, easier to schedule, and avoids
    building OAuth redirect/refresh-token handling before it is needed.
  - Keep OAuth2 as a future option if the integration becomes multi-user,
    customer-facing, or needs delegated access per Moneybird user.
- Default administration: `Gebroeders vroege cv`.
- Default collection period: `this_year`.
- Historical backfill for older invoices and bank mutations: out of scope.
- Attachments and invoice PDFs: out of scope.
- Dashboard scope: one administration.

## Out of Scope for MVP

- Creating or sending invoices.
- Registering payments.
- Updating contacts.
- Downloading attachments.
- OAuth multi-user authorization UI.
- Webhooks.
- Real-time bank sync.
- Accountant workflows.
