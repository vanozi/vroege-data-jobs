from datetime import date, datetime
from decimal import Decimal

import polars as pl

from dashboard import moneybird_dashboard


def test_format_euro_cell_handles_decimal_none_and_invalid_values():
    assert moneybird_dashboard._format_euro_cell(Decimal("1234.5")) == "EUR 1.234,50"
    assert moneybird_dashboard._format_euro_cell(None) == "EUR 0,00"
    assert moneybird_dashboard._format_euro_cell("invalid") == "EUR 0,00"


def test_status_label_translates_known_values_and_keeps_unknown_readable():
    assert moneybird_dashboard._status_label("open") == "Open"
    assert moneybird_dashboard._status_label("paid") == "Betaald"
    assert moneybird_dashboard._status_label("partially_settled") == "Deels afgeletterd"
    assert moneybird_dashboard._status_label("custom_status") == "Custom Status"
    assert moneybird_dashboard._status_label(None) == "Onbekend"


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
        moneybird_dashboard._count_missing_lookup(
            df,
            id_column="contact_id",
            name_column="contact_name",
            pl=pl,
        )
        == 2
    )


def test_dataset_quality_row_handles_empty_dataframes():
    df = pl.DataFrame(schema={"synced_at": pl.Datetime})

    row = moneybird_dashboard._dataset_quality_row(
        "Verkoopfacturen", df, "synced_at", pl
    )

    assert row == {
        "Dataset": "Verkoopfacturen",
        "Rijen": 0,
        "Laatste sync": "",
    }


def test_count_overdue_invoices_counts_unpaid_past_due_rows():
    df = pl.DataFrame(
        [
            {"due_date": date(2026, 6, 1), "paid_at": None},
            {"due_date": date(2026, 6, 1), "paid_at": date(2026, 6, 2)},
            {"due_date": date(2026, 7, 1), "paid_at": None},
            {"due_date": None, "paid_at": None},
        ]
    )

    count = moneybird_dashboard._count_overdue_invoices(
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

    open_rows = moneybird_dashboard._open_invoice_rows(
        df, paid_at_column="paid_at", pl=pl
    )
    overdue_rows = moneybird_dashboard._overdue_invoice_rows(
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

    assert moneybird_dashboard._top_unique_strings(
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

    display_df = moneybird_dashboard._sales_invoice_display_df(df)

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


def test_latest_sync_text_returns_latest_timestamp_or_no_data():
    df = pl.DataFrame(
        [
            {"synced_at": datetime(2026, 6, 22, 10, 0)},
            {"synced_at": datetime(2026, 6, 23, 11, 0)},
        ]
    )
    empty_df = pl.DataFrame(schema={"synced_at": pl.Datetime})

    assert moneybird_dashboard._latest_sync_text(df, "synced_at", pl) == (
        "2026-06-23 11:00:00"
    )
    assert moneybird_dashboard._latest_sync_text(empty_df, "synced_at", pl) == (
        "Geen data"
    )
