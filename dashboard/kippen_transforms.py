"""Pure transform functions for the Kippen analytics dashboard.

All functions operate on Polars DataFrames and plain Python values.
No database access — testable without a running database.

Flock age convention: identical to kippen_app/flock_age.py.
  curve_day = max(elapsed_days - 1, 0)
  flock_week = curve_day // 7
So day 1 of life = curve_day 0 = week 0, day 0.
Week 33 starts on curve_day 231 = elapsed_day 232 (dob + 232 days).
"""

import unicodedata
from datetime import date
from decimal import Decimal

import polars as pl


# ---------------------------------------------------------------------------
# Flock age helpers
# ---------------------------------------------------------------------------


def calculate_flock_week(registration_date: date, date_of_birth: date) -> int:
    """Return flock age week for a registration date.

    Uses the same curve-day convention as kippen_app/flock_age.py:
    curve_day = max((registration_date - date_of_birth).days - 1, 0)
    flock_week = curve_day // 7
    """
    elapsed = (registration_date - date_of_birth).days
    curve_day = max(elapsed - 1, 0)
    return curve_day // 7


def add_flock_week_column(
    df: pl.DataFrame,
    date_col: str,
    date_of_birth: date,
    *,
    output_col: str = "flock_week",
) -> pl.DataFrame:
    """Add an integer flock_week column to a DataFrame.

    Vectorised: computes (elapsed_days - 1) // 7 for every row.
    """
    dob_pl = pl.lit(date_of_birth)
    elapsed = (pl.col(date_col).cast(pl.Date) - dob_pl).dt.total_days()
    curve_day = (elapsed - 1).clip(lower_bound=0)
    return df.with_columns((curve_day // 7).alias(output_col).cast(pl.Int32))


# ---------------------------------------------------------------------------
# Bird count / mortality
# ---------------------------------------------------------------------------


def daily_bird_count(
    dead_hen_df: pl.DataFrame,
    initial_bird_count: int,
    *,
    date_col: str = "found_date",
    count_col: str = "dead_count",
    output_date_col: str = "registration_date",
    output_count_col: str = "bird_count",
) -> pl.DataFrame:
    """Return a per-date DataFrame with running bird count after cumulative mortality.

    dead_hen_df must have `date_col` (Date) and `count_col` (Int) columns.
    Returns columns: [registration_date, dead_today, cum_dead, bird_count].
    Dates with no deaths still appear if they are in the input DataFrame.
    """
    if dead_hen_df.is_empty():
        return pl.DataFrame(
            {
                output_date_col: pl.Series([], dtype=pl.Date),
                "dead_today": pl.Series([], dtype=pl.Int64),
                "cum_dead": pl.Series([], dtype=pl.Int64),
                output_count_col: pl.Series([], dtype=pl.Int64),
            }
        )

    daily = (
        dead_hen_df.group_by(date_col)
        .agg(pl.col(count_col).sum().alias("dead_today"))
        .sort(date_col)
        .with_columns(pl.col("dead_today").cum_sum().alias("cum_dead"))
        .with_columns(
            (pl.lit(initial_bird_count) - pl.col("cum_dead")).alias(output_count_col)
        )
        .rename({date_col: output_date_col})
    )
    return daily


def cumulative_mortality_percentage(
    dead_hen_df: pl.DataFrame,
    initial_bird_count: int,
    *,
    date_col: str = "found_date",
    count_col: str = "dead_count",
) -> pl.DataFrame:
    """Return per-date cumulative mortality percentage.

    Returns columns: [registration_date, cum_dead_pct].
    """
    if initial_bird_count <= 0 or dead_hen_df.is_empty():
        return pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "cum_dead_pct": pl.Series([], dtype=pl.Float64),
            }
        )

    daily = (
        dead_hen_df.group_by(date_col)
        .agg(pl.col(count_col).sum().alias("dead_today"))
        .sort(date_col)
        .with_columns(pl.col("dead_today").cum_sum().alias("cum_dead"))
        .with_columns(
            (pl.col("cum_dead") / initial_bird_count * 100.0).alias("cum_dead_pct")
        )
        .rename({date_col: "registration_date"})
        .select(["registration_date", "cum_dead_pct"])
    )
    return daily


# ---------------------------------------------------------------------------
# Egg weight forward-fill
# ---------------------------------------------------------------------------


def forward_fill_egg_weight(
    pallet_df: pl.DataFrame,
    *,
    date_col: str = "registration_date",
    weight_col: str = "egg_weight_grams",
) -> pl.DataFrame:
    """Return a per-date DataFrame with forward-filled average egg weight.

    On days where multiple pallets were weighed, the daily average is used.
    The forward fill propagates forward without limit (no cap) — the dashboard
    renders markers on measured days so users see how stale the value is.

    Returns columns: [registration_date, egg_weight_grams_filled, is_measured].
    """
    if pallet_df.is_empty():
        return pl.DataFrame(
            {
                date_col: pl.Series([], dtype=pl.Date),
                "egg_weight_grams_filled": pl.Series([], dtype=pl.Float64),
                "is_measured": pl.Series([], dtype=pl.Boolean),
            }
        )

    daily_avg = (
        pallet_df.group_by(date_col)
        .agg(pl.col(weight_col).mean().alias("egg_weight_grams_filled"))
        .sort(date_col)
        .with_columns(pl.lit(True).alias("is_measured"))
    )
    return daily_avg


