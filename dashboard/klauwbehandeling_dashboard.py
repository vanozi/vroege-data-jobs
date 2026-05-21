"""Klauwbehandeling dashboard."""

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full")


@app.cell
def _():
    """Imports en configuratie."""
    import importlib.util
    import os
    from datetime import datetime
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl
    from dotenv import load_dotenv

    _repo_root = Path(__file__).parent.parent
    _env_path = _repo_root / ".env"
    load_dotenv(_env_path)

    _transforms_path = Path(__file__).with_name("transforms.py")
    _transforms_spec = importlib.util.spec_from_file_location(
        "klauwbehandeling_dashboard_transforms", _transforms_path
    )
    if _transforms_spec is None or _transforms_spec.loader is None:
        raise ImportError(
            f"Kan dashboard transforms niet laden vanaf {_transforms_path}"
        )

    transforms = importlib.util.module_from_spec(_transforms_spec)
    _transforms_spec.loader.exec_module(transforms)
    return alt, datetime, mo, os, pl, transforms


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
    """Header."""
    mo.md(
        """
        # Klauwbehandeling Dashboard

        Dashboard voor analyse van klauwbehandelingen in de actieve koppel.
        """
    )
    return


@app.cell
def _(connectorx_database_url, pl):
    """Data laden: actieve koeien met behandelingen."""
    behandelingen_query = """
    SELECT
        k.animal_id,
        k.name,
        k.collar_number,
        k.birth_date,
        k.eartag,
        k.eartag_short,
        kb.id as behandeling_id,
        kb.behandeldatum,
        kb.notatie,
        kd.lactation_number,
        kd.current_dim,
        kd.feeding_group_number,
        kd.feeding_group_name,
        kd.barn_group_name
    FROM koeien k
    LEFT JOIN klauw_behandelingen kb
        ON k.eartag_short = kb.eartag_short
        AND kb.behandeldatum > k.birth_date
    LEFT JOIN koe_details kd
        ON k.animal_id = kd.animal_id
    WHERE k.in_current_herd = true
    ORDER BY kb.behandeldatum DESC NULLS last
    """

    df_raw = pl.read_database_uri(
        query=behandelingen_query,
        uri=connectorx_database_url,
    )
    return (df_raw,)


@app.cell
def _(df_raw, pl, transforms):
    """Parse notaties en voeg gestructureerde velden toe."""
    df_behandelingen = df_raw.filter(pl.col("behandeling_id").is_not_null())

    def _parse_row(notatie):
        parsed = transforms.parse_notatie(notatie)
        return {
            "positie_code": parsed.positie_code,
            "positie": parsed.positie_volledig,
            "zijde": parsed.zijde,
            "poot": parsed.poot,
            "probleem": parsed.probleem,
            "categorie": transforms.get_probleem_categorie(parsed.probleem),
            "is_mortellaro": parsed.is_mortellaro,
            "is_vierkant": parsed.is_vierkant,
        }

    parsed_rows = [_parse_row(row["notatie"]) for row in df_behandelingen.to_dicts()]
    df_parsed_notities = pl.DataFrame(parsed_rows)
    df_behandelingen_parsed = pl.concat(
        [df_behandelingen, df_parsed_notities], how="horizontal"
    )
    return (df_behandelingen_parsed,)


@app.cell
def _(df_behandelingen_parsed, pl, transforms):
    """Bereken Mortellaro-cases over de volledige actieve-koppel-historie."""
    case_rows = transforms.add_mortellaro_case_columns(
        df_behandelingen_parsed.to_dicts()
    )
    followup_rows = transforms.build_mortellaro_followup_status(
        df_behandelingen_parsed.to_dicts()
    )

    df_case_columns_all = pl.DataFrame(case_rows)
    df_mortellaro_cases_all = df_case_columns_all.filter(
        pl.col("mortellaro_case_key").is_not_null()
    )

    if followup_rows:
        df_mortellaro_followup_all = pl.DataFrame(followup_rows)
    else:
        df_mortellaro_followup_all = pl.DataFrame(
            {
                "mortellaro_case_key": [],
                "animal_id": [],
                "eartag_short": [],
                "name": [],
                "positie_code": [],
                "positie": [],
                "eerste_datum": [],
                "laatste_mortellaro_datum": [],
                "herhaling_nummer": [],
                "opvolgstatus": [],
                "volgende_inspectie": [],
                "opgelost_op": [],
            }
        )
    return df_mortellaro_cases_all, df_mortellaro_followup_all


