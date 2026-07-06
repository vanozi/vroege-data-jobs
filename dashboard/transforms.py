"""Transformatie functies voor klauwbehandeling data."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    is_aandoening: bool
    is_behandeling: bool


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

AANDOENINGEN = {
    "mortellaro",
    "mortelaro",
    "tussenklauwontsteking",
    "zoolzweer",
    "wittelijndefect",
    "tyloom",
    "stinkpoot",
    "bont",
    "chronisch bevangen",
}

BEHANDELINGEN = {
    "verband",
    "klos",
    "vierkant",
}

HERCONTROLE_DAGEN = 84
PREVENTIEF_DAGEN = 183
MIN_DIM_PREVENTIEF = 50

UNIFORM_AGRI_POSITION_CODES = {
    "RV": "1",
    "LV": "3",
    "RA": "5",
    "LA": "7",
}

UNIFORM_AGRI_CONDITION_CODES = {
    "mortellaro": "D",
    "mortelaro": "D",
    "tussenklauwontsteking": "I",
    "zoolzweer": "U",
    "wittelijndefect": "W",
    "tyloom": "K",
    "stinkpoot": "F",
    "bont": "H",
    "chronisch bevangen": "O",
}

UNIFORM_AGRI_ACTION_CODES = {
    "verband": "W",
    "klos": "B",
    "behandeling": "T",
}

UNIFORM_AGRI_TRIM_TYPE_CODES = {
    "vierkant": "R",
}

UNIFORM_AGRI_CSV_COLUMNS = [
    "animal no.",
    "date",
    "health conditions and location",
    "treatment",
]


def parse_notatie(notatie: Optional[str]) -> ParsedNotatie:
    """Parse klauwbehandeling notatie naar gestructureerde velden."""
    if not notatie or not notatie.strip():
        return ParsedNotatie(
            "Geen", "Geen", None, None, "", notatie or "", False, False, False, False
        )

    notatie_normalized = " ".join(notatie.strip().split())
    notatie_normalized = notatie_normalized.removeprefix("-").strip()
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
    normalized_problem = _normalize_text(probleem)
    is_aandoening = _matches_known_item(normalized_problem, AANDOENINGEN)
    is_behandeling = _matches_known_item(normalized_problem, BEHANDELINGEN)

    return ParsedNotatie(
        positie_code=positie_code,
        positie_volledig=positie_volledig,
        zijde=zijde,
        poot=poot,
        probleem=probleem,
        originele_tekst=notatie_normalized,
        is_mortellaro=is_mortellaro,
        is_vierkant=is_vierkant,
        is_aandoening=is_aandoening,
        is_behandeling=is_behandeling,
    )


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


def build_open_mortellaro_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Bouw tabelrijen voor koeien met Mortellaro zonder latere Vierkant."""
    rows_by_animal: dict[str, list[dict[str, object]]] = {}

    for row in rows:
        parsed_row = _ensure_parsed_fields(row)
        animal_identifier = _animal_identifier(parsed_row)
        if animal_identifier is None:
            continue

        rows_by_animal.setdefault(animal_identifier, []).append(parsed_row)

    for animal_rows in rows_by_animal.values():
        animal_rows.sort(
            key=lambda row: _parse_date(row.get("behandeldatum")) or date.min
        )

    open_rows = []
    for animal_rows in rows_by_animal.values():
        mortellaro_rows = [row for row in animal_rows if row.get("is_mortellaro")]
        if not mortellaro_rows:
            continue

        laatste_mortellaro_datum = max(
            _parse_date(row.get("behandeldatum")) or date.min for row in mortellaro_rows
        )
        if laatste_mortellaro_datum == date.min:
            continue

        behandelingen_na_mortellaro = [
            row
            for row in animal_rows
            if (_parse_date(row.get("behandeldatum")) or date.min)
            > laatste_mortellaro_datum
        ]

        if any(row.get("is_vierkant") for row in behandelingen_na_mortellaro):
            continue

        laatste_behandeling_na_mortellaro = None
        laatste_notatie_rows = [
            row
            for row in animal_rows
            if (_parse_date(row.get("behandeldatum")) or date.min)
            == laatste_mortellaro_datum
        ]
        if behandelingen_na_mortellaro:
            laatste_behandeling_na_mortellaro = max(
                _parse_date(row.get("behandeldatum")) or date.min
                for row in behandelingen_na_mortellaro
            )
            laatste_notatie_rows = [
                row
                for row in behandelingen_na_mortellaro
                if (_parse_date(row.get("behandeldatum")) or date.min)
                == laatste_behandeling_na_mortellaro
            ]

        latest_context_row = laatste_notatie_rows[0]
        open_rows.append(
            {
                "animal_id": latest_context_row.get("animal_id"),
                "Koe / naam": latest_context_row.get("name"),
                "Halsbandnummer": latest_context_row.get("collar_number"),
                "Oormerk kort": latest_context_row.get("eartag_short"),
                "Oormerk": latest_context_row.get("eartag"),
                "Laatste Mortellaro-datum": laatste_mortellaro_datum,
                "Laatste behandeling na Mortellaro": (
                    None
                    if laatste_behandeling_na_mortellaro is None
                    else laatste_behandeling_na_mortellaro
                ),
                "Laatste notatie(s)": ", ".join(
                    str(row.get("notatie"))
                    for row in laatste_notatie_rows
                    if row.get("notatie")
                ),
                "Voergroep": latest_context_row.get("feeding_group_name"),
            }
        )

    return sorted(
        open_rows,
        key=lambda row: (
            -(row.get("Laatste Mortellaro-datum") or date.min).toordinal(),
            str(row.get("Halsbandnummer") or ""),
        ),
    )


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


