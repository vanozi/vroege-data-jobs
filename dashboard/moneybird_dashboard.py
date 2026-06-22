"""Moneybird bookkeeping dashboard."""

from decimal import Decimal

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

    _repo_root = Path(__file__).parent.parent
    _env_path = _repo_root / ".env"
    load_dotenv(_env_path)

    return alt, date, mo, os, pl


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
        # Moneybird Dashboard

        Read-only overzicht van lokaal gesynchroniseerde boekhouddata.
        """
    )
    return


@app.cell
def _(connectorx_database_url, pl):
    """Data laden uit lokale Moneybird-tabellen."""
    sales_invoices_query = """
    SELECT
        s.moneybird_id,
        s.invoice_id,
        s.contact_id,
        COALESCE(
            NULLIF(c.company_name, ''),
            NULLIF(TRIM(COALESCE(c.firstname, '') || ' ' || COALESCE(c.lastname, '')), ''),
            s.contact_name
        ) AS contact_name,
        s.state,
        s.invoice_date,
        s.due_date,
        s.paid_at,
        s.currency,
        s.total_price_excl_tax,
        s.total_price_incl_tax,
        s.total_paid,
        s.total_unpaid,
        s.reminder_count,
        s.moneybird_updated_at,
        s.synced_at
    FROM moneybird_sales_invoices s
    LEFT JOIN moneybird_contacts c
        ON c.administration_id = s.administration_id
        AND c.moneybird_id = s.contact_id
    ORDER BY s.invoice_date DESC NULLS LAST, s.invoice_id DESC NULLS LAST
    """
    purchase_invoices_query = """
    SELECT
        p.moneybird_id,
        p.contact_id,
        COALESCE(
            NULLIF(c.company_name, ''),
            NULLIF(TRIM(COALESCE(c.firstname, '') || ' ' || COALESCE(c.lastname, '')), ''),
            p.contact_name
        ) AS contact_name,
        p.reference,
        p.entry_number,
        p.state,
        p.date,
        p.due_date,
        p.paid_at,
        p.currency,
        p.total_price_excl_tax,
        p.total_price_incl_tax,
        p.total_price_excl_tax_base,
        p.total_price_incl_tax_base,
        p.moneybird_updated_at,
        p.synced_at
    FROM moneybird_purchase_invoices p
    LEFT JOIN moneybird_contacts c
        ON c.administration_id = p.administration_id
        AND c.moneybird_id = p.contact_id
    ORDER BY p.date DESC NULLS LAST, p.entry_number DESC NULLS LAST
    """
    report_snapshots_query = """
    SELECT
        administration_id,
        report_type,
        period,
        total_revenue,
        total_expenses,
        gross_profit,
        operating_profit,
        net_profit,
        synced_at
    FROM moneybird_report_snapshots
    ORDER BY period DESC, report_type
    """
    ledger_accounts_query = """
    SELECT
        moneybird_id,
        name,
        account_type,
        account_id,
        moneybird_version,
        synced_at
    FROM moneybird_ledger_accounts
    ORDER BY account_type NULLS LAST, account_id NULLS LAST, name
    """
    financial_mutations_query = """
    SELECT
        m.moneybird_id,
        m.financial_account_id,
        a.name AS financial_account_name,
        m.date,
        m.amount,
        m.amount_open,
        m.message,
        m.code,
        m.contra_account_name,
        m.contra_account_number,
        m.state,
        m.settlement_state,
        m.moneybird_updated_at,
        m.synced_at
    FROM moneybird_financial_mutations m
    LEFT JOIN moneybird_financial_accounts a
        ON a.administration_id = m.administration_id
        AND a.moneybird_id = m.financial_account_id
    ORDER BY m.date DESC NULLS LAST, m.moneybird_id DESC
    """
    financial_accounts_query = """
    SELECT
        moneybird_id,
        type,
        name,
        identifier,
        currency,
        provider,
        active,
        synced_at
    FROM moneybird_financial_accounts
    ORDER BY active DESC NULLS LAST, name
    """

    df_sales_invoices = pl.read_database_uri(
        query=sales_invoices_query,
        uri=connectorx_database_url,
    )
    df_purchase_invoices = pl.read_database_uri(
        query=purchase_invoices_query,
        uri=connectorx_database_url,
    )
    df_report_snapshots = pl.read_database_uri(
        query=report_snapshots_query,
        uri=connectorx_database_url,
    )
    df_ledger_accounts = pl.read_database_uri(
        query=ledger_accounts_query,
        uri=connectorx_database_url,
    )
    df_financial_mutations = pl.read_database_uri(
        query=financial_mutations_query,
        uri=connectorx_database_url,
    )
    df_financial_accounts = pl.read_database_uri(
        query=financial_accounts_query,
        uri=connectorx_database_url,
    )
    return (
        df_financial_accounts,
        df_financial_mutations,
        df_ledger_accounts,
        df_purchase_invoices,
        df_report_snapshots,
        df_sales_invoices,
    )


@app.cell
def _(df_purchase_invoices, df_report_snapshots, df_sales_invoices, mo, pl):
    """Filter controls."""
    all_invoice_dates = []
    if df_sales_invoices.height > 0:
        all_invoice_dates.extend(
            df_sales_invoices.filter(pl.col("invoice_date").is_not_null())[
                "invoice_date"
            ].to_list()
        )
    if df_purchase_invoices.height > 0:
        all_invoice_dates.extend(
            df_purchase_invoices.filter(pl.col("date").is_not_null())["date"].to_list()
        )

    min_date = min(all_invoice_dates) if all_invoice_dates else None
    max_date = max(all_invoice_dates) if all_invoice_dates else None

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

    sales_states = _unique_strings(df_sales_invoices, "state", pl)
    purchase_states = _unique_strings(df_purchase_invoices, "state", pl)
    periods = _unique_strings(df_report_snapshots, "period", pl)

    sales_state_filter = mo.ui.multiselect(
        options=sales_states,
        value=sales_states,
        label="Verkoopstatus",
    )
    purchase_state_filter = mo.ui.multiselect(
        options=purchase_states,
        value=purchase_states,
        label="Inkoopstatus",
    )
    period_filter = mo.ui.dropdown(
        options=periods,
        value=periods[0] if periods else None,
        label="Rapportperiode",
    )

    filters_content = mo.hstack(
        [
            datum_van_filter,
            datum_tot_filter,
            period_filter,
            sales_state_filter,
            purchase_state_filter,
        ],
        justify="start",
    )
    return (
        datum_tot_filter,
        datum_van_filter,
        filters_content,
        period_filter,
        purchase_state_filter,
        sales_state_filter,
    )


@app.cell
def _(
    date,
    datum_tot_filter,
    datum_van_filter,
    df_financial_mutations,
    df_purchase_invoices,
    df_report_snapshots,
    df_sales_invoices,
    period_filter,
    pl,
    purchase_state_filter,
    sales_state_filter,
):
    """Filters toepassen."""
    df_sales_filtered = df_sales_invoices
    df_purchase_filtered = df_purchase_invoices
    df_mutations_filtered = df_financial_mutations
    df_reports_filtered = df_report_snapshots

    if period_filter.value and df_reports_filtered.height > 0:
        df_reports_filtered = df_reports_filtered.filter(
            pl.col("period") == str(period_filter.value)
        )

    if datum_van_filter.value:
        datum_van = date.fromisoformat(str(datum_van_filter.value))
        if df_sales_filtered.height > 0:
            df_sales_filtered = df_sales_filtered.filter(
                pl.col("invoice_date").is_null() | (pl.col("invoice_date") >= datum_van)
            )
        if df_purchase_filtered.height > 0:
            df_purchase_filtered = df_purchase_filtered.filter(
                pl.col("date").is_null() | (pl.col("date") >= datum_van)
            )
        if df_mutations_filtered.height > 0:
            df_mutations_filtered = df_mutations_filtered.filter(
                pl.col("date").is_null() | (pl.col("date") >= datum_van)
            )

    if datum_tot_filter.value:
        datum_tot = date.fromisoformat(str(datum_tot_filter.value))
        if df_sales_filtered.height > 0:
            df_sales_filtered = df_sales_filtered.filter(
                pl.col("invoice_date").is_null() | (pl.col("invoice_date") <= datum_tot)
            )
        if df_purchase_filtered.height > 0:
            df_purchase_filtered = df_purchase_filtered.filter(
                pl.col("date").is_null() | (pl.col("date") <= datum_tot)
            )
        if df_mutations_filtered.height > 0:
            df_mutations_filtered = df_mutations_filtered.filter(
                pl.col("date").is_null() | (pl.col("date") <= datum_tot)
            )

    if sales_state_filter.value and df_sales_filtered.height > 0:
        df_sales_filtered = df_sales_filtered.filter(
            pl.col("state").is_in(sales_state_filter.value)
        )
    if purchase_state_filter.value and df_purchase_filtered.height > 0:
        df_purchase_filtered = df_purchase_filtered.filter(
            pl.col("state").is_in(purchase_state_filter.value)
        )

    return (
        df_mutations_filtered,
        df_purchase_filtered,
        df_reports_filtered,
        df_sales_filtered,
    )


@app.cell
def _(
    df_mutations_filtered,
    df_purchase_filtered,
    df_reports_filtered,
    df_sales_filtered,
    mo,
    pl,
):
    """KPI's."""
    if (
        df_sales_filtered.height == 0
        and df_purchase_filtered.height == 0
        and df_reports_filtered.height == 0
    ):
        kpi_cards = mo.callout(
            mo.md("Nog geen Moneybird data gevonden in de lokale database."),
            kind="neutral",
        )
    else:
        omzet = _report_value(df_reports_filtered, "profit_loss", "total_revenue", pl)
        resultaat = _report_value(df_reports_filtered, "profit_loss", "net_profit", pl)
        open_debiteuren = _sum_column(df_sales_filtered, "total_unpaid", pl)
        open_crediteuren = _sum_open_purchase(df_purchase_filtered, pl)
        bank_mutaties = _sum_column(df_mutations_filtered, "amount", pl)

        kpi_cards = mo.hstack(
            [
                mo.stat(
                    value=_format_euro(omzet),
                    label="Omzet",
                    caption="profit/loss rapport",
                ),
                mo.stat(
                    value=_format_euro(resultaat),
                    label="Resultaat",
                    caption="netto resultaat",
                ),
                mo.stat(
                    value=_format_euro(open_debiteuren),
                    label="Open debiteuren",
                    caption="verkoopfacturen",
                ),
                mo.stat(
                    value=_format_euro(open_crediteuren),
                    label="Open crediteuren",
                    caption="onbetaalde inkoopfacturen",
                ),
                mo.stat(
                    value=_format_euro(bank_mutaties),
                    label="Bankmutaties",
                    caption="som binnen filter",
                ),
            ],
            justify="space-between",
        )
    return (kpi_cards,)


