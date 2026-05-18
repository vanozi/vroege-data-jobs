import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full", app_title="Klauwbehandelingen")


@app.cell
def _():
    from datetime import date
    import os

    import altair as alt
    from dotenv import load_dotenv
    import marimo as mo
    import pandas as pd
    import sqlalchemy

    alt.data_transformers.disable_max_rows()
    return alt, load_dotenv, mo, os, pd, sqlalchemy


@app.cell
def _(load_dotenv, os, sqlalchemy):
    load_dotenv()
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/gebroeders-vroege",
    )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql+psycopg2://"):
        database_url = database_url.replace(
            "postgresql+psycopg2://",
            "postgresql+psycopg://",
            1,
        )

    postgres_engine = sqlalchemy.create_engine(database_url, pool_pre_ping=True)
    return (postgres_engine,)


@app.cell
def _(mo, postgres_engine):
    klauw_behandelingen_raw = mo.sql(
        f"""
        SELECT
            id,
            halsbandnummer,
            CAST(behandeldatum AS DATE) AS behandeldatum,
            notatie,
            created_at,
            updated_at
        FROM klauw_behandelingen
        WHERE notatie IS NOT NULL
        """,
        output=False,
        engine=postgres_engine
    )
    return (klauw_behandelingen_raw,)


@app.cell
def _(pd):
    POSITIONS = {
        "Linksvoor": {"zijde": "Links", "poot": "Voor", "positie": "Linksvoor"},
        "Rechtsvoor": {"zijde": "Rechts", "poot": "Voor", "positie": "Rechtsvoor"},
        "Linksachter": {"zijde": "Links", "poot": "Achter", "positie": "Linksachter"},
        "Rechtsachter": {
            "zijde": "Rechts",
            "poot": "Achter",
            "positie": "Rechtsachter",
        },
    }

    PROBLEM_LABELS = {
        "Mortellaro": "Mortellaro / digital dermatitis",
        "Wittelijndefect": "Wittelijndefect / white line disease",
        "Zoolzweer": "Zoolzweer / sole ulcer",
        "Tussenklauwontsteking": "Tussenklauwontsteking / foot rot",
        "Stinkpoot": "Stinkpoot / interdigital dermatitis",
        "Tyloom": "Tyloom / interdigital hyperplasia",
        "Chronisch bevangen": "Chronisch bevangen",
        "Klos": "Klos",
        "Verband": "Verband",
        "Vierkant": "Vierkant bekapt",
    }

    DIAGNOSIS_PROBLEMS = {
        "Mortellaro",
        "Wittelijndefect",
        "Zoolzweer",
        "Tussenklauwontsteking",
        "Stinkpoot",
        "Tyloom",
        "Chronisch bevangen",
    }
    ACTION_PROBLEMS = {"Klos", "Verband", "Vierkant"}
    HIGH_SEVERITY = {"Mortellaro", "Wittelijndefect", "Zoolzweer", "Tussenklauwontsteking"}
    MEDIUM_SEVERITY = {"Stinkpoot", "Tyloom", "Chronisch bevangen"}

    def classify_notatie(notatie):
        text = str(notatie or "").strip()
        result = {
            "positie": "Onbekend",
            "zijde": "Onbekend",
            "poot": "Onbekend",
            "probleem": text or "Onbekend",
        }

        for prefix, position_data in POSITIONS.items():
            marker = f"{prefix} "
            if text.startswith(marker):
                result.update(position_data)
                result["probleem"] = text.removeprefix(marker).strip()
                break

        problem = result["probleem"]
        result["probleem_label"] = PROBLEM_LABELS.get(problem, problem)

        if problem in DIAGNOSIS_PROBLEMS:
            result["categorie"] = "Diagnose"
        elif problem in ACTION_PROBLEMS:
            result["categorie"] = "Behandeling / actie"
        else:
            result["categorie"] = "Overig / onbekend"

        if problem in HIGH_SEVERITY:
            result["ernst"] = "Hoog"
            result["ernst_score"] = 3
        elif problem in MEDIUM_SEVERITY:
            result["ernst"] = "Middel"
            result["ernst_score"] = 2
        elif problem in ACTION_PROBLEMS:
            result["ernst"] = "Actie"
            result["ernst_score"] = 0
        else:
            result["ernst"] = "Onbekend"
            result["ernst_score"] = 1

        return pd.Series(result)

    return (classify_notatie,)


