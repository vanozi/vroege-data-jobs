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
        kd.barn_group_name,
        kd.status,
        kd.status_days,
        kd.is_young_stock
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
def _(connectorx_database_url, pl):
    """Data laden: Uniform-Agri exportbron met validatiecontext."""
    uniform_agri_query = """
    SELECT
        kb.id AS behandeling_id,
        kb.animal_id,
        k.animal_id AS koe_animal_id,
        kb.eartag AS klauw_eartag,
        COALESCE(k.eartag, kb.eartag) AS eartag,
        kb.eartag_short,
        kb.behandeldatum,
        kb.notatie,
        kb.created_at,
        kb.updated_at,
        k.name,
        k.collar_number,
        k.birth_date,
        k.in_current_herd
    FROM klauw_behandelingen kb
    LEFT JOIN koeien k
        ON k.animal_id = kb.animal_id
    ORDER BY kb.behandeldatum DESC NULLS LAST, kb.id
    """

    df_uniform_agri_raw = pl.read_database_uri(
        query=uniform_agri_query,
        uri=connectorx_database_url,
    )
    return (df_uniform_agri_raw,)


@app.cell
def _(df_uniform_agri_raw, pl, transforms):
    """Transformeer Uniform-Agri brondata en splits export/validatie."""
    uniform_agri_source_rows = df_uniform_agri_raw.to_dicts()
    uniform_agri_notitie_rows = transforms.build_uniform_agri_export_rows(
        uniform_agri_source_rows
    )
    uniform_agri_csv_rows = transforms.build_uniform_agri_csv_rows(
        uniform_agri_source_rows
    )
    uniform_agri_download_rows = transforms.build_uniform_agri_csv_download_rows(
        uniform_agri_source_rows
    )

    df_uniform_agri_notitie_rows = (
        pl.DataFrame(uniform_agri_notitie_rows)
        if uniform_agri_notitie_rows
        else pl.DataFrame()
    )
    df_uniform_agri_csv_rows = (
        pl.DataFrame(uniform_agri_csv_rows) if uniform_agri_csv_rows else pl.DataFrame()
    )
    df_uniform_agri_download_rows = (
        pl.DataFrame(uniform_agri_download_rows)
        if uniform_agri_download_rows
        else pl.DataFrame()
    )

    if df_uniform_agri_notitie_rows.height > 0:
        df_uniform_agri_validation_rows = df_uniform_agri_notitie_rows.filter(
            ~pl.col("exportable")
        )
    else:
        df_uniform_agri_validation_rows = pl.DataFrame()

    if df_uniform_agri_csv_rows.height > 0:
        df_uniform_agri_export_dataset = df_uniform_agri_csv_rows.filter(
            pl.col("exportable")
        )
    else:
        df_uniform_agri_export_dataset = pl.DataFrame()

    return (
        df_uniform_agri_csv_rows,
        df_uniform_agri_download_rows,
        df_uniform_agri_export_dataset,
        df_uniform_agri_notitie_rows,
        df_uniform_agri_validation_rows,
    )


@app.cell
def _(df_raw, pl, transforms):
    """Parse notaties en voeg gestructureerde velden toe."""
    df_behandelingen = df_raw.filter(pl.col("behandeling_id").is_not_null())
    parsed_notatie_schema = {
        "positie_code": pl.String,
        "positie": pl.String,
        "zijde": pl.String,
        "poot": pl.String,
        "probleem": pl.String,
        "is_mortellaro": pl.Boolean,
        "is_vierkant": pl.Boolean,
        "is_aandoening": pl.Boolean,
        "is_behandeling": pl.Boolean,
    }

    def _parse_row(notatie):
        parsed = transforms.parse_notatie(notatie)
        return {
            "positie_code": parsed.positie_code,
            "positie": parsed.positie_volledig,
            "zijde": parsed.zijde,
            "poot": parsed.poot,
            "probleem": parsed.probleem,
            "is_mortellaro": parsed.is_mortellaro,
            "is_vierkant": parsed.is_vierkant,
            "is_aandoening": parsed.is_aandoening,
            "is_behandeling": parsed.is_behandeling,
        }

    parsed_rows = [_parse_row(row["notatie"]) for row in df_behandelingen.to_dicts()]
    df_parsed_notities = pl.DataFrame(
        parsed_rows,
        schema=parsed_notatie_schema,
    )
    df_behandelingen_parsed = pl.concat(
        [df_behandelingen, df_parsed_notities], how="horizontal"
    )
    return (df_behandelingen_parsed,)


