from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional

from pypdf import PdfReader


DATE_PATTERN = re.compile(r"\bop\s+(\d{2}-\d{2}-\d{4})\b")
COW_NUMBER_PATTERN = re.compile(r"^\d+$")
FOOTER_PATTERN = re.compile(r"^[^\s@]+@rundveepedicure\.nl\s*:.*\|\s*\d+\s*/\s*\d+$")


@dataclass(frozen=True)
class KlauwscorePdfRecord:
    behandeldatum: date
    eartag_short: str
    notities: list[str]


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract text from a text-based klauwscore PDF."""
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_pdf_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from a text-based klauwscore PDF in memory."""
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_klauwscore_pdf_text(text: str) -> list[KlauwscorePdfRecord]:
    """Parse klauwscore PDF text into one record per cow."""
    date_match = DATE_PATTERN.search(text)
    if not date_match:
        raise ValueError("Could not find inspection date in PDF text.")

    behandeldatum = datetime.strptime(date_match.group(1), "%d-%m-%Y").date()
    records: list[KlauwscorePdfRecord] = []
    current_eartag_short: Optional[str] = None
    current_notities: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if _should_skip_line(line):
            continue

        if COW_NUMBER_PATTERN.fullmatch(line):
            if current_eartag_short is not None:
                records.append(
                    KlauwscorePdfRecord(
                        behandeldatum=behandeldatum,
                        eartag_short=current_eartag_short,
                        notities=current_notities,
                    )
                )
            current_eartag_short = line
            current_notities = []
            continue

        if current_eartag_short is not None:
            current_notities.append(line)

    if current_eartag_short is not None:
        records.append(
            KlauwscorePdfRecord(
                behandeldatum=behandeldatum,
                eartag_short=current_eartag_short,
                notities=current_notities,
            )
        )

    return records


def parse_klauwscore_pdf(pdf_path: str | Path) -> list[KlauwscorePdfRecord]:
    """Parse a klauwscore PDF into one record per cow."""
    return parse_klauwscore_pdf_text(extract_pdf_text(pdf_path))


def parse_klauwscore_pdf_bytes(pdf_bytes: bytes) -> list[KlauwscorePdfRecord]:
    """Parse a klauwscore PDF from bytes into one record per cow."""
    return parse_klauwscore_pdf_text(extract_pdf_text_from_bytes(pdf_bytes))


def flatten_records(records: Iterable[KlauwscorePdfRecord]) -> list[dict[str, object]]:
    """Convert grouped cow records to one database row per notitie."""
    rows: list[dict[str, object]] = []
    for record in records:
        for notatie in record.notities:
            rows.append(
                {
                    "behandeldatum": record.behandeldatum,
                    "eartag_short": record.eartag_short,
                    "notatie": notatie,
                }
            )
    return rows


def records_to_json(records: Iterable[KlauwscorePdfRecord]) -> str:
    """Serialize parsed records for CLI output."""
    data = []
    for record in records:
        item = asdict(record)
        item["behandeldatum"] = record.behandeldatum.isoformat()
        data.append(item)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _should_skip_line(line: str) -> bool:
    return (
        not line
        or line.startswith("Registratie van")
        or FOOTER_PATTERN.match(line) is not None
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse klauwscore PDF exports.")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Output one row per notitie instead of one row per cow.",
    )
    args = parser.parse_args()

    records = parse_klauwscore_pdf(args.pdf_path)
    if args.flat:
        rows = flatten_records(records)
        data = [
            {
                **row,
                "behandeldatum": row["behandeldatum"].isoformat(),
            }
            for row in rows
        ]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(records_to_json(records))


if __name__ == "__main__":
    main()