@app.cell
def _(alt, df_purchase_filtered, df_sales_filtered, mo, pl):
    """Factuurtrend."""
    chart_frames = []
    if df_sales_filtered.height > 0:
        chart_frames.append(
            _monthly_amounts(
                df_sales_filtered,
                date_column="invoice_date",
                amount_column="total_price_incl_tax",
                label="Verkoop",
                pl=pl,
            )
        )
    if df_purchase_filtered.height > 0:
        chart_frames.append(
            _monthly_amounts(
                df_purchase_filtered,
                date_column="date",
                amount_column="total_price_incl_tax",
                label="Inkoop",
                pl=pl,
            )
        )

    chart_data = (
        pl.concat(chart_frames, how="vertical") if chart_frames else pl.DataFrame()
    )
    if chart_data.height == 0:
        invoice_chart = mo.md("")
    else:
        chart = (
            alt.Chart(chart_data.to_pandas())
            .mark_bar()
            .encode(
                x=alt.X("Maand:N", title="Maand"),
                y=alt.Y("Bedrag:Q", title="Bedrag incl. btw"),
                color=alt.Color("Type:N", title="Type"),
                tooltip=[
                    alt.Tooltip("Maand:N", title="Maand"),
                    alt.Tooltip("Type:N", title="Type"),
                    alt.Tooltip("Bedrag:Q", title="Bedrag", format=",.2f"),
                ],
            )
            .properties(width=900, height=320, title="Factuurbedragen per maand")
        )
        invoice_chart = mo.ui.altair_chart(chart)
    return (invoice_chart,)


