"""Load lay curve norms from a CSV seed file into the database.

Idempotent: existing rows (matched on breed_key + age_weeks) are updated;
new rows are inserted. Safe to run multiple times.

Usage:
    python -m database.seeds.load_lay_curve_norms
    python -m database.seeds.load_lay_curve_norms --csv path/to/other.csv
    python -m database.seeds.load_lay_curve_norms --dry-run
"""

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

from database import database
from database.repositories.laying_hens_repository import FlockLayCurveNormsRepository

_DEFAULT_CSV = Path(__file__).parent / "dekalb_white_norms.csv"

_INT_FIELDS = {"age_weeks", "hen_weight_grams"}
_DECIMAL_FIELDS = {
    "lay_percentage",
    "egg_weight_grams",
    "egg_mass_grams",
    "feed_intake_grams_per_day",
    "feed_conversion_ratio",
    "liveability_percentage",
    "cumulative_eggs_per_placed_hen",
    "cumulative_egg_kg_per_placed_hen",
    "cumulative_feed_kg_per_placed_hen",
    "cumulative_feed_conversion_ratio",
}


def _parse_row(row: dict[str, str]) -> dict:
    parsed: dict = {}
    for key, raw in row.items():
        key = key.strip()
        raw = raw.strip()
        if key in _INT_FIELDS:
            parsed[key] = int(raw) if raw else None
        elif key in _DECIMAL_FIELDS:
            parsed[key] = Decimal(raw) if raw else Decimal("0")
        else:
            parsed[key] = raw
    return parsed


def load_norms_with_repo(
    csv_path: Path,
    repo: FlockLayCurveNormsRepository,
    *,
    dry_run: bool = False,
) -> int:
    """Load norms from csv_path using the given repo. Returns rows upserted."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [_parse_row(row) for row in reader]

    if not rows:
        print("No rows found in CSV.")
        return 0

    if dry_run:
        first, last = rows[0], rows[-1]
        print(f"[dry-run] Would upsert {len(rows)} rows from {csv_path.name}.")
        print(f"  breed_key : {first['breed_key']}")
        print(f"  age_weeks : {first['age_weeks']} – {last['age_weeks']}")
        return len(rows)

    for row in rows:
        repo.upsert_norm(row)

    print(
        f"Upserted {len(rows)} rows for breed_key="
        f"'{rows[0]['breed_key']}' (weeks {rows[0]['age_weeks']}–{rows[-1]['age_weeks']})."
    )
    return len(rows)


def load_norms(csv_path: Path, *, dry_run: bool = False) -> int:
    """Load norms from csv_path using the production database session."""
    repo = FlockLayCurveNormsRepository(database.get_session)
    return load_norms_with_repo(csv_path, repo, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load lay curve norms from CSV.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=_DEFAULT_CSV,
        help="Path to the CSV seed file (default: dekalb_white_norms.csv).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be loaded without writing to the database.",
    )
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        return 1

    load_norms(args.csv, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
