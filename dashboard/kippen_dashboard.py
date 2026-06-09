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
def _(df_norms, flock_dob, transforms):
    """Normcurve projecteren naar kalenderdatums van het koppel."""
    df_norms_by_date = transforms.norm_dates_for_flock(df_norms, flock_dob)
    return (df_norms_by_date,)


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


@app.cell
def _(
    bird_count,
    cum_dead_pct,
    date_range_filter,
    df_eggs,
    df_feed_water,
    df_norms,
    df_pallets,
    last_flock_week,
    mo,
    selected_flock,
    show_norms_switch,
    transforms,
):
    """Cumulatieve KPI's per opgezette hen vergeleken met de norm."""
    if selected_flock is None or not date_range_filter.value:
        cumulative_kpi_block = mo.md("")
    else:
        actual = transforms.cumulative_kpis_per_placed_hen(
            df_eggs,
            df_feed_water,
            df_pallets,
            bird_count,
        )
        actual["liveability_percentage"] = (
            100.0 - cum_dead_pct if bird_count > 0 else None
        )

        norm_row = None
        if show_norms_switch.value and last_flock_week is not None:
            norm_row = transforms.get_norm_for_flock_week(df_norms, last_flock_week)

        def _fmt(value, precision=2, unit=""):
            if value is None:
                return "-"
            return f"{value:.{precision}f}{unit}"

        rows = [
            (
                "Eieren per opgezette hen",
                actual["eggs_per_placed_hen"],
                "cumulative_eggs_per_placed_hen_norm",
                1,
                "",
            ),
            (
                "Kg ei per opgezette hen",
                actual["egg_kg_per_placed_hen"],
                "cumulative_egg_kg_per_placed_hen_norm",
                2,
                " kg",
            ),
            (
                "Kg voer per opgezette hen",
                actual["feed_kg_per_placed_hen"],
                "cumulative_feed_kg_per_placed_hen_norm",
                2,
                " kg",
            ),
            (
                "Cumulatieve FCR",
                actual["cum_fcr"],
                "cumulative_feed_conversion_ratio_norm",
                3,
                "",
            ),
            (
                "Leefbaarheid",
                actual["liveability_percentage"],
                "liveability_percentage_norm",
                1,
                "%",
            ),
        ]

        table_rows = []
        for label, actual_value, norm_key, precision, unit in rows:
            norm_value = norm_row.get(norm_key) if norm_row else None
            delta = transforms.format_norm_delta(
                actual_value,
                norm_value,
                unit=unit,
                precision=precision,
            )
            table_rows.append(
                "| "
                f"{label} | {_fmt(actual_value, precision, unit)} | "
                f"{_fmt(norm_value, precision, unit)} | {delta or '-'} |"
            )

        cumulative_kpi_block = mo.md(
            "\n".join(
                [
                    "## Cumulatief vs norm",
                    "",
                    "| KPI | Werkelijk | Norm | Delta |",
                    "|---|---:|---:|---:|",
                    *table_rows,
                ]
            )
        )

    cumulative_kpi_block
    return (cumulative_kpi_block,)


@app.cell
def _(
    alt,
    bird_count,
    date_range_filter,
    df_dead_hens,
    df_eggs,
    df_feed_water,
    df_pallets,
    flock_dob,
    mo,
    pl,
    rolling_switch,
    transforms,
):
    """Chart 1: Voer en water per dag."""
    mo.md("## Voer en water per dag")
    return