def join_forward_filled_weight(
    base_df: pl.DataFrame,
    pallet_df: pl.DataFrame,
    *,
    date_col: str = "registration_date",
    weight_col: str = "egg_weight_grams",
) -> pl.DataFrame:
    """Join forward-filled egg weight onto base_df (one row per date).

    base_df must have `date_col`. Returns base_df with two extra columns:
    egg_weight_grams_filled (forward-filled Float64) and is_measured (Boolean).
    Days before the first pallet measurement get null for egg_weight_grams_filled.
    """
    filled = forward_fill_egg_weight(
        pallet_df, date_col=date_col, weight_col=weight_col
    )

    if filled.is_empty():
        return base_df.with_columns(
            pl.lit(None).cast(pl.Float64).alias("egg_weight_grams_filled"),
            pl.lit(False).alias("is_measured"),
        )

    joined = base_df.join(filled, on=date_col, how="left")
    joined = joined.with_columns(pl.col("is_measured").fill_null(False))
    joined = joined.with_columns(pl.col("egg_weight_grams_filled").forward_fill())
    return joined


# ---------------------------------------------------------------------------
# Lay percentage
# ---------------------------------------------------------------------------


def daily_lay_percentage(
    egg_df: pl.DataFrame,
    bird_count_df: pl.DataFrame,
    *,
    egg_date_col: str = "registration_date",
    egg_total_col: str = "total_eggs",
    bird_date_col: str = "registration_date",
    bird_count_col: str = "bird_count",
) -> pl.DataFrame:
    """Return per-date lay percentage.

    Lay % = total_eggs / bird_count * 100.
    Days where bird_count is 0 or null get null lay_percentage.

    Returns columns: [registration_date, lay_percentage].
    """
    if egg_df.is_empty():
        return pl.DataFrame(
            {
                egg_date_col: pl.Series([], dtype=pl.Date),
                "lay_percentage": pl.Series([], dtype=pl.Float64),
            }
        )

    joined = egg_df.join(
        bird_count_df.select([bird_date_col, bird_count_col]),
        left_on=egg_date_col,
        right_on=bird_date_col,
        how="left",
    )
    result = joined.with_columns(
        pl.when(pl.col(bird_count_col).is_not_null() & (pl.col(bird_count_col) > 0))
        .then(pl.col(egg_total_col) / pl.col(bird_count_col) * 100.0)
        .otherwise(pl.lit(None))
        .alias("lay_percentage")
    ).select([egg_date_col, "lay_percentage"])
    return result


# ---------------------------------------------------------------------------
# Feed conversion ratio (FCR)
# ---------------------------------------------------------------------------


def daily_fcr(
    feed_df: pl.DataFrame,
    pallet_df: pl.DataFrame,
    egg_df: pl.DataFrame,
    *,
    date_col: str = "registration_date",
    feed_col: str = "feed_grams",
    weight_col: str = "egg_weight_grams",
    egg_total_col: str = "total_eggs",
) -> pl.DataFrame:
    """Return per-date feed conversion ratio using forward-filled egg weight.

    FCR = feed_grams / egg_mass_grams
    egg_mass_grams = total_eggs * egg_weight_grams (forward-filled)

    Days without feed data or before first pallet measurement get null FCR.
    Returns columns: [registration_date, fcr, is_measured_weight].
    """
    if feed_df.is_empty() or egg_df.is_empty():
        return pl.DataFrame(
            {
                date_col: pl.Series([], dtype=pl.Date),
                "fcr": pl.Series([], dtype=pl.Float64),
                "is_measured_weight": pl.Series([], dtype=pl.Boolean),
            }
        )

    base = feed_df.select([date_col, feed_col]).join(
        egg_df.select([date_col, egg_total_col]),
        on=date_col,
        how="inner",
    )
    base = join_forward_filled_weight(
        base, pallet_df, date_col=date_col, weight_col=weight_col
    )
    result = (
        base.with_columns(
            pl.when(
                pl.col("egg_weight_grams_filled").is_not_null()
                & (pl.col("egg_weight_grams_filled") > 0)
                & (pl.col(egg_total_col) > 0)
            )
            .then(
                pl.col(feed_col)
                / (pl.col(egg_total_col) * pl.col("egg_weight_grams_filled"))
            )
            .otherwise(pl.lit(None))
            .alias("fcr")
        )
        .rename({"is_measured": "is_measured_weight"})
        .select([date_col, "fcr", "is_measured_weight"])
    )
    return result