def is_droogstaand(row: dict[str, object]) -> bool:
    """Bepaal of een koe droog staat op basis van Uniform status."""
    return _normalize_text(_optional_str(row.get("status"))) == "droog"


def build_klauwbekap_protocol_rows(
    rows: list[dict[str, object]],
    *,
    reference_date: Optional[date] = None,
) -> list[dict[str, object]]:
    """Bouw protocolbeslissingen per actieve koe."""
    peildatum = reference_date or date.today()
    rows_by_animal = _rows_by_animal(rows)
    protocol_rows = []

    for animal_rows in rows_by_animal.values():
        context_row = _latest_context_row(animal_rows)
        treatment_date_groups = _treatment_date_groups(animal_rows)
        row = _build_base_protocol_row(context_row, peildatum)

        if not treatment_date_groups:
            protocol_rows.append(
                _classify_cow_without_treatments(row, context_row, peildatum)
            )
            continue

        latest_group = treatment_date_groups[-1]
        latest_treatment_date = latest_group["behandeldatum"]
        latest_notes = latest_group["notities"]
        last_healthy_date = _last_healthy_date(treatment_date_groups)
        last_condition_group = _last_condition_group(treatment_date_groups)
        last_mortellaro_group = _last_mortellaro_group(treatment_date_groups)

        row.update(
            {
                "Laatste klauwdatum": latest_treatment_date,
                "Laatste notatie(s)": ", ".join(latest_notes),
                "Laatste gezonde datum": last_healthy_date,
                "Dagen sinds laatste behandeling": _days_between(
                    latest_treatment_date,
                    peildatum,
                ),
            }
        )

        if _has_active_mortellaro(treatment_date_groups, last_mortellaro_group):
            row.update(
                {
                    "Aanbiedcategorie": "Actieve Mortellaro",
                    "Aanbiedreden": "Mortellaro direct opvolgen",
                    "Moet aangeboden worden": True,
                    "Volgende actiedatum": peildatum,
                    "Urgentie": 1,
                }
            )
            protocol_rows.append(row)
            continue

        active_condition_group = _active_non_mortellaro_condition_group(
            treatment_date_groups,
            last_condition_group,
        )
        if active_condition_group is not None:
            protocol_rows.append(
                _classify_active_condition(row, active_condition_group, peildatum)
            )
            continue

        protocol_rows.append(
            _classify_preventive_status(row, context_row, last_healthy_date, peildatum)
        )

    return sorted(
        protocol_rows,
        key=lambda row: (
            int(row.get("Urgentie") or 99),
            row.get("Volgende actiedatum") or date.max,
            str(row.get("Halsbandnummer") or ""),
        ),
    )


def format_uniform_agri_date(value: object) -> str:
    """Format a date for Uniform Agri Hoof Supervisor CSV import."""
    parsed_date = _parse_date(value)
    if parsed_date is None:
        return ""

    return parsed_date.strftime("%d/%m/%Y")