@app.cell
def _(df_sales_filtered, mo):
    """Verkoopfacturen tabel."""
    if df_sales_filtered.height == 0:
        sales_table = mo.callout(
            mo.md("Geen verkoopfacturen binnen de huidige filter."),
            kind="neutral",
        )
    else:
        sales_table = mo.ui.table(
            df_sales_filtered.select(
                [
                    "invoice_date",
                    "invoice_id",
                    "contact_name",
                    "state",
                    "due_date",
                    "paid_at",
                    "currency",
                    "total_price_incl_tax",
                    "total_paid",
                    "total_unpaid",
                    "reminder_count",
                ]
            )
            .rename(
                {
                    "invoice_date": "Factuurdatum",
                    "invoice_id": "Factuurnummer",
                    "contact_name": "Contact",
                    "state": "Status",
                    "due_date": "Vervaldatum",
                    "paid_at": "Betaaldatum",
                    "currency": "Valuta",
                    "total_price_incl_tax": "Totaal incl. btw",
                    "total_paid": "Betaald",
                    "total_unpaid": "Open",
                    "reminder_count": "Herinneringen",
                }
            )
            .to_pandas(),
            selection=None,
            page_size=20,
            label="Verkoopfacturen",
        )
    return (sales_table,)


@app.cell
def _(df_purchase_filtered, mo):
    """Inkoopfacturen tabel."""
    if df_purchase_filtered.height == 0:
        purchase_table = mo.callout(
            mo.md("Geen inkoopfacturen binnen de huidige filter."),
            kind="neutral",
        )
    else:
        purchase_table = mo.ui.table(
            df_purchase_filtered.select(
                [
                    "date",
                    "entry_number",
                    "reference",
                    "contact_name",
                    "state",
                    "due_date",
                    "paid_at",
                    "currency",
                    "total_price_incl_tax",
                    "total_price_incl_tax_base",
                ]
            )
            .rename(
                {
                    "date": "Datum",
                    "entry_number": "Boekstuk",
                    "reference": "Referentie",
                    "contact_name": "Contact",
                    "state": "Status",
                    "due_date": "Vervaldatum",
                    "paid_at": "Betaaldatum",
                    "currency": "Valuta",
                    "total_price_incl_tax": "Totaal incl. btw",
                    "total_price_incl_tax_base": "Totaal basisvaluta",
                }
            )
            .to_pandas(),
            selection=None,
            page_size=20,
            label="Inkoopfacturen",
        )
    return (purchase_table,)