# ---------------------------------------------------------------------------
# Cumulative KPIs per placed hen
# ---------------------------------------------------------------------------


def cumulative_kpis_per_placed_hen(
    egg_df: pl.DataFrame,
    feed_df: pl.DataFrame,
    pallet_df: pl.DataFrame,
    initial_bird_count: int,
    *,
    date_col: str = "registration_date",
    egg_total_col: str = "total_eggs",
    feed_col: str = "feed_grams",
    weight_col: str = "egg_weight_grams",
) -> dict[str, float | None]:
    """Return cumulative production KPIs per placed (initial) hen.

    Returns a dict with:
      eggs_per_placed_hen, egg_kg_per_placed_hen,
      feed_kg_per_placed_hen, cum_fcr.
    All values are None when data is insufficient.
    """
    if initial_bird_count <= 0:
        return {
            "eggs_per_placed_hen": None,
            "egg_kg_per_placed_hen": None,
            "feed_kg_per_placed_hen": None,
            "cum_fcr": None,
        }

    total_eggs = egg_df[egg_total_col].sum() if not egg_df.is_empty() else 0
    total_feed_g = feed_df[feed_col].sum() if not feed_df.is_empty() else 0

    # Egg mass: sum(total_eggs * egg_weight per day using forward-fill)
    if not egg_df.is_empty() and not pallet_df.is_empty():
        base = join_forward_filled_weight(
            egg_df.select([date_col, egg_total_col]),
            pallet_df,
            date_col=date_col,
            weight_col=weight_col,
        )
        egg_mass_g = (
            (base[egg_total_col] * base["egg_weight_grams_filled"]).drop_nulls().sum()
        )
    else:
        egg_mass_g = 0.0

    eggs_per_hen = total_eggs / initial_bird_count
    egg_kg_per_hen = (egg_mass_g / 1000.0) / initial_bird_count if egg_mass_g else None
    feed_kg_per_hen = (total_feed_g / 1000.0) / initial_bird_count

    cum_fcr: float | None = None
    if egg_mass_g and egg_mass_g > 0:
        cum_fcr = float(Decimal(str(total_feed_g)) / Decimal(str(egg_mass_g)))

    return {
        "eggs_per_placed_hen": float(eggs_per_hen),
        "egg_kg_per_placed_hen": float(egg_kg_per_hen)
        if egg_kg_per_hen is not None
        else None,
        "feed_kg_per_placed_hen": float(feed_kg_per_hen),
        "cum_fcr": cum_fcr,
    }


# ---------------------------------------------------------------------------
# Norm curve helpers
# ---------------------------------------------------------------------------


def normalize_breed_key(breed: str | None) -> str | None:
    """Normalise a flock breed string to a breed_key for norm lookup.

    Lowercases, strips accents, replaces spaces/hyphens with underscores,
    and removes characters other than letters, digits, and underscores.

    Examples:
        "DEKALB WHITE SCHARREL EN VOLIÈRE" -> "dekalb_white_scharrel_en_voliere"
        "Dekalb Wit"                       -> "dekalb_wit"
        None                               -> None
    """
    if not breed or not breed.strip():
        return None

    normalised = unicodedata.normalize("NFD", breed.strip())
    without_accents = "".join(c for c in normalised if unicodedata.category(c) != "Mn")
    lowered = without_accents.lower()
    with_underscores = lowered.replace(" ", "_").replace("-", "_")
    clean = "".join(c for c in with_underscores if c.isalnum() or c == "_")
    clean = clean.strip("_")
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean or None


def join_norms_by_age_week(
    df: pl.DataFrame,
    norm_df: pl.DataFrame,
    *,
    flock_week_col: str = "flock_week",
    norm_week_col: str = "age_weeks",
) -> pl.DataFrame:
    """Left-join norm curve values onto df on flock_week = age_weeks.

    norm_df is expected to be the result of a `list_by_breed_key` query,
    already filtered to the correct breed. All norm columns are appended.
    Weeks not present in norm_df get null for norm columns.
    """
    if norm_df.is_empty():
        return df

    norm_renamed = norm_df.rename({norm_week_col: flock_week_col})
    cols_to_join = [flock_week_col] + [
        c for c in norm_renamed.columns if c != flock_week_col
    ]
    return df.join(norm_renamed.select(cols_to_join), on=flock_week_col, how="left")


# ---------------------------------------------------------------------------
# Rolling average
# ---------------------------------------------------------------------------


def add_rolling_average(
    df: pl.DataFrame,
    value_col: str,
    *,
    window: int = 7,
    output_col: str | None = None,
    date_col: str = "registration_date",
) -> pl.DataFrame:
    """Add a rolling N-day mean column sorted by date_col.

    The output column is named `<value_col>_rolling{window}` by default.
    """
    out_col = output_col or f"{value_col}_rolling{window}"
    return df.sort(date_col).with_columns(
        pl.col(value_col).rolling_mean(window_size=window).alias(out_col)
    )