@app.cell
def _(
    alt,
    date_range_filter,
    df_feed_water,
    df_norms,
    df_norms_by_date,
    flock_dob,
    mo,
    pl,
    rolling_switch,
    show_norms_switch,
    transforms,
):
    """Chart 1 inhoud: voer en water lijnen."""
    if df_feed_water.is_empty() or not date_range_filter.value:
        chart_feed_water = mo.callout(
            mo.md("Geen voer/water data in deze selectie."), kind="info"
        )
        summary_feed_water = mo.md("")
    else:
        df_fw = transforms.add_flock_week_column(
            df_feed_water.sort("registration_date"),
            "registration_date",
            flock_dob,
        )

        if rolling_switch.value:
            df_fw = transforms.add_rolling_average(df_fw, "feed_grams", window=7)
            df_fw = transforms.add_rolling_average(df_fw, "water_ml", window=7)

        df_fw_pd = df_fw.to_pandas()

        base = alt.Chart(df_fw_pd).encode(
            x=alt.X(
                "registration_date:T", title="Datum", axis=alt.Axis(format="%d-%m")
            ),
        )

        feed_bar = base.mark_bar(color="#c6a84b", opacity=0.5).encode(
            y=alt.Y(
                "feed_grams:Q", title="Voer (gram)", axis=alt.Axis(titleColor="#c6a84b")
            ),
            tooltip=[
                alt.Tooltip("registration_date:T", title="Datum", format="%d-%m-%Y"),
                alt.Tooltip("feed_grams:Q", title="Voer (gram)", format=","),
            ],
        )

        water_line = base.mark_line(color="#3182ce", strokeWidth=2).encode(
            y=alt.Y(
                "water_ml:Q", title="Water (ml)", axis=alt.Axis(titleColor="#3182ce")
            ),
            tooltip=[
                alt.Tooltip("registration_date:T", title="Datum", format="%d-%m-%Y"),
                alt.Tooltip("water_ml:Q", title="Water (ml)", format=","),
            ],
        )

        layers = [feed_bar, water_line]

        if rolling_switch.value and "feed_grams_rolling7" in df_fw_pd.columns:
            layers.append(
                base.mark_line(
                    color="#8B6914", strokeDash=[4, 2], strokeWidth=1.5
                ).encode(
                    y=alt.Y("feed_grams_rolling7:Q"),
                    tooltip=[
                        alt.Tooltip(
                            "feed_grams_rolling7:Q", title="Voer 7d gem.", format=".0f"
                        )
                    ],
                )
            )
        if rolling_switch.value and "water_ml_rolling7" in df_fw_pd.columns:
            layers.append(
                base.mark_line(
                    color="#1a5276", strokeDash=[4, 2], strokeWidth=1.5
                ).encode(
                    y=alt.Y("water_ml_rolling7:Q"),
                    tooltip=[
                        alt.Tooltip(
                            "water_ml_rolling7:Q", title="Water 7d gem.", format=".0f"
                        )
                    ],
                )
            )

        if show_norms_switch.value and not df_norms_by_date.is_empty():
            norm_feed_pd = df_norms_by_date.select(
                [
                    "registration_date",
                    "age_weeks",
                    "feed_intake_grams_per_day_norm",
                ]
            ).to_pandas()
            layers.append(
                alt.Chart(norm_feed_pd)
                .mark_line(color="#6b7280", strokeDash=[6, 4], strokeWidth=2)
                .encode(
                    x=alt.X("registration_date:T"),
                    y=alt.Y("feed_intake_grams_per_day_norm:Q"),
                    tooltip=[
                        alt.Tooltip(
                            "registration_date:T",
                            title="Normdatum",
                            format="%d-%m-%Y",
                        ),
                        alt.Tooltip("age_weeks:Q", title="Leeftijdsweek"),
                        alt.Tooltip(
                            "feed_intake_grams_per_day_norm:Q",
                            title="Norm voer (g/dag)",
                            format=".0f",
                        ),
                    ],
                )
            )

        chart_feed_water = mo.ui.altair_chart(
            alt.layer(*layers)
            .resolve_scale(y="independent")
            .properties(
                width=900, height=300, title="Voer (gram) en water (ml) per dag"
            )
        )

        avg_feed = df_feed_water["feed_grams"].mean()
        avg_water = df_feed_water["water_ml"].mean()
        last_fw = df_fw.tail(1).to_dicts()[0]
        norm_row = transforms.get_norm_for_flock_week(
            df_norms,
            last_fw["flock_week"],
        )
        feed_delta = ""
        if show_norms_switch.value and norm_row:
            feed_delta = transforms.format_norm_delta(
                last_fw["feed_grams"],
                norm_row["feed_intake_grams_per_day_norm"],
                unit=" gram",
                precision=0,
            )
        summary_feed_water = mo.md(
            f"Gemiddeld voer: **{avg_feed:.0f} gram/dag** · "
            f"Gemiddeld water: **{avg_water:.0f} ml/dag**"
            + (f" · Laatste voer vs norm: {feed_delta}" if feed_delta else "")
        )

    mo.vstack([chart_feed_water, summary_feed_water])
    return chart_feed_water, summary_feed_water


