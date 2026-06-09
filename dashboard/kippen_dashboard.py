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
    mo.md(
        """
        # Kippen Dashboard

        Productieanalyse per koppel — trends, legpercentage, voederconversie en
        vergelijking met de Dekalb White normcurve.
        """
    )
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
    """Filter: huis en koppel."""
    house_options = (
        df_flocks.select("house_id").unique().sort("house_id")["house_id"].to_list()
    )
    house_filter = mo.ui.dropdown(
        options=house_options,
        value=house_options[0] if house_options else None,
        label="Stal",
    )

    flocks_for_house = df_flocks.filter(pl.col("house_id") == house_filter.value)

    flock_options = {
        str(row["id"]): (
            f"{row['flock_name']} "
            f"({row['placement_date']} – {row['end_date'] or 'heden'})"
        )
        for row in flocks_for_house.to_dicts()
    }

    active_flock_ids = (
        flocks_for_house.filter(pl.col("is_active")).select("id")["id"].to_list()
    )
    default_flock_id = (
        str(active_flock_ids[0])
        if active_flock_ids
        else (list(flock_options.keys())[0] if flock_options else None)
    )

    flock_filter = mo.ui.dropdown(
        options=flock_options,
        value=default_flock_id,
        label="Koppel",
    )
    return (
        default_flock_id,
        flock_filter,
        flock_options,
        flocks_for_house,
        house_filter,
        house_options,
    )


