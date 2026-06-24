from decimal import Decimal

import polars as pl

from dashboard import moneybird_dashboard


def test_format_euro_cell_handles_decimal_none_and_invalid_values():
    assert moneybird_dashboard._format_euro_cell(Decimal("12.5")) == "EUR 12.50"
    assert moneybird_dashboard._format_euro_cell(None) == "EUR 0.00"
    assert moneybird_dashboard._format_euro_cell("invalid") == "EUR 0.00"


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
