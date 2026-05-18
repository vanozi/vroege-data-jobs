import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import lxml.html as lh
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from database.database import get_session
from database.repositories.behandelingen_repository import KlauwBehandelingenRepository
from data_jobs.logger import get_job_logger
from data_jobs.klauwscore.pdf_parser import flatten_records, parse_klauwscore_pdf_bytes

logger = get_job_logger(__file__)

BASE_URL = "http://klauwscore.nl"
LOGIN_URL = f"{BASE_URL}/login"
REGISTRATIELIJST_URL = f"{BASE_URL}/veehouder/agenda"

DUTCH_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


def print_progress(message):
    """Print human-readable run progress without corrupting JSON stdout."""
    print(message, file=sys.stderr, flush=True)


def load_klauwscore_env():
    """Load credentials from repo root .env and optional klauwscore .env."""
    load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)


load_klauwscore_env()


def login(page, username, password):
    """Log in to klauwscore.nl."""
    page.goto(LOGIN_URL)
    page.locator('//input[@id="username"]').fill(username)
    page.locator('//input[@id="password"]').fill(password)
    page.locator('//input[@id="_submit"]').click()
    page.wait_for_load_state("networkidle")


def parse_registratielijst(table):
    """Parse registration rows and return the Alle notaties PDF links."""
    rows = table.xpath(".//tbody/tr") or table.xpath(".//tr[td]")
    notatie_links = []

    for row in rows:
        alle_notaties_href = row.xpath(
            ".//a[normalize-space(.) = 'Alle notaties']/@href"
        )
        if not alle_notaties_href:
            continue

        notatie_links.append(
            {
                "behandeldatum": parse_agenda_date(row),
                "aantal_koeien": parse_aantal_koeien(row),
                "href": urljoin(BASE_URL, alle_notaties_href[0]),
            }
        )

    return notatie_links


def parse_agenda_date(row):
    """Parse the Dutch agenda date cell into a date."""
    day_text = row.xpath("normalize-space(.//*[contains(@class, 'dayofmonth')])")
    month_year_text = row.xpath("normalize-space(.//*[contains(@class, 'shortdate')])")
    month_year_parts = month_year_text.replace(",", " ").split()

    if len(month_year_parts) < 2:
        raise ValueError(f"Could not parse agenda date from row: {month_year_text}")

    month = DUTCH_MONTHS[month_year_parts[0].lower()]
    year = int(month_year_parts[1])
    return date(year, month, int(day_text))


def parse_aantal_koeien(row):
    """Parse the cow count from the registration row."""
    count_text = row.xpath("normalize-space(.//*[contains(@class, 'agenda-time')])")
    return int(count_text.split()[0])


