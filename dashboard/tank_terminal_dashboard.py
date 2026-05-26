"""Tank Terminal dashboard."""

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full")


@app.cell
def _():
    """Imports en configuratie."""
    import os
    from datetime import date
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl
    from dotenv import load_dotenv

    from database import database
    from database.persistence import tank_terminal as tank_terminal_persistence
    from database.repositories.tank_transactions_repository import (
        TankTransactionsRepository,
    )
    from data_jobs.tank_terminal import csv_parsers
    from data_jobs.tank_terminal.csv_parsers import TankTerminalCsvParseError

    _repo_root = Path(__file__).parent.parent
    _env_path = _repo_root / ".env"
    load_dotenv(_env_path)

    return (
        TankTerminalCsvParseError,
        TankTransactionsRepository,
        alt,
        csv_parsers,
        database,
        date,
        mo,
        os,
        pl,
        tank_terminal_persistence,
    )


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
        # Tank Terminal Dashboard

        Overzicht van dieseltransacties en handmatige CSV-imports.
        """
    )
    return


@app.cell
def _(mo):
    """CSV-upload controls."""
    csv_upload = mo.ui.file(
        filetypes=[".csv"],
        kind="area",
        label="Upload Tank Terminal CSV-export",
        max_size=25_000_000,
    )
    import_button = mo.ui.run_button(
        label="Importeer CSV",
        kind="success",
    )

    upload_content = mo.vstack(
        [
            mo.md("## CSV import"),
            csv_upload,
            import_button,
        ]
    )
    return csv_upload, import_button, upload_content


@app.cell
def _(
    TankTerminalCsvParseError,
    TankTransactionsRepository,
    csv_parsers,
    csv_upload,
    database,
    import_button,
    mo,
    tank_terminal_persistence,
):
    """CSV verwerken en opslaan op start_date_time."""
    import_result = {
        "attempted": False,
        "kind": "neutral",
        "message": "Nog geen CSV geimporteerd.",
    }

    if import_button.value:
        if not csv_upload.value:
            import_result = {
                "attempted": True,
                "kind": "warn",
                "message": "Kies eerst een CSV-bestand.",
            }
        else:
            try:
                csv_text = csv_upload.contents().decode("utf-8-sig")
                transactions = csv_parsers.parse_tank_transactions_csv_text(csv_text)
                repository = TankTransactionsRepository(database.get_session)
                saved_count = tank_terminal_persistence.save_tank_transaction_models_by_start_date_time(
                    transactions,
                    repository=repository,
                )
                import_result = {
                    "attempted": True,
                    "kind": "success",
                    "message": (
                        f"{saved_count} transacties verwerkt uit "
                        f"`{csv_upload.name()}`. Bestaande transacties met dezelfde "
                        "`start_date_time` zijn bijgewerkt."
                    ),
                }
            except (TankTerminalCsvParseError, UnicodeDecodeError, ValueError) as exc:
                import_result = {
                    "attempted": True,
                    "kind": "danger",
                    "message": f"CSV-import mislukt: {exc}",
                }

    import_status = mo.callout(
        mo.md(import_result["message"]),
        kind=import_result["kind"],
    )
    return import_result, import_status


@app.cell
def _(connectorx_database_url, import_result, pl):
    """Tanktransacties laden."""
    _ = import_result
    tank_transactions_query = """
    SELECT
        transaction_number,
        start_date_time,
        transaction_date,
        transaction_hour,
        vehicle,
        vehicle_number,
        driver,
        driver_number,
        product,
        quantity_liters,
        quantity_units,
        dispenser,
        tank,
        odometer,
        hours_counter,
        acquisition_mode,
        transaction_status,
        transaction_type,
        transaction_result,
        vehicle_identifier,
        driver_identifier,
        meter_value,
        meter_type
    FROM tank_transactions
    ORDER BY start_date_time DESC
    """

    df_transactions = pl.read_database_uri(
        query=tank_transactions_query,
        uri=connectorx_database_url,
    )
    return (df_transactions,)


@app.cell
def _(df_transactions, mo, pl):
    """Filter controls."""
    mo.md("## Filters")

    if df_transactions.height > 0:
        min_date = df_transactions["start_date_time"].dt.date().min()
        max_date = df_transactions["start_date_time"].dt.date().max()
    else:
        min_date = None
        max_date = None

    datum_van_filter = mo.ui.date(
        label="Van datum",
        value=str(min_date) if min_date else None,
        start=str(min_date) if min_date else None,
        stop=str(max_date) if max_date else None,
    )
    datum_tot_filter = mo.ui.date(
        label="Tot datum",
        value=str(max_date) if max_date else None,
        start=str(min_date) if min_date else None,
        stop=str(max_date) if max_date else None,
    )

    voertuigen = (
        df_transactions.filter(pl.col("vehicle").is_not_null())
        .select("vehicle")
        .unique()
        .sort("vehicle")["vehicle"]
        .to_list()
        if df_transactions.height > 0
        else []
    )
    vehicle_filter = mo.ui.multiselect(
        options=voertuigen,
        value=voertuigen,
        label="Voertuigen",
    )

    drivers = (
        df_transactions.filter(pl.col("driver").is_not_null())
        .select("driver")
        .unique()
        .sort("driver")["driver"]
        .to_list()
        if df_transactions.height > 0
        else []
    )
    driver_filter = mo.ui.multiselect(
        options=drivers,
        value=drivers,
        label="Chauffeurs",
    )

    filters_content = mo.hstack(
        [datum_van_filter, datum_tot_filter, vehicle_filter, driver_filter],
        justify="start",
    )
    return (
        datum_tot_filter,
        datum_van_filter,
        driver_filter,
        filters_content,
        vehicle_filter,
    )


@app.cell
def _(
    datum_tot_filter,
    datum_van_filter,
    date,
    df_transactions,
    driver_filter,
    pl,
    vehicle_filter,
):
    """Filters toepassen."""
    df_filtered = df_transactions

    if df_filtered.height > 0 and datum_van_filter.value:
        datum_van = date.fromisoformat(str(datum_van_filter.value))
        df_filtered = df_filtered.filter(
            pl.col("start_date_time").dt.date() >= datum_van
        )

    if df_filtered.height > 0 and datum_tot_filter.value:
        datum_tot = date.fromisoformat(str(datum_tot_filter.value))
        df_filtered = df_filtered.filter(
            pl.col("start_date_time").dt.date() <= datum_tot
        )

    if df_filtered.height > 0 and vehicle_filter.value:
        df_filtered = df_filtered.filter(pl.col("vehicle").is_in(vehicle_filter.value))

    if df_filtered.height > 0 and driver_filter.value:
        df_filtered = df_filtered.filter(pl.col("driver").is_in(driver_filter.value))

    return (df_filtered,)


@app.cell
def _(df_filtered, df_transactions, mo, pl):
    """KPI's."""
    if df_transactions.height == 0:
        kpi_cards = mo.callout(
            mo.md("Nog geen tanktransacties gevonden in de database."),
            kind="neutral",
        )
    else:
        totaal_liters = df_filtered.select(pl.col("quantity_liters").sum())[0, 0] or 0
        aantal_transacties = df_filtered.height
        aantal_voertuigen = df_filtered.select("vehicle").n_unique()
        laatste_transactie = df_transactions["start_date_time"].max()

        kpi_cards = mo.hstack(
            [
                mo.stat(
                    value=str(aantal_transacties),
                    label="Transacties",
                    caption="binnen huidige filter",
                ),
                mo.stat(
                    value=f"{totaal_liters:,.1f} L",
                    label="Totaal diesel",
                    caption="binnen huidige filter",
                ),
                mo.stat(
                    value=str(aantal_voertuigen),
                    label="Voertuigen",
                    caption="uniek binnen huidige filter",
                ),
                mo.stat(
                    value=str(laatste_transactie),
                    label="Laatste transactie",
                    caption="meest recente import/data",
                ),
            ],
            justify="space-between",
        )
    return (kpi_cards,)