@app.cell
def _(df_behandelingen_parsed, mo):
    """Filter controls."""
    mo.md("## Filters")

    min_behandeldatum = df_behandelingen_parsed["behandeldatum"].min()
    max_behandeldatum = df_behandelingen_parsed["behandeldatum"].max()

    datum_van_filter = mo.ui.date(
        label="Van datum",
        value=str(min_behandeldatum) if min_behandeldatum else None,
        start=str(min_behandeldatum) if min_behandeldatum else None,
        stop=str(max_behandeldatum) if max_behandeldatum else None,
    )

    datum_tot_filter = mo.ui.date(
        label="Tot datum",
        value=str(max_behandeldatum) if max_behandeldatum else None,
        start=str(min_behandeldatum) if min_behandeldatum else None,
        stop=str(max_behandeldatum) if max_behandeldatum else None,
    )

    alle_posities = (
        df_behandelingen_parsed.select("positie")
        .unique()
        .sort("positie")["positie"]
        .to_list()
    )
    positie_filter = mo.ui.multiselect(
        options=alle_posities,
        value=alle_posities,
        label="Posities",
    )

    alle_problemen = (
        df_behandelingen_parsed.select("probleem")
        .unique()
        .sort("probleem")["probleem"]
        .to_list()
    )
    probleem_filter = mo.ui.multiselect(
        options=alle_problemen,
        value=alle_problemen,
        label="Problemen",
    )

    koe_zoek_filter = mo.ui.text(
        label="Zoek koe (naam, halsbandnummer, oormerk of kort oormerk)",
        placeholder="Bijv. Bella, 101 of NL123...",
    )
    return (
        datum_tot_filter,
        datum_van_filter,
        koe_zoek_filter,
        positie_filter,
        probleem_filter,
    )


@app.cell
def _(
    datum_tot_filter,
    datum_van_filter,
    df_behandelingen_parsed,
    koe_zoek_filter,
    pl,
    positie_filter,
    probleem_filter,
):
    """Pas filters toe op data."""
    df_filtered = df_behandelingen_parsed

    if datum_van_filter.value:
        df_filtered = df_filtered.filter(
            pl.col("behandeldatum") >= datum_van_filter.value
        )

    if datum_tot_filter.value:
        df_filtered = df_filtered.filter(
            pl.col("behandeldatum") <= datum_tot_filter.value
        )

    if positie_filter.value:
        df_filtered = df_filtered.filter(pl.col("positie").is_in(positie_filter.value))

    if probleem_filter.value:
        df_filtered = df_filtered.filter(
            pl.col("probleem").is_in(probleem_filter.value)
        )

    if koe_zoek_filter.value and koe_zoek_filter.value.strip():
        _zoek_term = koe_zoek_filter.value.strip().lower()
        df_filtered = df_filtered.filter(
            pl.col("name").str.to_lowercase().str.contains(_zoek_term)
            | pl.col("collar_number").cast(pl.Utf8).str.contains(_zoek_term)
            | pl.col("eartag").str.to_lowercase().str.contains(_zoek_term)
            | pl.col("eartag_short").str.to_lowercase().str.contains(_zoek_term)
        )
    return (df_filtered,)


