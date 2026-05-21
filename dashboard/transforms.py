"""Transformatie functies voor klauwbehandeling data."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ParsedNotatie:
    """Parsed klauwbehandeling notatie."""

    positie_code: str
    positie_volledig: str
    zijde: Optional[str]
    poot: Optional[str]
    probleem: str
    originele_tekst: str
    is_mortellaro: bool
    is_vierkant: bool


POSITIE_PATTERNS = {
    "LV": (r"^links\s*voor\b", "Linksvoor", "Links", "Voor"),
    "RV": (r"^rechts\s*voor\b", "Rechtsvoor", "Rechts", "Voor"),
    "LA": (r"^links\s*achter\b", "Linksachter", "Links", "Achter"),
    "RA": (r"^rechts\s*achter\b", "Rechtsachter", "Rechts", "Achter"),
}

POSITION_ORDER = {
    "LV": 1,
    "RV": 2,
    "LA": 3,
    "RA": 4,
    "Geen": 5,
    "Onbekend": 6,
}

PROBLEEM_CATEGORIES = {
    "Infecties": ["Mortellaro", "Mortelaro", "Stinkpoot", "Tussenklauwontsteking"],
    "Structurele problemen": [
        "Wittelijndefect",
        "Zoolzweer",
        "Chronisch bevangen",
        "Klos",
    ],
    "Tumoren": ["Tyloom"],
    "Behandelingen": ["Bont", "Verband", "Vierkant"],
}


def parse_notatie(notatie: Optional[str]) -> ParsedNotatie:
    """Parse klauwbehandeling notatie naar gestructureerde velden."""
    if not notatie or not notatie.strip():
        return ParsedNotatie(
            "Geen", "Geen", None, None, "", notatie or "", False, False
        )

    notatie_normalized = " ".join(notatie.strip().split())
    positie_code = "Geen"
    positie_volledig = "Geen"
    zijde = None
    poot = None
    probleem = notatie_normalized

    for code, (
        pattern,
        volledig,
        parsed_zijde,
        parsed_poot,
    ) in POSITIE_PATTERNS.items():
        match = re.match(pattern, notatie_normalized, re.IGNORECASE)
        if not match:
            continue

        positie_code = code
        positie_volledig = volledig
        zijde = parsed_zijde
        poot = parsed_poot
        probleem = notatie_normalized[match.end() :].strip()
        break

    if not probleem:
        probleem = notatie_normalized

    is_mortellaro = _is_mortellaro_text(probleem)
    is_vierkant = _normalize_text(probleem) == "vierkant"

    return ParsedNotatie(
        positie_code=positie_code,
        positie_volledig=positie_volledig,
        zijde=zijde,
        poot=poot,
        probleem=probleem,
        originele_tekst=notatie_normalized,
        is_mortellaro=is_mortellaro,
        is_vierkant=is_vierkant,
    )


def get_probleem_categorie(probleem: str) -> str:
    """Geef de categorie van een probleem."""
    normalized_problem = _normalize_text(probleem)
    for categorie, problemen in PROBLEEM_CATEGORIES.items():
        if any(_normalize_text(item) in normalized_problem for item in problemen):
            return categorie

    return "Overig"


def get_position_sort_key(positie_code: Optional[str]) -> int:
    """Geef een stabiele sorteervolgorde voor pootposities."""
    return POSITION_ORDER.get(positie_code or "Onbekend", POSITION_ORDER["Onbekend"])


def build_mortellaro_case_key(row: dict[str, object]) -> Optional[tuple[str, str]]:
    """Bouw de case key voor een Mortellaro-notitie."""
    parsed_row = _ensure_parsed_fields(row)
    if not parsed_row["is_mortellaro"]:
        return None

    positie_code = parsed_row["positie_code"]
    if positie_code in {"Geen", "Onbekend", None}:
        return None

    animal_identifier = parsed_row.get("animal_id") or parsed_row.get("eartag_short")
    if animal_identifier is None:
        animal_identifier = parsed_row.get("halsbandnummer") or parsed_row.get(
            "collar_number"
        )

    if animal_identifier is None:
        return None

    return str(animal_identifier), str(positie_code)


def add_mortellaro_case_columns(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Voeg nieuwe/herhaalde Mortellaro-casevelden toe aan notitierijen."""
    enriched_rows = []
    for index, row in enumerate(rows):
        enriched_row = _ensure_parsed_fields(row)
        enriched_row["_original_index"] = index
        enriched_row["positie_sort_key"] = get_position_sort_key(
            _optional_str(enriched_row.get("positie_code"))
        )
        enriched_row["mortellaro_case_key"] = build_mortellaro_case_key(enriched_row)
        enriched_row["nieuwe_case"] = False
        enriched_row["herhaalde_case"] = False
        enriched_row["eerste_datum"] = None
        enriched_row["vorige_mortellaro_datum"] = None
        enriched_row["dagen_sinds_vorige"] = None
        enriched_row["dagen_sinds_eerste"] = None
        enriched_row["herhaling_nummer"] = None
        enriched_rows.append(enriched_row)

    case_rows = [row for row in enriched_rows if row["mortellaro_case_key"] is not None]
    case_rows.sort(
        key=lambda row: (
            row["mortellaro_case_key"],
            _parse_date(row.get("behandeldatum")) or date.min,
            row["_original_index"],
        )
    )

    case_state: dict[tuple[str, str], dict[str, object]] = {}
    for row in case_rows:
        case_key = row["mortellaro_case_key"]
        behandeldatum = _parse_date(row.get("behandeldatum"))
        state = case_state.get(case_key)

        if state is None:
            row["nieuwe_case"] = True
            row["herhaalde_case"] = False
            row["eerste_datum"] = behandeldatum
            row["vorige_mortellaro_datum"] = None
            row["dagen_sinds_vorige"] = None
            row["dagen_sinds_eerste"] = 0 if behandeldatum is not None else None
            row["herhaling_nummer"] = 0
            case_state[case_key] = {
                "eerste_datum": behandeldatum,
                "vorige_datum": behandeldatum,
                "herhaling_nummer": 0,
            }
            continue

        eerste_datum = state["eerste_datum"]
        vorige_datum = state["vorige_datum"]
        herhaling_nummer = int(state["herhaling_nummer"]) + 1
        row["nieuwe_case"] = False
        row["herhaalde_case"] = True
        row["eerste_datum"] = eerste_datum
        row["vorige_mortellaro_datum"] = vorige_datum
        row["dagen_sinds_vorige"] = _days_between(vorige_datum, behandeldatum)
        row["dagen_sinds_eerste"] = _days_between(eerste_datum, behandeldatum)
        row["herhaling_nummer"] = herhaling_nummer
        state["vorige_datum"] = behandeldatum
        state["herhaling_nummer"] = herhaling_nummer

    return [_strip_private_columns(row) for row in enriched_rows]