@app.cell
def _(alt, date_range_filter, df_outside_nest, mo, pl, rolling_switch, transforms):
    """Chart 2: Buitennest-eieren per dag."""
    mo.md("## Buitennest-eieren per dag")
    return


@app.cell
def _(alt, date_range_filter, df_outside_nest, mo, pl, rolling_switch, transforms):
    """Chart 2 inhoud."""
    if df_outside_nest.is_empty() or not date_range_filter.value:
        chart_outside_nest = mo.callout(
            mo.md("Geen buitennest data in deze selectie."), kind="info"
        )
        summary_outside_nest = mo.md("")
    else:
        df_on = (
            df_outside_nest.group_by("round_date")
            .agg(pl.col("egg_count").sum())
            .sort("round_date")
        )

        if rolling_switch.value:
            df_on = transforms.add_rolling_average(
                df_on, "egg_count", window=7, date_col="round_date"
            )

        df_on_pd = df_on.to_pandas()

        bar = (
            alt.Chart(df_on_pd)
            .mark_bar(color="#e67e22", opacity=0.75)
            .encode(
                x=alt.X("round_date:T", title="Datum", axis=alt.Axis(format="%d-%m")),
                y=alt.Y("egg_count:Q", title="Buitennest eieren"),
                tooltip=[
                    alt.Tooltip("round_date:T", title="Datum", format="%d-%m-%Y"),
                    alt.Tooltip("egg_count:Q", title="Buitennest eieren"),
                ],
            )
        )

        layers_on = [bar]
        if rolling_switch.value and "egg_count_rolling7" in df_on_pd.columns:
            layers_on.append(
                alt.Chart(df_on_pd)
                .mark_line(color="#784212", strokeDash=[4, 2], strokeWidth=1.5)
                .encode(
                    x=alt.X("round_date:T"),
                    y=alt.Y("egg_count_rolling7:Q"),
                    tooltip=[
                        alt.Tooltip(
                            "egg_count_rolling7:Q", title="7d gem.", format=".1f"
                        )
                    ],
                )
            )

        chart_outside_nest = mo.ui.altair_chart(
            alt.layer(*layers_on).properties(
                width=900, height=280, title="Buitennest-eieren per dag"
            )
        )

        avg_on = df_on["egg_count"].mean()
        total_on = int(df_on["egg_count"].sum())
        summary_outside_nest = mo.md(
            f"Totaal buitennest-eieren: **{total_on:,}** · Gemiddeld per dag: **{avg_on:.1f}**"
        )

    mo.vstack([chart_outside_nest, summary_outside_nest])
    return chart_outside_nest, summary_outside_nest


@app.cell
def _(alt, bird_count, date_range_filter, df_dead_hens, mo, pl, transforms):
    """Chart 3: Dode hennen per dag + cumulatieve uitval."""
    mo.md("## Dode hennen en uitval")
    return


