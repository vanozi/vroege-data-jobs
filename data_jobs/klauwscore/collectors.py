from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from data_jobs.klauwscore import agenda_parser
from data_jobs.klauwscore import pdf_parser
from data_jobs.klauwscore import scraper
from data_jobs.klauwscore import transforms
from data_jobs.klauwscore.config import KlauwscoreConfig
from data_jobs.klauwscore.transforms import DocumentCountMismatch
from data_jobs.klauwscore.transforms import ParsedKlauwscoreDocument


AgendaPdfLink = agenda_parser.AgendaPdfLink


@dataclass(frozen=True)
class DocumentCollectionFailure:
    stage: str
    href: str
    error: str
    behandeldatum: Optional[date] = None
    aantal_koeien: Optional[int] = None

    def as_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "href": self.href,
            "error": self.error,
            "behandeldatum": self.behandeldatum,
            "aantal_koeien": self.aantal_koeien,
        }


@dataclass
class KlauwscoreCollectionResult:
    documents: list[ParsedKlauwscoreDocument] = field(default_factory=list)
    rows: list[dict[str, object]] = field(default_factory=list)
    deduped_rows: list[dict[str, object]] = field(default_factory=list)
    count_mismatches: list[DocumentCountMismatch] = field(default_factory=list)
    failures: list[DocumentCollectionFailure] = field(default_factory=list)
    searched_cow_count: int = 0

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def cow_record_count(self) -> int:
        return sum(len(document.records) for document in self.documents)

    @property
    def stallijst_cow_count(self) -> int:
        return len(
            {(row.get("eartag_short"), row.get("behandeldatum")) for row in self.rows}
        )

    @property
    def notitie_row_count(self) -> int:
        return len(self.rows)

    @property
    def deduped_notitie_row_count(self) -> int:
        return len(self.deduped_rows)

    @property
    def duplicate_row_count(self) -> int:
        return self.notitie_row_count - self.deduped_notitie_row_count

    @property
    def count_mismatch_count(self) -> int:
        return len(self.count_mismatches)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    def summary_counts(self) -> dict[str, int]:
        return {
            "documents": self.document_count,
            "cow_records": self.cow_record_count,
            "stallijst_cows": self.stallijst_cow_count,
            "searched_cows": self.searched_cow_count,
            "notitie_rows": self.notitie_row_count,
            "deduped_notitie_rows": self.deduped_notitie_row_count,
            "duplicate_rows": self.duplicate_row_count,
            "count_mismatches": self.count_mismatch_count,
            "failures": self.failure_count,
        }


def collect_klauwscore_documents(
    config: KlauwscoreConfig,
    limit: Optional[int] = None,
    continue_on_document_error: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> KlauwscoreCollectionResult:
    """Collect and parse Klauwscore PDF documents without database writes."""
    failures: list[DocumentCollectionFailure] = []

    def record_download_failure(link: AgendaPdfLink, error: Exception) -> None:
        failures.append(
            _failure_from_link(
                stage="download_pdf",
                link=link,
                error=error,
            )
        )

    pdf_documents = scraper.scrape_alle_notaties_pdfs(
        config,
        limit=limit,
        progress_callback=progress_callback,
        continue_on_document_error=continue_on_document_error,
        failure_callback=record_download_failure,
    )

    documents: list[ParsedKlauwscoreDocument] = []
    for pdf_document in pdf_documents:
        try:
            records = pdf_parser.parse_klauwscore_pdf_bytes(
                _require_bytes(pdf_document, "pdf_bytes")
            )
        except Exception as error:
            failure = _failure_from_pdf_document("parse_pdf", pdf_document, error)
            if not continue_on_document_error:
                raise

            failures.append(failure)
            continue

        document = ParsedKlauwscoreDocument(
            behandeldatum=_require_date(pdf_document, "behandeldatum"),
            aantal_koeien=_require_int(pdf_document, "aantal_koeien"),
            href=_require_str(pdf_document, "href"),
            records=records,
        )
        documents.append(document)
        _report(
            progress_callback,
            f"Parsed PDF for date {document.behandeldatum}: {len(records)} cow records.",
        )

    return KlauwscoreCollectionResult(
        documents=documents,
        count_mismatches=transforms.validate_document_counts(documents),
        failures=failures,
    )


def collect_klauwscore_rows(
    config: KlauwscoreConfig,
    cows: Optional[list[dict[str, object]]] = None,
    limit: Optional[int] = None,
    continue_on_document_error: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> KlauwscoreCollectionResult:
    """Collect Klauwscore treatment rows by searching current-herd cows."""
    del continue_on_document_error

    failures: list[DocumentCollectionFailure] = []
    cow_rows = list(cows or [])
    if limit is not None:
        cow_rows = cow_rows[:limit]

    def record_cow_failure(cow: dict[str, object], error: Exception) -> None:
        failures.append(_failure_from_cow(cow, error, config.zoeken_url))

    rows = scraper.scrape_zoekresultaten_rows_for_cows(
        config,
        cows=cow_rows,
        progress_callback=progress_callback,
        failure_callback=record_cow_failure,
    )
    deduped_rows = transforms.dedupe_klauwbehandeling_rows(rows)

    return KlauwscoreCollectionResult(
        rows=rows,
        deduped_rows=deduped_rows,
        failures=failures,
        searched_cow_count=len(cow_rows),
    )


def _failure_from_link(
    stage: str,
    link: AgendaPdfLink,
    error: Exception,
) -> DocumentCollectionFailure:
    return DocumentCollectionFailure(
        stage=stage,
        href=link.href,
        behandeldatum=link.behandeldatum,
        aantal_koeien=link.aantal_koeien,
        error=str(error),
    )


def _failure_from_pdf_document(
    stage: str,
    pdf_document: dict[str, object],
    error: Exception,
) -> DocumentCollectionFailure:
    return DocumentCollectionFailure(
        stage=stage,
        href=str(pdf_document.get("href", "")),
        behandeldatum=_optional_date(pdf_document.get("behandeldatum")),
        aantal_koeien=_optional_int(pdf_document.get("aantal_koeien")),
        error=str(error),
    )


def _failure_from_cow(
    cow: dict[str, object],
    error: Exception,
    href: str,
) -> DocumentCollectionFailure:
    eartag_short = cow.get("eartag_short") or "unknown"
    return DocumentCollectionFailure(
        stage="search_cow",
        href=f"{href}#{eartag_short}",
        error=str(error),
    )


def _report(
    progress_callback: Optional[Callable[[str], None]],
    message: str,
) -> None:
    if progress_callback is None:
        return

    progress_callback(message)


def _require_bytes(row: dict[str, object], key: str) -> bytes:
    value = row[key]
    if isinstance(value, bytes):
        return value

    raise ValueError(f"Expected {key} to be bytes.")


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


def _optional_date(value: object) -> Optional[date]:
    if isinstance(value, date):
        return value

    return None


def _optional_int(value: object) -> Optional[int]:
    if isinstance(value, int):
        return value

    return None