@app.cell
def _(df_behandelingen_parsed, pl, transforms):
    """Bereken open Mortellaro-koeien over de volledige actieve-koppel-historie."""
    source_schema = dict(df_behandelingen_parsed.schema)
    open_mortellaro_schema = {
        "animal_id": source_schema.get("animal_id", pl.String),
        "Koe / naam": pl.String,
        "Halsbandnummer": source_schema.get("collar_number", pl.Int64),
        "Oormerk kort": source_schema.get("eartag_short", pl.String),
        "Oormerk": source_schema.get("eartag", pl.String),
        "Laatste Mortellaro-datum": pl.Date,
        "Laatste behandeling na Mortellaro": pl.Date,
        "Laatste notatie(s)": pl.String,
        "Voergroep": source_schema.get("feeding_group_name", pl.String),
    }

    open_mortellaro_rows = transforms.build_open_mortellaro_rows(
        df_behandelingen_parsed.to_dicts()
    )
    df_open_mortellaro_rows = pl.DataFrame(
        open_mortellaro_rows,
        schema=open_mortellaro_schema,
    )
    return (df_open_mortellaro_rows,)


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
def _(df_open_mortellaro_rows, mo):
    """Mortellaro overzicht - nieuwe open Mortellaro tabel."""
    if df_open_mortellaro_rows.height > 0:
        open_mortellaro_table = mo.ui.table(
            df_open_mortellaro_rows.drop("animal_id").to_pandas(),
            selection=None,
            page_size=25,
            label="Koeien met open Mortellaro",
        )
    else:
        open_mortellaro_table = mo.callout(
            mo.md("Er zijn geen koeien met open Mortellaro."),
            kind="success",
        )

    mortellaro_overzicht_content = mo.vstack(
        [
            mo.md("## Koeien met open Mortellaro"),
            mo.md(
                "Een koe staat in deze tabel wanneer er een Mortellaro-notatie is "
                "geweest en er daarna geen behandeling met notatie Vierkant is geweest."
            ),
            open_mortellaro_table,
        ]
    )
    return (mortellaro_overzicht_content,)


@app.cell
def _(datetime, mo):
    """Protocol tab - peildatum control."""
    protocol_peildatum = mo.ui.date(
        label="Peildatum / datum klauwbekapper",
        value=str(datetime.now().date()),
    )
    return (protocol_peildatum,)


@app.cell
def _(datetime, df_raw, pl, protocol_peildatum, transforms):
    """Protocol tab - bereken protocolrijen."""
    protocol_peildatum_value = protocol_peildatum.value
    if isinstance(protocol_peildatum_value, str):
        protocol_reference_date = datetime.fromisoformat(
            protocol_peildatum_value
        ).date()
    else:
        protocol_reference_date = protocol_peildatum_value

    protocol_schema = {
        "Peildatum": pl.Date,
        "animal_id": pl.String,
        "Koe / naam": pl.String,
        "Halsbandnummer": pl.Int64,
        "Oormerk kort": pl.String,
        "Oormerk": pl.String,
        "DIM": pl.Int64,
        "Lactatie": pl.Int64,
        "Voergroep nummer": pl.String,
        "Voergroep naam": pl.String,
        "Status": pl.String,
        "Status dagen": pl.Int64,
        "Laatste klauwdatum": pl.Date,
        "Laatste notatie(s)": pl.String,
        "Laatste gezonde datum": pl.Date,
        "Dagen sinds laatste behandeling": pl.Int64,
        "Volgende actiedatum": pl.Date,
        "Aanbiedcategorie": pl.String,
        "Reden selectie": pl.String,
        "Moet aangeboden worden": pl.Boolean,
        "Urgentie": pl.Int64,
    }

    protocol_rows = transforms.build_klauwbekap_protocol_rows(
        df_raw.to_dicts(),
        reference_date=protocol_reference_date,
    )
    df_protocol_rows = pl.DataFrame(protocol_rows, schema=protocol_schema)
    return df_protocol_rows, protocol_reference_date


@app.cell
def _(df_protocol_rows, mo):
    """Protocol tab - filter controls."""
    protocol_categories = (
        df_protocol_rows.select("Aanbiedcategorie")
        .unique()
        .sort("Aanbiedcategorie")["Aanbiedcategorie"]
        .to_list()
    )
    protocol_category_filter = mo.ui.multiselect(
        options=protocol_categories,
        value=protocol_categories,
        label="Categorie",
    )

    protocol_feed_groups = (
        df_protocol_rows.select("Voergroep naam")
        .unique()
        .sort("Voergroep naam")["Voergroep naam"]
        .to_list()
    )
    protocol_feed_group_filter = mo.ui.multiselect(
        options=protocol_feed_groups,
        value=protocol_feed_groups,
        label="Voergroep",
    )

    protocol_search_filter = mo.ui.text(
        label="Zoek koe",
        placeholder="Naam, halsbandnummer, oormerk of kort oormerk",
    )
    return (
        protocol_category_filter,
        protocol_feed_group_filter,
        protocol_search_filter,
    )