@app.cell
def _(
    df_behandelingen_parsed,
    df_mortellaro_cases_all,
    df_mortellaro_followup_all,
    df_raw,
    mo,
    pl,
):
    """Mortellaro overzicht - KPI cards."""
    totaal_actieve_koeien_mortellaro = df_raw.select("animal_id").n_unique()
    koeien_op_opvolglijst = (
        df_mortellaro_followup_all.filter(
            pl.col("opvolgstatus").is_in(
                ["Open/onbekend", "Actief/herhaald", "Onzeker"]
            )
        )
        .select("animal_id")
        .n_unique()
    )
    koeien_met_open_mortellaro = koeien_op_opvolglijst

    if df_behandelingen_parsed.height > 0:
        laatste_bekapdatum = df_behandelingen_parsed["behandeldatum"].max()
    else:
        laatste_bekapdatum = None

    if laatste_bekapdatum is not None and df_mortellaro_cases_all.height > 0:
        mortellaro_cases_laatste_bezoek = df_mortellaro_cases_all.filter(
            pl.col("behandeldatum") == laatste_bekapdatum
        )
        nieuwe_cases_laatste_bekapdatum = mortellaro_cases_laatste_bezoek.filter(
            pl.col("nieuwe_case")
        ).height
        herhalingen_laatste_bekapdatum = mortellaro_cases_laatste_bezoek.filter(
            pl.col("herhaalde_case")
        ).height
    else:
        nieuwe_cases_laatste_bekapdatum = 0
        herhalingen_laatste_bekapdatum = 0

    laatste_bekapdatum_caption = f"Laatste bekapdatum: {laatste_bekapdatum}"
    if laatste_bekapdatum is None:
        laatste_bekapdatum_caption = "Geen bekapdatum gevonden"

    mortellaro_kpi_cards = mo.hstack(
        [
            mo.stat(
                value=str(totaal_actieve_koeien_mortellaro),
                label="Actieve koeien",
                caption="in huidige koppel",
            ),
            mo.stat(
                value=str(koeien_met_open_mortellaro),
                label="Koeien met open Mortellaro",
                caption="nog geen latere Vierkant-notatie",
            ),
            mo.stat(
                value=str(nieuwe_cases_laatste_bekapdatum),
                label="Nieuwe cases laatste bezoek",
                caption=laatste_bekapdatum_caption,
            ),
            mo.stat(
                value=str(herhalingen_laatste_bekapdatum),
                label="Herhalingen laatste bezoek",
                caption=(f"{laatste_bekapdatum_caption}; zelfde koe en pootpositie"),
            ),
        ],
        justify="space-between",
    )
    return (mortellaro_kpi_cards,)


@app.cell
def _(datetime, df_mortellaro_followup_all, df_raw, mo, pl):
    """Mortellaro overzicht - open cases per koe."""
    open_statussen = ["Open/onbekend", "Actief/herhaald", "Onzeker"]

    if df_mortellaro_followup_all.height > 0:
        df_open_mortellaro_cases = df_mortellaro_followup_all.filter(
            pl.col("opvolgstatus").is_in(open_statussen)
        )
    else:
        df_open_mortellaro_cases = pl.DataFrame()

    if df_open_mortellaro_cases.height > 0:
        koe_details_by_animal = {}
        for _koe_detail_row in df_raw.unique(
            subset=["animal_id"], keep="first"
        ).to_dicts():
            koe_details_by_animal[str(_koe_detail_row["animal_id"])] = _koe_detail_row

        open_koeien_rows = []
        for animal_id, cases in df_open_mortellaro_cases.group_by("animal_id"):
            animal_id_value = (
                animal_id[0] if isinstance(animal_id, tuple) else animal_id
            )
            _case_rows = cases.to_dicts()
            koe_details = koe_details_by_animal.get(str(animal_id_value), {})
            posities = {str(_case_row.get("positie_code")) for _case_row in _case_rows}
            eerste_constatering = min(
                _case_row.get("eerste_datum") for _case_row in _case_rows
            )
            laatste_constatering = max(
                _case_row.get("laatste_mortellaro_datum") for _case_row in _case_rows
            )
            geboorte_datum = koe_details.get("birth_date")
            _leeftijd_jaren = None
            if geboorte_datum is not None:
                _leeftijd_jaren = round(
                    (datetime.now().date() - geboorte_datum).days / 365.25, 1
                )

            open_koeien_rows.append(
                {
                    "Koe": koe_details.get("name") or _case_rows[0].get("name"),
                    "Halsband": koe_details.get("collar_number"),
                    "Oormerk kort": koe_details.get("eartag_short")
                    or _case_rows[0].get("eartag_short"),
                    "Oormerk": koe_details.get("eartag"),
                    "Aantal open posities": len(posities),
                    "Linksvoor": "Ja" if "LV" in posities else "",
                    "Rechtsvoor": "Ja" if "RV" in posities else "",
                    "Linksachter": "Ja" if "LA" in posities else "",
                    "Rechtsachter": "Ja" if "RA" in posities else "",
                    "Eerste constatering": eerste_constatering,
                    "Laatste constatering": laatste_constatering,
                    "Totaal herhalingen": sum(
                        int(_case_row.get("herhaling_nummer") or 0)
                        for _case_row in _case_rows
                    ),
                    "Statussen": ", ".join(
                        sorted(
                            {
                                str(_case_row.get("opvolgstatus"))
                                for _case_row in _case_rows
                            }
                        )
                    ),
                    "Lactatie": koe_details.get("lactation_number"),
                    "DIM": koe_details.get("current_dim"),
                    "Voergroep": koe_details.get("feeding_group_name"),
                    "Stalgroep": koe_details.get("barn_group_name"),
                    "Leeftijd jaren": _leeftijd_jaren,
                }
            )

        df_open_mortellaro_koeien = pl.DataFrame(open_koeien_rows).sort(
            ["Aantal open posities", "Laatste constatering", "Totaal herhalingen"],
            descending=[True, True, True],
        )
        open_mortellaro_koeien_table = mo.ui.table(
            df_open_mortellaro_koeien.to_pandas(),
            selection=None,
            page_size=20,
            label="Koeien met open Mortellaro",
        )
    else:
        open_mortellaro_koeien_table = mo.callout(
            mo.md("Er zijn geen koeien met open Mortellaro-cases."),
            kind="success",
        )

    open_mortellaro_koeien_ui = mo.vstack(
        [
            mo.md("### Koeien met open Mortellaro"),
            mo.md(
                "Deze tabel toont koeien met een Mortellaro-notatie waarvoor nog "
                "geen latere Vierkant-notatie voor is gevonden."
            ),
            open_mortellaro_koeien_table,
        ]
    )
    return (open_mortellaro_koeien_ui,)