@app.cell
def _(date, df_flocks, flock_filter, mo, pl):
    """Selecteer het actieve koppel en bepaal het datumbereik."""
    selected_flock_id = int(flock_filter.value) if flock_filter.value else None
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
        row = selected_flock_rows.to_dicts()[0]
        selected_flock = row
        flock_start = row["placement_date"]
        flock_end = row["end_date"] or date.today()
        flock_dob = row["date_of_birth"]
        bird_count = row["bird_count"] or 0
        flock_breed = row["breed"]

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
            rolling_switch,
            show_norms_switch,
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
        date_from, date_to = date_range_filter.value
        df_eggs = pl.read_database_uri(
            query=f"""
            SELECT
                registration_date,
                first_quality_eggs,
                second_quality_eggs,
                total_eggs
            FROM egg_registrations
            WHERE flock_id = {selected_flock_id}
              AND registration_date BETWEEN '{date_from}' AND '{date_to}'
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
        date_from, date_to = date_range_filter.value
        df_feed_water = pl.read_database_uri(
            query=f"""
            SELECT
                registration_date,
                water_ml,
                feed_grams
            FROM feed_water_registrations
            WHERE flock_id = {selected_flock_id}
              AND registration_date BETWEEN '{date_from}' AND '{date_to}'
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
        date_from, date_to = date_range_filter.value
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
              AND found_at::date BETWEEN '{date_from}' AND '{date_to}'
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
        date_from, date_to = date_range_filter.value
        df_outside_nest = pl.read_database_uri(
            query=f"""
            SELECT
                round_at::date AS round_date,
                egg_count
            FROM outside_nest_egg_rounds
            WHERE flock_id = {selected_flock_id}
              AND round_at::date BETWEEN '{date_from}' AND '{date_to}'
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
        date_from, date_to = date_range_filter.value
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
              AND registration_date BETWEEN '{date_from}' AND '{date_to}'
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
def _(
    bird_count,
    date_range_filter,
    df_dead_hens,
    df_eggs,
    df_feed_water,
    df_norms,
    df_pallets,
    flock_dob,
    mo,
    norm_hint,
    selected_flock,
    show_norms_switch,
    transforms,
):
    """KPI-cards bovenin."""
    if selected_flock is None or not date_range_filter.value:
        mo.md("_Geen koppel geselecteerd._")
    else:
        date_from_kpi, date_to_kpi = date_range_filter.value

        # Legpercentage (laatste dag met data)
        if not df_eggs.is_empty():
            last_egg_row = df_eggs.tail(1).to_dicts()[0]
            last_date = last_egg_row["registration_date"]
            last_flock_week = transforms.calculate_flock_week(last_date, flock_dob)
            last_total_eggs = last_egg_row["total_eggs"]

            # Bird count op laatste dag
            dead_count_df = transforms.daily_bird_count(df_dead_hens, bird_count)
            if not dead_count_df.is_empty():
                import polars as _pl

                bird_row = dead_count_df.filter(
                    _pl.col("registration_date") == last_date
                )
                last_bird_count = (
                    bird_row["bird_count"][0] if not bird_row.is_empty() else bird_count
                )
            else:
                last_bird_count = bird_count

            last_lay_pct = (
                last_total_eggs / last_bird_count * 100.0
                if last_bird_count > 0
                else None
            )
        else:
            last_lay_pct = None
            last_flock_week = None
            last_total_eggs = None

        # Totaal eieren in selectie
        total_eggs_selection = (
            int(df_eggs["total_eggs"].sum()) if not df_eggs.is_empty() else 0
        )

        # Gemiddeld eigewicht in selectie (gemiddelde van pallet metingen)
        avg_egg_weight = (
            df_pallets["egg_weight_grams"].mean() if not df_pallets.is_empty() else None
        )

        # Cumulatieve uitval %
        cum_dead = (
            int(df_dead_hens["dead_count"].sum()) if not df_dead_hens.is_empty() else 0
        )
        cum_dead_pct = cum_dead / bird_count * 100.0 if bird_count > 0 else 0.0

        # Norm legpercentage voor huidige flock_week
        norm_lay_pct = None
        if (
            show_norms_switch.value
            and last_flock_week is not None
            and not df_norms.is_empty()
        ):
            import polars as _pl2

            norm_row = df_norms.filter(_pl2.col("age_weeks") == last_flock_week)
            if not norm_row.is_empty():
                norm_lay_pct = norm_row["lay_percentage_norm"][0]

        def _fmt_pct(v):
            return f"{v:.1f}%" if v is not None else "–"

        def _fmt_n(v):
            return f"{v:,}".replace(",", ".") if v is not None else "–"

        def _fmt_g(v):
            return f"{v:.2f} g" if v is not None else "–"

        flock_week_label = (
            f"week {last_flock_week}" if last_flock_week is not None else ""
        )

        cards = mo.hstack(
            [
                mo.stat(
                    label=f"Legpercentage ({flock_week_label})",
                    value=_fmt_pct(last_lay_pct),
                    caption=f"norm {_fmt_pct(norm_lay_pct)}"
                    if norm_lay_pct
                    else "geen norm",
                    bordered=True,
                ),
                mo.stat(
                    label="Totaal eieren (selectie)",
                    value=_fmt_n(total_eggs_selection),
                    bordered=True,
                ),
                mo.stat(
                    label="Gem. eigewicht (selectie)",
                    value=_fmt_g(avg_egg_weight),
                    bordered=True,
                ),
                mo.stat(
                    label="Cumulatieve uitval",
                    value=_fmt_pct(cum_dead_pct),
                    caption=f"{cum_dead} hennen",
                    bordered=True,
                ),
                mo.stat(
                    label="Aanwezige hennen (laatste dag)",
                    value=_fmt_n(
                        last_bird_count if last_total_eggs is not None else bird_count
                    ),
                    caption=f"opgezet: {_fmt_n(bird_count)}",
                    bordered=True,
                ),
            ],
            gap=2,
        )

        if norm_hint:
            mo.vstack(
                [
                    mo.callout(
                        mo.md(
                            f"Geen normcurve gevonden voor ras **{norm_hint}**. "
                            "Controleer of `flocks.breed` overeenkomt met een "
                            "`breed_key` in de `flock_lay_curve_norms` tabel."
                        ),
                        kind="warn",
                    ),
                    cards,
                ]
            )
        else:
            cards
    return (
        avg_egg_weight,
        cards,
        cum_dead,
        cum_dead_pct,
        date_from_kpi,
        date_to_kpi,
        flock_week_label,
        last_bird_count,
        last_flock_week,
        last_lay_pct,
        last_total_eggs,
        norm_lay_pct,
        total_eggs_selection,
    )


if __name__ == "__main__":
    app.run()