@app.cell
def _(df_ledger_accounts, df_reports_filtered, mo):
    """Rapporten en grootboekrekeningen."""
    if df_reports_filtered.height == 0:
        reports_table = mo.callout(
            mo.md("Geen rapport snapshots gevonden voor de gekozen periode."),
            kind="neutral",
        )
    else:
        reports_table = mo.ui.table(
            df_reports_filtered.rename(
                {
                    "report_type": "Rapport",
                    "period": "Periode",
                    "total_revenue": "Omzet",
                    "total_expenses": "Kosten",
                    "gross_profit": "Brutomarge",
                    "operating_profit": "Operationeel resultaat",
                    "net_profit": "Netto resultaat",
                    "synced_at": "Gesynchroniseerd",
                }
            ).to_pandas(),
            selection=None,
            page_size=10,
            label="Rapport snapshots",
        )

    if df_ledger_accounts.height == 0:
        ledger_table = mo.callout(
            mo.md("Geen grootboekrekeningen lokaal beschikbaar."),
            kind="neutral",
        )
    else:
        ledger_table = mo.ui.table(
            df_ledger_accounts.rename(
                {
                    "moneybird_id": "Moneybird ID",
                    "name": "Naam",
                    "account_type": "Type",
                    "account_id": "Rekening",
                    "moneybird_version": "Versie",
                    "synced_at": "Gesynchroniseerd",
                }
            ).to_pandas(),
            selection=None,
            page_size=20,
            label="Grootboekrekeningen",
        )

    reports_content = mo.vstack(
        [
            mo.md("## Rapporten"),
            reports_table,
            mo.md("## Grootboekrekeningen"),
            ledger_table,
        ]
    )
    return (reports_content,)