@app.cell
def _(
    alt,
    bird_count,
    date_range_filter,
    df_dead_hens,
    df_norms,
    df_norms_by_date,
    flock_dob,
    mo,
    pl,
    show_norms_switch,
    transforms,
):
    """Chart 3 inhoud."""
    if df_dead_hens.is_empty() or not date_range_filter.value:
        chart_dead_hens = mo.callout(
            mo.md("Geen dode-hennen data in deze selectie."), kind="info"
        )
        summary_dead_hens = mo.md("")
    else:
        df_daily_dead = (
            df_dead_hens.group_by("found_date")
            .agg(pl.col("dead_count").sum())
            .sort("found_date")
            .with_columns(pl.col("dead_count").cum_sum().alias("cum_dead"))
        )
        if bird_count > 0:
            df_daily_dead = df_daily_dead.with_columns(
                (pl.col("cum_dead") / bird_count * 100.0).alias("cum_dead_pct")
            )
        df_daily_dead = transforms.add_flock_week_column(
            df_daily_dead.rename({"found_date": "registration_date"}),
            "registration_date",
            flock_dob,
        ).rename({"registration_date": "found_date"})

        df_dd_pd = df_daily_dead.to_pandas()

        bar_dead = (
            alt.Chart(df_dd_pd)
            .mark_bar(color="#c0392b", opacity=0.7)
            .encode(
                x=alt.X("found_date:T", title="Datum", axis=alt.Axis(format="%d-%m")),
                y=alt.Y("dead_count:Q", title="Dode hennen"),
                tooltip=[
                    alt.Tooltip("found_date:T", title="Datum", format="%d-%m-%Y"),
                    alt.Tooltip("dead_count:Q", title="Dode hennen"),
                ],
            )
        )

        layers_dead = [bar_dead]

        if bird_count > 0 and "cum_dead_pct" in df_dd_pd.columns:
            line_cum = (
                alt.Chart(df_dd_pd)
                .mark_line(color="#7b241c", strokeWidth=2)
                .encode(
                    x=alt.X("found_date:T"),
                    y=alt.Y(
                        "cum_dead_pct:Q",
                        title="Cumulatieve uitval (%)",
                        axis=alt.Axis(titleColor="#7b241c"),
                    ),
                    tooltip=[
                        alt.Tooltip("found_date:T", title="Datum", format="%d-%m-%Y"),
                        alt.Tooltip(
                            "cum_dead_pct:Q", title="Cumulatief uitval %", format=".2f"
                        ),
                    ],
                )
            )
            layers_dead.append(line_cum)

            if show_norms_switch.value and not df_norms_by_date.is_empty():
                norm_dead_pd = (
                    df_norms_by_date.select(
                        [
                            "registration_date",
                            "age_weeks",
                            "liveability_percentage_norm",
                        ]
                    )
                    .with_columns(
                        (100.0 - pl.col("liveability_percentage_norm")).alias(
                            "cum_dead_pct_norm"
                        )
                    )
                    .to_pandas()
                )
                layers_dead.append(
                    alt.Chart(norm_dead_pd)
                    .mark_line(color="#6b7280", strokeDash=[6, 4], strokeWidth=2)
                    .encode(
                        x=alt.X("registration_date:T"),
                        y=alt.Y("cum_dead_pct_norm:Q"),
                        tooltip=[
                            alt.Tooltip(
                                "registration_date:T",
                                title="Normdatum",
                                format="%d-%m-%Y",
                            ),
                            alt.Tooltip("age_weeks:Q", title="Leeftijdsweek"),
                            alt.Tooltip(
                                "cum_dead_pct_norm:Q",
                                title="Norm uitval %",
                                format=".2f",
                            ),
                        ],
                    )
                )

        chart_dead_hens = mo.ui.altair_chart(
            alt.layer(*layers_dead)
            .resolve_scale(y="independent")
            .properties(
                width=900,
                height=280,
                title="Dode hennen per dag en cumulatieve uitval %",
            )
        )

        total_dead = int(df_dead_hens["dead_count"].sum())
        cum_pct = total_dead / bird_count * 100.0 if bird_count > 0 else 0.0
        avg_per_day = df_daily_dead["dead_count"].mean()
        last_dead_row = df_daily_dead.tail(1).to_dicts()[0]
        norm_row = transforms.get_norm_for_flock_week(
            df_norms,
            last_dead_row["flock_week"],
        )
        mortality_delta = ""
        if show_norms_switch.value and norm_row:
            mortality_delta = transforms.format_norm_delta(
                last_dead_row["cum_dead_pct"],
                100.0 - norm_row["liveability_percentage_norm"],
                unit="%",
                precision=2,
            )
        summary_dead_hens = mo.md(
            f"Totaal: **{total_dead}** dode hennen · "
            f"Cumulatieve uitval: **{cum_pct:.2f}%** · "
            f"Gemiddeld per dag: **{avg_per_day:.1f}**"
            + (
                f" · Laatste cumulatieve uitval vs norm: {mortality_delta}"
                if mortality_delta
                else ""
            )
        )

    mo.vstack([chart_dead_hens, summary_dead_hens])
    return chart_dead_hens, summary_dead_hens


@app.cell
def _(alt, date_range_filter, df_pallets, mo, pl, transforms):
    """Chart 4: Palletgewicht en eigewicht."""
    mo.md("## Palletgewicht en eigewicht")
    return