def parse_uniform_agri_export_row(row: dict[str, object]) -> dict[str, object]:
    """Transform one klauwbehandeling row to a Uniform Agri control row."""
    parsed_row = _ensure_parsed_fields(row)
    parsed = parse_notatie(_optional_str(parsed_row.get("notatie")))
    behandeldatum = _parse_date(parsed_row.get("behandeldatum"))
    animal_no = _optional_str(parsed_row.get("collar_number"))
    normalized_problem = _normalize_text(parsed.probleem)
    position_code = UNIFORM_AGRI_POSITION_CODES.get(parsed.positie_code)
    condition_code = _lookup_uniform_agri_code(
        normalized_problem,
        UNIFORM_AGRI_CONDITION_CODES,
    )
    action_code = _lookup_uniform_agri_code(
        normalized_problem,
        UNIFORM_AGRI_ACTION_CODES,
    )
    trim_type_code = _lookup_uniform_agri_code(
        normalized_problem,
        UNIFORM_AGRI_TRIM_TYPE_CODES,
    )
    health_conditions_location = ""
    treatment = ""

    validation_messages = []
    validation_status = "ok"

    if parsed_row.get("animal_id") is None:
        validation_messages.append("Geen gekoppelde koe")

    if (
        parsed_row.get("animal_id") is not None
        and "koe_animal_id" in parsed_row
        and parsed_row.get("koe_animal_id") is None
    ):
        validation_messages.append("Gekoppelde koe niet gevonden in koeien")

    if (
        "in_current_herd" in parsed_row
        and parsed_row.get("in_current_herd") is not True
    ):
        validation_messages.append("Koe is niet onderdeel van de huidige kudde")

    if not animal_no:
        validation_messages.append("Geen werknummer/collar_number voor animal no.")

    if behandeldatum is None:
        validation_messages.append("Geen behandeldatum")

    if condition_code:
        if position_code:
            health_conditions_location = f"{condition_code}{position_code}"
        else:
            validation_messages.append("Geen pootpositie voor condition")

    if action_code:
        treatment = action_code

    if trim_type_code:
        treatment = f"{treatment}{trim_type_code}"

    has_known_mapping = bool(condition_code or action_code or trim_type_code)
    if not has_known_mapping:
        validation_messages.append("Onbekende of niet vertaalbare notatie")

    if validation_messages:
        validation_status = "error"

    return {
        **parsed_row,
        "behandeling_id": parsed_row.get("behandeling_id") or parsed_row.get("id"),
        "animal_no": animal_no,
        "animal_no_source": "koeien.collar_number",
        "date": format_uniform_agri_date(behandeldatum),
        "health_conditions_location": health_conditions_location,
        "treatment": treatment,
        "uniform_position_code": position_code,
        "condition_code": condition_code,
        "action_code": action_code,
        "trim_type_code": trim_type_code,
        "notatie": parsed_row.get("notatie"),
        "eartag": parsed_row.get("eartag"),
        "eartag_short": parsed_row.get("eartag_short"),
        "cow_name": parsed_row.get("name") or parsed_row.get("cow_name"),
        "validation_status": validation_status,
        "validation_message": "; ".join(validation_messages),
        "exportable": not validation_messages,
    }


def build_uniform_agri_export_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Transform klauwbehandeling rows to Uniform Agri control rows."""
    return [parse_uniform_agri_export_row(row) for row in rows]


def build_uniform_agri_csv_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Group Uniform Agri control rows into CSV-shaped rows per cow/date."""
    export_rows = build_uniform_agri_export_rows(rows)
    grouped_rows: dict[tuple[str, date], dict[str, object]] = {}

    for index, row in enumerate(export_rows):
        behandeldatum = _parse_date(row.get("behandeldatum"))
        animal_no = _optional_str(row.get("animal_no"))
        if animal_no is None or behandeldatum is None:
            continue

        key = (animal_no, behandeldatum)
        group = grouped_rows.setdefault(
            key,
            {
                "animal_no": animal_no,
                "date": row["date"],
                "health_conditions_location": "",
                "treatment": "",
                "behandeldatum": behandeldatum,
                "behandeling_ids": [],
                "notities": [],
                "row_count": 0,
                "exportable": True,
                "validation_status": "ok",
                "validation_message": "",
                "_first_index": index,
            },
        )
        group["health_conditions_location"] = (
            f"{group['health_conditions_location']}{row['health_conditions_location']}"
        )
        group["treatment"] = f"{group['treatment']}{row['treatment']}"
        group["row_count"] = int(group["row_count"]) + 1
        group["exportable"] = bool(group["exportable"]) and bool(row["exportable"])

        behandeling_id = row.get("behandeling_id")
        if behandeling_id is not None:
            group["behandeling_ids"].append(behandeling_id)

        notatie = row.get("notatie")
        if notatie:
            group["notities"].append(notatie)

        if row["validation_message"]:
            messages = [
                message
                for message in str(group["validation_message"]).split("; ")
                if message
            ]
            messages.append(str(row["validation_message"]))
            group["validation_message"] = "; ".join(messages)
            group["validation_status"] = "error"

    return [
        _format_uniform_agri_grouped_row(row)
        for row in sorted(
            grouped_rows.values(),
            key=lambda item: (
                item["behandeldatum"],
                item["animal_no"],
                item["_first_index"],
            ),
        )
    ]