@app.cell
def _(df_financial_accounts, df_mutations_filtered, mo):
    """Bank tabellen."""
    if df_financial_accounts.height == 0:
        accounts_table = mo.callout(
            mo.md("Geen financiele rekeningen lokaal beschikbaar."),
            kind="neutral",
        )
    else:
        accounts_table = mo.ui.table(
            df_financial_accounts.rename(
                {
                    "moneybird_id": "Moneybird ID",
                    "type": "Type",
                    "name": "Naam",
                    "identifier": "Identificatie",
                    "currency": "Valuta",
                    "provider": "Provider",
                    "active": "Actief",
                    "synced_at": "Gesynchroniseerd",
                }
            ).to_pandas(),
            selection=None,
            page_size=10,
            label="Financiele rekeningen",
        )

    if df_mutations_filtered.height == 0:
        mutations_table = mo.callout(
            mo.md("Geen bankmutaties binnen de huidige filter."),
            kind="neutral",
        )
    else:
        mutations_table = mo.ui.table(
            df_mutations_filtered.select(
                [
                    "date",
                    "financial_account_name",
                    "amount",
                    "amount_open",
                    "contra_account_name",
                    "contra_account_number",
                    "message",
                    "state",
                    "settlement_state",
                ]
            )
            .rename(
                {
                    "date": "Datum",
                    "financial_account_name": "Rekening",
                    "amount": "Bedrag",
                    "amount_open": "Open",
                    "contra_account_name": "Tegenrekening naam",
                    "contra_account_number": "Tegenrekening",
                    "message": "Omschrijving",
                    "state": "Status",
                    "settlement_state": "Afletterstatus",
                }
            )
            .to_pandas(),
            selection=None,
            page_size=25,
            label="Bankmutaties",
        )

    bank_content = mo.vstack(
        [
            mo.md("## Financiele rekeningen"),
            accounts_table,
            mo.md("## Bankmutaties"),
            mutations_table,
        ]
    )
    return (bank_content,)


@app.cell
def _(
    bank_content,
    filters_content,
    invoice_chart,
    kpi_cards,
    mo,
    purchase_table,
    reports_content,
    sales_table,
):
    """Dashboard layout."""
    tabs = mo.ui.tabs(
        {
            "Overzicht": mo.vstack(
                [
                    filters_content,
                    kpi_cards,
                    invoice_chart,
                ]
            ),
            "Verkoop": sales_table,
            "Inkoop": purchase_table,
            "Rapporten": reports_content,
            "Bank": bank_content,
        }
    )

    mo.vstack([tabs])
    return


def _unique_strings(df, column: str, pl) -> list[str]:
    if df.height == 0 or column not in df.columns:
        return []

    return (
        df.filter(pl.col(column).is_not_null())
        .select(column)
        .unique()
        .sort(column)[column]
        .cast(pl.String)
        .to_list()
    )


def _sum_column(df, column: str, pl) -> Decimal:
    if df.height == 0 or column not in df.columns:
        return Decimal("0")

    value = df.select(pl.col(column).sum())[0, 0]
    if value is None:
        return Decimal("0")

    return Decimal(str(value))


def _sum_open_purchase(df, pl) -> Decimal:
    if df.height == 0:
        return Decimal("0")

    open_rows = df.filter(pl.col("paid_at").is_null())
    return _sum_column(open_rows, "total_price_incl_tax", pl)


def _report_value(df, report_type: str, column: str, pl) -> Decimal:
    if df.height == 0 or column not in df.columns:
        return Decimal("0")

    rows = df.filter(pl.col("report_type") == report_type)
    return _sum_column(rows, column, pl)


def _format_euro(value: Decimal) -> str:
    return f"EUR {value:,.2f}"


def _monthly_amounts(
    df,
    *,
    date_column: str,
    amount_column: str,
    label: str,
    pl,
):
    if df.height == 0:
        return pl.DataFrame()

    return (
        df.filter(pl.col(date_column).is_not_null())
        .with_columns(pl.col(date_column).dt.strftime("%Y-%m").alias("Maand"))
        .group_by("Maand")
        .agg(pl.col(amount_column).sum().cast(pl.Float64).round(2).alias("Bedrag"))
        .with_columns(pl.lit(label).alias("Type"))
        .select(["Maand", "Type", "Bedrag"])
        .sort("Maand")
    )


if __name__ == "__main__":
    app.run()
