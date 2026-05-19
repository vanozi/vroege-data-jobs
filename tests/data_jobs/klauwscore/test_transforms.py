from copy import deepcopy
from datetime import date

import pytest

from data_jobs.klauwscore import pdf_parser
from data_jobs.klauwscore import transforms


def test_klauw_behandeling_from_row_builds_model_without_mutating_row():
    row = {
        "behandeldatum": date(2026, 5, 19),
        "halsbandnummer": 101,
        "notatie": "Bekapt",
        "pdf_href": "http://klauwscore.nl/export.pdf",
    }
    original = deepcopy(row)

    behandeling = transforms.klauw_behandeling_from_row(row)

    assert row == original
    assert behandeling.behandeldatum == date(2026, 5, 19)
    assert behandeling.halsbandnummer == 101
    assert behandeling.notatie == "Bekapt"


def test_flatten_documents_adds_document_metadata_without_mutating_documents():
    documents = [
        build_document(
            aantal_koeien=2,
            records=[
                build_record(101, ["Bekapt", "Blokje geplaatst"]),
                build_record(102, []),
            ],
        )
    ]
    original_records = list(documents[0].records)

    rows = transforms.flatten_documents(documents)

    assert documents[0].records == original_records
    assert rows == [
        {
            "behandeldatum": date(2026, 5, 19),
            "halsbandnummer": 101,
            "notatie": "Bekapt",
            "pdf_href": "http://klauwscore.nl/export.pdf",
            "aantal_koeien_document": 2,
        },
        {
            "behandeldatum": date(2026, 5, 19),
            "halsbandnummer": 101,
            "notatie": "Blokje geplaatst",
            "pdf_href": "http://klauwscore.nl/export.pdf",
            "aantal_koeien_document": 2,
        },
    ]


def test_flatten_documents_accepts_current_mapping_shape():
    documents = [
        {
            "behandeldatum": date(2026, 5, 19),
            "aantal_koeien": 1,
            "href": "http://klauwscore.nl/export.pdf",
            "records": [build_record(101, ["Bekapt"])],
        }
    ]

    rows = transforms.flatten_documents(documents)

    assert rows[0]["notatie"] == "Bekapt"
    assert rows[0]["pdf_href"] == "http://klauwscore.nl/export.pdf"


def test_dedupe_klauwbehandeling_rows_uses_explicit_identity_without_mutating_rows():
    rows = [
        build_row(101, "Bekapt"),
        build_row(101, "Bekapt"),
        build_row(101, "Blokje geplaatst"),
        build_row(102, "Bekapt"),
    ]
    original = deepcopy(rows)

    unique_rows = transforms.dedupe_klauwbehandeling_rows(rows)

    assert rows == original
    assert unique_rows == [
        build_row(101, "Bekapt"),
        build_row(101, "Blokje geplaatst"),
        build_row(102, "Bekapt"),
    ]


def test_dedupe_preserves_blank_notities_to_keep_current_behavior():
    rows = [
        build_row(101, ""),
        build_row(101, " "),
        build_row(101, ""),
    ]

    unique_rows = transforms.dedupe_klauwbehandeling_rows(rows)

    assert unique_rows == [
        build_row(101, ""),
        build_row(101, " "),
    ]


def test_validate_document_counts_returns_structured_mismatches():
    documents = [
        build_document(
            aantal_koeien=2,
            records=[build_record(101, ["Bekapt"])],
        ),
        build_document(
            aantal_koeien=1,
            href="http://klauwscore.nl/matching.pdf",
            records=[build_record(102, ["Bekapt"])],
        ),
    ]

    mismatches = transforms.validate_document_counts(documents)

    assert mismatches == [
        transforms.DocumentCountMismatch(
            behandeldatum=date(2026, 5, 19),
            href="http://klauwscore.nl/export.pdf",
            aantal_koeien=2,
            parsed_count=1,
        )
    ]
    assert mismatches[0].as_dict() == {
        "behandeldatum": date(2026, 5, 19),
        "href": "http://klauwscore.nl/export.pdf",
        "aantal_koeien": 2,
        "parsed_count": 1,
    }


def test_klauw_behandeling_from_row_rejects_invalid_notatie_type():
    with pytest.raises(ValueError, match="notatie"):
        transforms.klauw_behandeling_from_row(
            {
                "behandeldatum": date(2026, 5, 19),
                "halsbandnummer": 101,
                "notatie": 123,
            }
        )


def build_document(
    aantal_koeien: int,
    records: list[pdf_parser.KlauwscorePdfRecord],
    href: str = "http://klauwscore.nl/export.pdf",
) -> transforms.ParsedKlauwscoreDocument:
    return transforms.ParsedKlauwscoreDocument(
        behandeldatum=date(2026, 5, 19),
        aantal_koeien=aantal_koeien,
        href=href,
        records=records,
    )


def build_record(
    halsbandnummer: int,
    notities: list[str],
) -> pdf_parser.KlauwscorePdfRecord:
    return pdf_parser.KlauwscorePdfRecord(
        behandeldatum=date(2026, 5, 19),
        halsbandnummer=halsbandnummer,
        notities=notities,
    )


def build_row(halsbandnummer: int, notatie: str) -> dict[str, object]:
    return {
        "behandeldatum": date(2026, 5, 19),
        "halsbandnummer": halsbandnummer,
        "notatie": notatie,
    }