@app.cell
def _(alt, df_filtered, mo, pl):
    """Grafieken."""
    if df_filtered.height == 0:
        charts_content = mo.md("")
    else:
        liters_per_day = (
            df_filtered.with_columns(pl.col("start_date_time").dt.date().alias("datum"))
            .group_by("datum")
            .agg(pl.col("quantity_liters").sum().round(2).alias("Liters"))
            .sort("datum")
        )
        liters_per_vehicle = (
            df_filtered.group_by("vehicle")
            .agg(pl.col("quantity_liters").sum().round(2).alias("Liters"))
            .sort("Liters", descending=True)
            .head(15)
            .rename({"vehicle": "Voertuig"})
        )

        daily_chart = (
            alt.Chart(liters_per_day.to_pandas())
            .mark_bar(color="#2563eb")
            .encode(
                x=alt.X("datum:T", title="Datum"),
                y=alt.Y("Liters:Q", title="Liters"),
                tooltip=[
                    alt.Tooltip("datum:T", title="Datum", format="%d-%m-%Y"),
                    alt.Tooltip("Liters:Q", title="Liters"),
                ],
            )
            .properties(width=900, height=280, title="Dieselverbruik per dag")
        )
        vehicle_chart = (
            alt.Chart(liters_per_vehicle.to_pandas())
            .mark_bar(color="#16a34a")
            .encode(
                x=alt.X("Liters:Q", title="Liters"),
                y=alt.Y("Voertuig:N", title="Voertuig", sort="-x"),
                tooltip=[
                    alt.Tooltip("Voertuig:N", title="Voertuig"),
                    alt.Tooltip("Liters:Q", title="Liters"),
                ],
            )
            .properties(width=900, height=360, title="Dieselverbruik per voertuig")
        )
        charts_content = mo.vstack(
            [
                mo.ui.altair_chart(daily_chart),
                mo.ui.altair_chart(vehicle_chart),
            ]
        )
    return (charts_content,)


