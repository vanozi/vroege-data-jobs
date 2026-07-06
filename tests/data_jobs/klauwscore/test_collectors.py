from datetime import date

import pytest

from data_jobs.klauwscore import collectors
from data_jobs.klauwscore import pdf_parser
from data_jobs.klauwscore.config import KlauwscoreConfig


def test_collect_klauwscore_documents_parses_pdf_documents(monkeypatch):
    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        fake_parse_pdf_bytes,
    )

    result = collectors.collect_klauwscore_documents(build_config(), limit=1)

    assert result.document_count == 1
    assert result.cow_record_count == 2
    assert result.count_mismatch_count == 0
    assert result.failure_count == 0
    assert result.documents[0].href == "http://klauwscore.nl/export.pdf"


def test_collect_klauwscore_rows_flattens_pdf_documents_dedupes_and_summarizes(
    monkeypatch,
):
    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        fake_parse_pdf_bytes,
    )

    result = collectors.collect_klauwscore_rows(
        build_config(),
    )

    assert result.notitie_row_count == 3
    assert result.deduped_notitie_row_count == 2
    assert result.duplicate_row_count == 1
    assert result.searched_cow_count == 0
    assert result.document_count == 1
    assert result.cow_record_count == 2
    assert result.summary_counts() == {
        "documents": 1,
        "cow_records": 2,
        "stallijst_cows": 2,
        "searched_cows": 0,
        "notitie_rows": 3,
        "deduped_notitie_rows": 2,
        "duplicate_rows": 1,
        "count_mismatches": 0,
        "failures": 0,
    }


def test_collect_klauwscore_rows_reports_flatten_and_dedupe_progress(monkeypatch):
    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        fake_parse_pdf_bytes,
    )
    progress_messages = []

    collectors.collect_klauwscore_rows(
        build_config(),
        progress_callback=progress_messages.append,
    )

    assert "Flattening parsed PDF documents into notitie rows..." in progress_messages
    assert "Flattened 3 notitie rows from 1 PDF documents." in progress_messages
    assert "Deduped notitie rows: 2 unique rows, 1 duplicates removed." in (
        progress_messages
    )


def test_collect_klauwscore_rows_passes_existing_filters_to_pdf_scraper(monkeypatch):
    captured = {}

    def fake_scrape_pdfs_with_existing_filters(
        config,
        limit=None,
        progress_callback=None,
        continue_on_document_error=False,
        failure_callback=None,
        existing_behandeldatums=None,
        existing_pdf_hrefs=None,
    ):
        captured["existing_behandeldatums"] = existing_behandeldatums
        captured["existing_pdf_hrefs"] = existing_pdf_hrefs
        return fake_scrape_pdfs(
            config,
            limit=limit,
            progress_callback=progress_callback,
            continue_on_document_error=continue_on_document_error,
            failure_callback=failure_callback,
        )

    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs_with_existing_filters,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        fake_parse_pdf_bytes,
    )

    collectors.collect_klauwscore_rows(
        build_config(),
        existing_behandeldatums={date(2026, 5, 18)},
        existing_pdf_hrefs={"http://klauwscore.nl/export.pdf"},
    )

    assert captured["existing_behandeldatums"] == {date(2026, 5, 18)}
    assert captured["existing_pdf_hrefs"] == {"http://klauwscore.nl/export.pdf"}


def test_collect_klauwscore_documents_records_parse_failures_when_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        raise_parse_error,
    )

    result = collectors.collect_klauwscore_documents(
        build_config(),
        continue_on_document_error=True,
    )

    assert result.documents == []
    assert result.failure_count == 1
    assert result.failures[0].stage == "parse_pdf"
    assert result.failures[0].href == "http://klauwscore.nl/export.pdf"
    assert result.failures[0].behandeldatum == date(2026, 5, 19)
    assert "bad pdf" in result.failures[0].error


def test_collect_klauwscore_documents_aborts_parse_failures_by_default(monkeypatch):
    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        raise_parse_error,
    )

    with pytest.raises(ValueError, match="bad pdf"):
        collectors.collect_klauwscore_documents(build_config())


def test_collect_klauwscore_documents_surfaces_download_failures(monkeypatch):
    def fake_scrape_with_failure(
        config,
        limit=None,
        progress_callback=None,
        continue_on_document_error=False,
        failure_callback=None,
        existing_behandeldatums=None,
        existing_pdf_hrefs=None,
    ):
        failure_callback(
            collectors.AgendaPdfLink(
                behandeldatum=date(2026, 5, 19),
                aantal_koeien=1,
                href="http://klauwscore.nl/failed.pdf",
            ),
            RuntimeError("HTTP 502"),
        )
        return []

    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_with_failure,
    )

    result = collectors.collect_klauwscore_documents(
        build_config(),
        continue_on_document_error=True,
    )

    assert result.failure_count == 1
    assert result.failures[0].stage == "download_pdf"
    assert result.failures[0].href == "http://klauwscore.nl/failed.pdf"
    assert result.failures[0].error == "HTTP 502"


def test_collect_klauwscore_documents_reports_count_mismatches(monkeypatch):
    monkeypatch.setattr(
        collectors.scraper,
        "scrape_alle_notaties_pdfs",
        fake_scrape_pdfs_with_mismatch,
    )
    monkeypatch.setattr(
        collectors.pdf_parser,
        "parse_klauwscore_pdf_bytes",
        fake_parse_pdf_bytes,
    )

    result = collectors.collect_klauwscore_documents(build_config())

    assert result.count_mismatch_count == 1
    assert result.count_mismatches[0].aantal_koeien == 3
    assert result.count_mismatches[0].parsed_count == 2


def build_config() -> KlauwscoreConfig:
    return KlauwscoreConfig(username="user", password="secret")


def fake_scrape_pdfs(
    config,
    limit=None,
    progress_callback=None,
    continue_on_document_error=False,
    failure_callback=None,
    existing_behandeldatums=None,
    existing_pdf_hrefs=None,
):
    return [
        {
            "behandeldatum": date(2026, 5, 19),
            "aantal_koeien": 2,
            "href": "http://klauwscore.nl/export.pdf",
            "pdf_bytes": b"pdf",
        }
    ]


def fake_scrape_pdfs_with_mismatch(
    config,
    limit=None,
    progress_callback=None,
    continue_on_document_error=False,
    failure_callback=None,
    existing_behandeldatums=None,
    existing_pdf_hrefs=None,
):
    document = fake_scrape_pdfs(
        config,
        limit=limit,
        progress_callback=progress_callback,
        continue_on_document_error=continue_on_document_error,
        failure_callback=failure_callback,
        existing_behandeldatums=existing_behandeldatums,
        existing_pdf_hrefs=existing_pdf_hrefs,
    )[0]
    document["aantal_koeien"] = 3
    return [document]


def fake_parse_pdf_bytes(pdf_bytes):
    return [
        pdf_parser.KlauwscorePdfRecord(
            behandeldatum=date(2026, 5, 19),
            eartag_short="101",
            notities=["Bekapt", "Bekapt"],
        ),
        pdf_parser.KlauwscorePdfRecord(
            behandeldatum=date(2026, 5, 19),
            eartag_short="102",
            notities=["Blokje geplaatst"],
        ),
    ]


def raise_parse_error(pdf_bytes):
    raise ValueError("bad pdf")
