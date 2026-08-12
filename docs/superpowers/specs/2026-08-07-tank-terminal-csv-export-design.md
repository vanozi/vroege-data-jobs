# Tank Terminal CSV Export Design

## Goal

Refactor the Tank Terminal datajob to collect transactions through the
ProFleet `Administratien / Export / Transactions` CSV export instead of
scraping the visible transactions table.

## Export Flow

After login, the collector opens the exports area, selects the `Transactions`
export screen, chooses the `Export before purge` template, opens the filters
section, fills the start and end date-time fields, and clicks `Export`.

If the database already has tank transactions, the start date-time is the day
before the latest stored `start_date_time` date at `00:00:00`. The end
date-time is tomorrow at `00:00:00`. Both values use the ProFleet format
`dd/mm/yyyy hh:mm:ss`, for example `04/08/2026 00:00:00`.

If the database is empty, the collector leaves both date fields empty.

## Data Flow

The collector downloads the CSV file, reads it as UTF-8 with BOM support, and
parses it through the existing `data_jobs.tank_terminal.csv_parsers` module.
The CLI persists parsed `TankTransaction` models through
`save_tank_transaction_models_by_start_date_time`, so overlapping exports
update existing rows by `start_date_time`.

## Testing Constraints

The live ProFleet portal has a login-rate limit. Automated verification should
prefer unit tests and mocked Playwright interactions. If manual Playwright
testing is needed during development, reuse a single browser session and avoid
repeated login attempts.

## Error Handling

The collector should raise clear errors when login fails, the export page cannot
be reached, the template cannot be selected, the date fields cannot be found, no
download is produced, or the downloaded CSV cannot be parsed. CLI error handling
continues to log the exception and return a non-zero exit code.