@app.cell
def _(
    df_protocol_rows,
    pl,
    protocol_category_filter,
    protocol_feed_group_filter,
    protocol_search_filter,
):
    """Protocol tab - pas filters toe."""
    df_protocol_filtered_rows = df_protocol_rows

    if protocol_category_filter.value:
        df_protocol_filtered_rows = df_protocol_filtered_rows.filter(
            pl.col("Aanbiedcategorie").is_in(protocol_category_filter.value)
        )

    if protocol_feed_group_filter.value:
        df_protocol_filtered_rows = df_protocol_filtered_rows.filter(
            pl.col("Voergroep naam").is_in(protocol_feed_group_filter.value)
        )

    if protocol_search_filter.value and protocol_search_filter.value.strip():
        protocol_search_term = protocol_search_filter.value.strip().lower()
        df_protocol_filtered_rows = df_protocol_filtered_rows.filter(
            pl.col("Koe / naam")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(protocol_search_term)
            | pl.col("Halsbandnummer")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(protocol_search_term)
            | pl.col("Oormerk kort")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(protocol_search_term)
            | pl.col("Oormerk")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(protocol_search_term)
        )

    df_protocol_aanbiedlijst = df_protocol_filtered_rows.filter(
        pl.col("Moet aangeboden worden")
    ).sort(["Urgentie", "Volgende actiedatum", "Halsbandnummer"])
    df_protocol_nog_niet = df_protocol_filtered_rows.filter(
        (pl.col("Aanbiedcategorie") == "Tijdelijk niet aanbieden")
        & (~pl.col("Moet aangeboden worden"))
    ).sort(["Volgende actiedatum", "Halsbandnummer"])
    df_protocol_datacontrole = df_protocol_filtered_rows.filter(
        pl.col("Aanbiedcategorie") == "Onvoldoende data"
    ).sort(["Halsbandnummer", "Koe / naam"])

    return (
        df_protocol_aanbiedlijst,
        df_protocol_datacontrole,
        df_protocol_filtered_rows,
        df_protocol_nog_niet,
    )


@app.cell
def _(
    df_protocol_aanbiedlijst,
    df_protocol_datacontrole,
    df_protocol_nog_niet,
    df_protocol_rows,
    mo,
    pl,
    protocol_category_filter,
    protocol_feed_group_filter,
    protocol_peildatum,
    protocol_reference_date,
    protocol_search_filter,
):
    """Protocol tab - bouw filters, KPI's en tabellen."""
    protocol_filter_controls = mo.hstack(
        [
            protocol_peildatum,
            protocol_category_filter,
            protocol_feed_group_filter,
            protocol_search_filter,
        ],
        justify="start",
    )

    protocol_rules_summary = mo.md(
        """
        **Selectieregels klauwbekapper**

        - **Actieve Mortellaro:** aanbieden zodra de laatste Mortellaro nog niet is gevolgd door een latere gezonde registratie met alleen `Vierkant`.
        - **Hercontrole aandoening:** aanbieden 12 weken na laatste behandeling met een aandoening anders dan Mortellaro.
        - **Preventief bekappen:** aanbieden na 183 dagen wanneer de laatste registratie alleen `Vierkant` was, de koe niet droog staat en minimaal 30 DIM is.
        - **Geen klauwdata:** aanbieden vanaf 30 DIM, zolang het geen jongvee is en de koe niet droog staat.

        """
    )

    protocol_kpi_cards = mo.hstack(
        [
            mo.stat(
                value=str(
                    df_protocol_rows.filter(pl.col("Moet aangeboden worden")).height
                ),
                label="Nu aanbieden",
                caption=f"peildatum {protocol_reference_date}",
            ),
            mo.stat(
                value=str(
                    df_protocol_rows.filter(
                        pl.col("Aanbiedcategorie") == "Actieve Mortellaro"
                    ).height
                ),
                label="Actieve Mortellaro",
                caption="direct opvolgen",
            ),
            mo.stat(
                value=str(
                    df_protocol_rows.filter(
                        pl.col("Aanbiedcategorie") == "Hercontrole aandoening"
                    ).height
                ),
                label="Hercontrole",
                caption="na 12 weken",
            ),
            mo.stat(
                value=str(
                    df_protocol_rows.filter(
                        pl.col("Aanbiedcategorie") == "Preventief bekappen"
                    ).height
                ),
                label="Preventief",
                caption="183 dagen",
            ),
            mo.stat(
                value=str(
                    df_protocol_rows.filter(
                        pl.col("Aanbiedcategorie") == "Onvoldoende data"
                    ).height
                ),
                label="Datacontrole",
                caption="onvoldoende data",
            ),
        ],
        justify="space-between",
    )

    protocol_table_columns = [
        "Halsbandnummer",
        "Voergroep nummer",
        "Reden selectie",
        "Status",
        "Status dagen",
        "Lactatie",
        "DIM",
    ]
    if df_protocol_aanbiedlijst.height > 0:
        protocol_aanbiedlijst_data = df_protocol_aanbiedlijst.select(
            protocol_table_columns
        )
        protocol_aanbiedlijst_table = mo.ui.table(
            protocol_aanbiedlijst_data.to_pandas(),
            selection="single",
            page_size=25,
        )
    else:
        protocol_aanbiedlijst_table = mo.callout(
            mo.md(
                "Geen koeien gevonden die op deze peildatum aangeboden moeten worden."
            ),
            kind="success",
        )

    if df_protocol_nog_niet.height > 0:
        protocol_nog_niet_data = df_protocol_nog_niet.select(protocol_table_columns)
        protocol_nog_niet_table = mo.ui.table(
            protocol_nog_niet_data.to_pandas(),
            selection=None,
            page_size=15,
        )
    else:
        protocol_nog_niet_table = mo.callout(
            mo.md("Geen koeien in de categorie tijdelijk niet aanbieden."),
            kind="neutral",
        )

    if df_protocol_datacontrole.height > 0:
        protocol_datacontrole_data = df_protocol_datacontrole.select(
            protocol_table_columns
        )
        protocol_datacontrole_table = mo.ui.table(
            protocol_datacontrole_data.to_pandas(),
            selection=None,
            page_size=15,
        )
    else:
        protocol_datacontrole_table = mo.callout(
            mo.md("Geen koeien met onvoldoende protocoldata."),
            kind="success",
        )

    return (
        protocol_aanbiedlijst_table,
        protocol_datacontrole_table,
        protocol_filter_controls,
        protocol_kpi_cards,
        protocol_nog_niet_table,
        protocol_rules_summary,
    )