@app.cell
def _(
    alt,
    date_range_filter,
    df_norms,
    df_norms_by_date,
    df_pallets,
    flock_dob,
    mo,
    pl,
    show_norms_switch,
    transforms,
):
    """Chart 4 inhoud."""
    if df_pallets.is_empty() or not date_range_filter.value:
        chart_pallets = mo.callout(
            mo.md("Geen palletgewicht data in deze selectie."), kind="info"
        )
        summary_pallets = mo.md("")
    else:
        # Daily average egg weight as main line
        df_daily_ew = (
            df_pallets.group_by("registration_date")
            .agg(
                pl.col("egg_weight_grams").mean().alias("egg_weight_avg"),
                pl.col("pallet_weight_kg").sum().alias("pallet_weight_total"),
            )
            .sort("registration_date")
        )
        df_daily_ew = transforms.add_flock_week_column(
            df_daily_ew,
            "registration_date",
            flock_dob,
        )

        df_ew_pd = df_daily_ew.to_pandas()
        df_raw_pd = df_pallets.to_pandas()

        # Individual pallet scatter (markers)
        scatter = (
            alt.Chart(df_raw_pd)
            .mark_point(color="#7d3c98", size=50, opacity=0.5)
            .encode(
                x=alt.X(
                    "registration_date:T", title="Datum", axis=alt.Axis(format="%d-%m")
                ),
                y=alt.Y("egg_weight_grams:Q", title="Eigewicht (gram)"),
                tooltip=[
                    alt.Tooltip(
                        "registration_date:T", title="Datum", format="%d-%m-%Y"
                    ),
                    alt.Tooltip(
                        "egg_weight_grams:Q", title="Eigewicht (g)", format=".2f"
                    ),
                    alt.Tooltip("supplier_name:N", title="Leverancier"),
                    alt.Tooltip("pallet_weight_kg:Q", title="Pallet kg", format=".1f"),
                ],
            )
        )

        # Daily average line
        avg_line = (
            alt.Chart(df_ew_pd)
            .mark_line(color="#6c3483", strokeWidth=2)
            .encode(
                x=alt.X("registration_date:T"),
                y=alt.Y("egg_weight_avg:Q"),
                tooltip=[
                    alt.Tooltip(
                        "registration_date:T", title="Datum", format="%d-%m-%Y"
                    ),
                    alt.Tooltip(
                        "egg_weight_avg:Q", title="Daggemiddelde (g)", format=".2f"
                    ),
                ],
            )
        )

        layers_pallets = [scatter, avg_line]
        if show_norms_switch.value and not df_norms_by_date.is_empty():
            norm_weight_pd = df_norms_by_date.select(
                [
                    "registration_date",
                    "age_weeks",
                    "egg_weight_grams_norm",
                ]
            ).to_pandas()
            layers_pallets.append(
                alt.Chart(norm_weight_pd)
                .mark_line(color="#6b7280", strokeDash=[6, 4], strokeWidth=2)
                .encode(
                    x=alt.X("registration_date:T"),
                    y=alt.Y("egg_weight_grams_norm:Q"),
                    tooltip=[
                        alt.Tooltip(
                            "registration_date:T",
                            title="Normdatum",
                            format="%d-%m-%Y",
                        ),
                        alt.Tooltip("age_weeks:Q", title="Leeftijdsweek"),
                        alt.Tooltip(
                            "egg_weight_grams_norm:Q",
                            title="Norm eigewicht (g)",
                            format=".2f",
                        ),
                    ],
                )
            )

        chart_pallets = mo.ui.altair_chart(
            alt.layer(*layers_pallets).properties(
                width=900,
                height=280,
                title="Eigewicht per pallet (punten) en daggemiddelde (lijn)",
            )
        )

        avg_ew = df_pallets["egg_weight_grams"].mean()
        min_ew = df_pallets["egg_weight_grams"].min()
        max_ew = df_pallets["egg_weight_grams"].max()
        n_pallets = len(df_pallets)
        last_weight_row = df_daily_ew.tail(1).to_dicts()[0]
        norm_row = transforms.get_norm_for_flock_week(
            df_norms,
            last_weight_row["flock_week"],
        )
        egg_weight_delta = ""
        if show_norms_switch.value and norm_row:
            egg_weight_delta = transforms.format_norm_delta(
                last_weight_row["egg_weight_avg"],
                norm_row["egg_weight_grams_norm"],
                unit=" g",
                precision=2,
            )
        summary_pallets = mo.md(
            f"Gemiddeld eigewicht: **{avg_ew:.2f} g** · "
            f"Min: **{min_ew:.2f} g** · Max: **{max_ew:.2f} g** · "
            f"Aantal pallets: **{n_pallets}**"
            + (
                f" · Laatste eigewicht vs norm: {egg_weight_delta}"
                if egg_weight_delta
                else ""
            )
        )

    mo.vstack([chart_pallets, summary_pallets])
    return chart_pallets, summary_pallets


