"""Moneybird bookkeeping dashboard."""

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

    from dashboard import moneybird_transforms

    _repo_root = Path(__file__).parent.parent
    _env_path = _repo_root / ".env"
    load_dotenv(_env_path)

    return alt, date, mo, moneybird_transforms, os, pl


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
        c.moneybird_id AS local_contact_id,
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
        c.moneybird_id AS local_contact_id,
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
        raw_json,
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
def _(
    df_financial_mutations,
    df_purchase_invoices,
    df_report_snapshots,
    df_sales_invoices,
    moneybird_transforms,
    mo,
    pl,
):
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
    if df_financial_mutations.height > 0:
        all_invoice_dates.extend(
            df_financial_mutations.filter(pl.col("date").is_not_null())[
                "date"
            ].to_list()
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

    sales_states = moneybird_transforms._unique_strings(df_sales_invoices, "state", pl)
    purchase_states = moneybird_transforms._unique_strings(
        df_purchase_invoices, "state", pl
    )
    periods = moneybird_transforms._unique_strings(df_report_snapshots, "period", pl)
    sales_contacts = moneybird_transforms._top_unique_strings(
        df_sales_invoices,
        "contact_name",
        pl,
        limit=250,
    )
    purchase_contacts = moneybird_transforms._top_unique_strings(
        df_purchase_invoices,
        "contact_name",
        pl,
        limit=250,
    )
    bank_accounts = moneybird_transforms._top_unique_strings(
        df_financial_mutations,
        "financial_account_name",
        pl,
        limit=250,
    )
    bank_states = moneybird_transforms._unique_strings(
        df_financial_mutations, "state", pl
    )

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
    purchase_contact_filter = mo.ui.multiselect(
        options=purchase_contacts,
        value=purchase_contacts,
        label="Leverancier",
    )
    period_filter = mo.ui.dropdown(
        options=periods,
        value=periods[0] if periods else None,
        label="Rapportperiode",
    )
    sales_contact_filter = mo.ui.multiselect(
        options=sales_contacts,
        value=sales_contacts,
        label="Verkoopcontact",
    )
    bank_account_filter = mo.ui.multiselect(
        options=bank_accounts,
        value=bank_accounts,
        label="Bankrekening",
    )
    bank_state_filter = mo.ui.multiselect(
        options=bank_states,
        value=bank_states,
        label="Bankstatus",
    )

    filters_content = mo.hstack(
        [
            datum_van_filter,
            datum_tot_filter,
            period_filter,
            sales_state_filter,
            sales_contact_filter,
            purchase_state_filter,
            purchase_contact_filter,
            bank_account_filter,
            bank_state_filter,
        ],
        justify="start",
    )
    return (
        bank_account_filter,
        bank_state_filter,
        datum_tot_filter,
        datum_van_filter,
        filters_content,
        period_filter,
        sales_contact_filter,
        purchase_contact_filter,
        purchase_state_filter,
        sales_state_filter,
    )


@app.cell
def _(
    bank_account_filter,
    bank_state_filter,
    date,
    datum_tot_filter,
    datum_van_filter,
    df_financial_mutations,
    df_purchase_invoices,
    df_report_snapshots,
    df_sales_invoices,
    period_filter,
    pl,
    purchase_contact_filter,
    purchase_state_filter,
    sales_contact_filter,
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
    if sales_contact_filter.value and df_sales_filtered.height > 0:
        df_sales_filtered = df_sales_filtered.filter(
            pl.col("contact_name").is_in(sales_contact_filter.value)
        )
    if purchase_state_filter.value and df_purchase_filtered.height > 0:
        df_purchase_filtered = df_purchase_filtered.filter(
            pl.col("state").is_in(purchase_state_filter.value)
        )
    if purchase_contact_filter.value and df_purchase_filtered.height > 0:
        df_purchase_filtered = df_purchase_filtered.filter(
            pl.col("contact_name").is_in(purchase_contact_filter.value)
        )
    if bank_account_filter.value and df_mutations_filtered.height > 0:
        df_mutations_filtered = df_mutations_filtered.filter(
            pl.col("financial_account_name").is_in(bank_account_filter.value)
        )
    if bank_state_filter.value and df_mutations_filtered.height > 0:
        df_mutations_filtered = df_mutations_filtered.filter(
            pl.col("state").is_in(bank_state_filter.value)
        )

    return (
        df_mutations_filtered,
        df_purchase_filtered,
        df_reports_filtered,
        df_sales_filtered,
    )


@app.cell
def _(
    date,
    df_financial_accounts,
    df_financial_mutations,
    df_mutations_filtered,
    df_purchase_filtered,
    df_purchase_invoices,
    df_reports_filtered,
    df_sales_filtered,
    df_sales_invoices,
    df_report_snapshots,
    moneybird_transforms,
    mo,
    pl,
):
    """KPI's."""
    vandaag = date.today()
    omzet = moneybird_transforms._report_value(
        df_reports_filtered, "profit_loss", "total_revenue", pl
    )
    kosten = moneybird_transforms._report_value(
        df_reports_filtered, "profit_loss", "total_expenses", pl
    )
    bruto_marge = moneybird_transforms._report_value(
        df_reports_filtered, "profit_loss", "gross_profit", pl
    )
    operationeel_resultaat = moneybird_transforms._report_value(
        df_reports_filtered,
        "profit_loss",
        "operating_profit",
        pl,
    )
    netto_resultaat = moneybird_transforms._report_value(
        df_reports_filtered, "profit_loss", "net_profit", pl
    )
    open_debiteuren = moneybird_transforms._sum_column(
        df_sales_filtered, "total_unpaid", pl
    )
    open_crediteuren = moneybird_transforms._sum_open_purchase(df_purchase_filtered, pl)
    verlopen_verkoopfacturen = moneybird_transforms._count_overdue_invoices(
        df_sales_filtered,
        due_date_column="due_date",
        paid_at_column="paid_at",
        today=vandaag,
        pl=pl,
    )
    verlopen_inkoopfacturen = moneybird_transforms._count_overdue_invoices(
        df_purchase_filtered,
        due_date_column="due_date",
        paid_at_column="paid_at",
        today=vandaag,
        pl=pl,
    )

    kpi_cards = mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(
                        value=moneybird_transforms._format_euro(omzet),
                        label="Omzet",
                        caption="gekozen rapportperiode",
                    ),
                    mo.stat(
                        value=moneybird_transforms._format_euro(kosten),
                        label="Kosten",
                        caption="gekozen rapportperiode",
                    ),
                    mo.stat(
                        value=moneybird_transforms._format_euro(bruto_marge),
                        label="Bruto marge",
                        caption="gekozen rapportperiode",
                    ),
                    mo.stat(
                        value=moneybird_transforms._format_euro(operationeel_resultaat),
                        label="Operationeel resultaat",
                        caption="gekozen rapportperiode",
                    ),
                    mo.stat(
                        value=moneybird_transforms._format_euro(netto_resultaat),
                        label="Netto resultaat",
                        caption="gekozen rapportperiode",
                    ),
                ],
                justify="space-between",
            ),
            mo.hstack(
                [
                    mo.stat(
                        value=moneybird_transforms._format_euro(open_debiteuren),
                        label="Open debiteuren",
                        caption="binnen huidige filter",
                    ),
                    mo.stat(
                        value=moneybird_transforms._format_euro(open_crediteuren),
                        label="Open crediteuren",
                        caption="binnen huidige filter",
                    ),
                    mo.stat(
                        value=str(verlopen_verkoopfacturen),
                        label="Verlopen verkoopfacturen",
                        caption="open en vervallen",
                    ),
                    mo.stat(
                        value=str(verlopen_inkoopfacturen),
                        label="Verlopen inkoopfacturen",
                        caption="open en vervallen",
                    ),
                ],
                justify="space-between",
            ),
            mo.hstack(
                [
                    mo.stat(
                        value=moneybird_transforms._latest_sync_text(
                            df_sales_invoices, "synced_at", pl
                        ),
                        label="Sync verkoop",
                        caption=f"{df_sales_invoices.height} rijen",
                    ),
                    mo.stat(
                        value=moneybird_transforms._latest_sync_text(
                            df_purchase_invoices, "synced_at", pl
                        ),
                        label="Sync inkoop",
                        caption=f"{df_purchase_invoices.height} rijen",
                    ),
                    mo.stat(
                        value=moneybird_transforms._latest_sync_text(
                            df_report_snapshots, "synced_at", pl
                        ),
                        label="Sync rapporten",
                        caption=f"{df_report_snapshots.height} rijen",
                    ),
                    mo.stat(
                        value=moneybird_transforms._latest_sync_text(
                            df_financial_accounts, "synced_at", pl
                        ),
                        label="Sync rekeningen",
                        caption=f"{df_financial_accounts.height} rijen",
                    ),
                    mo.stat(
                        value=moneybird_transforms._latest_sync_text(
                            df_financial_mutations, "synced_at", pl
                        ),
                        label="Sync bank",
                        caption=f"{df_financial_mutations.height} rijen",
                    ),
                ],
                justify="space-between",
            ),
        ]
    )
    if (
        df_sales_invoices.height == 0
        and df_purchase_invoices.height == 0
        and df_report_snapshots.height == 0
        and df_financial_accounts.height == 0
        and df_financial_mutations.height == 0
    ):
        kpi_cards = mo.vstack(
            [
                mo.callout(
                    mo.md("Nog geen Moneybird data gevonden in de lokale database."),
                    kind="neutral",
                ),
                kpi_cards,
            ]
        )
    return (kpi_cards,)