@app.cell
def _(
    df_behandelingen_parsed,
    df_protocol_aanbiedlijst,
    mo,
    pl,
    protocol_aanbiedlijst_table,
):
    """Protocol tab - registraties voor geselecteerde aanbiedlijst-koe."""
    if df_protocol_aanbiedlijst.height == 0:
        protocol_registraties_table = mo.md("")
    elif len(protocol_aanbiedlijst_table.value) == 0:
        protocol_registraties_table = mo.callout(
            mo.md("Selecteer een koe in de aanbiedlijst om alle registraties te zien."),
            kind="neutral",
        )
    else:
        selected_protocol_row = protocol_aanbiedlijst_table.value.iloc[0]
        selected_protocol_koe = df_protocol_aanbiedlijst.filter(
            pl.col("Halsbandnummer") == selected_protocol_row["Halsbandnummer"]
        ).head(1)

        if selected_protocol_koe.height == 0:
            protocol_registraties_table = mo.callout(
                mo.md("De geselecteerde koe kon niet worden teruggevonden."),
                kind="warn",
            )
        else:
            selected_protocol_animal_id = selected_protocol_koe["animal_id"][0]
            selected_protocol_koe_naam = selected_protocol_koe["Koe / naam"][0]
            protocol_registraties_koe = (
                df_behandelingen_parsed.filter(
                    pl.col("animal_id") == selected_protocol_animal_id
                )
                .select(
                    [
                        "behandeldatum",
                        "notatie",
                    ]
                )
                .rename(
                    {
                        "behandeldatum": "Behandeldatum",
                        "notatie": "Originele notatie",
                    }
                )
                .sort("Behandeldatum", descending=True)
            )

            if protocol_registraties_koe.height == 0:
                protocol_registraties_table = mo.callout(
                    mo.md(
                        "Geen klauwbehandelingsregistraties gevonden voor "
                        f"{selected_protocol_koe_naam}."
                    ),
                    kind="warn",
                )
            else:
                protocol_registraties_table = mo.vstack(
                    [
                        mo.md(f"### Registraties {selected_protocol_koe_naam}"),
                        mo.ui.table(
                            protocol_registraties_koe.to_pandas(),
                            selection=None,
                            page_size=20,
                            label="Chronologische klauwbehandelingen",
                        ),
                    ]
                )
    return (protocol_registraties_table,)