def build_mortellaro_followup_status(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Bouw een opvolgstatus per Mortellaro-case."""
    case_rows = add_mortellaro_case_columns(rows)
    rows_by_animal: dict[str, list[dict[str, object]]] = {}
    latest_by_case: dict[tuple[str, str], dict[str, object]] = {}

    for row in case_rows:
        animal_identifier = _animal_identifier(row)
        if animal_identifier is not None:
            rows_by_animal.setdefault(animal_identifier, []).append(row)

        case_key = row.get("mortellaro_case_key")
        if case_key is None:
            continue

        latest_row = latest_by_case.get(case_key)
        row_date = _parse_date(row.get("behandeldatum"))
        latest_date = (
            _parse_date(latest_row.get("behandeldatum")) if latest_row else None
        )
        if latest_row is None or (row_date or date.min) >= (latest_date or date.min):
            latest_by_case[case_key] = row

    for animal_rows in rows_by_animal.values():
        animal_rows.sort(
            key=lambda row: _parse_date(row.get("behandeldatum")) or date.min
        )

    followup_rows = []
    for case_key, latest_row in latest_by_case.items():
        animal_identifier, positie_code = case_key
        laatste_mortellaro_datum = _parse_date(latest_row.get("behandeldatum"))
        latere_notities = [
            row
            for row in rows_by_animal.get(animal_identifier, [])
            if (_parse_date(row.get("behandeldatum")) or date.min)
            > (laatste_mortellaro_datum or date.max)
        ]

        status = "Open/onbekend"
        opgelost_op = None
        volgende_inspectie = None
        for latere_notitie in latere_notities:
            volgende_inspectie = _parse_date(latere_notitie.get("behandeldatum"))
            latere_case_key = latere_notitie.get("mortellaro_case_key")
            if latere_case_key == case_key:
                status = "Actief/herhaald"
                break

            if latere_notitie.get("is_vierkant"):
                status = "Opgelost"
                opgelost_op = volgende_inspectie
                break

            status = "Onzeker"
            break

        followup_rows.append(
            {
                "mortellaro_case_key": case_key,
                "animal_id": latest_row.get("animal_id"),
                "eartag_short": latest_row.get("eartag_short")
                or latest_row.get("halsbandnummer"),
                "halsbandnummer": latest_row.get("collar_number"),
                "name": latest_row.get("name"),
                "positie_code": positie_code,
                "positie": latest_row.get("positie"),
                "eerste_datum": latest_row.get("eerste_datum"),
                "laatste_mortellaro_datum": laatste_mortellaro_datum,
                "herhaling_nummer": latest_row.get("herhaling_nummer"),
                "opvolgstatus": status,
                "volgende_inspectie": volgende_inspectie,
                "opgelost_op": opgelost_op,
            }
        )

    return sorted(
        followup_rows,
        key=lambda row: (
            str(row.get("animal_id") or ""),
            get_position_sort_key(_optional_str(row.get("positie_code"))),
        ),
    )


def _ensure_parsed_fields(row: dict[str, object]) -> dict[str, object]:
    copied_row = dict(row)
    parsed = parse_notatie(_optional_str(copied_row.get("notatie")))
    copied_row.setdefault("positie_code", parsed.positie_code)
    copied_row.setdefault("positie", parsed.positie_volledig)
    copied_row.setdefault("zijde", parsed.zijde)
    copied_row.setdefault("poot", parsed.poot)
    copied_row.setdefault("probleem", parsed.probleem)
    copied_row.setdefault("categorie", get_probleem_categorie(parsed.probleem))
    copied_row.setdefault("is_mortellaro", parsed.is_mortellaro)
    copied_row.setdefault("is_vierkant", parsed.is_vierkant)
    return copied_row


def _is_mortellaro_text(value: str) -> bool:
    return re.search(r"\bmortel{1,2}aro\b", _normalize_text(value)) is not None


def _normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""

    return " ".join(str(value).strip().lower().split())


def _parse_date(value: object) -> Optional[date]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return datetime.fromisoformat(value[:10]).date()

    return None


def _days_between(start: object, end: object) -> Optional[int]:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date is None or end_date is None:
        return None

    return (end_date - start_date).days


def _animal_identifier(row: dict[str, object]) -> Optional[str]:
    identifier = (
        row.get("animal_id")
        or row.get("eartag_short")
        or row.get("halsbandnummer")
        or row.get("collar_number")
    )
    if identifier is None:
        return None

    return str(identifier)


def _optional_str(value: object) -> Optional[str]:
    if value is None:
        return None

    return str(value)


def _strip_private_columns(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if not key.startswith("_")}