def build_uniform_agri_csv_download_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, str]]:
    """Return only the four CSV columns for exportable grouped rows."""
    csv_rows = []
    for row in build_uniform_agri_csv_rows(rows):
        if not row["exportable"]:
            continue

        csv_rows.append(
            {
                "animal no.": str(row["animal_no"]),
                "date": str(row["date"]),
                "health conditions and location": str(
                    row["health_conditions_location"]
                ),
                "treatment": str(row["treatment"]),
            }
        )

    return csv_rows


def _ensure_parsed_fields(row: dict[str, object]) -> dict[str, object]:
    copied_row = dict(row)
    parsed = parse_notatie(_optional_str(copied_row.get("notatie")))
    copied_row.setdefault("positie_code", parsed.positie_code)
    copied_row.setdefault("positie", parsed.positie_volledig)
    copied_row.setdefault("zijde", parsed.zijde)
    copied_row.setdefault("poot", parsed.poot)
    copied_row.setdefault("probleem", parsed.probleem)
    copied_row.setdefault("is_mortellaro", parsed.is_mortellaro)
    copied_row.setdefault("is_vierkant", parsed.is_vierkant)
    copied_row.setdefault("is_aandoening", parsed.is_aandoening)
    copied_row.setdefault("is_behandeling", parsed.is_behandeling)
    return copied_row