@app.cell
def _(classify_notatie, klauw_behandelingen_raw, pd):
    klauw_df = klauw_behandelingen_raw.copy()
    klauw_df["behandeldatum"] = pd.to_datetime(klauw_df["behandeldatum"]).dt.date
    klauw_df["halsbandnummer"] = klauw_df["halsbandnummer"].astype("Int64")

    classification_df = klauw_df["notatie"].apply(classify_notatie)
    klauw_df = pd.concat([klauw_df, classification_df], axis=1)
    klauw_df["maand"] = pd.to_datetime(klauw_df["behandeldatum"]).dt.to_period("M").dt.to_timestamp()
    return (klauw_df,)


@app.cell
def _(klauw_df, mo):
    min_date = klauw_df["behandeldatum"].min()
    max_date = klauw_df["behandeldatum"].max()

    start_date = mo.ui.date(value=min_date, label="Van")
    end_date = mo.ui.date(value=max_date, label="Tot")
    category_filter = mo.ui.dropdown(
        options=["Alle"] + sorted(klauw_df["categorie"].dropna().unique().tolist()),
        value="Alle",
        label="Categorie",
    )
    severity_filter = mo.ui.dropdown(
        options=["Alle", "Hoog", "Middel", "Actie", "Onbekend"],
        value="Alle",
        label="Ernst",
    )
    problem_filter = mo.ui.dropdown(
        options=["Alle"] + sorted(klauw_df["probleem"].dropna().unique().tolist()),
        value="Alle",
        label="Probleem",
    )
    min_count_filter = mo.ui.number(
        start=1,
        stop=10000,
        value=1,
        label="Minimum aantal in verdeling",
    )

    filters = mo.hstack(
        [
            start_date,
            end_date,
            category_filter,
            severity_filter,
            problem_filter,
            min_count_filter,
        ],
        wrap=True,
    )
    return (
        category_filter,
        end_date,
        filters,
        min_count_filter,
        problem_filter,
        severity_filter,
        start_date,
    )


@app.cell
def _(
    category_filter,
    end_date,
    klauw_df,
    problem_filter,
    severity_filter,
    start_date,
):
    filtered_df = klauw_df[
        (klauw_df["behandeldatum"] >= start_date.value)
        & (klauw_df["behandeldatum"] <= end_date.value)
    ].copy()

    if category_filter.value != "Alle":
        filtered_df = filtered_df[filtered_df["categorie"] == category_filter.value]
    if severity_filter.value != "Alle":
        filtered_df = filtered_df[filtered_df["ernst"] == severity_filter.value]
    if problem_filter.value != "Alle":
        filtered_df = filtered_df[filtered_df["probleem"] == problem_filter.value]

    diagnosis_df = filtered_df[filtered_df["categorie"] == "Diagnose"].copy()
    severe_df = filtered_df[filtered_df["ernst"] == "Hoog"].copy()
    return diagnosis_df, filtered_df, severe_df


@app.cell
def _(filtered_df, klauw_df):
    def pct(value, total):
        if total == 0:
            return "0.0%"
        return f"{value / total:.1%}"

    total_records = len(filtered_df)
    total_cows = filtered_df["halsbandnummer"].nunique()
    total_dates = filtered_df["behandeldatum"].nunique()
    latest_date = filtered_df["behandeldatum"].max() if total_records else None
    severe_records = len(filtered_df[filtered_df["ernst"] == "Hoog"])
    diagnosis_records = len(filtered_df[filtered_df["categorie"] == "Diagnose"])
    repeat_cows = (
        filtered_df.groupby("halsbandnummer")
        .size()
        .reset_index(name="aantal")
        .query("aantal > 1")["halsbandnummer"]
        .nunique()
        if total_records
        else 0
    )

    metrics = {
        "records": f"{total_records:,}".replace(",", "."),
        "koeien": f"{total_cows:,}".replace(",", "."),
        "inspecties": f"{total_dates:,}".replace(",", "."),
        "laatste_datum": str(latest_date) if latest_date else "-",
        "ernstig": f"{severe_records:,}".replace(",", "."),
        "ernstig_pct": pct(severe_records, total_records),
        "diagnose_pct": pct(diagnosis_records, total_records),
        "herhaal_koeien": f"{repeat_cows:,}".replace(",", "."),
        "alle_records": f"{len(klauw_df):,}".replace(",", "."),
        "dataset_range": (
            f"{klauw_df['behandeldatum'].min()} t/m {klauw_df['behandeldatum'].max()}"
            if len(klauw_df)
            else "-"
        ),
    }
    return (metrics,)


