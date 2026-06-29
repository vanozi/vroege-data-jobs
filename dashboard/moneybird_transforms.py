"""Moneybird dashboard helpers and transformations."""

import json
from decimal import Decimal

import polars as pl


LEDGER_ACCOUNT_TYPE_DESCRIPTIONS = {
    "revenue": (
        "Omzet/opbrengsten. Bijvoorbeeld verkoop melk, vee, diensten, subsidies "
        "of andere bedrijfsopbrengsten."
    ),
    "expenses": (
        "Bedrijfskosten. Bijvoorbeeld energie, onderhoud, verzekering, kantoor "
        "en abonnementen."
    ),
    "direct_costs": (
        "Directe kosten die direct samenhangen met productie of omzet. "
        "Bijvoorbeeld voer, diergezondheid en productiegerelateerde inkoop."
    ),
    "current_assets": (
        "Vlottende activa. Bezittingen die meestal binnen een jaar in geld omgaan, "
        "zoals bank, kas, debiteuren en voorraad."
    ),
    "non_current_assets": (
        "Vaste activa. Bezittingen voor langere termijn, zoals machines, "
        "gebouwen, installaties en inventaris."
    ),
    "current_liabilities": (
        "Kortlopende schulden. Verplichtingen binnen een jaar, zoals crediteuren, "
        "te betalen btw en kortlopende leningen."
    ),
    "non_current_liabilities": (
        "Langlopende schulden. Leningen of verplichtingen langer dan een jaar."
    ),
    "equity": (
        "Eigen vermogen. Kapitaal van de onderneming, resultaat lopend boekjaar, "
        "reserves en prive-opnames of stortingen afhankelijk van inrichting."
    ),
}


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