@app.cell
def _(alt, df_behandelingen_parsed, mo, pl):
    """Mortellaro overzicht - distributie over tijd."""
    df_mortellaro_notities = df_behandelingen_parsed.filter(pl.col("is_mortellaro"))

    if df_mortellaro_notities.height > 0:
        mortellaro_per_datum = (
            df_mortellaro_notities.group_by("behandeldatum")
            .agg(pl.len().alias("Aantal Mortellaro-notaties"))
            .sort("behandeldatum")
        )

        mortellaro_distributie_chart = (
            alt.Chart(mortellaro_per_datum.to_pandas())
            .mark_bar(color="#2f855a")
            .encode(
                x=alt.X("behandeldatum:T", title="Behandeldatum"),
                y=alt.Y(
                    "Aantal Mortellaro-notaties:Q",
                    title="Aantal Mortellaro-notaties",
                ),
                tooltip=[
                    alt.Tooltip(
                        "behandeldatum:T",
                        title="Behandeldatum",
                        format="%d-%m-%Y",
                    ),
                    alt.Tooltip(
                        "Aantal Mortellaro-notaties:Q",
                        title="Aantal Mortellaro-notaties",
                    ),
                ],
            )
            .properties(
                width=900,
                height=320,
                title="Mortellaro-notaties door de tijd heen",
            )
        )
        mortellaro_distributie_ui = mo.vstack(
            [
                mo.md("### Mortellaro door de tijd heen"),
                mo.ui.altair_chart(mortellaro_distributie_chart),
            ]
        )
    else:
        mortellaro_distributie_ui = mo.callout(
            mo.md("Geen Mortellaro-notaties gevonden in de actieve-koppeldata."),
            kind="neutral",
        )
    return (mortellaro_distributie_ui,)


@app.cell
def _(
    mo,
    mortellaro_distributie_ui,
    mortellaro_kpi_cards,
    open_mortellaro_koeien_ui,
):
    """Mortellaro overzicht - verzamel content."""
    mortellaro_overzicht_content = mo.vstack(
        [
            mo.md("## Mortellaro overzicht"),
            mortellaro_kpi_cards,
            open_mortellaro_koeien_ui,
            mortellaro_distributie_ui,
        ]
    )
    return (mortellaro_overzicht_content,)


