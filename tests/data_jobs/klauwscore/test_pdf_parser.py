from datetime import date

import pytest

from data_jobs.klauwscore import pdf_parser


def test_parse_klauwscore_pdf_text_extracts_inspection_date():
    records = pdf_parser.parse_klauwscore_pdf_text(
        """
        Registratie van behandelingen op 19-05-2026
        101
        Bekapt
        """
    )

    assert len(records) == 1
    assert records[0].behandeldatum == date(2026, 5, 19)


def test_parse_klauwscore_pdf_text_uses_numeric_lines_as_cow_boundaries():
    records = pdf_parser.parse_klauwscore_pdf_text(
        """
        Registratie van behandelingen op 19-05-2026
        101
        Mortellaro linksvoor
        102
        Wittelijndefect rechtsachter
        """
    )

    assert [record.eartag_short for record in records] == ["101", "102"]
    assert records[0].notities == ["Mortellaro linksvoor"]
    assert records[1].notities == ["Wittelijndefect rechtsachter"]


def test_parse_klauwscore_pdf_text_keeps_multiple_notities_per_cow():
    records = pdf_parser.parse_klauwscore_pdf_text(
        """
        Registratie van behandelingen op 19-05-2026
        101
        Mortellaro linksvoor
        Blokje geplaatst
        Spray gebruikt
        """
    )

    assert len(records) == 1
    assert records[0].notities == [
        "Mortellaro linksvoor",
        "Blokje geplaatst",
        "Spray gebruikt",
    ]


def test_parse_klauwscore_pdf_text_skips_header_footer_and_blank_lines():
    records = pdf_parser.parse_klauwscore_pdf_text(
        """
        Registratie van behandelingen op 19-05-2026

        101
        Bekapt
        test@rundveepedicure.nl : footer text | 1 / 2

        102
        Geen bijzonderheden
        """
    )

    assert [record.eartag_short for record in records] == ["101", "102"]
    assert records[0].notities == ["Bekapt"]
    assert records[1].notities == ["Geen bijzonderheden"]


def test_parse_klauwscore_pdf_text_raises_for_missing_inspection_date():
    with pytest.raises(ValueError, match="Could not find inspection date"):
        pdf_parser.parse_klauwscore_pdf_text(
            """
            101
            Bekapt
            """
        )


def test_flatten_records_returns_one_row_per_notitie():
    records = [
        pdf_parser.KlauwscorePdfRecord(
            behandeldatum=date(2026, 5, 19),
            eartag_short="101",
            notities=["Bekapt", "Blokje geplaatst"],
        ),
        pdf_parser.KlauwscorePdfRecord(
            behandeldatum=date(2026, 5, 19),
            eartag_short="102",
            notities=[],
        ),
    ]

    rows = pdf_parser.flatten_records(records)

    assert rows == [
        {
            "behandeldatum": date(2026, 5, 19),
            "eartag_short": "101",
            "notatie": "Bekapt",
        },
        {
            "behandeldatum": date(2026, 5, 19),
            "eartag_short": "101",
            "notatie": "Blokje geplaatst",
        },
    ]


def test_records_to_json_serializes_dates():
    records = [
        pdf_parser.KlauwscorePdfRecord(
            behandeldatum=date(2026, 5, 19),
            eartag_short="101",
            notities=["Bekapt"],
        )
    ]

    json_text = pdf_parser.records_to_json(records)

    assert '"behandeldatum": "2026-05-19"' in json_text
    assert '"eartag_short": "101"' in json_text