@app.cell
def _(
    alt,
    bird_count,
    date_range_filter,
    df_dead_hens,
    df_eggs,
    flock_dob,
    mo,
    pl,
    rolling_switch,
    transforms,
):
    """Chart 5: Totaal eieren en legpercentage."""
    mo.md("## Eieren en legpercentage")
    return


@app.cell
def _(
    alt,
    bird_count,
    date_range_filter,
    df_dead_hens,
    df_eggs,
    df_norms,
    df_norms_by_date,
    flock_dob,
    mo,
    pl,
    rolling_switch,
    show_norms_switch,
    transforms,
):
    """Chart 5 inhoud."""
    if df_eggs.is_empty() or not date_range_filter.value:
        chart_eggs = mo.callout(
            mo.md("Geen eiregistraties in deze selectie."), kind="info"
        )
        summary_eggs = mo.md("")
    else:
        # Bird count per day for lay %
        bird_count_df = transforms.daily_bird_count(df_dead_hens, bird_count)
        lay_pct_df = transforms.daily_lay_percentage(df_eggs, bird_count_df)

        df_eggs_w = df_eggs.sort("registration_date")
        if not lay_pct_df.is_empty():
            df_eggs_w = df_eggs_w.join(lay_pct_df, on="registration_date", how="left")

        if rolling_switch.value and "lay_percentage" in df_eggs_w.columns:
            df_eggs_w = transforms.add_rolling_average(
                df_eggs_w, "lay_percentage", window=7
            )

        df_eggs_w = transforms.add_flock_week_column(
            df_eggs_w, "registration_date", flock_dob
        )
        df_ep = df_eggs_w.to_pandas()

        bar_eggs = (
            alt.Chart(df_ep)
            .mark_bar(opacity=0.7)
            .encode(
                x=alt.X(
                    "registration_date:T", title="Datum", axis=alt.Axis(format="%d-%m")
                ),
                y=alt.Y("total_eggs:Q", title="Eieren"),
                color=alt.value("#27ae60"),
                tooltip=[
                    alt.Tooltip(
                        "registration_date:T", title="Datum", format="%d-%m-%Y"
                    ),
                    alt.Tooltip("flock_week:Q", title="Leeftijdsweek"),
                    alt.Tooltip("total_eggs:Q", title="Totaal eieren", format=","),
                    alt.Tooltip("first_quality_eggs:Q", title="1e soort"),
                    alt.Tooltip("second_quality_eggs:Q", title="2e soort"),
                ],
            )
        )

        layers_eggs = [bar_eggs]

        if "lay_percentage" in df_ep.columns:
            line_lay = (
                alt.Chart(df_ep)
                .mark_line(color="#1a5276", strokeWidth=2)
                .encode(
                    x=alt.X("registration_date:T"),
                    y=alt.Y(
                        "lay_percentage:Q",
                        title="Legpercentage (%)",
                        axis=alt.Axis(titleColor="#1a5276"),
                        scale=alt.Scale(zero=False),
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "registration_date:T", title="Datum", format="%d-%m-%Y"
                        ),
                        alt.Tooltip(
                            "lay_percentage:Q", title="Legpercentage %", format=".1f"
                        ),
                    ],
                )
            )
            layers_eggs.append(line_lay)

            if rolling_switch.value and "lay_percentage_rolling7" in df_ep.columns:
                layers_eggs.append(
                    alt.Chart(df_ep)
                    .mark_line(color="#0d3349", strokeDash=[4, 2], strokeWidth=1.5)
                    .encode(
                        x=alt.X("registration_date:T"),
                        y=alt.Y("lay_percentage_rolling7:Q"),
                        tooltip=[
                            alt.Tooltip(
                                "lay_percentage_rolling7:Q",
                                title="Leg% 7d gem.",
                                format=".1f",
                            )
                        ],
                    )
                )

            if show_norms_switch.value and not df_norms_by_date.is_empty():
                norm_lay_pd = df_norms_by_date.select(
                    [
                        "registration_date",
                        "age_weeks",
                        "lay_percentage_norm",
                    ]
                ).to_pandas()
                layers_eggs.append(
                    alt.Chart(norm_lay_pd)
                    .mark_line(color="#6b7280", strokeDash=[6, 4], strokeWidth=2)
                    .encode(
                        x=alt.X("registration_date:T"),
                        y=alt.Y("lay_percentage_norm:Q"),
                        tooltip=[
                            alt.Tooltip(
                                "registration_date:T",
                                title="Normdatum",
                                format="%d-%m-%Y",
                            ),
                            alt.Tooltip("age_weeks:Q", title="Leeftijdsweek"),
                            alt.Tooltip(
                                "lay_percentage_norm:Q",
                                title="Norm legpercentage",
                                format=".1f",
                            ),
                        ],
                    )
                )

        chart_eggs = mo.ui.altair_chart(
            alt.layer(*layers_eggs)
            .resolve_scale(y="independent")
            .properties(
                width=900,
                height=300,
                title="Totaal eieren (bars) en legpercentage % (lijn)",
            )
        )

        avg_lay = (
            lay_pct_df["lay_percentage"].mean() if not lay_pct_df.is_empty() else None
        )
        total_eggs_c = int(df_eggs["total_eggs"].sum())
        lay_str = (
            f"Gem. legpercentage: **{avg_lay:.1f}%**"
            if avg_lay is not None
            else "Legpercentage: geen kippenstand data"
        )
        last_egg_day = df_eggs_w.tail(1).to_dicts()[0]
        norm_row = transforms.get_norm_for_flock_week(
            df_norms,
            last_egg_day["flock_week"],
        )
        lay_delta = ""
        if show_norms_switch.value and norm_row:
            lay_delta = transforms.format_norm_delta(
                last_egg_day.get("lay_percentage"),
                norm_row["lay_percentage_norm"],
                unit="%",
                precision=1,
            )
        summary_eggs = mo.md(
            f"Totaal eieren: **{total_eggs_c:,}** · {lay_str}"
            + (f" · Laatste legpercentage vs norm: {lay_delta}" if lay_delta else "")
        )

    mo.vstack([chart_eggs, summary_eggs])
    return chart_eggs, summary_eggs