@app.cell
def _(
    mo,
    protocol_aanbiedlijst_table,
    protocol_datacontrole_table,
    protocol_filter_controls,
    protocol_kpi_cards,
    protocol_nog_niet_table,
    protocol_registraties_table,
    protocol_rules_summary,
):
    """Protocol tab - bouw tab content."""
    protocol_content = mo.vstack(
        [
            mo.md("## Klauwbekapprotocol"),
            protocol_rules_summary,
            protocol_filter_controls,
            protocol_kpi_cards,
            mo.md("### Selectielijst te bekappen koeien"),
            protocol_aanbiedlijst_table,
            protocol_registraties_table,
            mo.md("### Niet bekappen"),
            protocol_nog_niet_table,
            mo.md("### Onvoldoende data"),
            protocol_datacontrole_table,
        ]
    )
    return (protocol_content,)


@app.cell
def _(df_behandelingen_parsed, df_open_mortellaro_rows, df_raw, mo, pl):
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

    open_mortellaro_koeien = df_open_mortellaro_rows.height

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
            unieke_aandoeningen = (
                koe_data.filter(pl.col("is_aandoening")).select("probleem").n_unique()
            )
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
                        caption=f"{unieke_aandoeningen} unieke aandoeningen",
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
                tooltip=[
                    alt.Tooltip("Behandeldatum:T", title="Datum", format="%d-%m-%Y"),
                    alt.Tooltip("Positie:N", title="Positie"),
                    alt.Tooltip("Probleem:N", title="Probleem"),
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
    """Per koe tab - chronologische klauwbehandelingen."""
    if len(koe_data) > 0:
        klauwbehandelingen_koe = (
            koe_data.select(
                [
                    "behandeldatum",
                    "notatie",
                ]
            )
            .rename(
                {
                    "behandeldatum": "Behandeldatum",
                    "notatie": "Originele notatie",
                }
            )
            .sort("Behandeldatum", descending=True)
        )

        if klauwbehandelingen_koe.height > 0:
            klauwbehandelingen_tabel_ui = mo.ui.table(
                klauwbehandelingen_koe.to_pandas(),
                selection=None,
                page_size=20,
                label="Chronologische klauwbehandelingen",
            )
        else:
            klauwbehandelingen_tabel_ui = mo.callout(
                mo.md("Deze koe heeft geen klauwbehandelingsnotaties."),
                kind="success",
            )
    else:
        klauwbehandelingen_tabel_ui = mo.md("")
    return (klauwbehandelingen_tabel_ui,)


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
    klauwbehandelingen_tabel_ui,
    koe_profiel_cards,
    koe_selectie_table,
    koe_tijdlijn_ui,
    mo,
    positie_heatmap_ui,
):
    """Per koe tab - verzamel content."""
    per_koe_content = mo.vstack(
        [
            mo.md("## Individuele koeien"),
            mo.md(
                "Klik op een koe in de tabel om gedetailleerde informatie en "
                "behandelhistorie te zien."
            ),
            koe_selectie_table,
            koe_profiel_cards,
            mo.md("### Chronologische klauwbehandelingen"),
            klauwbehandelingen_tabel_ui,
            mo.md("### Behandelhistorie tijdlijn"),
            koe_tijdlijn_ui,
            positie_heatmap_ui,
        ]
    )
    return (per_koe_content,)


@app.cell
def _(df_uniform_agri_csv_rows, mo):
    """Uniform-Agri tab - filter controls."""
    if df_uniform_agri_csv_rows.height > 0:
        min_uniform_agri_datum = df_uniform_agri_csv_rows["behandeldatum"].min()
        max_uniform_agri_datum = df_uniform_agri_csv_rows["behandeldatum"].max()
    else:
        min_uniform_agri_datum = None
        max_uniform_agri_datum = None

    uniform_agri_datum_van_filter = mo.ui.date(
        label="Van datum",
        value=str(min_uniform_agri_datum) if min_uniform_agri_datum else None,
        start=str(min_uniform_agri_datum) if min_uniform_agri_datum else None,
        stop=str(max_uniform_agri_datum) if max_uniform_agri_datum else None,
    )
    uniform_agri_datum_tot_filter = mo.ui.date(
        label="Tot datum",
        value=str(max_uniform_agri_datum) if max_uniform_agri_datum else None,
        start=str(min_uniform_agri_datum) if min_uniform_agri_datum else None,
        stop=str(max_uniform_agri_datum) if max_uniform_agri_datum else None,
    )
    uniform_agri_status_filter = mo.ui.dropdown(
        options=["Alles", "Exporteerbaar", "Fouten"],
        value="Alles",
        label="Status",
    )
    uniform_agri_zoek_filter = mo.ui.text(
        label="Zoek",
        placeholder="Animal no., notatie, behandeling-id of foutmelding",
    )
    return (
        uniform_agri_datum_tot_filter,
        uniform_agri_datum_van_filter,
        uniform_agri_status_filter,
        uniform_agri_zoek_filter,
    )


