from datetime import date
from typing import Optional

import pandas as pd

from dashboard import klauwbehandeling_transforms


def test_classify_mortellaro_with_position_prefix() -> None:
    classification = klauwbehandeling_transforms.classify_notatie(
        "Linksachter Mortellaro",
    )

    assert classification["is_mortellaro"] is True
    assert classification["positie"] == "Linksachter"
    assert classification["zijde"] == "Links"
    assert classification["poot"] == "Achter"
    assert classification["diagnose_tekst"] == "Mortellaro"
    assert classification["probleem"] == "Mortellaro"
    assert classification["categorie"] == "Diagnose"
    assert classification["ernst"] == "Hoog"
    assert classification["ernst_score"] == 3


def test_classify_mortellaro_is_case_and_whitespace_tolerant() -> None:
    classification = klauwbehandeling_transforms.classify_notatie(
        "  rechtsachter   mortellaro  ",
    )

    assert classification["is_mortellaro"] is True
    assert classification["positie"] == "Rechtsachter"
    assert classification["zijde"] == "Rechts"
    assert classification["poot"] == "Achter"
    assert classification["diagnose_tekst"] == "mortellaro"
    assert classification["probleem"] == "Mortellaro"


def test_classify_mortelaro_spelling_as_mortellaro() -> None:
    classification = klauwbehandeling_transforms.classify_notatie("Linksvoor Mortelaro")

    assert classification["is_mortellaro"] is True
    assert classification["positie"] == "Linksvoor"
    assert classification["probleem"] == "Mortellaro"


def test_classify_non_mortellaro_notitie() -> None:
    classification = klauwbehandeling_transforms.classify_notatie("Rechtsvoor Klos")

    assert classification["is_mortellaro"] is False
    assert classification["positie"] == "Rechtsvoor"
    assert classification["diagnose_tekst"] == "Klos"
    assert classification["probleem"] == "Klos"
    assert classification["categorie"] == "Behandeling / actie"
    assert classification["ernst"] == "Actie"
    assert classification["ernst_score"] == 0


def test_classify_unknown_notitie_keeps_text_available() -> None:
    classification = klauwbehandeling_transforms.classify_notatie("Losse opmerking")

    assert classification["is_mortellaro"] is False
    assert classification["positie"] == "Onbekende positie"
    assert classification["diagnose_tekst"] == "Losse opmerking"
    assert classification["probleem"] == "Losse opmerking"
    assert classification["categorie"] == "Overig / onbekend"


def test_add_mortellaro_case_columns_marks_new_and_repeated_cases() -> None:
    rows = [
        build_notitie_row(
            1,
            "cow-1",
            101,
            date(2026, 1, 1),
            "Linksachter Mortellaro",
        ),
        build_notitie_row(
            2,
            "cow-1",
            101,
            date(2026, 1, 15),
            "Linksachter Mortellaro",
        ),
        build_notitie_row(
            3,
            "cow-1",
            101,
            date(2026, 2, 1),
            "Rechtsachter Mortellaro",
        ),
        build_notitie_row(
            4,
            "cow-1",
            101,
            date(2026, 2, 10),
            "Rechtsachter Klos",
        ),
    ]
    klauw_df = pd.DataFrame(rows)
    classification_df = klauw_df["notatie"].apply(
        lambda notatie: pd.Series(
            klauwbehandeling_transforms.classify_notatie(notatie),
        ),
    )
    klauw_df = pd.concat([klauw_df, classification_df], axis=1)

    result_df = klauwbehandeling_transforms.add_mortellaro_case_columns(klauw_df)

    first_left = result_df.loc[result_df["id"] == 1].iloc[0]
    repeated_left = result_df.loc[result_df["id"] == 2].iloc[0]
    first_right = result_df.loc[result_df["id"] == 3].iloc[0]
    non_mortellaro = result_df.loc[result_df["id"] == 4].iloc[0]

    assert bool(first_left["nieuwe_case"]) is True
    assert bool(first_left["herhaalde_case"]) is False
    assert first_left["eerste_datum"] == date(2026, 1, 1)
    assert pd.isna(first_left["vorige_datum"])
    assert first_left["dagen_sinds_eerste"] == 0
    assert first_left["herhaling_nummer"] == 0

    assert bool(repeated_left["nieuwe_case"]) is False
    assert bool(repeated_left["herhaalde_case"]) is True
    assert repeated_left["eerste_datum"] == date(2026, 1, 1)
    assert repeated_left["vorige_datum"] == date(2026, 1, 1)
    assert repeated_left["dagen_sinds_vorige"] == 14
    assert repeated_left["dagen_sinds_eerste"] == 14
    assert repeated_left["herhaling_nummer"] == 1

    assert bool(first_right["nieuwe_case"]) is True
    assert bool(first_right["herhaalde_case"]) is False
    assert first_right["eerste_datum"] == date(2026, 2, 1)
    assert first_right["herhaling_nummer"] == 0

    assert bool(non_mortellaro["nieuwe_case"]) is False
    assert bool(non_mortellaro["herhaalde_case"]) is False
    assert pd.isna(non_mortellaro["herhaling_nummer"])