@app.cell
def _(df_filtered, mo, pl):
    """Tabellen."""
    if df_filtered.height == 0:
        transactions_table = mo.callout(
            mo.md("Geen transacties binnen de huidige filter."),
            kind="neutral",
        )
        driver_table = mo.md("")
    else:
        transactions_table_data = df_filtered.select(
            [
                "start_date_time",
                "transaction_number",
                "vehicle",
                "vehicle_number",
                "driver",
                "driver_number",
                "quantity_liters",
                "quantity_units",
                "dispenser",
                "tank",
                "odometer",
                "hours_counter",
                "transaction_status",
                "transaction_result",
            ]
        ).rename(
            {
                "start_date_time": "Start",
                "transaction_number": "Transactie",
                "vehicle": "Voertuig",
                "vehicle_number": "Voertuig nr",
                "driver": "Chauffeur",
                "driver_number": "Chauffeur nr",
                "quantity_liters": "Liters",
                "quantity_units": "Eenheid",
                "dispenser": "Dispenser",
                "tank": "Tank",
                "odometer": "Kilometerstand",
                "hours_counter": "Urenteller",
                "transaction_status": "Status",
                "transaction_result": "Resultaat",
            }
        )
        transactions_table = mo.ui.table(
            transactions_table_data.to_pandas(),
            selection=None,
            page_size=20,
            label="Tanktransacties",
        )

        driver_table_data = (
            df_filtered.group_by("driver")
            .agg(
                [
                    pl.len().alias("Transacties"),
                    pl.col("quantity_liters").sum().round(2).alias("Liters"),
                ]
            )
            .sort("Liters", descending=True)
            .rename({"driver": "Chauffeur"})
        )
        driver_table = mo.ui.table(
            driver_table_data.to_pandas(),
            selection=None,
            page_size=15,
            label="Dieselverbruik per chauffeur",
        )

    tables_content = mo.vstack(
        [
            mo.md("## Details"),
            transactions_table,
            mo.md("### Per chauffeur"),
            driver_table,
        ]
    )
    return (tables_content,)


@app.cell
def _(
    charts_content,
    filters_content,
    import_status,
    kpi_cards,
    mo,
    tables_content,
    upload_content,
):
    """Dashboard layout."""
    tabs = mo.ui.tabs(
        {
            "Overzicht": mo.vstack(
                [
                    filters_content,
                    kpi_cards,
                    charts_content,
                    tables_content,
                ]
            ),
            "CSV import": mo.vstack([upload_content, import_status]),
        }
    )

    mo.vstack([tabs])
    return


if __name__ == "__main__":
    app.run()
