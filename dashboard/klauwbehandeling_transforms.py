"""Compatibility helpers for older klauwbehandeling dashboard tests."""

from typing import Optional

import pandas as pd

from dashboard import transforms

FOLLOWUP_NO_NEXT_VISIT = "Geen volgend bezoek"
FOLLOWUP_REPEATED = "Herhaald"
FOLLOWUP_RESOLVED = "Opgelost"
FOLLOWUP_UNKNOWN = "Onzeker"


def classify_notatie(notatie: Optional[str]) -> dict[str, object]:
    """Classify a hoof-treatment note into the legacy dashboard shape."""
    parsed = transforms.parse_notatie(notatie)
    category = _legacy_category(parsed.probleem, parsed.is_mortellaro)
    severity, severity_score = _legacy_severity(parsed.probleem, parsed.is_mortellaro)
    return {
        "is_mortellaro": parsed.is_mortellaro,
        "positie": (
            "Onbekende positie"
            if parsed.positie_volledig == "Geen"
            else parsed.positie_volledig
        ),
        "zijde": parsed.zijde,
        "poot": parsed.poot,
        "diagnose_tekst": parsed.probleem,
        "probleem": "Mortellaro" if parsed.is_mortellaro else parsed.probleem,
        "categorie": category,
        "ernst": severity,
        "ernst_score": severity_score,
    }


def add_mortellaro_case_columns(klauw_df: pd.DataFrame) -> pd.DataFrame:
    """Add legacy Mortellaro case columns to a DataFrame."""
    if klauw_df.empty:
        return klauw_df.copy()

    rows = transforms.add_mortellaro_case_columns(
        klauw_df.to_dict(orient="records"),
    )
    result_df = pd.DataFrame(rows)
    if "vorige_mortellaro_datum" in result_df.columns:
        result_df["vorige_datum"] = result_df["vorige_mortellaro_datum"]

    return result_df


def summarize_mortellaro_cases(klauw_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize follow-up status for legacy Mortellaro case reports."""
    if klauw_df.empty:
        return pd.DataFrame()

    case_df = add_mortellaro_case_columns(klauw_df)
    case_rows = case_df.to_dict(orient="records")
    mortellaro_rows = [
        row for row in case_rows if row.get("mortellaro_case_key") is not None
    ]
    latest_rows = _latest_rows_by_case(mortellaro_rows)
    rows_by_animal = _rows_by_animal(case_rows)

    summaries = []
    for case_key, latest_row in latest_rows.items():
        animal_identifier, _position = case_key
        latest_date = latest_row.get("behandeldatum")
        later_rows = [
            row
            for row in rows_by_animal.get(str(animal_identifier), [])
            if row.get("behandeldatum") > latest_date
        ]
        if int(latest_row.get("herhaling_nummer") or 0) > 0:
            status = FOLLOWUP_REPEATED
            next_row = latest_row
        else:
            status, next_row = _followup_status(case_key, later_rows)
        summaries.append(
            {
                "mortellaro_case_key": case_key,
                "animal_id": latest_row.get("animal_id"),
                "halsbandnummer": latest_row.get("halsbandnummer"),
                "positie": latest_row.get("positie"),
                "eerste_datum": latest_row.get("eerste_datum"),
                "laatste_mortellaro_datum": latest_date,
                "herhaling_nummer": latest_row.get("herhaling_nummer"),
                "opvolgstatus": status,
                "volgende_bezoekdatum": (
                    None if next_row is None else next_row.get("behandeldatum")
                ),
                "dagen_tot_volgend_bezoek": _days_between(
                    latest_date,
                    None if next_row is None else next_row.get("behandeldatum"),
                ),
                "volgende_bezoek_notities": (
                    None if next_row is None else next_row.get("notatie")
                ),
            }
        )

    return pd.DataFrame(summaries)


def _legacy_category(probleem: str, is_mortellaro: bool) -> str:
    if is_mortellaro:
        return "Diagnose"
    if transforms.get_probleem_categorie(probleem) == "Overig":
        return "Overig / onbekend"
    if probleem:
        return "Behandeling / actie"
    return "Diagnose"


def _legacy_severity(probleem: str, is_mortellaro: bool) -> tuple[str, int]:
    if is_mortellaro:
        return "Hoog", 3
    if probleem:
        return "Actie", 0
    return "Onbekend", 0


def _latest_rows_by_case(
    mortellaro_rows: list[dict[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    latest_rows = {}
    for row in mortellaro_rows:
        case_key = row["mortellaro_case_key"]
        current = latest_rows.get(case_key)
        if current is None or row.get("behandeldatum") >= current.get("behandeldatum"):
            latest_rows[case_key] = row

    return latest_rows


def _rows_by_animal(
    rows: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    grouped_rows = {}
    for row in rows:
        identifier = row.get("animal_id") or row.get("halsbandnummer")
        if identifier is None:
            continue
        grouped_rows.setdefault(str(identifier), []).append(row)

    for animal_rows in grouped_rows.values():
        animal_rows.sort(key=lambda row: row.get("behandeldatum"))

    return grouped_rows


def _followup_status(
    case_key: tuple[str, str],
    later_rows: list[dict[str, object]],
) -> tuple[str, Optional[dict[str, object]]]:
    repeated_rows = [
        row
        for row in later_rows
        if row.get("mortellaro_case_key") == case_key
        and int(row.get("herhaling_nummer") or 0) > 0
    ]
    if repeated_rows:
        return FOLLOWUP_REPEATED, repeated_rows[0]

    if not later_rows:
        return FOLLOWUP_NO_NEXT_VISIT, None

    for row in later_rows:
        if row.get("mortellaro_case_key") == case_key:
            return FOLLOWUP_REPEATED, row
        if row.get("is_vierkant"):
            return FOLLOWUP_RESOLVED, row
        return FOLLOWUP_UNKNOWN, row

    return FOLLOWUP_NO_NEXT_VISIT, None


def _days_between(start: object, end: object) -> Optional[int]:
    if start is None or end is None:
        return None
    return (end - start).days
