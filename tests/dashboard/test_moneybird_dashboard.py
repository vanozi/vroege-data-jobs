from datetime import date, datetime
from decimal import Decimal

import polars as pl

from dashboard import moneybird_transforms


def test_format_euro_cell_handles_decimal_none_and_invalid_values():
    assert moneybird_transforms._format_euro_cell(Decimal("1234.5")) == "EUR 1.234,50"
    assert moneybird_transforms._format_euro_cell(None) == "EUR 0,00"
    assert moneybird_transforms._format_euro_cell("invalid") == "EUR 0,00"


def test_status_label_translates_known_values_and_keeps_unknown_readable():
    assert moneybird_transforms._status_label("open") == "Open"
    assert moneybird_transforms._status_label("paid") == "Betaald"
    assert (
        moneybird_transforms._status_label("partially_settled") == "Deels afgeletterd"
    )
    assert moneybird_transforms._status_label("custom_status") == "Custom Status"
    assert moneybird_transforms._status_label(None) == "Onbekend"


def test_count_missing_lookup_counts_rows_with_id_without_name():
    df = pl.DataFrame(
        [
            {"contact_id": "1", "contact_name": "Klant"},
            {"contact_id": "2", "contact_name": None},
            {"contact_id": "3", "contact_name": ""},
            {"contact_id": None, "contact_name": None},
        ]
    )

    assert (
        moneybird_transforms._count_missing_lookup(
            df,
            id_column="contact_id",
            name_column="contact_name",
            pl=pl,
        )
        == 2
    )


def test_dataset_quality_row_handles_empty_dataframes():
    df = pl.DataFrame(schema={"synced_at": pl.Datetime})

    row = moneybird_transforms._dataset_quality_row(
        "Verkoopfacturen", df, "synced_at", pl
    )

    assert row == {
        "Dataset": "Verkoopfacturen",
        "Rijen": 0,
        "Laatste sync": "",
    }


def test_quality_check_row_marks_warnings_and_ok_rows():
    warning = moneybird_transforms._quality_check_row(
        "Facturen zonder contact",
        2,
        "Synchroniseer contacten.",
    )
    ok = moneybird_transforms._quality_check_row(
        "Facturen zonder contact",
        0,
        "Synchroniseer contacten.",
    )

    assert warning == {
        "Controle": "Facturen zonder contact",
        "Aantal": 2,
        "Status": "Waarschuwing",
        "Actie": "Synchroniseer contacten.",
    }
    assert ok == {
        "Controle": "Facturen zonder contact",
        "Aantal": 0,
        "Status": "OK",
        "Actie": "",
    }


def test_count_empty_report_snapshots_counts_only_empty_rows_without_values():
    df = pl.DataFrame(
        [
            {
                "raw_json": "{}",
                "total_revenue": None,
                "total_expenses": None,
                "gross_profit": None,
                "operating_profit": None,
                "net_profit": None,
            },
            {
                "raw_json": '{"total_revenue":"100"}',
                "total_revenue": None,
                "total_expenses": None,
                "gross_profit": None,
                "operating_profit": None,
                "net_profit": None,
            },
            {
                "raw_json": None,
                "total_revenue": Decimal("100.00"),
                "total_expenses": None,
                "gross_profit": None,
                "operating_profit": None,
                "net_profit": None,
            },
        ]
    )

    assert moneybird_transforms._count_empty_report_snapshots(df, pl) == 1


def test_count_empty_report_snapshots_warns_when_dataset_is_missing():
    df = pl.DataFrame(schema={"raw_json": pl.String})

    assert moneybird_transforms._count_empty_report_snapshots(df, pl) == 1


def test_count_overdue_invoices_counts_unpaid_past_due_rows():
    df = pl.DataFrame(
        [
            {"due_date": date(2026, 6, 1), "paid_at": None},
            {"due_date": date(2026, 6, 1), "paid_at": date(2026, 6, 2)},
            {"due_date": date(2026, 7, 1), "paid_at": None},
            {"due_date": None, "paid_at": None},
        ]
    )

    count = moneybird_transforms._count_overdue_invoices(
        df,
        due_date_column="due_date",
        paid_at_column="paid_at",
        today=date(2026, 6, 24),
        pl=pl,
    )

    assert count == 1


def test_open_and_overdue_invoice_rows_return_expected_rows():
    df = pl.DataFrame(
        [
            {"invoice_id": "open-late", "due_date": date(2026, 6, 1), "paid_at": None},
            {
                "invoice_id": "paid-late",
                "due_date": date(2026, 6, 1),
                "paid_at": date(2026, 6, 2),
            },
            {
                "invoice_id": "open-current",
                "due_date": date(2026, 7, 1),
                "paid_at": None,
            },
        ]
    )

    open_rows = moneybird_transforms._open_invoice_rows(
        df, paid_at_column="paid_at", pl=pl
    )
    overdue_rows = moneybird_transforms._overdue_invoice_rows(
        df,
        due_date_column="due_date",
        paid_at_column="paid_at",
        today=date(2026, 6, 24),
        pl=pl,
    )

    assert open_rows["invoice_id"].to_list() == ["open-late", "open-current"]
    assert overdue_rows["invoice_id"].to_list() == ["open-late"]