@app.cell
def _(df_behandelingen_parsed, df_mortellaro_followup_all, df_raw, mo, pl):
    """Algemeen overzicht boven de tabs."""
    df_actieve_koeien = df_raw.unique(subset=["animal_id"], keep="first")

    df_koeien_met_notitie = df_behandelingen_parsed.select("animal_id").unique()
    df_koeien_zonder_notitie = df_actieve_koeien.join(
        df_koeien_met_notitie,
        on="animal_id",
        how="anti",
    )
    aantal_koeien_zonder_notitie = df_koeien_zonder_notitie.height
    koeien_met_actief_probleem = set()
    koeien_met_actief_probleem_rows = []

    if df_behandelingen_parsed.height > 0:
        laatste_bekapdatum_algemeen = df_behandelingen_parsed["behandeldatum"].max()
        df_laatste_bezoek = df_behandelingen_parsed.filter(
            pl.col("behandeldatum") == laatste_bekapdatum_algemeen
        )
        koeien_laatste_bezoek = df_laatste_bezoek.select("animal_id").n_unique()
        notities_laatste_bezoek = df_laatste_bezoek.height
        df_probleem_notities = df_behandelingen_parsed.filter(~pl.col("is_vierkant"))
        if df_probleem_notities.height > 0:
            problemen_tabel_data = (
                df_probleem_notities.group_by("probleem")
                .agg(pl.len().alias("Aantal"))
                .sort("Aantal", descending=True)
                .with_columns(
                    (pl.col("Aantal") / df_probleem_notities.height * 100)
                    .round(1)
                    .alias("Percentage")
                )
                .rename({"probleem": "Probleem"})
            )
            meest_voorkomend_probleem = problemen_tabel_data["Probleem"][0]
            meest_voorkomend_aantal = problemen_tabel_data["Aantal"][0]
        else:
            problemen_tabel_data = pl.DataFrame(
                {"Probleem": [], "Aantal": [], "Percentage": []}
            )
            meest_voorkomend_probleem = "N.v.t."
            meest_voorkomend_aantal = 0

        for _animal_id, koe_notities in df_behandelingen_parsed.group_by("animal_id"):
            _animal_id_value = (
                _animal_id[0] if isinstance(_animal_id, tuple) else _animal_id
            )
            laatste_vierkant_behandeling = None

            for datum, datum_notities in koe_notities.group_by("behandeldatum"):
                datum_value = datum[0] if isinstance(datum, tuple) else datum
                alleen_vierkant = datum_notities.select("is_vierkant").to_series().all()
                if alleen_vierkant:
                    if (
                        laatste_vierkant_behandeling is None
                        or datum_value > laatste_vierkant_behandeling
                    ):
                        laatste_vierkant_behandeling = datum_value

            actieve_probleem_rows = [
                row
                for row in koe_notities.to_dicts()
                if not row["is_vierkant"]
                and (
                    laatste_vierkant_behandeling is None
                    or row["behandeldatum"] > laatste_vierkant_behandeling
                )
            ]

            if actieve_probleem_rows:
                _latest_active_problem_date = max(
                    row["behandeldatum"] for row in actieve_probleem_rows
                )
                _latest_active_problem_rows = [
                    row
                    for row in actieve_probleem_rows
                    if row["behandeldatum"] == _latest_active_problem_date
                ]
                _koe_row = _latest_active_problem_rows[0]
                koeien_met_actief_probleem.add(_animal_id_value)
                koeien_met_actief_probleem_rows.append(
                    {
                        "Naam": _koe_row.get("name"),
                        "Halsband": _koe_row.get("collar_number"),
                        "Kort oormerk": _koe_row.get("eartag_short"),
                        "Oormerk": _koe_row.get("eartag"),
                        "Laatste probleemdatum": _latest_active_problem_date,
                        "Actieve probleemnotaties": len(actieve_probleem_rows),
                        "Problemen": ", ".join(
                            sorted(
                                {
                                    str(row.get("probleem"))
                                    for row in actieve_probleem_rows
                                }
                            )
                        ),
                        "Laatste problemen": ", ".join(
                            sorted(
                                {
                                    str(row.get("probleem"))
                                    for row in _latest_active_problem_rows
                                }
                            )
                        ),
                        "Lactatie": _koe_row.get("lactation_number"),
                        "DIM": _koe_row.get("current_dim"),
                        "Voergroep nummer": _koe_row.get("feeding_group_number"),
                        "Voergroep": _koe_row.get("feeding_group_name"),
                    }
                )
    else:
        laatste_bekapdatum_algemeen = None
        koeien_laatste_bezoek = 0
        notities_laatste_bezoek = 0
        problemen_tabel_data = pl.DataFrame(
            {"Probleem": [], "Aantal": [], "Percentage": []}
        )
        meest_voorkomend_probleem = "N.v.t."
        meest_voorkomend_aantal = 0

    open_mortellaro_koeien = (
        df_mortellaro_followup_all.filter(
            pl.col("opvolgstatus").is_in(
                ["Open/onbekend", "Actief/herhaald", "Onzeker"]
            )
        )
        .select("animal_id")
        .n_unique()
    )

    if df_koeien_zonder_notitie.height > 0:
        koeien_zonder_notitie_tabel_data = (
            df_koeien_zonder_notitie.select(
                [
                    "name",
                    "collar_number",
                    "eartag_short",
                    "eartag",
                    "birth_date",
                    "lactation_number",
                    "current_dim",
                    "feeding_group_number",
                    "feeding_group_name",
                ]
            )
            .rename(
                {
                    "name": "Naam",
                    "collar_number": "Halsband",
                    "eartag_short": "Kort oormerk",
                    "eartag": "Oormerk",
                    "birth_date": "Geboortedatum",
                    "lactation_number": "Lactatie",
                    "current_dim": "DIM",
                    "feeding_group_number": "Voergroep nummer",
                    "feeding_group_name": "Voergroep",
                }
            )
            .sort(["Halsband", "Naam"])
        )
        koeien_zonder_notitie_tabel = mo.ui.table(
            koeien_zonder_notitie_tabel_data.to_pandas(),
            selection=None,
            page_size=10,
            label="Koeien nog nooit behandeld",
        )
    else:
        koeien_zonder_notitie_tabel = mo.callout(
            mo.md("Alle actieve koeien hebben minstens een klauwbehandelingsnotatie."),
            kind="success",
        )

    if koeien_met_actief_probleem_rows:
        koeien_met_actief_probleem_tabel_data = pl.DataFrame(
            koeien_met_actief_probleem_rows
        ).sort(
            ["Laatste probleemdatum", "Actieve probleemnotaties", "Halsband"],
            descending=[True, True, False],
        )
        koeien_met_actief_probleem_tabel = mo.ui.table(
            koeien_met_actief_probleem_tabel_data.to_pandas(),
            selection=None,
            page_size=10,
            label="Koeien met actief probleem",
        )
    else:
        koeien_met_actief_probleem_tabel = mo.callout(
            mo.md("Er zijn geen actieve koeien met een open probleem gevonden."),
            kind="success",
        )

    algemeen_kpi_cards = mo.hstack(
        [
            mo.stat(
                value=str(laatste_bekapdatum_algemeen or "N.v.t."),
                label="Laatste bekapdatum",
                caption=f"{koeien_laatste_bezoek} koeien behandeld",
            ),
            mo.stat(
                value=str(len(koeien_met_actief_probleem)),
                label="Koeien met actief probleem",
                caption="niet opgevolgd door alleen Vierkant",
            ),
            mo.stat(
                value=str(aantal_koeien_zonder_notitie),
                label="Koeien nog nooit behandeld",
                caption="geen gekoppelde klauwnotatie",
            ),
        ],
        justify="space-between",
    )
    algemeen_kpi_cards_extra = mo.hstack(
        [
            mo.stat(
                value=str(notities_laatste_bezoek),
                label="Notaties laatste bezoek",
                caption=str(laatste_bekapdatum_algemeen or "N.v.t."),
            ),
            mo.stat(
                value=str(meest_voorkomend_probleem),
                label="Meest voorkomend probleem",
                caption=f"{meest_voorkomend_aantal} notaties",
            ),
            mo.stat(
                value=str(open_mortellaro_koeien),
                label="Open Mortellaro-koeien",
                caption="zie Mortellaro overzicht",
            ),
        ],
        justify="space-between",
    )

    problemen_tabel = mo.ui.table(
        problemen_tabel_data.to_pandas(),
        selection=None,
        page_size=15,
        label="Meest voorkomende problemen",
    )

    algemeen_overzicht_content = mo.vstack(
        [
            mo.md("## Algemeen overzicht"),
            algemeen_kpi_cards,
            algemeen_kpi_cards_extra,
            mo.vstack(
                [
                    mo.md("### Koeien met actief probleem"),
                    koeien_met_actief_probleem_tabel,
                ]
            ),
            mo.hstack(
                [
                    mo.vstack(
                        [mo.md("### Meest voorkomende problemen"), problemen_tabel]
                    ),
                    mo.vstack(
                        [
                            mo.md("### Koeien nog nooit behandeld"),
                            koeien_zonder_notitie_tabel,
                        ]
                    ),
                ],
                gap=3,
            ),
        ]
    )
    return (algemeen_overzicht_content,)