def _top_unique_strings(df, column: str, pl, *, limit: int) -> list[str]:
    if df.height == 0 or column not in df.columns:
        return []

    return (
        df.filter(pl.col(column).is_not_null())
        .with_columns(pl.col(column).cast(pl.String).str.strip_chars().alias(column))
        .filter(pl.col(column) != "")
        .group_by(column)
        .agg(pl.len().alias("count"))
        .sort(["count", column], descending=[True, False])
        .head(limit)
        .sort(column)[column]
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


def _count_overdue_invoices(
    df,
    *,
    due_date_column: str,
    paid_at_column: str,
    today,
    pl,
) -> int:
    if df.height == 0:
        return 0
    if due_date_column not in df.columns or paid_at_column not in df.columns:
        return 0

    return df.filter(
        pl.col(due_date_column).is_not_null()
        & (pl.col(due_date_column) < today)
        & pl.col(paid_at_column).is_null()
    ).height


def _open_invoice_rows(df, *, paid_at_column: str, pl):
    if df.height == 0 or paid_at_column not in df.columns:
        return df

    return df.filter(pl.col(paid_at_column).is_null())


def _overdue_invoice_rows(
    df,
    *,
    due_date_column: str,
    paid_at_column: str,
    today,
    pl,
):
    if df.height == 0:
        return df
    if due_date_column not in df.columns or paid_at_column not in df.columns:
        return df

    return df.filter(
        pl.col(due_date_column).is_not_null()
        & (pl.col(due_date_column) < today)
        & pl.col(paid_at_column).is_null()
    )


def _report_value(df, report_type: str, column: str, pl) -> Decimal:
    if df.height == 0 or column not in df.columns:
        return Decimal("0")

    rows = df.filter(pl.col("report_type") == report_type)
    return _sum_column(rows, column, pl)


def _report_snapshot_row(df, report_type: str, pl):
    if df.height == 0 or "report_type" not in df.columns:
        return None

    rows = df.filter(pl.col("report_type") == report_type)
    if rows.height == 0:
        return None

    return rows.head(1).to_dicts()[0]


def _coerce_report_json(value: object):
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if value is None:
        return {}

    value_text = str(value).strip()
    if not value_text:
        return {}

    try:
        parsed = json.loads(value_text)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return parsed

    return {}


def _report_json_money_rows(raw_json, *, max_rows: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def walk(node, path: list[str]) -> None:
        if len(rows) >= max_rows:
            return
        if isinstance(node, list):
            for item in node:
                walk(item, path)
            return
        if not isinstance(node, dict):
            return

        amount = _report_node_amount(node)
        label = _report_node_label(node, path)
        if amount is not None and label:
            rows.append(
                {
                    "label": label,
                    "account_id": _report_node_account_id(node),
                    "amount": amount,
                    "path": " / ".join(path),
                }
            )

        for key, value in node.items():
            if isinstance(value, (dict, list)):
                walk(value, [*path, _humanize_report_key(key)])

    walk(raw_json, [])
    return rows


def _report_node_amount(node: dict) -> object:
    for key in (
        "total",
        "amount",
        "balance",
        "value",
        "total_amount",
        "total_value",
        "total_revenue",
        "total_expenses",
        "gross_profit",
        "operating_profit",
        "net_profit",
    ):
        amount = _decimal_or_none(node.get(key))
        if amount is not None:
            return amount

    return None


def _report_node_label(node: dict, path: list[str]) -> str:
    for key in ("name", "label", "title", "description"):
        value = node.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()

    if path:
        return path[-1]

    return ""


def _report_node_account_id(node: dict) -> str:
    for key in ("account_id", "ledger_account_id", "ledger_account"):
        value = node.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()

    return ""


def _humanize_report_key(value: object) -> str:
    value_text = "" if value is None else str(value).strip()
    if not value_text:
        return ""

    return value_text.replace("_", " ").title()


def _decimal_or_none(value: object):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    value_text = str(value).strip()
    if not value_text:
        return None

    try:
        return Decimal(value_text)
    except (ArithmeticError, ValueError):
        return None


def _format_euro(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    dutch_formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {dutch_formatted}"


def _format_euro_cell(value: object) -> str:
    if value is None:
        return "EUR 0,00"

    try:
        amount = Decimal(str(value))
    except (ValueError, ArithmeticError):
        return "EUR 0,00"

    return _format_euro(amount)


def _latest_sync_text(df, synced_at_column: str, polars_module) -> str:
    if df.height == 0 or synced_at_column not in df.columns:
        return "Geen data"

    latest_sync = df.select(polars_module.col(synced_at_column).max())[0, 0]
    if latest_sync is None:
        return "Geen data"

    return str(latest_sync)


def _format_money_columns(df, columns: list[str]):
    if df.height == 0:
        return df

    expressions = []
    for column in columns:
        if column not in df.columns:
            continue
        expressions.append(
            pl.col(column)
            .map_elements(_format_euro_cell, return_dtype=pl.String)
            .alias(column)
        )

    if not expressions:
        return df

    return df.with_columns(expressions)


def _sales_invoice_display_df(df):
    sales_table_data = _format_money_columns(
        _add_status_label(df, source_column="state", label_column="Status"),
        [
            "total_price_incl_tax",
            "total_paid",
            "total_unpaid",
        ],
    )
    return sales_table_data.select(
        [
            "invoice_date",
            "invoice_id",
            "contact_name",
            "Status",
            "due_date",
            "paid_at",
            "total_price_incl_tax",
            "total_paid",
            "total_unpaid",
            "reminder_count",
        ]
    ).rename(
        {
            "invoice_date": "Factuurdatum",
            "invoice_id": "Factuurnummer",
            "contact_name": "Contact",
            "due_date": "Vervaldatum",
            "paid_at": "Betaaldatum",
            "total_price_incl_tax": "Totaal incl. btw",
            "total_paid": "Betaald",
            "total_unpaid": "Open bedrag",
            "reminder_count": "Herinneringen",
        }
    )


def _sales_invoice_table(
    df,
    mo,
    *,
    empty_message: str,
    label: str,
    page_size: int,
):
    if df.height == 0:
        return mo.callout(mo.md(empty_message), kind="neutral")

    return mo.ui.table(
        _sales_invoice_display_df(df).to_pandas(),
        selection=None,
        page_size=page_size,
        label=label,
    )


def _purchase_invoice_display_df(df):
    purchase_table_data = _format_money_columns(
        _add_status_label(df, source_column="state", label_column="Status"),
        [
            "total_price_incl_tax",
            "total_price_incl_tax_base",
        ],
    )
    return purchase_table_data.select(
        [
            "date",
            "entry_number",
            "reference",
            "contact_name",
            "Status",
            "due_date",
            "paid_at",
            "total_price_incl_tax",
            "total_price_incl_tax_base",
        ]
    ).rename(
        {
            "date": "Datum",
            "entry_number": "Boekstuk",
            "reference": "Referentie",
            "contact_name": "Leverancier",
            "due_date": "Vervaldatum",
            "paid_at": "Betaaldatum",
            "total_price_incl_tax": "Totaal incl. btw",
            "total_price_incl_tax_base": "Totaal basisvaluta",
        }
    )


def _purchase_invoice_table(
    df,
    mo,
    *,
    empty_message: str,
    label: str,
    page_size: int,
):
    if df.height == 0:
        return mo.callout(mo.md(empty_message), kind="neutral")

    return mo.ui.table(
        _purchase_invoice_display_df(df).to_pandas(),
        selection=None,
        page_size=page_size,
        label=label,
    )


def _profit_loss_report_card(df, mo, pl):
    profit_loss_rows = _profit_loss_report_rows(df, pl)
    if profit_loss_rows.height == 0:
        return mo.callout(
            mo.md("Geen winst-en-verlies snapshot gevonden voor de gekozen periode."),
            kind="neutral",
        )

    return mo.hstack(
        [
            mo.stat(
                value=row["Waarde"],
                label=row["Onderdeel"],
                caption=row["Periode"],
            )
            for row in profit_loss_rows.to_dicts()
        ],
        justify="space-between",
    )


def _profit_loss_report_rows(df, pl):
    row = _report_snapshot_row(df, "profit_loss", pl)
    if row is None:
        return pl.DataFrame(schema={"Onderdeel": pl.String, "Waarde": pl.String})

    period = "" if row.get("period") is None else str(row.get("period"))
    rows = [
        ("Omzet", row.get("total_revenue")),
        ("Kosten", row.get("total_expenses")),
        ("Brutomarge", row.get("gross_profit")),
        ("Operationeel resultaat", row.get("operating_profit")),
        ("Netto resultaat", row.get("net_profit")),
    ]
    return pl.DataFrame(
        [
            {
                "Onderdeel": label,
                "Waarde": _format_euro_cell(value),
                "Periode": period,
            }
            for label, value in rows
        ]
    )


def _balance_sheet_report_table(df, mo, pl):
    balance_rows = _balance_sheet_report_rows(df, pl)
    if balance_rows.height == 0:
        return mo.callout(
            mo.md("Geen bruikbare balanssnapshot gevonden voor de gekozen periode."),
            kind="neutral",
        )

    return mo.ui.table(
        balance_rows.to_pandas(),
        selection=None,
        page_size=20,
        label="Balans snapshot",
    )


def _balance_sheet_report_rows(df, pl):
    row = _report_snapshot_row(df, "balance_sheet", pl)
    if row is None:
        return pl.DataFrame(
            schema={
                "Onderdeel": pl.String,
                "Account ID": pl.String,
                "Waarde": pl.String,
            }
        )

    raw_json = _coerce_report_json(row.get("raw_json"))
    money_rows = _report_json_money_rows(raw_json, max_rows=50)
    if not money_rows:
        return pl.DataFrame(
            schema={
                "Onderdeel": pl.String,
                "Account ID": pl.String,
                "Waarde": pl.String,
            }
        )

    return pl.DataFrame(
        [
            {
                "Onderdeel": item["label"],
                "Account ID": item["account_id"],
                "Waarde": _format_euro(item["amount"]),
            }
            for item in money_rows
        ]
    )


def _report_snapshots_table(df, mo):
    if df.height == 0:
        return mo.callout(
            mo.md("Geen rapport snapshots gevonden voor de gekozen periode."),
            kind="neutral",
        )

    reports_table_data = _format_money_columns(
        _add_report_type_label(df),
        [
            "total_revenue",
            "total_expenses",
            "gross_profit",
            "operating_profit",
            "net_profit",
        ],
    )
    return mo.ui.table(
        reports_table_data.select(
            [
                "Rapport",
                "period",
                "total_revenue",
                "total_expenses",
                "gross_profit",
                "operating_profit",
                "net_profit",
                "synced_at",
            ]
        )
        .rename(
            {
                "period": "Periode",
                "total_revenue": "Omzet",
                "total_expenses": "Kosten",
                "gross_profit": "Brutomarge",
                "operating_profit": "Operationeel resultaat",
                "net_profit": "Netto resultaat",
                "synced_at": "Gesynchroniseerd",
            }
        )
        .to_pandas(),
        selection=None,
        page_size=10,
        label="Rapport snapshots",
    )


def _ledger_accounts_display_df(df):
    return df.select(
        [
            "account_id",
            "name",
            "account_type",
            "moneybird_id",
            "moneybird_version",
            "synced_at",
        ]
    ).rename(
        {
            "account_id": "Account ID",
            "name": "Naam",
            "account_type": "Type",
            "moneybird_id": "Moneybird ID",
            "moneybird_version": "Versie",
            "synced_at": "Gesynchroniseerd",
        }
    )


def _ledger_accounts_table(df, mo):
    if df.height == 0:
        return mo.callout(
            mo.md("Geen grootboekrekeningen lokaal beschikbaar."),
            kind="neutral",
        )

    return mo.ui.table(
        _ledger_accounts_display_df(df).to_pandas(),
        selection=None,
        page_size=20,
        label="Grootboekrekeningen",
    )


def _ledger_account_type_description_rows(pl):
    return pl.DataFrame(
        [
            {
                "Grootboektype": _ledger_account_type_label(account_type),
                "Omschrijving": description,
            }
            for account_type, description in LEDGER_ACCOUNT_TYPE_DESCRIPTIONS.items()
        ],
        schema={
            "Grootboektype": pl.String,
            "Omschrijving": pl.String,
        },
    )


def _ledger_account_type_label(value: object) -> str:
    value_text = "" if value is None else str(value).strip()
    if not value_text:
        return "Onbekend"

    labels = {
        "revenue": "Revenue",
        "expenses": "Expenses",
        "direct_costs": "Direct costs",
        "current_assets": "Current assets",
        "non_current_assets": "Non-current assets",
        "current_liabilities": "Current liabilities",
        "non_current_liabilities": "Non-current liabilities",
        "equity": "Equity",
    }
    normalized = value_text.lower()
    return labels.get(normalized, value_text.replace("_", " ").title())


def _ledger_account_type_description(value: object) -> str:
    value_text = "" if value is None else str(value).strip().lower()
    if not value_text:
        return ""

    return LEDGER_ACCOUNT_TYPE_DESCRIPTIONS.get(value_text, "")


def _financial_accounts_display_df(df):
    return (
        df.with_columns(
            pl.col("active")
            .map_elements(_bool_label, return_dtype=pl.String)
            .alias("active")
        )
        .select(
            [
                "name",
                "type",
                "identifier",
                "currency",
                "provider",
                "active",
            ]
        )
        .rename(
            {
                "name": "Naam",
                "type": "Type",
                "identifier": "Identifier",
                "currency": "Valuta",
                "provider": "Provider",
                "active": "Actief",
            }
        )
    )


def _financial_accounts_table(
    df,
    mo,
    *,
    empty_message: str,
    label: str,
    page_size: int,
):
    if df.height == 0:
        return mo.callout(mo.md(empty_message), kind="neutral")

    return mo.ui.table(
        _financial_accounts_display_df(df).to_pandas(),
        selection=None,
        page_size=page_size,
        label=label,
    )


def _bank_mutations_display_df(df):
    mutations_table_data = _format_money_columns(
        _add_status_label(
            _add_status_label(
                df,
                source_column="state",
                label_column="Status",
            ),
            source_column="settlement_state",
            label_column="Afletterstatus",
        ),
        ["amount", "amount_open"],
    )
    return mutations_table_data.select(
        [
            "date",
            "financial_account_name",
            "amount",
            "amount_open",
            "contra_account_name",
            "contra_account_number",
            "message",
            "Status",
            "Afletterstatus",
        ]
    ).rename(
        {
            "date": "Datum",
            "financial_account_name": "Rekening",
            "amount": "Bedrag",
            "amount_open": "Open bedrag",
            "contra_account_name": "Tegenrekening naam",
            "contra_account_number": "Tegenrekening nummer",
            "message": "Omschrijving",
        }
    )


def _bank_mutations_table(
    df,
    mo,
    *,
    empty_message: str,
    label: str,
    page_size: int,
):
    if df.height == 0:
        return mo.callout(mo.md(empty_message), kind="neutral")

    return mo.ui.table(
        _bank_mutations_display_df(df).to_pandas(),
        selection=None,
        page_size=page_size,
        label=label,
    )


def _add_status_label(df, *, source_column: str, label_column: str):
    if df.height == 0 or source_column not in df.columns:
        return df

    return df.with_columns(
        pl.col(source_column)
        .map_elements(_status_label, return_dtype=pl.String)
        .alias(label_column)
    )


def _status_label(value: object) -> str:
    value_text = "" if value is None else str(value).strip()
    if not value_text:
        return "Onbekend"

    status_labels = {
        "draft": "Concept",
        "open": "Open",
        "late": "Verlopen",
        "paid": "Betaald",
        "pending_payment": "Betaling onderweg",
        "reminded": "Herinnerd",
        "uncollectible": "Oninbaar",
        "processed": "Verwerkt",
        "unprocessed": "Niet verwerkt",
        "all": "Alles",
        "settled": "Afgeletterd",
        "unsettled": "Niet afgeletterd",
        "partially_settled": "Deels afgeletterd",
    }
    normalized = value_text.lower()
    return status_labels.get(normalized, value_text.replace("_", " ").title())


def _bool_label(value: object) -> str:
    if value is True:
        return "Ja"
    if value is False:
        return "Nee"

    value_text = "" if value is None else str(value).strip().lower()
    if value_text in {"true", "1", "yes", "ja"}:
        return "Ja"
    if value_text in {"false", "0", "no", "nee"}:
        return "Nee"

    return "Onbekend"


def _add_report_type_label(df):
    if df.height == 0 or "report_type" not in df.columns:
        return df

    return df.with_columns(
        pl.col("report_type")
        .map_elements(_report_type_label, return_dtype=pl.String)
        .alias("Rapport")
    )


def _report_type_label(value: object) -> str:
    value_text = "" if value is None else str(value).strip()
    report_labels = {
        "profit_loss": "Winst en verlies",
        "balance_sheet": "Balans",
    }
    return report_labels.get(value_text, value_text.replace("_", " ").title())


def _dataset_quality_row(label: str, df, synced_at_column: str, polars_module) -> dict:
    latest_sync = None
    if df.height > 0 and synced_at_column in df.columns:
        latest_sync = df.select(polars_module.col(synced_at_column).max())[0, 0]

    return {
        "Dataset": label,
        "Rijen": df.height,
        "Laatste sync": str(latest_sync) if latest_sync else "",
    }


def _moneybird_sync_quality_rows(
    *,
    df_sales_invoices,
    df_purchase_invoices,
    df_report_snapshots,
    df_financial_accounts,
    df_financial_mutations,
    pl,
) -> list[dict]:
    return [
        _dataset_quality_row("Verkoopfacturen", df_sales_invoices, "synced_at", pl),
        _dataset_quality_row("Inkoopfacturen", df_purchase_invoices, "synced_at", pl),
        _dataset_quality_row("Rapport snapshots", df_report_snapshots, "synced_at", pl),
        _dataset_quality_row(
            "Financiele rekeningen", df_financial_accounts, "synced_at", pl
        ),
        _dataset_quality_row("Bankmutaties", df_financial_mutations, "synced_at", pl),
    ]


def _quality_check_row(label: str, count: int, action: str) -> dict:
    return {
        "Controle": label,
        "Aantal": count,
        "Status": "Waarschuwing" if count > 0 else "OK",
        "Actie": action if count > 0 else "",
    }


def _count_missing_lookup(
    df,
    *,
    id_column: str,
    name_column: str,
    pl,
) -> int:
    if df.height == 0:
        return 0
    if id_column not in df.columns or name_column not in df.columns:
        return 0

    return df.filter(
        pl.col(id_column).is_not_null()
        & (
            pl.col(name_column).is_null()
            | (pl.col(name_column).cast(pl.String).str.strip_chars() == "")
        )
    ).height


def _count_empty_report_snapshots(df, pl) -> int:
    if df.height == 0:
        return 1
    if "raw_json" not in df.columns:
        return df.height

    numeric_columns = [
        column
        for column in [
            "total_revenue",
            "total_expenses",
            "gross_profit",
            "operating_profit",
            "net_profit",
        ]
        if column in df.columns
    ]
    empty_raw_expression = (
        pl.col("raw_json").is_null()
        | (pl.col("raw_json").cast(pl.String).str.strip_chars() == "")
        | (pl.col("raw_json").cast(pl.String).str.strip_chars().is_in(["{}", "[]"]))
    )
    if not numeric_columns:
        return df.filter(empty_raw_expression).height

    all_values_missing = pl.all_horizontal(
        [pl.col(column).is_null() for column in numeric_columns]
    )
    return df.filter(empty_raw_expression & all_values_missing).height


def _open_bank_mutation_rows(df, pl):
    if df.height == 0 or "amount_open" not in df.columns:
        return df

    return df.filter(pl.col("amount_open").is_not_null() & (pl.col("amount_open") != 0))


def _bank_state_rows(df, *, state: str, pl):
    if df.height == 0 or "state" not in df.columns:
        return df

    return df.filter(pl.col("state") == state)


def _sum_positive_amounts(df, column: str, pl) -> Decimal:
    if df.height == 0 or column not in df.columns:
        return Decimal("0")

    return _sum_column(df.filter(pl.col(column) > 0), column, pl)


def _sum_negative_amounts_abs(df, column: str, pl) -> Decimal:
    if df.height == 0 or column not in df.columns:
        return Decimal("0")

    value = _sum_column(df.filter(pl.col(column) < 0), column, pl)
    return abs(value)


def _report_account_detail_rows(
    df_reports, df_ledger_accounts, *, report_type: str, pl
):
    row = _report_snapshot_row(df_reports, report_type, pl)
    if row is None:
        return _empty_report_account_detail_df(pl)

    raw_json = _coerce_report_json(row.get("raw_json"))
    money_rows = [
        item
        for item in _report_json_money_rows(raw_json, max_rows=250)
        if item["account_id"]
    ]
    if not money_rows:
        return _empty_report_account_detail_df(pl)

    account_names = _ledger_account_name_map(df_ledger_accounts)
    account_types = _ledger_account_type_map(df_ledger_accounts)
    detail_rows = []
    for item in money_rows:
        amount = item["amount"]
        account_id = str(item["account_id"])
        category = str(item["path"] or _report_type_label(report_type))
        account_type = account_types.get(account_id, "") or _account_type_from_category(
            category
        )
        detail_rows.append(
            {
                "Categorie": category,
                "Account ID": account_id,
                "Grootboekrekening": account_names.get(account_id, ""),
                "Grootboektype": _ledger_account_type_label(account_type),
                "Omschrijving type": _ledger_account_type_description(account_type),
                "Onderdeel": str(item["label"]),
                "Bedrag": _format_euro(amount),
                "BedragSort": float(amount),
            }
        )

    return pl.DataFrame(detail_rows).sort(["Categorie", "Account ID", "Onderdeel"])


def _top_cost_account_rows(df, *, pl):
    if df.height == 0 or "BedragSort" not in df.columns:
        return df

    return (
        df.with_columns(pl.col("Categorie").str.to_lowercase().alias("_categorie"))
        .filter(
            (pl.col("BedragSort") < 0)
            | pl.col("_categorie").str.contains("kosten|cost|expense")
        )
        .with_columns(pl.col("BedragSort").abs().alias("_absolute_amount"))
        .sort("_absolute_amount", descending=True)
        .head(10)
        .drop(["_categorie", "_absolute_amount"])
    )


def _ledger_account_name_map(df) -> dict[str, str]:
    if df.height == 0:
        return {}
    if "name" not in df.columns:
        return {}

    lookup = {}
    lookup_columns = [
        column for column in ["account_id", "moneybird_id"] if column in df.columns
    ]
    for row in df.select([*lookup_columns, "name"]).to_dicts():
        name = row.get("name")
        if name is None:
            continue
        for lookup_column in lookup_columns:
            lookup_value = row.get(lookup_column)
            if lookup_value is None:
                continue
            lookup[str(lookup_value)] = str(name)

    return lookup


def _ledger_account_type_map(df) -> dict[str, str]:
    if df.height == 0:
        return {}
    if "account_type" not in df.columns:
        return {}

    lookup = {}
    lookup_columns = [
        column for column in ["account_id", "moneybird_id"] if column in df.columns
    ]
    for row in df.select([*lookup_columns, "account_type"]).to_dicts():
        account_type = row.get("account_type")
        if account_type is None:
            continue
        for lookup_column in lookup_columns:
            lookup_value = row.get(lookup_column)
            if lookup_value is None:
                continue
            lookup[str(lookup_value)] = str(account_type)

    return lookup


def _account_type_from_category(category: object) -> str:
    category_text = "" if category is None else str(category).lower()
    category_mapping = {
        "direct costs": "direct_costs",
        "revenue": "revenue",
        "expenses": "expenses",
        "current assets": "current_assets",
        "non-current assets": "non_current_assets",
        "non current assets": "non_current_assets",
        "current liabilities": "current_liabilities",
        "non-current liabilities": "non_current_liabilities",
        "non current liabilities": "non_current_liabilities",
        "equity": "equity",
    }
    for category_key, account_type in category_mapping.items():
        if category_key in category_text:
            return account_type

    return ""


def _empty_report_account_detail_df(pl):
    return pl.DataFrame(
        schema={
            "Categorie": pl.String,
            "Account ID": pl.String,
            "Grootboekrekening": pl.String,
            "Grootboektype": pl.String,
            "Omschrijving type": pl.String,
            "Onderdeel": pl.String,
            "Bedrag": pl.String,
            "BedragSort": pl.Float64,
        }
    )


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


def _bank_monthly_flows(df, *, pl):
    if df.height == 0:
        return pl.DataFrame(
            schema={"Maand": pl.String, "Richting": pl.String, "Bedrag": pl.Float64}
        )

    return (
        df.filter(pl.col("date").is_not_null() & pl.col("amount").is_not_null())
        .with_columns(
            pl.col("date").dt.strftime("%Y-%m").alias("Maand"),
            pl.when(pl.col("amount") >= 0)
            .then(pl.lit("Inkomend"))
            .otherwise(pl.lit("Uitgaand"))
            .alias("Richting"),
            pl.col("amount").abs().alias("absolute_amount"),
        )
        .group_by(["Maand", "Richting"])
        .agg(pl.col("absolute_amount").sum().cast(pl.Float64).round(2).alias("Bedrag"))
        .select(["Maand", "Richting", "Bedrag"])
        .sort(["Maand", "Richting"])
    )