def test_top_unique_strings_limits_and_sorts_by_name_after_frequency_selection():
    df = pl.DataFrame(
        [
            {"contact_name": "B klant"},
            {"contact_name": "A klant"},
            {"contact_name": "B klant"},
            {"contact_name": "C klant"},
            {"contact_name": ""},
            {"contact_name": None},
        ]
    )

    assert moneybird_transforms._top_unique_strings(
        df,
        "contact_name",
        pl,
        limit=2,
    ) == ["A klant", "B klant"]


def test_sales_invoice_display_df_formats_expected_columns():
    df = pl.DataFrame(
        [
            {
                "invoice_date": date(2026, 6, 1),
                "invoice_id": "2026-001",
                "contact_name": "Klant",
                "state": "open",
                "due_date": date(2026, 6, 15),
                "paid_at": None,
                "total_price_incl_tax": Decimal("121.00"),
                "total_paid": Decimal("0"),
                "total_unpaid": Decimal("121.00"),
                "reminder_count": 1,
            }
        ]
    )

    display_df = moneybird_transforms._sales_invoice_display_df(df)

    assert display_df.columns == [
        "Factuurdatum",
        "Factuurnummer",
        "Contact",
        "Status",
        "Vervaldatum",
        "Betaaldatum",
        "Totaal incl. btw",
        "Betaald",
        "Open bedrag",
        "Herinneringen",
    ]
    assert display_df["Status"].to_list() == ["Open"]
    assert display_df["Open bedrag"].to_list() == ["EUR 121,00"]


def test_purchase_invoice_display_df_formats_expected_columns():
    df = pl.DataFrame(
        [
            {
                "date": date(2026, 6, 1),
                "entry_number": 42,
                "reference": "INK-001",
                "contact_name": "Leverancier",
                "state": "open",
                "due_date": date(2026, 6, 15),
                "paid_at": None,
                "total_price_incl_tax": Decimal("242.00"),
                "total_price_incl_tax_base": Decimal("242.00"),
            }
        ]
    )

    display_df = moneybird_transforms._purchase_invoice_display_df(df)

    assert display_df.columns == [
        "Datum",
        "Boekstuk",
        "Referentie",
        "Leverancier",
        "Status",
        "Vervaldatum",
        "Betaaldatum",
        "Totaal incl. btw",
        "Totaal basisvaluta",
    ]
    assert display_df["Status"].to_list() == ["Open"]
    assert display_df["Totaal incl. btw"].to_list() == ["EUR 242,00"]


def test_profit_loss_report_rows_format_compact_report_card_data():
    df = pl.DataFrame(
        [
            {
                "report_type": "profit_loss",
                "period": "this_year",
                "total_revenue": Decimal("1000.00"),
                "total_expenses": Decimal("250.00"),
                "gross_profit": Decimal("750.00"),
                "operating_profit": Decimal("700.00"),
                "net_profit": Decimal("650.00"),
            }
        ]
    )

    rows = moneybird_transforms._profit_loss_report_rows(df, pl)

    assert rows.to_dicts() == [
        {"Onderdeel": "Omzet", "Waarde": "EUR 1.000,00", "Periode": "this_year"},
        {"Onderdeel": "Kosten", "Waarde": "EUR 250,00", "Periode": "this_year"},
        {"Onderdeel": "Brutomarge", "Waarde": "EUR 750,00", "Periode": "this_year"},
        {
            "Onderdeel": "Operationeel resultaat",
            "Waarde": "EUR 700,00",
            "Periode": "this_year",
        },
        {
            "Onderdeel": "Netto resultaat",
            "Waarde": "EUR 650,00",
            "Periode": "this_year",
        },
    ]


def test_balance_sheet_report_rows_extract_money_values_from_raw_json():
    df = pl.DataFrame(
        [
            {
                "report_type": "balance_sheet",
                "period": "this_year",
                "raw_json": {
                    "assets": [
                        {
                            "name": "Bank",
                            "account_id": "1000",
                            "balance": "1250.50",
                        }
                    ],
                    "equity": {"label": "Eigen vermogen", "total": "1250.50"},
                },
            }
        ]
    )

    rows = moneybird_transforms._balance_sheet_report_rows(df, pl)

    assert rows.to_dicts() == [
        {"Onderdeel": "Bank", "Account ID": "1000", "Waarde": "EUR 1.250,50"},
        {
            "Onderdeel": "Eigen vermogen",
            "Account ID": "",
            "Waarde": "EUR 1.250,50",
        },
    ]