@app.cell
def _(df_filtered, mo, pl):
    """Per koe tab - koe selectie via table."""
    koeien_overzicht = (
        df_filtered.group_by(["animal_id", "name", "collar_number", "eartag_short"])
        .agg(
            [
                pl.len().alias("Aantal behandelingen"),
                pl.col("behandeldatum").min().alias("Eerste behandeling"),
                pl.col("behandeldatum").max().alias("Laatste behandeling"),
            ]
        )
        .sort("name")
    )

    koe_selectie_table = mo.ui.table(
        koeien_overzicht.to_pandas(),
        selection="single",
        label="Selecteer een koe door op een rij te klikken",
        page_size=10,
    )
    return (koe_selectie_table,)


@app.cell
def _(datetime, df_filtered, df_raw, koe_selectie_table, mo, pl):
    """Per koe tab - data op basis van selectie."""
    if len(koe_selectie_table.value) > 0 and len(df_filtered) > 0:
        selected_animal_id = koe_selectie_table.value.iloc[0]["animal_id"]
        koe_data = df_filtered.filter(pl.col("animal_id") == selected_animal_id)
        koe_info = df_raw.filter(pl.col("animal_id") == selected_animal_id).head(1)

        if koe_info.height > 0 and koe_data.height > 0:
            koe_row = koe_info.to_dicts()[0]
            geboortedatum = koe_row["birth_date"]
            leeftijd_dagen = (datetime.now().date() - geboortedatum).days
            leeftijd_jaren = leeftijd_dagen // 365
            leeftijd_maanden = (leeftijd_dagen % 365) // 30
            totaal_behandelingen_koe = koe_data.height
            unieke_problemen = koe_data.select("probleem").n_unique()
            laatste_behandeling = koe_data.select("behandeldatum").max()[0, 0]
            eerste_behandeling = koe_data.select("behandeldatum").min()[0, 0]

            koe_profiel_cards = mo.hstack(
                [
                    mo.stat(
                        value=koe_row["name"],
                        label=f"Koe #{koe_row['collar_number']}",
                        caption=f"ID: {str(koe_row['animal_id'])[:8]}...",
                    ),
                    mo.stat(
                        value=f"{leeftijd_jaren}j {leeftijd_maanden}m",
                        label="Leeftijd",
                        caption=f"Geboren: {geboortedatum}",
                    ),
                    mo.stat(
                        value=str(koe_row.get("lactation_number", "N/A")),
                        label="Lactatie",
                        caption=f"DIM: {koe_row.get('current_dim', 'N/A')}",
                    ),
                    mo.stat(
                        value=str(totaal_behandelingen_koe),
                        label="Behandelingen",
                        caption=f"{unieke_problemen} unieke problemen",
                    ),
                    mo.stat(
                        value=str(laatste_behandeling),
                        label="Laatste behandeling",
                        caption=f"Eerste: {eerste_behandeling}",
                    ),
                ],
                justify="space-between",
            )
        else:
            koe_profiel_cards = mo.callout(
                mo.md("*Geen data beschikbaar voor deze koe*"), kind="warn"
            )
            koe_data = pl.DataFrame()
    else:
        koe_profiel_cards = mo.callout(
            mo.md("*Selecteer een koe uit de tabel hierboven*"), kind="neutral"
        )
        koe_data = pl.DataFrame()
    return koe_data, koe_profiel_cards