def test_add_mortellaro_case_columns_falls_back_to_collar_number() -> None:
    rows = [
        build_notitie_row(
            1,
            None,
            101,
            date(2026, 1, 1),
            "Linksachter Mortellaro",
        ),
        build_notitie_row(
            2,
            None,
            101,
            date(2026, 1, 10),
            "Linksachter Mortellaro",
        ),
    ]
    klauw_df = pd.DataFrame(rows)
    classification_df = klauw_df["notatie"].apply(
        lambda notatie: pd.Series(
            klauwbehandeling_transforms.classify_notatie(notatie),
        ),
    )
    klauw_df = pd.concat([klauw_df, classification_df], axis=1)

    result_df = klauwbehandeling_transforms.add_mortellaro_case_columns(klauw_df)

    assert bool(result_df.loc[result_df["id"] == 1, "nieuwe_case"].iloc[0]) is True
    assert bool(result_df.loc[result_df["id"] == 2, "herhaalde_case"].iloc[0]) is True
    assert result_df.loc[result_df["id"] == 2, "dagen_sinds_vorige"].iloc[0] == 9


def test_summarize_mortellaro_cases_marks_resolved_by_next_vierkant() -> None:
    klauw_df = build_classified_df(
        [
            build_notitie_row(
                1,
                "cow-1",
                101,
                date(2026, 1, 1),
                "Linksachter Mortellaro",
            ),
            build_notitie_row(2, "cow-1", 101, date(2026, 1, 15), "Vierkant"),
        ],
    )

    summary_df = klauwbehandeling_transforms.summarize_mortellaro_cases(klauw_df)

    case = summary_df.iloc[0]
    assert case["opvolgstatus"] == klauwbehandeling_transforms.FOLLOWUP_RESOLVED
    assert case["volgende_bezoekdatum"] == date(2026, 1, 15)
    assert case["dagen_tot_volgend_bezoek"] == 14
    assert case["volgende_bezoek_notities"] == "Vierkant"


def test_summarize_mortellaro_cases_keeps_same_position_repeated_active() -> None:
    klauw_df = build_classified_df(
        [
            build_notitie_row(
                1,
                "cow-1",
                101,
                date(2026, 1, 1),
                "Linksachter Mortellaro",
            ),
            build_notitie_row(
                2,
                "cow-1",
                101,
                date(2026, 1, 15),
                "Linksachter Mortellaro",
            ),
            build_notitie_row(3, "cow-1", 101, date(2026, 1, 15), "Vierkant"),
        ],
    )

    summary_df = klauwbehandeling_transforms.summarize_mortellaro_cases(klauw_df)

    case = summary_df.iloc[0]
    assert case["opvolgstatus"] == klauwbehandeling_transforms.FOLLOWUP_REPEATED
    assert case["volgende_bezoekdatum"] == date(2026, 1, 15)
    assert "Linksachter Mortellaro" in case["volgende_bezoek_notities"]


def test_summarize_mortellaro_cases_marks_open_without_next_visit() -> None:
    klauw_df = build_classified_df(
        [
            build_notitie_row(
                1,
                "cow-1",
                101,
                date(2026, 1, 1),
                "Linksachter Mortellaro",
            ),
        ],
    )

    summary_df = klauwbehandeling_transforms.summarize_mortellaro_cases(klauw_df)

    case = summary_df.iloc[0]
    assert case["opvolgstatus"] == klauwbehandeling_transforms.FOLLOWUP_NO_NEXT_VISIT
    assert pd.isna(case["volgende_bezoekdatum"])
    assert pd.isna(case["dagen_tot_volgend_bezoek"])


def build_classified_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    klauw_df = pd.DataFrame(rows)
    classification_df = klauw_df["notatie"].apply(
        lambda notatie: pd.Series(
            klauwbehandeling_transforms.classify_notatie(notatie),
        ),
    )
    klauw_df = pd.concat([klauw_df, classification_df], axis=1)
    return klauwbehandeling_transforms.add_mortellaro_case_columns(klauw_df)


def build_notitie_row(
    row_id: int,
    animal_id: Optional[str],
    halsbandnummer: int,
    behandeldatum: date,
    notatie: str,
) -> dict[str, object]:
    return {
        "id": row_id,
        "animal_id": animal_id,
        "halsbandnummer": halsbandnummer,
        "behandeldatum": behandeldatum,
        "notatie": notatie,
    }