def test_ledger_accounts_display_df_formats_lookup_columns():
    df = pl.DataFrame(
        [
            {
                "account_id": "8000",
                "name": "Omzet",
                "account_type": "revenue",
                "moneybird_id": "ledger-1",
                "moneybird_version": 3,
                "synced_at": datetime(2026, 6, 23, 11, 0),
            }
        ]
    )

    display_df = moneybird_transforms._ledger_accounts_display_df(df)

    assert display_df.columns == [
        "Account ID",
        "Naam",
        "Type",
        "Moneybird ID",
        "Versie",
        "Gesynchroniseerd",
    ]
    assert display_df["Naam"].to_list() == ["Omzet"]


def test_report_account_detail_rows_map_account_ids_to_ledger_names():
    reports = pl.DataFrame(
        [
            {
                "report_type": "profit_loss",
                "period": "this_year",
                "raw_json": {
                    "expenses": [
                        {
                            "name": "Voerkosten",
                            "account_id": "4000",
                            "amount": "325.75",
                        }
                    ],
                },
            }
        ]
    )
    ledger_accounts = pl.DataFrame(
        [
            {
                "account_id": "4000",
                "moneybird_id": "ledger-moneybird-4000",
                "name": "Voer",
                "account_type": "direct_costs",
            }
        ]
    )

    rows = moneybird_transforms._report_account_detail_rows(
        reports,
        ledger_accounts,
        report_type="profit_loss",
        pl=pl,
    )

    assert rows.drop("BedragSort").to_dicts() == [
        {
            "Categorie": "Expenses",
            "Account ID": "4000",
            "Grootboekrekening": "Voer",
            "Grootboektype": "Direct costs",
            "Omschrijving type": (
                "Directe kosten die direct samenhangen met productie of omzet. "
                "Bijvoorbeeld voer, diergezondheid en productiegerelateerde inkoop."
            ),
            "Onderdeel": "Voerkosten",
            "Bedrag": "EUR 325,75",
        }
    ]


def test_report_account_detail_rows_map_moneybird_ledger_ids():
    reports = pl.DataFrame(
        [
            {
                "report_type": "profit_loss",
                "period": "this_year",
                "raw_json": {
                    "revenue": [
                        {
                            "name": "Melk",
                            "account_id": "ledger-moneybird-8000",
                            "amount": "1000.00",
                        }
                    ],
                },
            }
        ]
    )
    ledger_accounts = pl.DataFrame(
        [
            {
                "account_id": "8000",
                "moneybird_id": "ledger-moneybird-8000",
                "name": "Melkopbrengsten",
                "account_type": "revenue",
            }
        ]
    )

    rows = moneybird_transforms._report_account_detail_rows(
        reports,
        ledger_accounts,
        report_type="profit_loss",
        pl=pl,
    )

    assert rows["Grootboekrekening"].to_list() == ["Melkopbrengsten"]
    assert rows["Grootboektype"].to_list() == ["Revenue"]


def test_report_account_detail_rows_fall_back_to_category_for_account_type():
    reports = pl.DataFrame(
        [
            {
                "report_type": "profit_loss",
                "period": "this_year",
                "raw_json": {
                    "direct_costs": [
                        {
                            "name": "Voer",
                            "account_id": "missing-ledger",
                            "amount": "250.00",
                        }
                    ],
                },
            }
        ]
    )

    rows = moneybird_transforms._report_account_detail_rows(
        reports,
        pl.DataFrame(),
        report_type="profit_loss",
        pl=pl,
    )

    assert rows["Grootboektype"].to_list() == ["Direct costs"]
    assert rows["Omschrijving type"].to_list()[0].startswith("Directe kosten")


def test_ledger_account_type_description_rows_explain_moneybird_categories():
    rows = moneybird_transforms._ledger_account_type_description_rows(pl)

    assert rows.height == 8
    assert rows.filter(pl.col("Grootboektype") == "Revenue")[0, "Omschrijving"] == (
        "Omzet/opbrengsten. Bijvoorbeeld verkoop melk, vee, diensten, subsidies "
        "of andere bedrijfsopbrengsten."
    )
    assert rows.filter(pl.col("Grootboektype") == "Current assets")[
        0, "Omschrijving"
    ].startswith("Vlottende activa.")


def test_financial_accounts_display_df_formats_expected_columns():
    df = pl.DataFrame(
        [
            {
                "name": "Rabobank",
                "type": "bank",
                "identifier": "NL00RABO0000000000",
                "currency": "EUR",
                "provider": "rabo",
                "active": True,
            }
        ]
    )

    display_df = moneybird_transforms._financial_accounts_display_df(df)

    assert display_df.columns == [
        "Naam",
        "Type",
        "Identifier",
        "Valuta",
        "Provider",
        "Actief",
    ]
    assert display_df["Actief"].to_list() == ["Ja"]