@app.cell
def _(
    alt,
    date_range_filter,
    df_norms,
    df_norms_by_date,
    df_eggs,
    df_feed_water,
    df_pallets,
    flock_dob,
    mo,
    show_norms_switch,
    rolling_switch,
    transforms,
):
    """Chart 6: Voederconversie (FCR)."""
    mo.md("## Voederconversie (FCR)")
    return


@app.cell
def _(
    alt,
    date_range_filter,
    df_norms,
    df_norms_by_date,
    df_eggs,
    df_feed_water,
    df_pallets,
    flock_dob,
    mo,
    pl,
    show_norms_switch,
    rolling_switch,
    transforms,
):
    """Chart 6 inhoud."""
    if df_feed_water.is_empty() or df_eggs.is_empty() or not date_range_filter.value:
        chart_fcr = mo.callout(
            mo.md("Onvoldoende data voor FCR-berekening (voer + eieren nodig)."),
            kind="info",
        )
        summary_fcr = mo.md("")
    else:
        fcr_df = transforms.daily_fcr(df_feed_water, df_pallets, df_eggs)

        if fcr_df.is_empty() or fcr_df["fcr"].drop_nulls().is_empty():
            chart_fcr = mo.callout(
                mo.md("FCR kan pas berekend worden na de eerste palletmeting."),
                kind="warn",
            )
            summary_fcr = mo.md("")
        else:
            fcr_df = transforms.add_flock_week_column(
                fcr_df, "registration_date", flock_dob
            )

            if rolling_switch.value:
                fcr_df = transforms.add_rolling_average(
                    fcr_df.filter(pl.col("fcr").is_not_null()),
                    "fcr",
                    window=7,
                )

            df_fcr_pd = fcr_df.to_pandas()

            fcr_line = (
                alt.Chart(df_fcr_pd)
                .mark_line(color="#1abc9c", strokeWidth=2)
                .encode(
                    x=alt.X(
                        "registration_date:T",
                        title="Datum",
                        axis=alt.Axis(format="%d-%m"),
                    ),
                    y=alt.Y(
                        "fcr:Q",
                        title="FCR (gram voer / gram ei)",
                        scale=alt.Scale(zero=False),
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "registration_date:T", title="Datum", format="%d-%m-%Y"
                        ),
                        alt.Tooltip("flock_week:Q", title="Leeftijdsweek"),
                        alt.Tooltip("fcr:Q", title="FCR", format=".3f"),
                    ],
                )
            )

            # Measured-weight markers on top of the FCR line
            df_measured = df_fcr_pd[df_fcr_pd["is_measured_weight"] == True]  # noqa: E712
            measured_points = (
                alt.Chart(df_measured)
                .mark_point(color="#117a65", size=60, filled=True)
                .encode(
                    x=alt.X("registration_date:T"),
                    y=alt.Y("fcr:Q"),
                    tooltip=[
                        alt.Tooltip(
                            "registration_date:T",
                            title="Datum (gemeten)",
                            format="%d-%m-%Y",
                        ),
                        alt.Tooltip("fcr:Q", title="FCR (gemeten dag)", format=".3f"),
                    ],
                )
            )

            layers_fcr = [fcr_line, measured_points]

            if rolling_switch.value and "fcr_rolling7" in df_fcr_pd.columns:
                layers_fcr.append(
                    alt.Chart(df_fcr_pd)
                    .mark_line(color="#0e6655", strokeDash=[4, 2], strokeWidth=1.5)
                    .encode(
                        x=alt.X("registration_date:T"),
                        y=alt.Y("fcr_rolling7:Q"),
                        tooltip=[
                            alt.Tooltip(
                                "fcr_rolling7:Q", title="FCR 7d gem.", format=".3f"
                            )
                        ],
                    )
                )

            if show_norms_switch.value and not df_norms_by_date.is_empty():
                norm_fcr_pd = df_norms_by_date.select(
                    [
                        "registration_date",
                        "age_weeks",
                        "feed_conversion_ratio_norm",
                    ]
                ).to_pandas()
                layers_fcr.append(
                    alt.Chart(norm_fcr_pd)
                    .mark_line(color="#6b7280", strokeDash=[6, 4], strokeWidth=2)
                    .encode(
                        x=alt.X("registration_date:T"),
                        y=alt.Y("feed_conversion_ratio_norm:Q"),
                        tooltip=[
                            alt.Tooltip(
                                "registration_date:T",
                                title="Normdatum",
                                format="%d-%m-%Y",
                            ),
                            alt.Tooltip("age_weeks:Q", title="Leeftijdsweek"),
                            alt.Tooltip(
                                "feed_conversion_ratio_norm:Q",
                                title="Norm FCR",
                                format=".3f",
                            ),
                        ],
                    )
                )

            chart_fcr = mo.ui.altair_chart(
                alt.layer(*layers_fcr).properties(
                    width=900,
                    height=280,
                    title="Voederconversie per dag (lijn) — gevulde punten = palletmeting aanwezig",
                )
            )

            avg_fcr = fcr_df["fcr"].drop_nulls().mean()
            n_measured = int(fcr_df["is_measured_weight"].sum())
            last_fcr_row = (
                fcr_df.filter(pl.col("fcr").is_not_null()).tail(1).to_dicts()[0]
            )
            norm_row = transforms.get_norm_for_flock_week(
                df_norms,
                last_fcr_row["flock_week"],
            )
            fcr_delta = ""
            if show_norms_switch.value and norm_row:
                fcr_delta = transforms.format_norm_delta(
                    last_fcr_row["fcr"],
                    norm_row["feed_conversion_ratio_norm"],
                    precision=3,
                )
            summary_fcr = mo.md(
                f"Gemiddelde FCR: **{avg_fcr:.3f}** · "
                f"Dagen met palletmeting: **{n_measured}**"
                + (f" · Laatste FCR vs norm: {fcr_delta}" if fcr_delta else "")
            )

    mo.vstack([chart_fcr, summary_fcr])
    return chart_fcr, summary_fcr


if __name__ == "__main__":
    app.run()