def _rows_by_animal(
    rows: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    rows_by_animal: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        animal_identifier = _animal_identifier(row)
        if animal_identifier is None:
            continue

        rows_by_animal.setdefault(animal_identifier, []).append(
            _ensure_parsed_fields(row)
        )

    return rows_by_animal


def _latest_context_row(rows: list[dict[str, object]]) -> dict[str, object]:
    sorted_rows = sorted(
        rows,
        key=lambda row: _parse_date(row.get("behandeldatum")) or date.min,
        reverse=True,
    )
    for row in sorted_rows:
        if row.get("name") or row.get("collar_number") or row.get("eartag_short"):
            return row

    return sorted_rows[0] if sorted_rows else {}


def _treatment_date_groups(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    groups_by_date: dict[date, list[dict[str, object]]] = {}
    for row in rows:
        if row.get("behandeling_id") is None and row.get("notatie") is None:
            continue

        treated_on = _parse_date(row.get("behandeldatum"))
        if treated_on is None:
            continue

        groups_by_date.setdefault(treated_on, []).append(row)

    groups = []
    for treated_on, group_rows in groups_by_date.items():
        note_rows = [row for row in group_rows if row.get("notatie")]
        notes = [str(row.get("notatie")) for row in note_rows if row.get("notatie")]
        has_mortellaro = any(row.get("is_mortellaro") for row in note_rows)
        has_condition = any(row.get("is_aandoening") for row in note_rows)
        has_other_condition = any(
            row.get("is_aandoening") and not row.get("is_mortellaro")
            for row in note_rows
        )
        has_vierkant = any(row.get("is_vierkant") for row in note_rows)
        groups.append(
            {
                "behandeldatum": treated_on,
                "rows": note_rows,
                "notities": notes,
                "has_mortellaro": has_mortellaro,
                "has_condition": has_condition,
                "has_other_condition": has_other_condition,
                "has_vierkant": has_vierkant,
                "is_healthy": has_vierkant and not has_condition,
            }
        )

    return sorted(groups, key=lambda group: group["behandeldatum"])


def _build_base_protocol_row(
    context_row: dict[str, object],
    peildatum: date,
) -> dict[str, object]:
    return {
        "Peildatum": peildatum,
        "animal_id": context_row.get("animal_id"),
        "Koe / naam": context_row.get("name"),
        "Halsbandnummer": context_row.get("collar_number"),
        "Oormerk kort": context_row.get("eartag_short"),
        "Oormerk": context_row.get("eartag"),
        "DIM": context_row.get("current_dim"),
        "Laatste melk": context_row.get("last_milk"),
        "Lactatie": context_row.get("lactation_number"),
        "Voergroep nummer": _parse_optional_int(
            context_row.get("feeding_group_number")
        ),
        "Voergroep naam": context_row.get("feeding_group_name") or "Onbekend",
        "Status": context_row.get("status") or "Onbekend",
        "Status dagen": context_row.get("status_days"),
        "Laatste klauwdatum": None,
        "Laatste notatie(s)": "",
        "Laatste gezonde datum": None,
        "Dagen sinds laatste behandeling": None,
        "Volgende actiedatum": None,
        "Aanbiedcategorie": "Geen actie",
        "Aanbiedreden": "Geen actie volgens protocol",
        "Moet aangeboden worden": False,
        "Urgentie": 50,
    }


def _parse_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify_cow_without_treatments(
    row: dict[str, object],
    context_row: dict[str, object],
    peildatum: date,
) -> dict[str, object]:
    if bool(context_row.get("is_young_stock")):
        row.update(
            {
                "Aanbiedcategorie": "Onvoldoende data",
                "Aanbiedreden": "Jongvee zonder klauwdata",
                "Urgentie": 90,
            }
        )
        return row

    current_dim = _optional_int(context_row.get("current_dim"))
    if current_dim is None:
        row.update(
            {
                "Aanbiedcategorie": "Onvoldoende data",
                "Aanbiedreden": "Geen klauwdata en DIM ontbreekt",
                "Urgentie": 90,
            }
        )
        return row

    if is_droogstaand(context_row):
        row.update(
            {
                "Aanbiedcategorie": "Tijdelijk niet aanbieden",
                "Aanbiedreden": "Geen klauwdata, maar koe staat droog",
                "Urgentie": 60,
            }
        )
        return row

    if current_dim < MIN_DIM_PREVENTIEF:
        row.update(
            {
                "Aanbiedcategorie": "Tijdelijk niet aanbieden",
                "Aanbiedreden": f"Geen klauwdata; preventief vanaf {MIN_DIM_PREVENTIEF} DIM",
                "Volgende actiedatum": peildatum
                + timedelta(days=MIN_DIM_PREVENTIEF - current_dim),
                "Urgentie": 60,
            }
        )
        return row

    row.update(
        {
            "Aanbiedcategorie": "Eerste bekapping",
            "Aanbiedreden": "Geen klauwdata en koe voldoet aan eerste-bekapping criteria",
            "Moet aangeboden worden": True,
            "Volgende actiedatum": peildatum,
            "Urgentie": 3,
        }
    )
    return row


def _last_healthy_date(groups: list[dict[str, object]]) -> Optional[date]:
    for group in reversed(groups):
        if group["is_healthy"]:
            return group["behandeldatum"]

    return None


def _last_condition_group(
    groups: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    for group in reversed(groups):
        if group["has_condition"]:
            return group

    return None


def _last_mortellaro_group(
    groups: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    for group in reversed(groups):
        if group["has_mortellaro"]:
            return group

    return None


def _has_active_mortellaro(
    groups: list[dict[str, object]],
    last_mortellaro_group: Optional[dict[str, object]],
) -> bool:
    if last_mortellaro_group is None:
        return False

    last_mortellaro_date = last_mortellaro_group["behandeldatum"]
    later_groups = [
        group for group in groups if group["behandeldatum"] > last_mortellaro_date
    ]
    return not any(not group["has_mortellaro"] for group in later_groups)


def _active_non_mortellaro_condition_group(
    groups: list[dict[str, object]],
    last_condition_group: Optional[dict[str, object]],
) -> Optional[dict[str, object]]:
    if last_condition_group is None or not last_condition_group["has_other_condition"]:
        return None

    last_condition_date = last_condition_group["behandeldatum"]
    later_groups = [
        group for group in groups if group["behandeldatum"] > last_condition_date
    ]
    if any(not group["has_condition"] for group in later_groups):
        return None

    return last_condition_group


def _classify_active_condition(
    row: dict[str, object],
    active_condition_group: dict[str, object],
    peildatum: date,
) -> dict[str, object]:
    condition_date = active_condition_group["behandeldatum"]
    due_date = condition_date + timedelta(days=HERCONTROLE_DAGEN)
    condition_names = _condition_names(active_condition_group)
    if peildatum >= due_date:
        row.update(
            {
                "Aanbiedcategorie": "Hercontrole aandoening",
                "Aanbiedreden": (
                    f"Hercontrole na 12 weken voor {', '.join(condition_names)}"
                ),
                "Moet aangeboden worden": True,
                "Volgende actiedatum": due_date,
                "Urgentie": 2,
            }
        )
        return row

    row.update(
        {
            "Aanbiedcategorie": "Tijdelijk niet aanbieden",
            "Aanbiedreden": (
                f"Hercontrole voor {', '.join(condition_names)} vanaf {due_date}"
            ),
            "Volgende actiedatum": due_date,
            "Urgentie": 60,
        }
    )
    return row


def _condition_names(group: dict[str, object]) -> list[str]:
    names = []
    for row in group["rows"]:
        if row.get("is_aandoening") and not row.get("is_mortellaro"):
            problem = _optional_str(row.get("probleem"))
            if problem:
                names.append(problem)

    return sorted(set(names)) or ["aandoening"]


def _classify_preventive_status(
    row: dict[str, object],
    context_row: dict[str, object],
    last_healthy_date: Optional[date],
    peildatum: date,
) -> dict[str, object]:
    current_dim = _optional_int(context_row.get("current_dim"))
    if is_droogstaand(context_row):
        row.update(
            {
                "Aanbiedcategorie": "Tijdelijk niet aanbieden",
                "Aanbiedreden": "Koe staat droog",
                "Urgentie": 60,
            }
        )
        return row

    if current_dim is None:
        row.update(
            {
                "Aanbiedcategorie": "Onvoldoende data",
                "Aanbiedreden": "DIM ontbreekt",
                "Urgentie": 90,
            }
        )
        return row

    if current_dim < MIN_DIM_PREVENTIEF:
        row.update(
            {
                "Aanbiedcategorie": "Tijdelijk niet aanbieden",
                "Aanbiedreden": f"Preventief vanaf {MIN_DIM_PREVENTIEF} DIM",
                "Volgende actiedatum": peildatum
                + timedelta(days=MIN_DIM_PREVENTIEF - current_dim),
                "Urgentie": 60,
            }
        )
        return row

    if last_healthy_date is None:
        row.update(
            {
                "Aanbiedcategorie": "Onvoldoende data",
                "Aanbiedreden": "Geen gezonde Vierkant-registratie gevonden",
                "Urgentie": 90,
            }
        )
        return row

    due_date = last_healthy_date + timedelta(days=PREVENTIEF_DAGEN)
    if peildatum >= due_date:
        row.update(
            {
                "Aanbiedcategorie": "Preventief bekappen",
                "Aanbiedreden": "Meer dan 183 dagen sinds zuivere Vierkant-registratie",
                "Moet aangeboden worden": True,
                "Volgende actiedatum": due_date,
                "Urgentie": 3,
            }
        )
        return row

    row.update(
        {
            "Aanbiedcategorie": "Tijdelijk niet aanbieden",
            "Aanbiedreden": f"Preventief bekappen vanaf {due_date}",
            "Volgende actiedatum": due_date,
            "Urgentie": 60,
        }
    )
    return row


def _lookup_uniform_agri_code(
    normalized_problem: str,
    mappings: dict[str, str],
) -> Optional[str]:
    for problem, code in mappings.items():
        if problem in normalized_problem:
            return code

    return None


def _format_uniform_agri_grouped_row(row: dict[str, object]) -> dict[str, object]:
    formatted_row = _strip_private_columns(row)
    formatted_row["behandeling_ids"] = ", ".join(
        str(behandeling_id) for behandeling_id in row["behandeling_ids"]
    )
    formatted_row["notities"] = ", ".join(str(notatie) for notatie in row["notities"])
    return formatted_row


def _is_mortellaro_text(value: str) -> bool:
    return re.search(r"\bmortel{1,2}aro\b", _normalize_text(value)) is not None


def _matches_known_item(value: str, known_items: set[str]) -> bool:
    return any(item in value for item in known_items)


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


def _optional_int(value: object) -> Optional[int]:
    if value is None:
        return None

    return int(value)


def _strip_private_columns(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if not key.startswith("_")}