@app.cell
def _(
    df_uniform_agri_csv_rows,
    df_uniform_agri_validation_rows,
    pl,
    uniform_agri_datum_tot_filter,
    uniform_agri_datum_van_filter,
    uniform_agri_status_filter,
    uniform_agri_zoek_filter,
):
    """Uniform-Agri tab - pas filters toe op tabel en downloaddata."""
    df_uniform_agri_filtered_rows = df_uniform_agri_csv_rows

    if df_uniform_agri_filtered_rows.height > 0 and uniform_agri_datum_van_filter.value:
        df_uniform_agri_filtered_rows = df_uniform_agri_filtered_rows.filter(
            pl.col("behandeldatum") >= uniform_agri_datum_van_filter.value
        )

    if df_uniform_agri_filtered_rows.height > 0 and uniform_agri_datum_tot_filter.value:
        df_uniform_agri_filtered_rows = df_uniform_agri_filtered_rows.filter(
            pl.col("behandeldatum") <= uniform_agri_datum_tot_filter.value
        )

    if df_uniform_agri_filtered_rows.height > 0:
        if uniform_agri_status_filter.value == "Exporteerbaar":
            df_uniform_agri_filtered_rows = df_uniform_agri_filtered_rows.filter(
                pl.col("exportable")
            )
        if uniform_agri_status_filter.value == "Fouten":
            df_uniform_agri_filtered_rows = df_uniform_agri_filtered_rows.filter(
                ~pl.col("exportable")
            )

    if (
        df_uniform_agri_filtered_rows.height > 0
        and uniform_agri_zoek_filter.value
        and uniform_agri_zoek_filter.value.strip()
    ):
        zoek_term = uniform_agri_zoek_filter.value.strip().lower()
        df_uniform_agri_filtered_rows = df_uniform_agri_filtered_rows.filter(
            pl.col("animal_no").cast(pl.Utf8).str.to_lowercase().str.contains(zoek_term)
            | pl.col("notities")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(zoek_term)
            | pl.col("behandeling_ids")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(zoek_term)
            | pl.col("validation_message")
            .cast(pl.Utf8)
            .str.to_lowercase()
            .str.contains(zoek_term)
        )

    if df_uniform_agri_filtered_rows.height > 0:
        df_uniform_agri_filtered_rows = df_uniform_agri_filtered_rows.sort(
            ["exportable", "behandeldatum", "animal_no"],
            descending=[False, True, False],
        )

    df_uniform_agri_filtered_validation_rows = df_uniform_agri_validation_rows
    if (
        df_uniform_agri_filtered_validation_rows.height > 0
        and uniform_agri_datum_van_filter.value
    ):
        df_uniform_agri_filtered_validation_rows = (
            df_uniform_agri_filtered_validation_rows.filter(
                pl.col("behandeldatum") >= uniform_agri_datum_van_filter.value
            )
        )

    if (
        df_uniform_agri_filtered_validation_rows.height > 0
        and uniform_agri_datum_tot_filter.value
    ):
        df_uniform_agri_filtered_validation_rows = (
            df_uniform_agri_filtered_validation_rows.filter(
                pl.col("behandeldatum") <= uniform_agri_datum_tot_filter.value
            )
        )

    if (
        df_uniform_agri_filtered_validation_rows.height > 0
        and uniform_agri_zoek_filter.value
        and uniform_agri_zoek_filter.value.strip()
    ):
        zoek_term = uniform_agri_zoek_filter.value.strip().lower()
        df_uniform_agri_filtered_validation_rows = (
            df_uniform_agri_filtered_validation_rows.filter(
                pl.col("notatie")
                .cast(pl.Utf8)
                .str.to_lowercase()
                .str.contains(zoek_term)
                | pl.col("behandeling_id")
                .cast(pl.Utf8)
                .str.to_lowercase()
                .str.contains(zoek_term)
                | pl.col("animal_id")
                .cast(pl.Utf8)
                .str.to_lowercase()
                .str.contains(zoek_term)
                | pl.col("collar_number")
                .cast(pl.Utf8)
                .str.to_lowercase()
                .str.contains(zoek_term)
                | pl.col("validation_message")
                .cast(pl.Utf8)
                .str.to_lowercase()
                .str.contains(zoek_term)
            )
        )

    if df_uniform_agri_filtered_rows.height > 0:
        df_uniform_agri_filtered_export_rows = df_uniform_agri_filtered_rows.filter(
            pl.col("exportable")
        )
    else:
        df_uniform_agri_filtered_export_rows = pl.DataFrame()

    if df_uniform_agri_filtered_export_rows.height > 0:
        df_uniform_agri_filtered_download_rows = (
            df_uniform_agri_filtered_export_rows.select(
                [
                    "animal_no",
                    "date",
                    "health_conditions_location",
                    "treatment",
                ]
            ).rename(
                {
                    "animal_no": "animal no.",
                    "health_conditions_location": "health conditions and location",
                }
            )
        )
    else:
        df_uniform_agri_filtered_download_rows = pl.DataFrame(
            {
                "animal no.": [],
                "date": [],
                "health conditions and location": [],
                "treatment": [],
            }
        )

    return (
        df_uniform_agri_filtered_export_rows,
        df_uniform_agri_filtered_rows,
        df_uniform_agri_filtered_validation_rows,
        df_uniform_agri_filtered_download_rows,
    )