@app.cell
def _(alt, koe_data, mo, pl, transforms):
    """Per koe tab - behandelhistorie tijdlijn."""
    if len(koe_data) > 0:
        tijdlijn_rows = []
        for row in koe_data.to_dicts():
            parsed = transforms.parse_notatie(row.get("notatie"))
            tijdlijn_rows.append(
                {
                    "Behandeldatum": row.get("behandeldatum"),
                    "Originele notatie": row.get("notatie"),
                    "Positie": parsed.positie_volledig,
                    "Probleem": parsed.probleem,
                    "Categorie": transforms.get_probleem_categorie(parsed.probleem),
                }
            )
        koe_tijdlijn_data = pl.DataFrame(tijdlijn_rows)
        koe_tijdlijn_chart = (
            alt.Chart(koe_tijdlijn_data.to_pandas())
            .mark_circle(size=150, opacity=0.8)
            .encode(
                x=alt.X(
                    "Behandeldatum:T",
                    title="Datum",
                    axis=alt.Axis(format="%Y-%m-%d"),
                ),
                y=alt.Y(
                    "Originele notatie:N",
                    title="Originele notatie",
                ),
                color=alt.Color(
                    "Probleem:N", title="Probleem", scale=alt.Scale(scheme="category20")
                ),
                shape=alt.Shape("Categorie:N", title="Categorie"),
                tooltip=[
                    alt.Tooltip("Behandeldatum:T", title="Datum", format="%d-%m-%Y"),
                    alt.Tooltip("Positie:N", title="Positie"),
                    alt.Tooltip("Probleem:N", title="Probleem"),
                    alt.Tooltip("Categorie:N", title="Categorie"),
                    alt.Tooltip("Originele notatie:N", title="Originele notatie"),
                ],
            )
            .properties(
                width=900,
                height=350,
                title="Behandelhistorie tijdlijn - elk punt is een behandeling",
            )
            .interactive()
        )
        koe_tijdlijn_ui = mo.ui.altair_chart(koe_tijdlijn_chart)
    else:
        koe_tijdlijn_ui = mo.md("")
    return (koe_tijdlijn_ui,)