@app.cell
def _(metrics, mo):
    header = mo.md(
        f"""
        # Klauwbehandelingen

        <div style="display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;margin:12px 0 16px 0;">
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Aantal notities in selectie</div><div style="font-size:28px;font-weight:700;">{metrics["records"]}</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Unieke koeien</div><div style="font-size:28px;font-weight:700;">{metrics["koeien"]}</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Inspectiedatums</div><div style="font-size:28px;font-weight:700;">{metrics["inspecties"]}</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Laatste inspectie</div><div style="font-size:28px;font-weight:700;">{metrics["laatste_datum"]}</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Ernstige aandoeningen</div><div style="font-size:28px;font-weight:700;">{metrics["ernstig"]}</div><div style="font-size:13px;color:#666;">{metrics["ernstig_pct"]} van selectie</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Aandeel gediagnoseerde aandoeningen</div><div style="font-size:28px;font-weight:700;">{metrics["diagnose_pct"]}</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Koeien met herhaling</div><div style="font-size:28px;font-weight:700;">{metrics["herhaal_koeien"]}</div></div>
          <div style="border:1px solid #ddd;border-radius:8px;padding:12px;"><div style="font-size:13px;color:#666;">Dataset</div><div style="font-size:18px;font-weight:700;">{metrics["alle_records"]} notities</div><div style="font-size:13px;color:#666;">{metrics["dataset_range"]}</div></div>
        </div>
        """
    )
    return (header,)


@app.cell
def _(filtered_df):
    daily_df = (
        filtered_df.groupby("behandeldatum")
        .agg(
            records=("id", "count"),
            koeien=("halsbandnummer", "nunique"),
            ernstig=("ernst", lambda values: (values == "Hoog").sum()),
        )
        .reset_index()
    )
    daily_long_df = daily_df.melt(
        id_vars="behandeldatum",
        value_vars=["records", "koeien", "ernstig"],
        var_name="meting",
        value_name="aantal",
    )

    monthly_problem_df = (
        filtered_df.groupby(["maand", "probleem"])
        .size()
        .reset_index(name="aantal")
        .sort_values(["maand", "aantal"], ascending=[True, False])
    )
    top_monthly_problems = (
        filtered_df.groupby("probleem")
        .size()
        .sort_values(ascending=False)
        .head(8)
        .index.tolist()
    )
    monthly_problem_df = monthly_problem_df[
        monthly_problem_df["probleem"].isin(top_monthly_problems)
    ]

    latest_inspections_df = (
        filtered_df.groupby("behandeldatum")
        .agg(
            records=("id", "count"),
            koeien=("halsbandnummer", "nunique"),
            ernstige_records=("ernst", lambda values: (values == "Hoog").sum()),
        )
        .reset_index()
        .sort_values("behandeldatum", ascending=False)
        .head(15)
    )
    return daily_long_df, latest_inspections_df, monthly_problem_df