@app.cell
def _(
    df_uniform_agri_export_dataset,
    df_uniform_agri_filtered_download_rows,
    df_uniform_agri_filtered_export_rows,
    df_uniform_agri_filtered_rows,
    df_uniform_agri_filtered_validation_rows,
    df_uniform_agri_validation_rows,
    mo,
    pl,
    uniform_agri_datum_tot_filter,
    uniform_agri_datum_van_filter,
    uniform_agri_status_filter,
    uniform_agri_zoek_filter,
):
    """Uniform-Agri tab - KPI's, tabel en CSV-download."""
    uniform_agri_export_csv = df_uniform_agri_filtered_download_rows.write_csv()
    uniform_agri_export_download = mo.download(
        data=uniform_agri_export_csv.encode("utf-8-sig"),
        filename="uniform-agri-klauwbehandelingen.csv",
        mimetype="text/csv",
        label="Download CSV",
    )

    filter_controls = mo.hstack(
        [
            uniform_agri_datum_van_filter,
            uniform_agri_datum_tot_filter,
            uniform_agri_status_filter,
            uniform_agri_zoek_filter,
        ],
        justify="start",
    )
    uniform_agri_transformatie_uitleg = mo.md(
        """
        ### Transformatie Klauwscore naar Uniform-Agri

        De export gebruikt alleen klauwbehandelingen die gekoppeld zijn aan een koe
        in de huidige kudde en waarvoor een werknummer beschikbaar is.
        `animal no.` is het werknummer uit `koeien.collar_number`.
        Meerdere Klauwscore-regels van dezelfde koe op dezelfde behandeldatum worden
        samengevoegd tot een Uniform-Agri-regel.

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; align-items: start;">
        <div>
        <table>
        <thead><tr><th>Uniform-Agri veld</th><th>Transformatie</th></tr></thead>
        <tbody>
        <tr><td><code>animal no.</code></td><td><code>koeien.collar_number</code> van de gekoppelde koe</td></tr>
        <tr><td><code>date</code></td><td><code>klauw_behandelingen.behandeldatum</code> als <code>dd/mm/yyyy</code></td></tr>
        <tr><td><code>health conditions and location</code></td><td>condition-code + pootpositie-code, achter elkaar gezet per bronregel</td></tr>
        <tr><td><code>treatment</code></td><td>action-code en trim-type-code, achter elkaar gezet per bronregel</td></tr>
        </tbody>
        </table>
        </div>
        <div>
        <table>
        <thead><tr><th>Pootpositie in Klauwscore</th><th>Uniform-Agri locatiecode</th></tr></thead>
        <tbody>
        <tr><td>Rechtsvoor</td><td><code>1</code></td></tr>
        <tr><td>Linksvoor</td><td><code>3</code></td></tr>
        <tr><td>Rechtsachter</td><td><code>5</code></td></tr>
        <tr><td>Linksachter</td><td><code>7</code></td></tr>
        </tbody>
        </table>
        </div>
        </div>

        Hoofzones worden niet geexporteerd. De oude hoofzone `0` wordt dus niet in
        de CSV gezet; de CSV bevat alleen condition/location en treatment.

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; align-items: start;">
        <div>
        <table>
        <thead><tr><th>Klauwscore notatie</th><th>Uniform-Agri condition</th></tr></thead>
        <tbody>
        <tr><td>Mortellaro / Mortelaro</td><td><code>D</code></td></tr>
        <tr><td>Tussenklauwontsteking</td><td><code>I</code></td></tr>
        <tr><td>Zoolzweer</td><td><code>U</code></td></tr>
        <tr><td>Wittelijndefect</td><td><code>W</code></td></tr>
        <tr><td>Tyloom</td><td><code>K</code></td></tr>
        <tr><td>Stinkpoot</td><td><code>F</code></td></tr>
        <tr><td>Bont</td><td><code>H</code></td></tr>
        <tr><td>Chronisch bevangen</td><td><code>O</code></td></tr>
        </tbody>
        </table>
        </div>
        <div>
        <table>
        <thead><tr><th>Klauwscore behandeling</th><th>Uniform-Agri treatment</th></tr></thead>
        <tbody>
        <tr><td>Verband</td><td><code>W</code></td></tr>
        <tr><td>Klos</td><td><code>B</code></td></tr>
        <tr><td>Behandeling</td><td><code>T</code></td></tr>
        <tr><td>Vierkant</td><td><code>R</code></td></tr>
        </tbody>
        </table>
        </div>
        </div>

        Een condition zonder pootpositie, een onbekende notatie, een ontbrekende
        koppeling met `koeien`, een koe buiten de huidige kudde of een ontbrekend
        `collar_number` komt niet in de CSV en staat in het validatieoverzicht.
        """
    )

    if df_uniform_agri_filtered_rows.height > 0:
        uniform_agri_table_data = (
            df_uniform_agri_filtered_rows.with_columns(
                pl.when(pl.col("exportable"))
                .then(pl.lit("OK"))
                .otherwise(pl.lit("Fout"))
                .alias("Status")
            )
            .select(
                [
                    "Status",
                    "animal_no",
                    "date",
                    "health_conditions_location",
                    "treatment",
                    "row_count",
                    "notities",
                    "behandeling_ids",
                    "validation_message",
                ]
            )
            .rename(
                {
                    "animal_no": "animal no.",
                    "health_conditions_location": "health conditions and location",
                    "row_count": "Aantal bronregels",
                    "notities": "Notaties",
                    "behandeling_ids": "Behandeling IDs",
                    "validation_message": "Validatie",
                }
            )
        )
        uniform_agri_export_table = mo.ui.table(
            uniform_agri_table_data.to_pandas(),
            selection=None,
            page_size=20,
            label="Uniform-Agri regels",
        )
    else:
        uniform_agri_export_table = mo.callout(
            mo.md("Geen Uniform-Agri regels gevonden voor deze filters."),
            kind="warn",
        )

    if df_uniform_agri_filtered_validation_rows.height > 0:
        validation_columns = [
            column
            for column in [
                "behandeling_id",
                "animal_id",
                "koe_animal_id",
                "collar_number",
                "in_current_herd",
                "behandeldatum",
                "notatie",
                "eartag_short",
                "eartag",
                "validation_message",
            ]
            if column in df_uniform_agri_filtered_validation_rows.columns
        ]
        uniform_agri_validation_table = mo.ui.table(
            df_uniform_agri_filtered_validation_rows.select(
                validation_columns
            ).to_pandas(),
            selection=None,
            page_size=20,
            label="Niet-exporteerbare bronregels",
        )
    else:
        uniform_agri_validation_table = mo.callout(
            mo.md("Geen niet-exporteerbare bronregels gevonden voor deze filters."),
            kind="success",
        )

    uniform_agri_content = mo.vstack(
        [
            mo.md("## Uniform-Agri"),
            mo.hstack(
                [
                    mo.stat(
                        value=str(df_uniform_agri_export_dataset.height),
                        label="Exportregels totaal",
                        caption="huidige kudde met werknummer",
                    ),
                    mo.stat(
                        value=str(df_uniform_agri_filtered_export_rows.height),
                        label="Exportregels gefilterd",
                        caption="worden opgenomen in CSV",
                    ),
                    mo.stat(
                        value=str(df_uniform_agri_validation_rows.height),
                        label="Fouten totaal",
                        caption="niet opgenomen in CSV",
                    ),
                    mo.stat(
                        value=str(df_uniform_agri_filtered_validation_rows.height),
                        label="Fouten gefilterd",
                        caption="bronregels met validatiemelding",
                    ),
                ],
                justify="space-between",
            ),
            filter_controls,
            uniform_agri_export_download,
            uniform_agri_transformatie_uitleg,
            mo.md("### Regels"),
            uniform_agri_export_table,
            mo.md("### Validatieoverzicht"),
            uniform_agri_validation_table,
        ]
    )
    return (uniform_agri_content,)


@app.cell
def _(
    mo,
    per_koe_content,
    protocol_content,
    uniform_agri_content,
):
    """Tab navigatie - hoofdstructuur."""
    tabs = mo.ui.tabs(
        {
            "Protocol": protocol_content,
            "Individuele koeien": per_koe_content,
            "Uniform-Agri": uniform_agri_content,
        }
    )

    mo.vstack([tabs])
    return


if __name__ == "__main__":
    app.run()