@app.cell
def _(alt, df_purchase_filtered, df_sales_filtered, moneybird_transforms, mo, pl):
    """Factuurtrend."""
    chart_frames = []
    if df_sales_filtered.height > 0:
        chart_frames.append(
            moneybird_transforms._monthly_amounts(
                df_sales_filtered,
                date_column="invoice_date",
                amount_column="total_price_incl_tax",
                label="Verkoop",
                pl=pl,
            )
        )
    if df_purchase_filtered.height > 0:
        chart_frames.append(
            moneybird_transforms._monthly_amounts(
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
def _(df_sales_filtered, moneybird_transforms, mo):
    """Verkoopfacturen tabel."""
    sales_table = moneybird_transforms._sales_invoice_table(
        df_sales_filtered,
        mo,
        empty_message="Geen verkoopfacturen binnen de huidige filter.",
        label="Alle verkoopfacturen",
        page_size=25,
    )
    return (sales_table,)


@app.cell
def _(alt, date, df_sales_filtered, moneybird_transforms, mo, pl, sales_table):
    """Verkoop tab met openstaande en verlopen facturen."""
    sales_today = date.today()
    df_sales_open = moneybird_transforms._open_invoice_rows(
        df_sales_filtered, paid_at_column="paid_at", pl=pl
    )
    df_sales_overdue = moneybird_transforms._overdue_invoice_rows(
        df_sales_filtered,
        due_date_column="due_date",
        paid_at_column="paid_at",
        today=sales_today,
        pl=pl,
    )
    sales_revenue = moneybird_transforms._sum_column(
        df_sales_filtered, "total_price_incl_tax", pl
    )
    sales_open_amount = moneybird_transforms._sum_column(
        df_sales_open, "total_unpaid", pl
    )
    sales_overdue_amount = moneybird_transforms._sum_column(
        df_sales_overdue, "total_unpaid", pl
    )

    sales_summary = mo.hstack(
        [
            mo.stat(
                value=str(df_sales_filtered.height),
                label="Verkoopfacturen",
                caption="binnen huidige filter",
            ),
            mo.stat(
                value=moneybird_transforms._format_euro(sales_revenue),
                label="Gefactureerd",
                caption="totaal incl. btw",
            ),
            mo.stat(
                value=str(df_sales_open.height),
                label="Openstaand",
                caption=moneybird_transforms._format_euro(sales_open_amount),
            ),
            mo.stat(
                value=str(df_sales_overdue.height),
                label="Verlopen",
                caption=moneybird_transforms._format_euro(sales_overdue_amount),
            ),
        ],
        justify="space-between",
    )

    sales_chart_data = moneybird_transforms._monthly_amounts(
        df_sales_filtered,
        date_column="invoice_date",
        amount_column="total_price_incl_tax",
        label="Omzet",
        pl=pl,
    )
    if sales_chart_data.height == 0:
        sales_revenue_chart = mo.callout(
            mo.md("Geen omzetdata binnen de huidige verkoopfilter."),
            kind="neutral",
        )
    else:
        sales_chart = (
            alt.Chart(sales_chart_data.to_pandas())
            .mark_bar(color="#2563eb")
            .encode(
                x=alt.X("Maand:N", title="Maand"),
                y=alt.Y("Bedrag:Q", title="Omzet incl. btw"),
                tooltip=[
                    alt.Tooltip("Maand:N", title="Maand"),
                    alt.Tooltip("Bedrag:Q", title="Omzet", format=",.2f"),
                ],
            )
            .properties(width=900, height=320, title="Omzet per maand")
        )
        sales_revenue_chart = mo.ui.altair_chart(sales_chart)

    sales_open_table = moneybird_transforms._sales_invoice_table(
        df_sales_open,
        mo,
        empty_message="Geen openstaande verkoopfacturen binnen de huidige filter.",
        label="Openstaande verkoopfacturen",
        page_size=15,
    )
    sales_overdue_table = moneybird_transforms._sales_invoice_table(
        df_sales_overdue,
        mo,
        empty_message="Geen verlopen verkoopfacturen binnen de huidige filter.",
        label="Verlopen verkoopfacturen",
        page_size=15,
    )

    sales_content = mo.vstack(
        [
            sales_summary,
            sales_revenue_chart,
            mo.md("## Openstaande verkoopfacturen"),
            sales_open_table,
            mo.md("## Verlopen verkoopfacturen"),
            sales_overdue_table,
            mo.md("## Alle verkoopfacturen"),
            sales_table,
        ]
    )
    return (sales_content,)


@app.cell
def _(df_purchase_filtered, moneybird_transforms, mo):
    """Inkoopfacturen tabel."""
    purchase_table = moneybird_transforms._purchase_invoice_table(
        df_purchase_filtered,
        mo,
        empty_message="Geen inkoopfacturen binnen de huidige filter.",
        label="Alle inkoopfacturen",
        page_size=25,
    )
    return (purchase_table,)


@app.cell
def _(alt, date, df_purchase_filtered, moneybird_transforms, mo, pl, purchase_table):
    """Inkoop tab met openstaande en verlopen facturen."""
    purchase_today = date.today()
    df_purchase_open = moneybird_transforms._open_invoice_rows(
        df_purchase_filtered,
        paid_at_column="paid_at",
        pl=pl,
    )
    df_purchase_overdue = moneybird_transforms._overdue_invoice_rows(
        df_purchase_filtered,
        due_date_column="due_date",
        paid_at_column="paid_at",
        today=purchase_today,
        pl=pl,
    )
    purchase_costs = moneybird_transforms._sum_column(
        df_purchase_filtered, "total_price_incl_tax", pl
    )
    purchase_open_amount = moneybird_transforms._sum_column(
        df_purchase_open,
        "total_price_incl_tax",
        pl,
    )
    purchase_overdue_amount = moneybird_transforms._sum_column(
        df_purchase_overdue,
        "total_price_incl_tax",
        pl,
    )

    purchase_summary = mo.hstack(
        [
            mo.stat(
                value=str(df_purchase_filtered.height),
                label="Inkoopfacturen",
                caption="binnen huidige filter",
            ),
            mo.stat(
                value=moneybird_transforms._format_euro(purchase_costs),
                label="Kosten",
                caption="totaal incl. btw",
            ),
            mo.stat(
                value=str(df_purchase_open.height),
                label="Openstaand",
                caption=moneybird_transforms._format_euro(purchase_open_amount),
            ),
            mo.stat(
                value=str(df_purchase_overdue.height),
                label="Verlopen",
                caption=moneybird_transforms._format_euro(purchase_overdue_amount),
            ),
        ],
        justify="space-between",
    )

    purchase_chart_data = moneybird_transforms._monthly_amounts(
        df_purchase_filtered,
        date_column="date",
        amount_column="total_price_incl_tax",
        label="Kosten",
        pl=pl,
    )
    if purchase_chart_data.height == 0:
        purchase_cost_chart = mo.callout(
            mo.md("Geen kostendata binnen de huidige inkoopfilter."),
            kind="neutral",
        )
    else:
        purchase_chart = (
            alt.Chart(purchase_chart_data.to_pandas())
            .mark_bar(color="#dc2626")
            .encode(
                x=alt.X("Maand:N", title="Maand"),
                y=alt.Y("Bedrag:Q", title="Kosten incl. btw"),
                tooltip=[
                    alt.Tooltip("Maand:N", title="Maand"),
                    alt.Tooltip("Bedrag:Q", title="Kosten", format=",.2f"),
                ],
            )
            .properties(width=900, height=320, title="Inkoopkosten per maand")
        )
        purchase_cost_chart = mo.ui.altair_chart(purchase_chart)

    purchase_open_table = moneybird_transforms._purchase_invoice_table(
        df_purchase_open,
        mo,
        empty_message="Geen openstaande inkoopfacturen binnen de huidige filter.",
        label="Openstaande inkoopfacturen",
        page_size=15,
    )
    purchase_overdue_table = moneybird_transforms._purchase_invoice_table(
        df_purchase_overdue,
        mo,
        empty_message="Geen verlopen inkoopfacturen binnen de huidige filter.",
        label="Verlopen inkoopfacturen",
        page_size=15,
    )

    purchase_content = mo.vstack(
        [
            purchase_summary,
            purchase_cost_chart,
            mo.md("## Openstaande inkoopfacturen"),
            purchase_open_table,
            mo.md("## Verlopen inkoopfacturen"),
            purchase_overdue_table,
            mo.md("## Alle inkoopfacturen"),
            purchase_table,
        ]
    )
    return (purchase_content,)


@app.cell
def _(df_ledger_accounts, df_reports_filtered, moneybird_transforms, mo, pl):
    """Rapporten en grootboekrekeningen."""
    profit_loss_card = moneybird_transforms._profit_loss_report_card(
        df_reports_filtered, mo, pl
    )
    balance_sheet_table = moneybird_transforms._balance_sheet_report_table(
        df_reports_filtered, mo, pl
    )
    reports_table = moneybird_transforms._report_snapshots_table(
        df_reports_filtered, mo
    )
    ledger_table = moneybird_transforms._ledger_accounts_table(df_ledger_accounts, mo)
    ledger_type_explanation_table = mo.ui.table(
        moneybird_transforms._ledger_account_type_description_rows(pl).to_pandas(),
        selection=None,
        page_size=8,
        label="Uitleg grootboektypes",
    )

    account_detail_rows = moneybird_transforms._report_account_detail_rows(
        df_reports_filtered,
        df_ledger_accounts,
        report_type="profit_loss",
        pl=pl,
    )
    if account_detail_rows.height == 0:
        account_detail_content = mo.callout(
            mo.md(
                "Nog geen rapport-detailregels met grootboekrekening beschikbaar "
                "in de lokale snapshots. De grootboeklookup hieronder is klaar "
                "voor account-id mapping zodra deze regels worden opgeslagen."
            ),
            kind="neutral",
        )
        top_cost_accounts_content = mo.md("")
    else:
        account_detail_content = mo.ui.table(
            account_detail_rows.drop("BedragSort").to_pandas(),
            selection=None,
            page_size=20,
            label="Omzet en kosten per grootboekrekening",
        )
        top_cost_accounts = moneybird_transforms._top_cost_account_rows(
            account_detail_rows, pl=pl
        )
        if top_cost_accounts.height == 0:
            top_cost_accounts_content = mo.callout(
                mo.md("Geen kostenrekeningen gevonden in de rapport-detailregels."),
                kind="neutral",
            )
        else:
            top_cost_accounts_content = mo.vstack(
                [
                    mo.md("## Top kostenrekeningen"),
                    mo.ui.table(
                        top_cost_accounts.drop("BedragSort").to_pandas(),
                        selection=None,
                        page_size=10,
                        label="Top kostenrekeningen",
                    ),
                ]
            )

    reports_content = mo.vstack(
        [
            mo.md("## Winst en verlies"),
            profit_loss_card,
            mo.md("## Balans"),
            balance_sheet_table,
            mo.md("## Rapport snapshots"),
            reports_table,
            mo.md("## Omzet en kosten per grootboekrekening"),
            mo.md("### Uitleg grootboektypes"),
            ledger_type_explanation_table,
            account_detail_content,
            top_cost_accounts_content,
            mo.md("## Grootboekrekening lookup"),
            ledger_table,
        ]
    )
    return (reports_content,)


@app.cell
def _(alt, df_financial_accounts, df_mutations_filtered, moneybird_transforms, mo, pl):
    """Bank tab."""
    accounts_table = moneybird_transforms._financial_accounts_table(
        df_financial_accounts,
        mo,
        empty_message="Geen financiele rekeningen lokaal beschikbaar.",
        label="Financiele rekeningen",
        page_size=10,
    )
    mutations_table = moneybird_transforms._bank_mutations_table(
        df_mutations_filtered,
        mo,
        empty_message="Geen bankmutaties binnen de huidige filter.",
        label="Alle bankmutaties",
        page_size=25,
    )

    open_mutations = moneybird_transforms._open_bank_mutation_rows(
        df_mutations_filtered, pl
    )
    unprocessed_mutations = moneybird_transforms._bank_state_rows(
        df_mutations_filtered,
        state="unprocessed",
        pl=pl,
    )
    incoming_amount = moneybird_transforms._sum_positive_amounts(
        df_mutations_filtered, "amount", pl
    )
    outgoing_amount = moneybird_transforms._sum_negative_amounts_abs(
        df_mutations_filtered, "amount", pl
    )
    open_amount = moneybird_transforms._sum_column(open_mutations, "amount_open", pl)

    bank_summary = mo.hstack(
        [
            mo.stat(
                value=str(df_mutations_filtered.height),
                label="Bankmutaties",
                caption="binnen huidige filter",
            ),
            mo.stat(
                value=moneybird_transforms._format_euro(incoming_amount),
                label="Inkomend",
                caption="positieve mutaties",
            ),
            mo.stat(
                value=moneybird_transforms._format_euro(outgoing_amount),
                label="Uitgaand",
                caption="negatieve mutaties",
            ),
            mo.stat(
                value=str(unprocessed_mutations.height),
                label="Niet verwerkt",
                caption="status bankmutatie",
            ),
            mo.stat(
                value=str(open_mutations.height),
                label="Open mutaties",
                caption=moneybird_transforms._format_euro(open_amount),
            ),
        ],
        justify="space-between",
    )

    bank_chart_data = moneybird_transforms._bank_monthly_flows(
        df_mutations_filtered, pl=pl
    )
    if bank_chart_data.height == 0:
        bank_flow_chart = mo.callout(
            mo.md("Geen bankmutatiedata binnen de huidige bankfilter."),
            kind="neutral",
        )
    else:
        bank_chart = (
            alt.Chart(bank_chart_data.to_pandas())
            .mark_bar()
            .encode(
                x=alt.X("Maand:N", title="Maand"),
                y=alt.Y("Bedrag:Q", title="Bedrag"),
                color=alt.Color("Richting:N", title="Richting"),
                tooltip=[
                    alt.Tooltip("Maand:N", title="Maand"),
                    alt.Tooltip("Richting:N", title="Richting"),
                    alt.Tooltip("Bedrag:Q", title="Bedrag", format=",.2f"),
                ],
            )
            .properties(width=900, height=320, title="Inkomend en uitgaand per maand")
        )
        bank_flow_chart = mo.ui.altair_chart(bank_chart)

    open_mutations_table = moneybird_transforms._bank_mutations_table(
        open_mutations,
        mo,
        empty_message="Geen open bankmutaties binnen de huidige filter.",
        label="Open bankmutaties",
        page_size=15,
    )
    unprocessed_mutations_table = moneybird_transforms._bank_mutations_table(
        unprocessed_mutations,
        mo,
        empty_message="Geen niet-verwerkte bankmutaties binnen de huidige filter.",
        label="Niet-verwerkte bankmutaties",
        page_size=15,
    )

    bank_content = mo.vstack(
        [
            bank_summary,
            bank_flow_chart,
            mo.md("## Financiele rekeningen"),
            accounts_table,
            mo.md("## Open bankmutaties"),
            open_mutations_table,
            mo.md("## Niet-verwerkte bankmutaties"),
            unprocessed_mutations_table,
            mo.md("## Alle bankmutaties"),
            mutations_table,
        ]
    )
    return (bank_content,)


@app.cell
def _(
    df_financial_accounts,
    df_financial_mutations,
    df_purchase_invoices,
    df_report_snapshots,
    df_sales_invoices,
    moneybird_transforms,
    mo,
    pl,
):
    """Datakwaliteit tab."""
    quality_rows = moneybird_transforms._moneybird_sync_quality_rows(
        df_sales_invoices=df_sales_invoices,
        df_purchase_invoices=df_purchase_invoices,
        df_report_snapshots=df_report_snapshots,
        df_financial_accounts=df_financial_accounts,
        df_financial_mutations=df_financial_mutations,
        pl=pl,
    )
    quality_table = mo.ui.table(
        pl.DataFrame(quality_rows).to_pandas(),
        selection=None,
        page_size=10,
        label="Datastatus",
    )

    missing_sales_contacts = moneybird_transforms._count_missing_lookup(
        df_sales_invoices,
        id_column="contact_id",
        name_column="contact_name",
        pl=pl,
    )
    missing_purchase_contacts = moneybird_transforms._count_missing_lookup(
        df_purchase_invoices,
        id_column="contact_id",
        name_column="contact_name",
        pl=pl,
    )
    sales_without_local_contact = moneybird_transforms._count_missing_lookup(
        df_sales_invoices,
        id_column="contact_id",
        name_column="local_contact_id",
        pl=pl,
    )
    purchase_without_local_contact = moneybird_transforms._count_missing_lookup(
        df_purchase_invoices,
        id_column="contact_id",
        name_column="local_contact_id",
        pl=pl,
    )
    missing_financial_accounts = moneybird_transforms._count_missing_lookup(
        df_financial_mutations,
        id_column="financial_account_id",
        name_column="financial_account_name",
        pl=pl,
    )
    empty_report_snapshots = moneybird_transforms._count_empty_report_snapshots(
        df_report_snapshots, pl
    )

    checks = [
        moneybird_transforms._quality_check_row(
            "Verkoopfacturen zonder contactnaam",
            missing_sales_contacts,
            "Controleer contactsynchronisatie of contactnaam op de factuur.",
        ),
        moneybird_transforms._quality_check_row(
            "Inkoopfacturen zonder contactnaam",
            missing_purchase_contacts,
            "Controleer contactsynchronisatie of leveranciernaam op het document.",
        ),
        moneybird_transforms._quality_check_row(
            "Verkoopfacturen met contact_id zonder lokaal contact",
            sales_without_local_contact,
            "De factuur verwijst naar een contact dat lokaal niet is gevonden.",
        ),
        moneybird_transforms._quality_check_row(
            "Inkoopfacturen met contact_id zonder lokaal contact",
            purchase_without_local_contact,
            "Het document verwijst naar een contact dat lokaal niet is gevonden.",
        ),
        moneybird_transforms._quality_check_row(
            "Bankmutaties zonder financiele rekeningnaam",
            missing_financial_accounts,
            "Synchroniseer financiele rekeningen om bankmutaties goed te groeperen.",
        ),
        moneybird_transforms._quality_check_row(
            "Rapport snapshots ontbreken of zijn leeg",
            empty_report_snapshots,
            "Rapportdata kan ontbreken of niet bruikbaar zijn voor conclusies.",
        ),
    ]

    warning_callouts = [
        mo.callout(
            mo.md(f"**{row['Controle']}**: {row['Aantal']} rij(en). {row['Actie']}"),
            kind="warn",
        )
        for row in checks
        if row["Aantal"] > 0
    ]
    if not warning_callouts:
        warning_callouts = [
            mo.callout(
                mo.md("Geen datakwaliteitswaarschuwingen gevonden."),
                kind="success",
            )
        ]

    quality_checks = mo.ui.table(
        pl.DataFrame(checks).to_pandas(),
        selection=None,
        page_size=10,
        label="Controles",
    )

    quality_content = mo.vstack(
        [
            mo.md("## Datakwaliteit"),
            mo.vstack(warning_callouts),
            mo.md("## Laatste sync per tabel"),
            quality_table,
            mo.md("## Controles"),
            quality_checks,
        ]
    )
    return (quality_content,)


@app.cell
def _(
    bank_content,
    filters_content,
    invoice_chart,
    kpi_cards,
    mo,
    purchase_content,
    quality_content,
    reports_content,
    sales_content,
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
            "Verkoop": sales_content,
            "Inkoop": purchase_content,
            "Bank": bank_content,
            "Rapporten": reports_content,
            "Datakwaliteit": quality_content,
        }
    )

    mo.vstack([tabs])
    return


if __name__ == "__main__":
    app.run()
