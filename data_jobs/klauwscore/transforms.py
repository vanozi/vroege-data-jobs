from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Optional, Union

from database.models.behandeling import KlauwBehandeling
from data_jobs.klauwscore import pdf_parser


@dataclass(frozen=True)
class ParsedKlauwscoreDocument:
    behandeldatum: date
    aantal_koeien: int
    href: str
    records: list[pdf_parser.KlauwscorePdfRecord]

    @classmethod
    def from_mapping(cls, document: dict[str, object]) -> "ParsedKlauwscoreDocument":
        return cls(
            behandeldatum=_require_date(document, "behandeldatum"),
            aantal_koeien=_require_int(document, "aantal_koeien"),
            href=_require_str(document, "href"),
            records=_require_records(document, "records"),
        )


@dataclass(frozen=True)
class DocumentCountMismatch:
    behandeldatum: date
    href: str
    aantal_koeien: int
    parsed_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "behandeldatum": self.behandeldatum,
            "href": self.href,
            "aantal_koeien": self.aantal_koeien,
            "parsed_count": self.parsed_count,
        }


def klauw_behandeling_from_row(row: dict[str, object]) -> KlauwBehandeling:
    """Convert one flattened row into a KlauwBehandeling model."""
    return KlauwBehandeling(
        behandeldatum=_require_date(row, "behandeldatum"),
        eartag_short=_require_str(row, "eartag_short"),
        notatie=_optional_str(row.get("notatie")),
        pdf_href=_optional_str(row.get("pdf_href")),
    )


def flatten_documents(
    documents: Iterable[Union[ParsedKlauwscoreDocument, dict[str, object]]],
) -> list[dict[str, object]]:
    """Flatten parsed PDF documents to database-shaped notitie rows."""
    rows: list[dict[str, object]] = []
    for document in _iter_documents(documents):
        for row in pdf_parser.flatten_records(document.records):
            rows.append(
                {
                    **row,
                    "pdf_href": document.href,
                    "aantal_koeien_document": document.aantal_koeien,
                }
            )

    return rows


def dedupe_klauwbehandeling_rows(
    rows: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    """Remove duplicate klauwbehandeling rows before database upsert."""
    unique_rows: list[dict[str, object]] = []
    seen_keys: set[tuple[object, object, object]] = set()

    for row in rows:
        key = (
            row["behandeldatum"],
            row["eartag_short"],
            row["notatie"],
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        unique_rows.append(dict(row))

    return unique_rows


def validate_document_counts(
    documents: Iterable[Union[ParsedKlauwscoreDocument, dict[str, object]]],
) -> list[DocumentCountMismatch]:
    """Return documents where the agenda count differs from parsed cow count."""
    mismatches: list[DocumentCountMismatch] = []
    for document in _iter_documents(documents):
        parsed_count = len(document.records)
        if parsed_count == document.aantal_koeien:
            continue

        mismatches.append(
            DocumentCountMismatch(
                behandeldatum=document.behandeldatum,
                href=document.href,
                aantal_koeien=document.aantal_koeien,
                parsed_count=parsed_count,
            )
        )

    return mismatches


def _iter_documents(
    documents: Iterable[Union[ParsedKlauwscoreDocument, dict[str, object]]],
):
    for document in documents:
        if isinstance(document, ParsedKlauwscoreDocument):
            yield document
            continue

        yield ParsedKlauwscoreDocument.from_mapping(document)


def _require_date(row: dict[str, object], key: str) -> date:
    value = row[key]
    if isinstance(value, date):
        return value

    raise ValueError(f"Expected {key} to be a date.")


def _require_int(row: dict[str, object], key: str) -> int:
    value = row[key]
    if isinstance(value, int):
        return value

    raise ValueError(f"Expected {key} to be an int.")


def _require_str(row: dict[str, object], key: str) -> str:
    value = row[key]
    if isinstance(value, str):
        return value

    raise ValueError(f"Expected {key} to be a string.")


def _require_records(
    row: dict[str, object],
    key: str,
) -> list[pdf_parser.KlauwscorePdfRecord]:
    value = row[key]
    if not isinstance(value, list):
        raise ValueError(f"Expected {key} to be a list.")

    for record in value:
        if not isinstance(record, pdf_parser.KlauwscorePdfRecord):
            raise ValueError(f"Expected {key} to contain KlauwscorePdfRecord values.")

    return value


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        return value

    raise ValueError("Expected notatie to be a string or None.")