@app.cell
def _(koe_data, mo, pl):
    """Per koe tab - chronologische probleemnotaties."""
    if len(koe_data) > 0:
        probleemnotaties_koe = (
            koe_data.filter(~pl.col("is_vierkant"))
            .select(
                [
                    "behandeldatum",
                    "positie",
                    "probleem",
                    "categorie",
                    "notatie",
                ]
            )
            .rename(
                {
                    "behandeldatum": "Behandeldatum",
                    "positie": "Positie",
                    "probleem": "Probleem",
                    "categorie": "Categorie",
                    "notatie": "Originele notatie",
                }
            )
            .sort("Behandeldatum", descending=True)
        )

        if probleemnotaties_koe.height > 0:
            probleemnotaties_tabel_ui = mo.ui.table(
                probleemnotaties_koe.to_pandas(),
                selection=None,
                page_size=20,
                label="Chronologische probleemnotaties",
            )
        else:
            probleemnotaties_tabel_ui = mo.callout(
                mo.md("Deze koe heeft geen probleemnotaties buiten Vierkant."),
                kind="success",
            )
    else:
        probleemnotaties_tabel_ui = mo.md("")
    return (probleemnotaties_tabel_ui,)


@app.cell
def _(koe_data, mo, pl):
    """Per koe tab - positie heatmap."""
    if len(koe_data) > 0:
        positie_counts = (
            koe_data.group_by("positie_code").agg(pl.len().alias("aantal")).to_dicts()
        )
        positie_dict = {row["positie_code"]: row["aantal"] for row in positie_counts}

        lv_count = positie_dict.get("LV", 0)
        rv_count = positie_dict.get("RV", 0)
        la_count = positie_dict.get("LA", 0)
        ra_count = positie_dict.get("RA", 0)
        geen_count = positie_dict.get("Geen", 0)

        total_posities = max(1, lv_count + rv_count + la_count + ra_count)

        heatmap_text = f"""
        ### Notaties per pootpositie

        | Positie | Aantal | Aandeel |
        | --- | ---: | ---: |
        | Linksvoor | {lv_count} | {lv_count * 100 // total_posities}% |
        | Rechtsvoor | {rv_count} | {rv_count * 100 // total_posities}% |
        | Linksachter | {la_count} | {la_count * 100 // total_posities}% |
        | Rechtsachter | {ra_count} | {ra_count * 100 // total_posities}% |

        Geen positie: {geen_count}
        """
        positie_heatmap_ui = mo.md(heatmap_text)
    else:
        positie_heatmap_ui = mo.md("")
    return (positie_heatmap_ui,)


@app.cell
def _(
    koe_profiel_cards,
    koe_selectie_table,
    koe_tijdlijn_ui,
    mo,
    positie_heatmap_ui,
    probleemnotaties_tabel_ui,
):
    """Per koe tab - verzamel content."""
    per_koe_content = mo.vstack(
        [
            mo.md("## Per koe analyse"),
            mo.md(
                "Klik op een koe in de tabel om gedetailleerde informatie en "
                "behandelhistorie te zien."
            ),
            koe_selectie_table,
            koe_profiel_cards,
            mo.md("### Chronologische probleemnotaties"),
            probleemnotaties_tabel_ui,
            mo.md("### Behandelhistorie tijdlijn"),
            koe_tijdlijn_ui,
            positie_heatmap_ui,
        ]
    )
    return (per_koe_content,)


@app.cell
def _(
    algemeen_overzicht_content,
    mo,
    mortellaro_overzicht_content,
    per_koe_content,
):
    """Tab navigatie - hoofdstructuur."""
    tabs = mo.ui.tabs(
        {
            "Mortellaro overzicht": mortellaro_overzicht_content,
            "Per koe": per_koe_content,
        }
    )

    mo.vstack([algemeen_overzicht_content, tabs])
    return


if __name__ == "__main__":
    app.run()
