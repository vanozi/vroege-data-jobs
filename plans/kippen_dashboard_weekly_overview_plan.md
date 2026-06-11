# Kippen Dashboard Weekly Overview Plan

This plan is for review before implementation. Do not start code changes until
the plan is approved.

## Goal

Add a per-week overview table to `Kippen Productieoverzicht`, alongside the
existing per-day overview table.

The weekly table should compare actual weekly values against weekly norm values,
because the norm calendar is expressed as week averages.

## Requested outcome

Add a new table:

- `Per-week overzicht met werkelijke en normwaarden`

Keep the visible KPI set aligned with the existing day table, and add
`curve dag` to both tables.

## Scope

In scope:

- Extend the existing day table with `curve dag`
- Add a new weekly overview table derived from the daily overview dataset
- Add exports for the weekly overview

Out of scope:

- Changing the current norm import format
- Replacing the existing day table

## Table columns

Both the day table and the new week table should show:

- `Datum`
- `Week`
- `Curve dag`
- `Legpercentage %`
- `Norm legpercentage %`
- `Eigewicht g`
- `Norm eigewicht g`
- `Voeropname g/dag`
- `Norm voeropname g/dag`
- `FCR`
- `Norm FCR`
- `Leefbaarheid %`
- `Norm leefbaarheid %`
- `Cum. eieren / opgezette hen`
- `Norm cum. eieren/hen`

## Definitions

### Curve dag

`curve dag` should represent how many days old the flock is on that row date.

Planned calculation:

- `curve_day = (registration_date - flock_dob).days`

This should be added to the daily overview dataset and then reused by both
tables.

### Weekly row date

Each weekly row should be represented by the last available day of that
`flock_week` in the selected range.

So for flock week 20:

- aggregate over all rows in flock week 20
- use the last `registration_date` in that week as the row `Datum`
- use the corresponding `curve dag` of that last day for the row

This matches your requirement that the week row is shown on the last day of
that week.

## Data source strategy

Reuse `df_daily_overview` as the single source of truth.

Reason:

- the daily overview already merges actual values, norm values, egg weight
  filling, FCR, liveability, and cumulative eggs per placed hen
- this avoids building a second parallel transform pipeline
- weekly aggregation can stay close to the current dashboard behavior

## Implementation plan

### 1. Extend daily overview with `curve_day`

In `dashboard/kippen_dashboard.py`:

- add a new derived column to `df_daily_overview`
  - `curve_day`
- base it on `registration_date` and `flock_dob`

Then expose it in the day table as:

- `Curve dag`

### 2. Add a reusable weekly transform

Add a new transform in `dashboard/kippen_transforms.py`, for example:

- `weekly_overview_from_daily(df_daily_overview: pl.DataFrame) -> pl.DataFrame`

Responsibilities:

- group rows by `flock_week`
- compute one weekly row per flock week
- carry the final row date and final `curve_day`
- preserve norm alignment by flock week

### 3. Weekly aggregation rules

Planned per-column behavior:

Average over the week:

- `lay_percentage`
- `egg_weight_grams_filled`
- `feed_intake_grams_per_day_actual`
- `fcr`
- `liveability_percentage`

Norm values for the week:

- `lay_percentage_norm`
- `egg_weight_grams_norm`
- `feed_intake_grams_per_day_norm`
- `feed_conversion_ratio_norm`
- `liveability_percentage_norm`

These should come from the weekly norm row for that `flock_week`.
Because the norm is already week-based, the implementation may either:

- take the last non-null norm value in that group, or
- take the mean if all rows in the week carry the same norm value

Preferred implementation:

- use the last non-null norm value in the group

Snapshot on the last day of the week:

- `registration_date`
- `curve_day`
- `cumulative_eggs_per_placed_hen`
- `cumulative_eggs_per_placed_hen_norm`

Reason:

- cumulative KPIs should not be averaged across the week
- they should reflect the state at the end of the week

### 4. Render a second table in the dashboard

In `dashboard/kippen_dashboard.py`:

- keep the current day table
- add a second table below it with label:
  - `Per-week overzicht met werkelijke en normwaarden`

Suggested layout order:

1. day table + CSV download
2. weekly table
3. outside-nest chart

### 5. Add weekly overview exports

Add export support for the weekly overview table.

Planned scope:

- add a weekly CSV export alongside the weekly table
- use the same visible column set as the weekly table
- apply the same rounding/display conventions in the exported structure only
  where that is appropriate for export readability

Preferred filename:

- `kippen-weekoverzicht.csv`

Implementation approach:

- build the weekly export from the same weekly dataframe used by the UI table
- keep the existing day CSV export unchanged

### 6. Apply the same display rounding rules

For both day and week tables:

- `Legpercentage %`: 2 decimals
- `Eigewicht g`: 1 decimal
- `Voeropname g/dag`: whole numbers
- `FCR`: 2 decimals
- `Leefbaarheid %`: 2 decimals
- `Cum. eieren / opgezette hen`: 1 decimal

Apply the same rounding to matching norm columns.

## Files expected to change

- `dashboard/kippen_dashboard.py`
- `dashboard/kippen_transforms.py`
- `tests/dashboard/test_kippen_transforms.py`

## Test plan

### Transform tests

Add focused tests in `tests/dashboard/test_kippen_transforms.py` for:

- `curve_day` calculation from `flock_dob`
- weekly grouping by `flock_week`
- weekly row using the last day of the week as `Datum`
- weekly averages for:
  - lay percentage
  - egg weight
  - feed intake per hen
  - FCR
  - liveability
- weekly snapshot behavior for:
  - cumulative eggs per placed hen
  - norm cumulative eggs per hen

### Dashboard smoke checks

After implementation:

- open `Kippen Productieoverzicht`
- verify the day table shows `Curve dag`
- verify the week table is visible
- verify the weekly CSV export is visible and downloads correctly
- verify a week row date matches the last selected day inside that flock week
- verify actual values and norm values remain aligned

## Open point for review

Proposed weekly behavior for `Leefbaarheid %`:

- weekly table shows the average of daily liveability values inside that week

Alternative:

- show the last-day liveability snapshot of the week

My recommendation is to keep it as a weekly average, because that matches the
general meaning of the weekly table. If you want, I can instead treat
`Leefbaarheid %` like a weekly end-state metric.