@app.cell
def _(alt, daily_long_df, latest_inspections_df, mo, monthly_problem_df):
    timeline_chart = alt.Chart(daily_long_df).mark_line(point=True).encode(
        x=alt.X("behandeldatum:T", title="Inspectiedatum"),
        y=alt.Y("aantal:Q", title="Aantal"),
        color=alt.Color("meting:N", title="Meting"),
        tooltip=[
            alt.Tooltip("behandeldatum:T", title="Datum"),
            alt.Tooltip("meting:N", title="Meting"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=320)

    monthly_problem_chart = alt.Chart(monthly_problem_df).mark_bar().encode(
        x=alt.X("maand:T", title="Maand"),
        y=alt.Y("aantal:Q", title="Records"),
        color=alt.Color("probleem:N", title="Probleem"),
        tooltip=[
            alt.Tooltip("maand:T", title="Maand"),
            alt.Tooltip("probleem:N", title="Probleem"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=320)

    overview_tab = mo.vstack(
        [
            mo.md("## Overzicht"),
            mo.hstack(
                [
                    mo.ui.altair_chart(timeline_chart),
                    mo.ui.altair_chart(monthly_problem_chart),
                ],
                widths=[1, 1],
            ),
            mo.md("### Laatste inspecties"),
            mo.ui.table(latest_inspections_df, page_size=15),
        ]
    )
    return (overview_tab,)


@app.cell
def _(diagnosis_df, filtered_df, min_count_filter):
    notitie_distribution_df = (
        filtered_df.groupby(["notatie", "categorie", "ernst"])
        .size()
        .reset_index(name="aantal")
    )
    notitie_distribution_df["percentage"] = (
        notitie_distribution_df["aantal"] / notitie_distribution_df["aantal"].sum()
        if len(notitie_distribution_df)
        else 0
    )
    notitie_distribution_df = notitie_distribution_df[
        notitie_distribution_df["aantal"] >= min_count_filter.value
    ].sort_values("aantal", ascending=False)

    diagnosis_distribution_df = (
        diagnosis_df.groupby(["probleem", "probleem_label", "ernst"])
        .size()
        .reset_index(name="aantal")
        .sort_values("aantal", ascending=False)
    )
    diagnosis_distribution_df["percentage"] = (
        diagnosis_distribution_df["aantal"] / diagnosis_distribution_df["aantal"].sum()
        if len(diagnosis_distribution_df)
        else 0
    )
    diagnosis_distribution_df = diagnosis_distribution_df[
        diagnosis_distribution_df["aantal"] >= min_count_filter.value
    ]

    category_distribution_df = (
        filtered_df.groupby("categorie")
        .size()
        .reset_index(name="aantal")
        .sort_values("aantal", ascending=False)
    )
    return (
        category_distribution_df,
        diagnosis_distribution_df,
        notitie_distribution_df,
    )


@app.cell
def _(
    alt,
    category_distribution_df,
    diagnosis_distribution_df,
    mo,
    notitie_distribution_df,
):
    notitie_chart = alt.Chart(notitie_distribution_df.head(25)).mark_bar().encode(
        x=alt.X("aantal:Q", title="Aantal"),
        y=alt.Y("notitie:N", sort="-x", title="Notitie"),
        color=alt.Color("categorie:N", title="Categorie"),
        tooltip=[
            alt.Tooltip("notitie:N", title="Notitie"),
            alt.Tooltip("categorie:N", title="Categorie"),
            alt.Tooltip("ernst:N", title="Ernst"),
            alt.Tooltip("aantal:Q", title="Aantal"),
            alt.Tooltip("percentage:Q", title="Percentage", format=".1%"),
        ],
    ).properties(height=520)

    diagnosis_chart = alt.Chart(diagnosis_distribution_df.head(20)).mark_bar().encode(
        x=alt.X("aantal:Q", title="Aantal"),
        y=alt.Y("probleem_label:N", sort="-x", title="Diagnose"),
        color=alt.Color(
            "ernst:N",
            title="Ernst",
            scale=alt.Scale(
                domain=["Hoog", "Middel", "Onbekend"],
                range=["#b42318", "#b54708", "#667085"],
            ),
        ),
        tooltip=[
            alt.Tooltip("probleem_label:N", title="Diagnose"),
            alt.Tooltip("ernst:N", title="Ernst"),
            alt.Tooltip("aantal:Q", title="Aantal"),
            alt.Tooltip("percentage:Q", title="Percentage", format=".1%"),
        ],
    ).properties(height=420)

    category_chart = alt.Chart(category_distribution_df).mark_arc(innerRadius=55).encode(
        theta=alt.Theta("aantal:Q"),
        color=alt.Color("categorie:N", title="Categorie"),
        tooltip=[
            alt.Tooltip("categorie:N", title="Categorie"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=300)

    distribution_tab = mo.vstack(
        [
            mo.md("## Verdeling van notities"),
            mo.hstack(
                [
                    mo.ui.altair_chart(notitie_chart),
                    mo.vstack(
                        [
                            mo.ui.altair_chart(category_chart),
                            mo.ui.altair_chart(diagnosis_chart),
                        ]
                    ),
                ],
                widths=[1.2, 1],
            ),
            mo.md("### Verdelingstabel"),
            mo.ui.table(notitie_distribution_df, page_size=20),
        ]
    )
    return (distribution_tab,)


@app.cell
def _(filtered_df, severe_df):
    severity_distribution_df = (
        filtered_df.groupby(["ernst", "categorie"])
        .size()
        .reset_index(name="aantal")
    )

    severe_over_time_df = (
        severe_df.groupby(["maand", "probleem"])
        .size()
        .reset_index(name="aantal")
        .sort_values(["maand", "aantal"], ascending=[True, False])
    )

    severe_cows_df = (
        severe_df.groupby("halsbandnummer")
        .agg(
            ernstige_records=("id", "count"),
            verschillende_problemen=("probleem", "nunique"),
            laatste_datum=("behandeldatum", "max"),
            problemen=("probleem", lambda values: ", ".join(sorted(set(values)))),
        )
        .reset_index()
        .sort_values(["ernstige_records", "laatste_datum"], ascending=[False, False])
        .head(25)
    )
    return severe_cows_df, severe_over_time_df, severity_distribution_df


@app.cell
def _(alt, mo, severe_cows_df, severe_over_time_df, severity_distribution_df):
    severity_chart = alt.Chart(severity_distribution_df).mark_bar().encode(
        x=alt.X("ernst:N", title="Ernst", sort=["Hoog", "Middel", "Onbekend", "Actie"]),
        y=alt.Y("aantal:Q", title="Aantal"),
        color=alt.Color(
            "ernst:N",
            title="Ernst",
            scale=alt.Scale(
                domain=["Hoog", "Middel", "Onbekend", "Actie"],
                range=["#b42318", "#b54708", "#667085", "#1570ef"],
            ),
        ),
        column=alt.Column("categorie:N", title="Categorie"),
        tooltip=[
            alt.Tooltip("categorie:N", title="Categorie"),
            alt.Tooltip("ernst:N", title="Ernst"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=320)

    severe_time_chart = alt.Chart(severe_over_time_df).mark_line(point=True).encode(
        x=alt.X("maand:T", title="Maand"),
        y=alt.Y("aantal:Q", title="Ernstige records"),
        color=alt.Color("probleem:N", title="Probleem"),
        tooltip=[
            alt.Tooltip("maand:T", title="Maand"),
            alt.Tooltip("probleem:N", title="Probleem"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=360)

    severity_tab = mo.vstack(
        [
            mo.md("## Ernst en aandachtsproblemen"),
            mo.hstack(
                [
                    mo.ui.altair_chart(severity_chart),
                    mo.ui.altair_chart(severe_time_chart),
                ],
                widths=[1, 1],
            ),
            mo.md("### Koeien met meeste ernstige records"),
            mo.ui.table(severe_cows_df, page_size=15),
        ]
    )
    return (severity_tab,)


@app.cell
def _(diagnosis_df, filtered_df):
    position_df = filtered_df[filtered_df["positie"] != "Onbekend"].copy()
    position_counts_df = (
        position_df.groupby(["positie", "zijde", "poot"])
        .size()
        .reset_index(name="aantal")
    )
    position_problem_df = (
        diagnosis_df[diagnosis_df["positie"] != "Onbekend"]
        .groupby(["positie", "probleem"])
        .size()
        .reset_index(name="aantal")
    )
    side_df = (
        position_df.groupby("zijde")
        .size()
        .reset_index(name="aantal")
        .sort_values("aantal", ascending=False)
    )
    leg_df = (
        position_df.groupby("poot")
        .size()
        .reset_index(name="aantal")
        .sort_values("aantal", ascending=False)
    )
    return leg_df, position_counts_df, position_problem_df, side_df


@app.cell
def _(alt, leg_df, mo, position_counts_df, position_problem_df, side_df):
    position_heatmap = alt.Chart(position_counts_df).mark_rect().encode(
        x=alt.X("zijde:N", title="Zijde", sort=["Links", "Rechts"]),
        y=alt.Y("poot:N", title="Poot", sort=["Voor", "Achter"]),
        color=alt.Color("aantal:Q", title="Aantal", scale=alt.Scale(scheme="reds")),
        tooltip=[
            alt.Tooltip("positie:N", title="Positie"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=280)

    position_problem_chart = alt.Chart(position_problem_df).mark_bar().encode(
        x=alt.X("aantal:Q", title="Aantal"),
        y=alt.Y("probleem:N", title="Probleem", sort="-x"),
        color=alt.Color("positie:N", title="Positie"),
        tooltip=[
            alt.Tooltip("positie:N", title="Positie"),
            alt.Tooltip("probleem:N", title="Probleem"),
            alt.Tooltip("aantal:Q", title="Aantal"),
        ],
    ).properties(height=420)

    side_chart = alt.Chart(side_df).mark_bar().encode(
        x=alt.X("zijde:N", title="Zijde"),
        y=alt.Y("aantal:Q", title="Aantal"),
        color=alt.Color("zijde:N", legend=None),
        tooltip=["zijde:N", "aantal:Q"],
    ).properties(height=250)

    leg_chart = alt.Chart(leg_df).mark_bar().encode(
        x=alt.X("poot:N", title="Poot"),
        y=alt.Y("aantal:Q", title="Aantal"),
        color=alt.Color("poot:N", legend=None),
        tooltip=["poot:N", "aantal:Q"],
    ).properties(height=250)

    location_tab = mo.vstack(
        [
            mo.md("## Locatiepatronen"),
            mo.hstack(
                [
                    mo.ui.altair_chart(position_heatmap),
                    mo.ui.altair_chart(side_chart),
                    mo.ui.altair_chart(leg_chart),
                ],
                widths=[1, 1, 1],
            ),
            mo.ui.altair_chart(position_problem_chart),
        ]
    )
    return (location_tab,)


@app.cell
def _(filtered_df, severe_df):
    cow_summary_df = (
        filtered_df.groupby("halsbandnummer")
        .agg(
            records=("id", "count"),
            inspecties=("behandeldatum", "nunique"),
            ernstige_records=("ernst", lambda values: (values == "Hoog").sum()),
            laatste_datum=("behandeldatum", "max"),
            problemen=("probleem", lambda values: ", ".join(sorted(set(values)))),
        )
        .reset_index()
    )
    cow_summary_df["prioriteit_score"] = (
        cow_summary_df["ernstige_records"] * 3
        + cow_summary_df["records"]
        + cow_summary_df["inspecties"]
    )
    cow_watchlist_df = cow_summary_df.sort_values(
        ["prioriteit_score", "laatste_datum"],
        ascending=[False, False],
    ).head(50)

    recurring_problem_df = (
        severe_df.groupby(["halsbandnummer", "probleem"])
        .agg(
            records=("id", "count"),
            eerste_datum=("behandeldatum", "min"),
            laatste_datum=("behandeldatum", "max"),
        )
        .reset_index()
        .query("records > 1")
        .sort_values(["records", "laatste_datum"], ascending=[False, False])
        .head(50)
    )
    return cow_watchlist_df, recurring_problem_df


@app.cell
def _(cow_watchlist_df, mo, recurring_problem_df):
    cows_tab = mo.vstack(
        [
            mo.md("## Koeien-watchlist"),
            mo.md("### Hoogste prioriteit"),
            mo.ui.table(cow_watchlist_df, page_size=20),
            mo.md("### Terugkerende ernstige problemen"),
            mo.ui.table(recurring_problem_df, page_size=20),
        ]
    )
    return (cows_tab,)


@app.cell
def _(
    cows_tab,
    distribution_tab,
    filters,
    header,
    location_tab,
    mo,
    overview_tab,
    severity_tab,
):
    mo.vstack(
        [
            header,
            filters,
            mo.ui.tabs(
                {
                    "Overzicht": overview_tab,
                    "Verdeling notities": distribution_tab,
                    "Ernst": severity_tab,
                    "Locatie": location_tab,
                    "Koeien": cows_tab,
                }
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
