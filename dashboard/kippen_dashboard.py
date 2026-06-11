"""Kippen productie dashboard."""

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full")


@app.cell
def _():
    """Imports en configuratie."""
    import importlib.util
    import os
    from datetime import date, datetime
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl
    from dotenv import load_dotenv

    _repo_root = Path(__file__).parent.parent
    _env_path = _repo_root / ".env"
    load_dotenv(_env_path)

    _transforms_path = Path(__file__).with_name("kippen_transforms.py")
    _transforms_spec = importlib.util.spec_from_file_location(
        "kippen_dashboard_transforms", _transforms_path
    )
    if _transforms_spec is None or _transforms_spec.loader is None:
        raise ImportError(f"Kan kippen transforms niet laden vanaf {_transforms_path}")

    transforms = importlib.util.module_from_spec(_transforms_spec)
    _transforms_spec.loader.exec_module(transforms)
    return alt, date, datetime, mo, os, pl, transforms


@app.cell
def _(os):
    """Database connectie configuratie."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL niet gevonden in .env bestand. "
            "Zorg ervoor dat .env bestaat in de repository root."
        )

    connectorx_database_url = (
        database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        .replace("postgresql+psycopg2://", "postgresql://", 1)
        .replace("postgres+psycopg://", "postgres://", 1)
        .replace("postgres+psycopg2://", "postgres://", 1)
    )
    return (connectorx_database_url,)


@app.cell
def _(mo):
    """Paginatitel."""
    mo.md("# Kippen Productieoverzicht")
    return


@app.cell
def _(connectorx_database_url, pl):
    """Data laden: koppels en huizen."""
    df_flocks = pl.read_database_uri(
        query="""
        SELECT
            id,
            flock_name,
            house_id,
            date_of_birth,
            placement_date,
            end_date,
            bird_count,
            breed,
            is_active
        FROM flocks
        WHERE archived_at IS NULL
        ORDER BY house_id, placement_date DESC
        """,
        uri=connectorx_database_url,
    )
    return (df_flocks,)


@app.cell
def _(df_flocks, mo, pl):
    """Filter: huis."""
    house_options = (
        df_flocks.select("house_id").unique().sort("house_id")["house_id"].to_list()
    )
    house_filter = mo.ui.dropdown(
        options=house_options,
        value=house_options[0] if house_options else None,
        label="Stal",
    )
    return house_filter, house_options


@app.cell
def _(df_flocks, house_filter, mo, pl):
    """Filter: koppel voor gekozen huis."""

    flocks_for_house = df_flocks.filter(pl.col("house_id") == house_filter.value)

    flock_options = {}
    for _flock_row in flocks_for_house.to_dicts():
        _flock_label = (
            f"{_flock_row['flock_name']} "
            f"({_flock_row['placement_date']} - {_flock_row['end_date'] or 'heden'})"
        )
        flock_options[_flock_label] = str(_flock_row["id"])

    active_flock_ids = (
        flocks_for_house.filter(pl.col("is_active")).select("id")["id"].to_list()
    )
    default_flock_id = str(active_flock_ids[0]) if active_flock_ids else None
    default_flock_option = None
    if default_flock_id is not None:
        for _option_label, _option_value in flock_options.items():
            if _option_value == default_flock_id:
                default_flock_option = _option_label
                break
    if default_flock_option is None and flock_options:
        default_flock_option = next(iter(flock_options.keys()))

    flock_filter = mo.ui.dropdown(
        options=flock_options,
        value=default_flock_option,
        label="Koppel",
    )
    return default_flock_id, flock_filter, flock_options, flocks_for_house


@app.cell
def _(date, df_flocks, flock_filter, flock_options, mo, pl):
    """Selecteer het actieve koppel en bepaal het datumbereik."""
    selected_flock_value = flock_filter.value
    if not selected_flock_value:
        selected_flock_id = None
    else:
        selected_flock_key = str(selected_flock_value)
        selected_flock_id_value = flock_options.get(
            selected_flock_key, selected_flock_key
        )
        selected_flock_id = int(selected_flock_id_value)
    selected_flock_rows = (
        df_flocks.filter(pl.col("id") == selected_flock_id)
        if selected_flock_id is not None
        else df_flocks.head(0)
    )

    if selected_flock_rows.is_empty():
        selected_flock = None
        flock_start = date.today()
        flock_end = date.today()
        flock_dob = date.today()
        bird_count = 0
        flock_breed = None
    else:
        _selected_row = selected_flock_rows.to_dicts()[0]
        selected_flock = _selected_row
        flock_start = _selected_row["placement_date"]
        flock_end = _selected_row["end_date"] or date.today()
        flock_dob = _selected_row["date_of_birth"]
        bird_count = _selected_row["bird_count"] or 0
        flock_breed = _selected_row["breed"]

    date_range_filter = mo.ui.date_range(
        label="Datumbereik",
        value=(str(flock_start), str(min(flock_end, date.today()))),
        start=str(flock_start),
        stop=str(min(flock_end, date.today())),
    )

    rolling_switch = mo.ui.switch(
        label="Toon 7-daags voortschrijdend gemiddelde",
        value=True,
    )

    show_norms_switch = mo.ui.switch(
        label="Toon normcurve",
        value=True,
    )
    return (
        bird_count,
        date_range_filter,
        flock_breed,
        flock_dob,
        flock_end,
        flock_start,
        rolling_switch,
        selected_flock,
        selected_flock_id,
        show_norms_switch,
    )


@app.cell
def _(
    date_range_filter, flock_filter, house_filter, mo, rolling_switch, show_norms_switch
):
    """Filter UI weergave."""
    mo.hstack(
        [
            house_filter,
            flock_filter,
            date_range_filter,
        ],
        gap=2,
    )
    return


@app.cell
def _(connectorx_database_url, date_range_filter, pl, selected_flock_id):
    """Data laden: eiregistraties voor geselecteerd koppel + datumbereik."""
    if selected_flock_id is None or not date_range_filter.value:
        df_eggs = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "first_quality_eggs": pl.Series([], dtype=pl.Int64),
                "second_quality_eggs": pl.Series([], dtype=pl.Int64),
                "total_eggs": pl.Series([], dtype=pl.Int64),
            }
        )
    else:
        _date_from, _date_to = date_range_filter.value
        df_eggs = pl.read_database_uri(
            query=f"""
            SELECT
                registration_date,
                first_quality_eggs,
                second_quality_eggs,
                total_eggs
            FROM egg_registrations
            WHERE flock_id = {selected_flock_id}
              AND registration_date BETWEEN '{_date_from}' AND '{_date_to}'
            ORDER BY registration_date
            """,
            uri=connectorx_database_url,
        )
    return (df_eggs,)


@app.cell
def _(connectorx_database_url, date_range_filter, pl, selected_flock_id):
    """Data laden: water en voer registraties."""
    if selected_flock_id is None or not date_range_filter.value:
        df_feed_water = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "water_ml": pl.Series([], dtype=pl.Int64),
                "feed_grams": pl.Series([], dtype=pl.Int64),
            }
        )
    else:
        _date_from, _date_to = date_range_filter.value
        df_feed_water = pl.read_database_uri(
            query=f"""
            SELECT
                registration_date,
                water_ml,
                feed_grams
            FROM feed_water_registrations
            WHERE flock_id = {selected_flock_id}
              AND registration_date BETWEEN '{_date_from}' AND '{_date_to}'
            ORDER BY registration_date
            """,
            uri=connectorx_database_url,
        )
    return (df_feed_water,)


@app.cell
def _(connectorx_database_url, date_range_filter, pl, selected_flock_id):
    """Data laden: dode hennen."""
    if selected_flock_id is None or not date_range_filter.value:
        df_dead_hens = pl.DataFrame(
            {
                "found_date": pl.Series([], dtype=pl.Date),
                "dead_count": pl.Series([], dtype=pl.Int64),
                "stable_side": pl.Series([], dtype=pl.String),
                "found_place": pl.Series([], dtype=pl.String),
                "suspected_cause": pl.Series([], dtype=pl.String),
            }
        )
    else:
        _date_from, _date_to = date_range_filter.value
        df_dead_hens = pl.read_database_uri(
            query=f"""
            SELECT
                found_at::date AS found_date,
                count AS dead_count,
                stable_side,
                found_place,
                suspected_cause
            FROM dead_hen_registrations
            WHERE flock_id = {selected_flock_id}
              AND found_at::date BETWEEN '{_date_from}' AND '{_date_to}'
            ORDER BY found_at
            """,
            uri=connectorx_database_url,
        )
    return (df_dead_hens,)


@app.cell
def _(connectorx_database_url, date_range_filter, pl, selected_flock_id):
    """Data laden: buitennest rondes."""
    if selected_flock_id is None or not date_range_filter.value:
        df_outside_nest = pl.DataFrame(
            {
                "round_date": pl.Series([], dtype=pl.Date),
                "egg_count": pl.Series([], dtype=pl.Int64),
            }
        )
    else:
        _date_from, _date_to = date_range_filter.value
        df_outside_nest = pl.read_database_uri(
            query=f"""
            SELECT
                round_at::date AS round_date,
                egg_count
            FROM outside_nest_egg_rounds
            WHERE flock_id = {selected_flock_id}
              AND round_at::date BETWEEN '{_date_from}' AND '{_date_to}'
            ORDER BY round_at
            """,
            uri=connectorx_database_url,
        )
    return (df_outside_nest,)


@app.cell
def _(connectorx_database_url, date_range_filter, pl, selected_flock_id):
    """Data laden: palletgewicht registraties."""
    if selected_flock_id is None or not date_range_filter.value:
        df_pallets = pl.DataFrame(
            {
                "registration_date": pl.Series([], dtype=pl.Date),
                "pallet_weight_kg": pl.Series([], dtype=pl.Float64),
                "empty_packaging_weight_kg": pl.Series([], dtype=pl.Float64),
                "egg_weight_grams": pl.Series([], dtype=pl.Float64),
                "supplier_name": pl.Series([], dtype=pl.String),
            }
        )
    else:
        _date_from, _date_to = date_range_filter.value
        df_pallets = pl.read_database_uri(
            query=f"""
            SELECT
                registration_date,
                pallet_weight_kg::float AS pallet_weight_kg,
                empty_packaging_weight_kg::float AS empty_packaging_weight_kg,
                egg_weight_grams::float AS egg_weight_grams,
                supplier_name
            FROM egg_pallet_weight_registrations
            WHERE flock_id = {selected_flock_id}
              AND registration_date BETWEEN '{_date_from}' AND '{_date_to}'
            ORDER BY registration_date
            """,
            uri=connectorx_database_url,
        )
    return (df_pallets,)


@app.cell
def _(connectorx_database_url, flock_breed, pl, transforms):
    """Data laden: normcurve voor het geselecteerde ras."""
    breed_key = transforms.normalize_breed_key(flock_breed)

    if breed_key is None:
        df_norms = pl.DataFrame({"age_weeks": pl.Series([], dtype=pl.Int32)})
        norm_hint = flock_breed
    else:
        df_norms = pl.read_database_uri(
            query=f"""
            SELECT
                age_weeks,
                lay_percentage::float          AS lay_percentage_norm,
                egg_weight_grams::float        AS egg_weight_grams_norm,
                egg_mass_grams::float          AS egg_mass_grams_norm,
                feed_intake_grams_per_day::float AS feed_intake_grams_per_day_norm,
                feed_conversion_ratio::float   AS feed_conversion_ratio_norm,
                liveability_percentage::float  AS liveability_percentage_norm,
                cumulative_eggs_per_placed_hen::float     AS cumulative_eggs_per_placed_hen_norm,
                cumulative_egg_kg_per_placed_hen::float   AS cumulative_egg_kg_per_placed_hen_norm,
                cumulative_feed_kg_per_placed_hen::float  AS cumulative_feed_kg_per_placed_hen_norm,
                cumulative_feed_conversion_ratio::float   AS cumulative_feed_conversion_ratio_norm
            FROM flock_lay_curve_norms
            WHERE breed_key = '{breed_key}'
            ORDER BY age_weeks
            """,
            uri=connectorx_database_url,
        )
        norm_hint = None if not df_norms.is_empty() else flock_breed

    return breed_key, df_norms, norm_hint


@app.cell
def _(df_norms, flock_dob, transforms):
    """Normcurve projecteren naar kalenderdatums van het koppel."""
    df_norms_by_date = transforms.norm_dates_for_flock(df_norms, flock_dob)
    return (df_norms_by_date,)


@app.cell
def _(
    bird_count,
    date,
    date_range_filter,
    df_dead_hens,
    df_eggs,
    df_feed_water,
    df_norms,
    df_outside_nest,
    df_pallets,
    flock_dob,
    pl,
    rolling_switch,
    transforms,
):
    """Per-dag analysetabel met werkelijke en norm-kolommen."""
    if not date_range_filter.value:
        df_daily_overview = pl.DataFrame(
            {"registration_date": pl.Series([], dtype=pl.Date)}
        )
    else:
        _date_from, _date_to = date_range_filter.value
        date_from_value = (
            _date_from
            if isinstance(_date_from, date)
            else date.fromisoformat(_date_from)
        )
        date_to_value = (
            _date_to if isinstance(_date_to, date) else date.fromisoformat(_date_to)
        )
        base_df = pl.DataFrame(
            {
                "registration_date": pl.date_range(
                    date_from_value,
                    date_to_value,
                    interval="1d",
                    eager=True,
                )
            }
        )

        dead_daily = transforms.daily_bird_count(df_dead_hens, bird_count)
        if dead_daily.is_empty():
            dead_daily = base_df.select("registration_date").with_columns(
                pl.lit(0).alias("dead_today"),
                pl.lit(0).alias("cum_dead"),
                pl.lit(bird_count).alias("bird_count"),
            )

        daily_birds = (
            base_df.join(dead_daily, on="registration_date", how="left")
            .with_columns(
                pl.col("dead_today").fill_null(0),
                pl.col("cum_dead").forward_fill().fill_null(0),
                pl.col("bird_count").forward_fill().fill_null(bird_count),
            )
            .with_columns(
                pl.when(pl.lit(bird_count) > 0)
                .then(pl.col("cum_dead") / bird_count * 100.0)
                .otherwise(pl.lit(None))
                .alias("cum_dead_pct")
            )
        )

        outside_daily = (
            df_outside_nest.group_by("round_date")
            .agg(pl.col("egg_count").sum().alias("outside_nest_eggs"))
            .rename({"round_date": "registration_date"})
            if not df_outside_nest.is_empty()
            else base_df.select("registration_date").with_columns(
                pl.lit(0).alias("outside_nest_eggs")
            )
        )

        measured_weights = (
            df_pallets.group_by("registration_date").agg(
                pl.col("egg_weight_grams").mean().alias("egg_weight_avg_measured"),
                pl.col("pallet_weight_kg").sum().alias("pallet_weight_kg_total"),
                pl.len().alias("pallet_count"),
            )
            if not df_pallets.is_empty()
            else base_df.select("registration_date").with_columns(
                pl.lit(None).cast(pl.Float64).alias("egg_weight_avg_measured"),
                pl.lit(None).cast(pl.Float64).alias("pallet_weight_kg_total"),
                pl.lit(0).alias("pallet_count"),
            )
        )

        _lay_pct_df = transforms.daily_lay_percentage(df_eggs, daily_birds)
        _weight_filled_df = transforms.join_forward_filled_weight(
            base_df,
            df_pallets,
        )

        df_daily_overview = (
            base_df.join(
                df_eggs,
                on="registration_date",
                how="left",
            )
            .join(df_feed_water, on="registration_date", how="left")
            .join(daily_birds, on="registration_date", how="left")
            .join(outside_daily, on="registration_date", how="left")
            .join(measured_weights, on="registration_date", how="left")
            .join(_weight_filled_df, on="registration_date", how="left")
            .join(_lay_pct_df, on="registration_date", how="left")
            .with_columns(
                pl.col("first_quality_eggs").fill_null(0),
                pl.col("second_quality_eggs").fill_null(0),
                pl.col("outside_nest_eggs").fill_null(0),
                pl.col("pallet_count").fill_null(0),
                pl.col("is_measured").fill_null(False),
            )
        )

        df_daily_overview = transforms.add_flock_week_column(
            df_daily_overview,
            "registration_date",
            flock_dob,
        )
        df_daily_overview = transforms.join_norms_by_age_week(
            df_daily_overview,
            df_norms,
        )
        for norm_col in [
            "lay_percentage_norm",
            "egg_weight_grams_norm",
            "egg_mass_grams_norm",
            "feed_intake_grams_per_day_norm",
            "feed_conversion_ratio_norm",
            "liveability_percentage_norm",
            "cumulative_eggs_per_placed_hen_norm",
            "cumulative_egg_kg_per_placed_hen_norm",
            "cumulative_feed_kg_per_placed_hen_norm",
            "cumulative_feed_conversion_ratio_norm",
        ]:
            if norm_col not in df_daily_overview.columns:
                df_daily_overview = df_daily_overview.with_columns(
                    pl.lit(None).cast(pl.Float64).alias(norm_col)
                )
        df_daily_overview = df_daily_overview.with_columns(
            pl.col("registration_date")
            .sub(pl.lit(flock_dob))
            .dt.total_days()
            .alias("curve_day"),
            pl.col("egg_weight_avg_measured").alias("egg_weight_grams_actual"),
            (pl.col("total_eggs") * pl.col("egg_weight_grams_filled")).alias(
                "egg_mass_grams"
            ),
            pl.col("feed_grams").alias("feed_intake_grams_per_day_actual"),
            pl.when(pl.col("feed_grams").is_not_null() & (pl.col("bird_count") > 0))
            .then(pl.col("feed_grams") * pl.col("bird_count"))
            .otherwise(pl.lit(None))
            .alias("total_feed_grams"),
            pl.when(
                pl.col("feed_grams").is_not_null()
                & pl.col("egg_weight_avg_measured").is_not_null()
                & (pl.col("egg_weight_avg_measured") > 0)
                & pl.col("total_eggs").is_not_null()
                & (pl.col("total_eggs") > 0)
                & (pl.col("bird_count") > 0)
            )
            .then(
                (pl.col("feed_grams") * pl.col("bird_count"))
                / (pl.col("total_eggs") * pl.col("egg_weight_avg_measured"))
            )
            .otherwise(pl.lit(None))
            .alias("fcr_actual"),
            pl.when(pl.lit(bird_count) > 0)
            .then(100.0 - pl.col("cum_dead_pct"))
            .otherwise(pl.lit(None))
            .alias("liveability_percentage"),
            pl.col("total_eggs").fill_null(0).cum_sum().alias("cumulative_total_eggs"),
        ).with_columns(
            pl.when(pl.lit(bird_count) > 0)
            .then(pl.col("cumulative_total_eggs") / bird_count)
            .otherwise(pl.lit(None))
            .alias("cumulative_eggs_per_placed_hen"),
        )

        if rolling_switch.value:
            df_daily_overview = transforms.add_rolling_average(
                df_daily_overview,
                "feed_grams",
                window=7,
            )
            df_daily_overview = transforms.add_rolling_average(
                df_daily_overview,
                "water_ml",
                window=7,
            )
            df_daily_overview = transforms.add_rolling_average(
                df_daily_overview,
                "lay_percentage",
                window=7,
            )
            df_daily_overview = transforms.add_rolling_average(
                df_daily_overview,
                "fcr_actual",
                window=7,
            )

        df_daily_overview = df_daily_overview.select(
            [
                "registration_date",
                "flock_week",
                "curve_day",
                "bird_count",
                "dead_today",
                "cum_dead",
                "cum_dead_pct",
                "first_quality_eggs",
                "second_quality_eggs",
                "total_eggs",
                "lay_percentage",
                "lay_percentage_norm",
                "outside_nest_eggs",
                "water_ml",
                "feed_grams",
                "feed_intake_grams_per_day_actual",
                "total_feed_grams",
                "feed_intake_grams_per_day_norm",
                "egg_weight_avg_measured",
                "egg_weight_grams_actual",
                "egg_weight_grams_filled",
                "egg_weight_grams_norm",
                "egg_mass_grams",
                "egg_mass_grams_norm",
                "pallet_weight_kg_total",
                "pallet_count",
                "fcr_actual",
                "feed_conversion_ratio_norm",
                "liveability_percentage",
                "liveability_percentage_norm",
                "cumulative_eggs_per_placed_hen",
                "cumulative_eggs_per_placed_hen_norm",
                "cumulative_egg_kg_per_placed_hen_norm",
                "cumulative_feed_kg_per_placed_hen_norm",
                "cumulative_feed_conversion_ratio_norm",
                "is_measured",
                *(
                    [
                        "feed_grams_rolling7",
                        "water_ml_rolling7",
                        "lay_percentage_rolling7",
                    ]
                    if rolling_switch.value
                    else []
                ),
            ]
        ).sort("registration_date")

    return (df_daily_overview,)


@app.cell
def _(
    alt,
    date,
    df_daily_overview,
    df_norms,
    flock_dob,
    mo,
    pl,
    selected_flock,
    transforms,
):
    """Datatabel, CSV-download en buitennest-grafiek onderaan de pagina."""
    if selected_flock is None or df_daily_overview.is_empty():
        daily_table_section = mo.callout(
            mo.md("Geen dagoverzicht beschikbaar voor de huidige selectie."),
            kind="info",
        )
    else:

        def _format_overview_table(df: pl.DataFrame) -> pl.DataFrame:
            return (
                df.select(
                    [
                        "registration_date",
                        "flock_week",
                        "curve_day",
                        "lay_percentage",
                        "lay_percentage_norm",
                        "egg_weight_grams_actual",
                        "egg_weight_grams_norm",
                        "feed_intake_grams_per_day_actual",
                        "feed_intake_grams_per_day_norm",
                        "fcr_actual",
                        "feed_conversion_ratio_norm",
                        "liveability_percentage",
                        "liveability_percentage_norm",
                        "cumulative_eggs_per_placed_hen",
                        "cumulative_eggs_per_placed_hen_norm",
                    ]
                )
                .with_columns(
                    pl.col("registration_date").cast(pl.String),
                    pl.col("curve_day").cast(pl.Int64),
                    pl.col("lay_percentage").round(2),
                    pl.col("lay_percentage_norm").round(2),
                    pl.col("egg_weight_grams_actual").round(1),
                    pl.col("egg_weight_grams_norm").round(1),
                    pl.col("feed_intake_grams_per_day_actual").round(0).cast(pl.Int64),
                    pl.col("feed_intake_grams_per_day_norm").round(0).cast(pl.Int64),
                    pl.col("fcr_actual").round(2),
                    pl.col("feed_conversion_ratio_norm").round(2),
                    pl.col("liveability_percentage").round(2),
                    pl.col("liveability_percentage_norm").round(2),
                    pl.col("cumulative_eggs_per_placed_hen").round(1),
                    pl.col("cumulative_eggs_per_placed_hen_norm").round(1),
                )
                .rename(
                    {
                        "registration_date": "Datum",
                        "flock_week": "Week",
                        "curve_day": "Curve dag",
                        "lay_percentage": "Legpercentage %",
                        "lay_percentage_norm": "Norm legpercentage %",
                        "egg_weight_grams_actual": "Eigewicht g",
                        "egg_weight_grams_norm": "Norm eigewicht g",
                        "feed_intake_grams_per_day_actual": "Voeropname g/dag",
                        "feed_intake_grams_per_day_norm": "Norm voeropname g/dag",
                        "fcr_actual": "FCR",
                        "feed_conversion_ratio_norm": "Norm FCR",
                        "liveability_percentage": "Leefbaarheid %",
                        "liveability_percentage_norm": "Norm leefbaarheid %",
                        "cumulative_eggs_per_placed_hen": "Cum. eieren / opgezette hen",
                        "cumulative_eggs_per_placed_hen_norm": "Norm cum. eieren/hen",
                    }
                )
            )

        table_df = _format_overview_table(df_daily_overview)
        weekly_overview_df = transforms.weekly_overview_from_daily(df_daily_overview)
        weekly_actual_df = weekly_overview_df.select(
            [
                "flock_week",
                "lay_percentage",
                "egg_weight_grams_actual",
                "feed_intake_grams_per_day_actual",
                "fcr_actual",
                "liveability_percentage",
                "cumulative_eggs_per_placed_hen",
            ]
        )
        weekly_norm_scaffold_df = df_norms.select(
            [
                "age_weeks",
                "lay_percentage_norm",
                "egg_weight_grams_norm",
                "feed_intake_grams_per_day_norm",
                "feed_conversion_ratio_norm",
                "liveability_percentage_norm",
                "cumulative_eggs_per_placed_hen_norm",
            ]
        ).with_columns(
            (pl.lit(flock_dob) + pl.duration(days=pl.col("age_weeks") * 7 + 7)).alias(
                "registration_date"
            ),
            pl.col("age_weeks").alias("flock_week"),
            (pl.col("age_weeks") * 7 + 6).alias("curve_day"),
        )
        weekly_table_source_df = (
            weekly_norm_scaffold_df.drop("age_weeks")
            .join(weekly_actual_df, on="flock_week", how="left")
            .sort("flock_week")
        )
        weekly_table_df = _format_overview_table(weekly_table_source_df)
        current_flock_week = transforms.calculate_flock_week(date.today(), flock_dob)
        weekly_quality_df = (
            df_daily_overview.group_by("flock_week")
            .agg(
                pl.len().alias("row_count"),
                pl.col("lay_percentage").count().alias("lay_count"),
                pl.col("egg_weight_grams_actual").count().alias("egg_weight_count"),
                pl.col("feed_intake_grams_per_day_actual").count().alias("feed_count"),
                pl.col("fcr_actual").count().alias("fcr_count"),
                pl.col("liveability_percentage").count().alias("liveability_count"),
            )
            .with_columns(
                (
                    (pl.col("row_count") < 7)
                    | (pl.col("lay_count") < pl.col("row_count"))
                    | (pl.col("egg_weight_count") < pl.col("row_count"))
                    | (pl.col("feed_count") < pl.col("row_count"))
                    | (pl.col("fcr_count") < pl.col("row_count"))
                    | (pl.col("liveability_count") < pl.col("row_count"))
                ).alias("is_incomplete_week")
            )
            .select(["flock_week", "is_incomplete_week"])
        )
        weekly_table_with_flags = weekly_table_df.join(
            weekly_quality_df, left_on="Week", right_on="flock_week", how="left"
        ).with_columns(
            pl.col("is_incomplete_week").fill_null(False),
            (pl.col("Week") == current_flock_week).alias("is_active_week"),
        )

        csv_download = mo.download(
            data=df_daily_overview.write_csv().encode("utf-8"),
            filename="kippen-dagoverzicht.csv",
            mimetype="text/csv",
            label="Download CSV",
        )
        weekly_csv_download = mo.download(
            data=weekly_table_df.write_csv().encode("utf-8"),
            filename="kippen-weekoverzicht.csv",
            mimetype="text/csv",
            label="Download week CSV",
        )
        daily_table = mo.ui.table(
            table_df.to_pandas(),
            selection=None,
            page_size=20,
            label="Per-dag overzicht met werkelijke en normwaarden",
        )
        weekly_table = mo.ui.table(
            weekly_table_with_flags.drop(
                ["is_active_week", "is_incomplete_week"]
            ).to_pandas(),
            selection=None,
            page_size=100,
            label="Per-week overzicht met werkelijke en normwaarden",
        )
        outside_nest_chart_df = (
            df_daily_overview.select(["registration_date", "outside_nest_eggs"])
            .filter(pl.col("outside_nest_eggs") > 0)
            .with_columns(
                pl.col("registration_date").dt.strftime("%d-%m-%Y").alias("date_label")
            )
        )

        if outside_nest_chart_df.is_empty():
            outside_nest_chart = mo.callout(
                mo.md("Geen buitennest-eieren in de huidige selectie."),
                kind="info",
            )
        else:
            outside_nest_chart_pd = outside_nest_chart_df.to_pandas()
            base_chart = alt.Chart(outside_nest_chart_pd).encode(
                x=alt.X(
                    "date_label:N",
                    title="Datum",
                    sort=None,
                    axis=alt.Axis(labelAngle=-45),
                ),
                y=alt.Y("outside_nest_eggs:Q", title="Buitennest eieren"),
            )

            outside_nest_chart = mo.ui.altair_chart(
                (
                    base_chart.mark_bar(color="#e67e22")
                    + base_chart.mark_text(
                        dy=-8,
                        color="#784212",
                    ).encode(text=alt.Text("outside_nest_eggs:Q", format=".0f"))
                ).properties(
                    width=900,
                    height=320,
                    title="Buitennest eieren per dag",
                )
            )

        daily_table_section = mo.vstack(
            [
                weekly_csv_download,
                weekly_table,
                csv_download,
                daily_table,
                outside_nest_chart,
            ],
            gap=1,
        )

    daily_table_section
    return (daily_table_section,)


if __name__ == "__main__":
    app.run()