def test_bank_mutations_display_df_formats_expected_columns():
    df = pl.DataFrame(
        [
            {
                "date": date(2026, 6, 1),
                "financial_account_name": "Rabobank",
                "amount": Decimal("121.00"),
                "amount_open": Decimal("21.00"),
                "contra_account_name": "Klant",
                "contra_account_number": "NL00TEST",
                "message": "Factuur betaald",
                "state": "processed",
                "settlement_state": "partially_settled",
            }
        ]
    )

    display_df = moneybird_transforms._bank_mutations_display_df(df)

    assert display_df.columns == [
        "Datum",
        "Rekening",
        "Bedrag",
        "Open bedrag",
        "Tegenrekening naam",
        "Tegenrekening nummer",
        "Omschrijving",
        "Status",
        "Afletterstatus",
    ]
    assert display_df["Bedrag"].to_list() == ["EUR 121,00"]
    assert display_df["Afletterstatus"].to_list() == ["Deels afgeletterd"]


def test_bank_open_and_state_rows_return_expected_rows():
    df = pl.DataFrame(
        [
            {"moneybird_id": "1", "amount_open": Decimal("10.00"), "state": "open"},
            {
                "moneybird_id": "2",
                "amount_open": Decimal("0.00"),
                "state": "unprocessed",
            },
            {
                "moneybird_id": "3",
                "amount_open": None,
                "state": "unprocessed",
            },
        ]
    )

    open_rows = moneybird_transforms._open_bank_mutation_rows(df, pl)
    unprocessed_rows = moneybird_transforms._bank_state_rows(
        df,
        state="unprocessed",
        pl=pl,
    )

    assert open_rows["moneybird_id"].to_list() == ["1"]
    assert unprocessed_rows["moneybird_id"].to_list() == ["2", "3"]


def test_bank_amount_sums_split_positive_and_negative_values():
    df = pl.DataFrame(
        [
            {"amount": Decimal("100.00")},
            {"amount": Decimal("-25.50")},
            {"amount": Decimal("-10.00")},
        ]
    )

    assert moneybird_transforms._sum_positive_amounts(df, "amount", pl) == Decimal(
        "100.00"
    )
    assert moneybird_transforms._sum_negative_amounts_abs(df, "amount", pl) == Decimal(
        "35.50"
    )


def test_bank_monthly_flows_splits_incoming_and_outgoing_per_month():
    df = pl.DataFrame(
        [
            {"date": date(2026, 6, 1), "amount": Decimal("100.00")},
            {"date": date(2026, 6, 2), "amount": Decimal("-25.00")},
            {"date": date(2026, 6, 3), "amount": Decimal("-5.00")},
            {"date": date(2026, 7, 1), "amount": Decimal("10.00")},
        ]
    )

    monthly = moneybird_transforms._bank_monthly_flows(df, pl=pl)

    assert monthly.to_dicts() == [
        {"Maand": "2026-06", "Richting": "Inkomend", "Bedrag": 100.0},
        {"Maand": "2026-06", "Richting": "Uitgaand", "Bedrag": 30.0},
        {"Maand": "2026-07", "Richting": "Inkomend", "Bedrag": 10.0},
    ]


def test_monthly_amounts_builds_scanable_purchase_costs_per_month():
    df = pl.DataFrame(
        [
            {"date": date(2026, 6, 1), "total_price_incl_tax": Decimal("100.00")},
            {"date": date(2026, 6, 15), "total_price_incl_tax": Decimal("50.00")},
            {"date": date(2026, 7, 1), "total_price_incl_tax": Decimal("25.00")},
        ]
    )

    monthly = moneybird_transforms._monthly_amounts(
        df,
        date_column="date",
        amount_column="total_price_incl_tax",
        label="Kosten",
        pl=pl,
    )

    assert monthly.to_dicts() == [
        {"Maand": "2026-06", "Type": "Kosten", "Bedrag": 150.0},
        {"Maand": "2026-07", "Type": "Kosten", "Bedrag": 25.0},
    ]


def test_latest_sync_text_returns_latest_timestamp_or_no_data():
    df = pl.DataFrame(
        [
            {"synced_at": datetime(2026, 6, 22, 10, 0)},
            {"synced_at": datetime(2026, 6, 23, 11, 0)},
        ]
    )
    empty_df = pl.DataFrame(schema={"synced_at": pl.Datetime})

    assert moneybird_transforms._latest_sync_text(df, "synced_at", pl) == (
        "2026-06-23 11:00:00"
    )
    assert moneybird_transforms._latest_sync_text(empty_df, "synced_at", pl) == (
        "Geen data"
    )