def scrape_alle_notaties_links():
    """Scrape all Alle notaties PDF links from the registration list."""
    username = os.getenv("KLAUWSCORE_USERNAME")
    password = os.getenv("KLAUWSCORE_PASSWORD")

    if not username or not password:
        raise RuntimeError("Missing KLAUWSCORE_USERNAME or KLAUWSCORE_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        login(page, username, password)
        page.goto(REGISTRATIELIJST_URL)
        registratielijst_html = page.inner_html("//div[@class='account-wrapper']")
        browser.close()

    table = lh.fragment_fromstring(registratielijst_html)
    return parse_registratielijst(table)


def download_pdf(page, href, attempts=3, timeout_ms=120_000):
    """Download a PDF through the authenticated Playwright context."""
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            response = page.context.request.get(href, timeout=timeout_ms)
        except Exception as error:
            last_error = error
            logger.warning(
                "PDF download attempt %s/%s failed for %s: %s",
                attempt,
                attempts,
                href,
                error,
            )
            continue

        if not response.ok:
            last_error = RuntimeError(
                f"Failed to download PDF {href}: HTTP {response.status}"
            )
            logger.warning(
                "PDF download attempt %s/%s failed for %s: HTTP %s",
                attempt,
                attempts,
                href,
                response.status,
            )
            continue

        body = response.body()
        if body:
            return body

        last_error = RuntimeError(f"Downloaded empty PDF body for {href}")
        logger.warning(
            "PDF download attempt %s/%s returned an empty body for %s",
            attempt,
            attempts,
            href,
        )

    raise RuntimeError(
        f"Failed to download PDF after {attempts} attempts: {href}"
    ) from last_error


def validate_document_counts(parsed_documents):
    """Return documents where the agenda count differs from parsed cow count."""
    mismatches = []
    for document in parsed_documents:
        parsed_count = len(document["records"])
        if parsed_count != document["aantal_koeien"]:
            mismatches.append(
                {
                    "behandeldatum": document["behandeldatum"],
                    "href": document["href"],
                    "aantal_koeien": document["aantal_koeien"],
                    "parsed_count": parsed_count,
                }
            )
    return mismatches


def scrape_alle_notaties_records(limit=None):
    """Download and parse all notaties PDFs."""
    username = os.getenv("KLAUWSCORE_USERNAME")
    password = os.getenv("KLAUWSCORE_PASSWORD")

    if not username or not password:
        raise RuntimeError("Missing KLAUWSCORE_USERNAME or KLAUWSCORE_PASSWORD")

    parsed_documents = []

    with sync_playwright() as p:
        print_progress("Starting browser and logging in to Klauwscore...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        login(page, username, password)

        print_progress("Loading Klauwscore agenda...")
        page.goto(REGISTRATIELIJST_URL)
        registratielijst_html = page.inner_html("//div[@class='account-wrapper']")
        notatie_links = parse_registratielijst(
            lh.fragment_fromstring(registratielijst_html)
        )
        print_progress(f"Found {len(notatie_links)} Alle notaties PDFs.")

        if limit is not None:
            notatie_links = notatie_links[:limit]
            print_progress(f"Limiting run to first {len(notatie_links)} PDFs.")

        for index, notatie_link in enumerate(notatie_links, start=1):
            print_progress(
                "Downloading PDF "
                f"{index}/{len(notatie_links)} for date "
                f"{notatie_link['behandeldatum']}: {notatie_link['href']}"
            )
            pdf_bytes = download_pdf(page, notatie_link["href"])
            records = parse_klauwscore_pdf_bytes(pdf_bytes)
            print_progress(
                "Parsed PDF "
                f"{index}/{len(notatie_links)} for date "
                f"{notatie_link['behandeldatum']}: {len(records)} cow records."
            )
            parsed_documents.append(
                {
                    **notatie_link,
                    "records": records,
                }
            )

        browser.close()
        print_progress("Finished downloading and parsing Klauwscore PDFs.")

    return parsed_documents


def flatten_documents(parsed_documents):
    """Flatten parsed PDF documents to database-shaped notitie rows."""
    rows = []
    for document in parsed_documents:
        for row in flatten_records(document["records"]):
            rows.append(
                {
                    **row,
                    "pdf_href": document["href"],
                    "aantal_koeien_document": document["aantal_koeien"],
                }
            )
    return rows


def serialize_documents(parsed_documents):
    """Convert parsed documents to JSON-serializable dictionaries."""
    data = []
    for document in parsed_documents:
        data.append(
            {
                "behandeldatum": document["behandeldatum"].isoformat(),
                "aantal_koeien": document["aantal_koeien"],
                "href": document["href"],
                "records": [
                    {
                        "behandeldatum": record.behandeldatum.isoformat(),
                        "halsbandnummer": record.halsbandnummer,
                        "notities": record.notities,
                    }
                    for record in document["records"]
                ],
            }
        )
    return data


def serialize_flat_rows(rows):
    """Convert flattened rows to JSON-serializable dictionaries."""
    data = []
    for row in rows:
        data.append(
            {
                **row,
                "behandeldatum": row["behandeldatum"].isoformat(),
            }
        )
    return data


def upsert_klauwbehandeling_rows(rows):
    """Upsert flattened Klauwscore rows into klauw_behandelingen."""
    repository = KlauwBehandelingenRepository(get_session)
    upserted_count = 0

    if not rows:
        print_progress("No flattened notitie rows available to upsert.")
        return upserted_count

    rows_by_date = {}
    for row in rows:
        rows_by_date.setdefault(row["behandeldatum"], []).append(row)

    for behandeldatum, date_rows in sorted(rows_by_date.items()):
        print_progress(
            f"Saving {len(date_rows)} klauwbehandeling records "
            f"to database for date {behandeldatum}..."
        )
        for row in date_rows:
            repository.upsert_klauw_behandeling(
                {
                    "halsbandnummer": row["halsbandnummer"],
                    "behandeldatum": row["behandeldatum"],
                    "notatie": row["notatie"],
                }
            )
            upserted_count += 1
        print_progress(f"Saved records to database for date {behandeldatum}.")

    return upserted_count


def dedupe_klauwbehandeling_rows(rows):
    """Remove duplicate klauwbehandeling rows before database upsert."""
    unique_rows = []
    seen_keys = set()

    for row in rows:
        key = (
            row["behandeldatum"],
            row["halsbandnummer"],
            row["notatie"],
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)
        unique_rows.append(row)

    duplicate_count = len(rows) - len(unique_rows)
    if duplicate_count:
        print_progress(
            "Removed "
            f"{duplicate_count} duplicate klauwbehandeling rows before database upsert."
        )

    return unique_rows


def print_summary(parsed_documents):
    """Print counts for a parsed scraper run."""
    notitie_rows = flatten_documents(parsed_documents)
    mismatches = validate_document_counts(parsed_documents)
    print(f"documents={len(parsed_documents)}")
    print(f"cow_records={sum(len(document['records']) for document in parsed_documents)}")
    print(f"notitie_rows={len(notitie_rows)}")
    print(f"count_mismatches={len(mismatches)}")
    for mismatch in mismatches[:10]:
        print(
            "count_mismatch="
            f"{mismatch['behandeldatum']} "
            f"agenda={mismatch['aantal_koeien']} "
            f"parsed={mismatch['parsed_count']} "
            f"{mismatch['href']}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Scrape and parse Klauwscore Alle notaties PDFs."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only parse the first N Alle notaties PDFs.",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Output one row per notitie instead of one grouped record per cow.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print document, cow, notitie, and count-mismatch totals.",
    )
    parser.add_argument(
        "--upsert-db",
        action="store_true",
        help="Upsert flattened notitie rows into the klauw_behandelingen table.",
    )
    args = parser.parse_args()

    parsed_documents = scrape_alle_notaties_records(limit=args.limit)
    flat_rows = None

    if args.upsert_db:
        flat_rows = flatten_documents(parsed_documents)
        deduped_rows = dedupe_klauwbehandeling_rows(flat_rows)
        print(
            "upserted_klauw_behandelingen="
            f"{upsert_klauwbehandeling_rows(deduped_rows)}"
        )

    if args.summary:
        print_progress("Printing summary output.")
        print_summary(parsed_documents)
        return

    if args.upsert_db and not args.flat:
        return

    if args.flat:
        print_progress("Printing flattened JSON output.")
        if flat_rows is None:
            flat_rows = flatten_documents(parsed_documents)
        print(
            json.dumps(
                serialize_flat_rows(flat_rows),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_progress("Printing grouped JSON output.")
        print(
            json.dumps(
                serialize_documents(parsed_documents),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
