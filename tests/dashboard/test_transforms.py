"""Tests voor dashboard transforms module."""

from datetime import date

from dashboard.transforms import (
    add_mortellaro_case_columns,
    build_mortellaro_case_key,
    build_mortellaro_followup_status,
    get_position_sort_key,
    get_probleem_categorie,
    parse_notatie,
)


class TestParseNotatie:
    """Tests voor parse_notatie functie."""

    def test_parse_mortellaro_linksachter(self):
        """Test parsing van 'Linksachter Mortellaro'."""
        result = parse_notatie("Linksachter Mortellaro")
        assert result.positie_code == "LA"
        assert result.positie_volledig == "Linksachter"
        assert result.zijde == "Links"
        assert result.poot == "Achter"
        assert result.probleem == "Mortellaro"
        assert result.originele_tekst == "Linksachter Mortellaro"
        assert result.is_mortellaro is True
        assert result.is_vierkant is False

    def test_parse_mortelaro_spelling(self):
        """Test parsing van alternatieve spelling 'Mortelaro'."""
        result = parse_notatie("Rechtsachter Mortelaro")
        assert result.positie_code == "RA"
        assert result.probleem == "Mortelaro"
        assert result.is_mortellaro is True

    def test_parse_rechtsvoor_wittelijndefect(self):
        """Test parsing van 'Rechtsvoor Wittelijndefect'."""
        result = parse_notatie("Rechtsvoor Wittelijndefect")
        assert result.positie_code == "RV"
        assert result.positie_volledig == "Rechtsvoor"
        assert result.zijde == "Rechts"
        assert result.poot == "Voor"
        assert result.probleem == "Wittelijndefect"

    def test_parse_linksvoor_klos(self):
        """Test parsing van 'Linksvoor Klos'."""
        result = parse_notatie("Linksvoor Klos")
        assert result.positie_code == "LV"
        assert result.positie_volledig == "Linksvoor"
        assert result.probleem == "Klos"

    def test_parse_rechtsachter_tyloom(self):
        """Test parsing van 'Rechtsachter Tyloom'."""
        result = parse_notatie("Rechtsachter Tyloom")
        assert result.positie_code == "RA"
        assert result.positie_volledig == "Rechtsachter"
        assert result.zijde == "Rechts"
        assert result.poot == "Achter"
        assert result.probleem == "Tyloom"

    def test_parse_no_position_bont(self):
        """Test parsing van 'Bont' (zonder positie)."""
        result = parse_notatie("Bont")
        assert result.positie_code == "Geen"
        assert result.positie_volledig == "Geen"
        assert result.zijde is None
        assert result.poot is None
        assert result.probleem == "Bont"

    def test_parse_no_position_vierkant(self):
        """Test parsing van 'Vierkant' (zonder positie)."""
        result = parse_notatie("Vierkant")
        assert result.positie_code == "Geen"
        assert result.positie_volledig == "Geen"
        assert result.zijde is None
        assert result.poot is None
        assert result.probleem == "Vierkant"
        assert result.is_vierkant is True
        assert result.is_mortellaro is False

    def test_parse_mortellaro_without_position_is_visible(self):
        """Test dat Mortellaro zonder positie herkenbaar blijft."""
        result = parse_notatie("Mortellaro")
        assert result.positie_code == "Geen"
        assert result.positie_volledig == "Geen"
        assert result.is_mortellaro is True

    def test_parse_case_insensitive(self):
        """Test dat parsing case-insensitive is."""
        result = parse_notatie("RECHTSVOOR MORTELLARO")
        assert result.positie_code == "RV"
        assert result.probleem == "MORTELLARO"

    def test_parse_lowercase(self):
        """Test parsing met lowercase."""
        result = parse_notatie("linksvoor mortellaro")
        assert result.positie_code == "LV"
        assert result.probleem == "mortellaro"

    def test_parse_empty_string(self):
        """Test parsing van lege string."""
        result = parse_notatie("")
        assert result.positie_code == "Geen"
        assert result.probleem == ""

    def test_parse_none(self):
        """Test parsing van None."""
        result = parse_notatie(None)
        assert result.positie_code == "Geen"
        assert result.probleem == ""

    def test_parse_whitespace(self):
        """Test parsing van alleen whitespace."""
        result = parse_notatie("   ")
        assert result.positie_code == "Geen"
        assert result.probleem == ""

    def test_parse_with_leading_whitespace(self):
        """Test parsing met leading whitespace."""
        result = parse_notatie("  Linksvoor Mortellaro  ")
        assert result.positie_code == "LV"
        assert result.probleem == "Mortellaro"

    def test_parse_all_real_examples(self):
        """Test parsing van alle echte database voorbeelden."""
        test_cases = [
            ("Rechtsvoor Bont", "RV", "Bont"),
            ("Rechtsvoor Wittelijndefect", "RV", "Wittelijndefect"),
            ("Linksachter Tyloom", "LA", "Tyloom"),
            ("Linksvoor Mortellaro", "LV", "Mortellaro"),
            ("Linksvoor Klos", "LV", "Klos"),
            ("Linksachter Klos", "LA", "Klos"),
            ("Rechtsvoor Tussenklauwontsteking", "RV", "Tussenklauwontsteking"),
            ("Rechtsvoor Stinkpoot", "RV", "Stinkpoot"),
            ("Rechtsvoor Chronisch bevangen", "RV", "Chronisch bevangen"),
            ("Linksachter Wittelijndefect", "LA", "Wittelijndefect"),
            ("Linksachter Zoolzweer", "LA", "Zoolzweer"),
            ("Rechtsachter Bont", "RA", "Bont"),
            ("Rechtsachter Verband", "RA", "Verband"),
            ("Linksvoor Verband", "LV", "Verband"),
            ("Bont", "Geen", "Bont"),
            ("Vierkant", "Geen", "Vierkant"),
        ]

        for notatie, expected_code, expected_probleem in test_cases:
            result = parse_notatie(notatie)
            assert result.positie_code == expected_code, f"Failed for: {notatie}"
            assert result.probleem == expected_probleem, f"Failed for: {notatie}"


class TestGetProbleemCategorie:
    """Tests voor get_probleem_categorie functie."""

    def test_categorie_mortellaro(self):
        """Test categorie voor Mortellaro."""
        assert get_probleem_categorie("Mortellaro") == "Infecties"

    def test_categorie_stinkpoot(self):
        """Test categorie voor Stinkpoot."""
        assert get_probleem_categorie("Stinkpoot") == "Infecties"

    def test_categorie_tussenklauwontsteking(self):
        """Test categorie voor Tussenklauwontsteking."""
        assert get_probleem_categorie("Tussenklauwontsteking") == "Infecties"

    def test_categorie_wittelijndefect(self):
        """Test categorie voor Wittelijndefect."""
        assert get_probleem_categorie("Wittelijndefect") == "Structurele problemen"

    def test_categorie_zoolzweer(self):
        """Test categorie voor Zoolzweer."""
        assert get_probleem_categorie("Zoolzweer") == "Structurele problemen"

    def test_categorie_chronisch_bevangen(self):
        """Test categorie voor Chronisch bevangen."""
        assert get_probleem_categorie("Chronisch bevangen") == "Structurele problemen"

    def test_categorie_klos(self):
        """Test categorie voor Klos."""
        assert get_probleem_categorie("Klos") == "Structurele problemen"

    def test_categorie_tyloom(self):
        """Test categorie voor Tyloom."""
        assert get_probleem_categorie("Tyloom") == "Tumoren"

    def test_categorie_bont(self):
        """Test categorie voor Bont."""
        assert get_probleem_categorie("Bont") == "Behandelingen"

    def test_categorie_verband(self):
        """Test categorie voor Verband."""
        assert get_probleem_categorie("Verband") == "Behandelingen"

    def test_categorie_vierkant(self):
        """Test categorie voor Vierkant."""
        assert get_probleem_categorie("Vierkant") == "Behandelingen"

    def test_categorie_case_insensitive(self):
        """Test dat categorie bepaling case-insensitive is."""
        assert get_probleem_categorie("MORTELLARO") == "Infecties"
        assert get_probleem_categorie("mortellaro") == "Infecties"
        assert get_probleem_categorie("Mortelaro") == "Infecties"

    def test_categorie_onbekend(self):
        """Test categorie voor onbekend probleem."""
        assert get_probleem_categorie("Onbekend probleem") == "Overig"
        assert get_probleem_categorie("") == "Overig"


class TestMortellaroCases:
    """Tests voor Mortellaro case tracking."""

    def test_position_sort_key(self):
        """Test stabiele sortering van pootposities."""
        assert get_position_sort_key("LV") < get_position_sort_key("RV")
        assert get_position_sort_key("RA") < get_position_sort_key("Geen")
        assert get_position_sort_key("bestaat-niet") > get_position_sort_key("Geen")

    def test_build_case_key_for_mortellaro_with_position(self):
        """Test case key voor koe en pootpositie."""
        row = {
            "animal_id": "koe-1",
            "halsbandnummer": 12,
            "behandeldatum": date(2026, 1, 1),
            "notatie": "Linksachter Mortellaro",
        }

        assert build_mortellaro_case_key(row) == ("koe-1", "LA")

    def test_no_case_key_for_mortellaro_without_position(self):
        """Test dat onbekende positie niet stilzwijgend wordt samengevoegd."""
        row = {
            "animal_id": "koe-1",
            "behandeldatum": date(2026, 1, 1),
            "notatie": "Mortellaro",
        }

        assert build_mortellaro_case_key(row) is None

    def test_left_and_right_back_are_two_new_cases(self):
        """Een koe met LA en later RA telt als twee nieuwe cases."""
        rows = [
            {
                "animal_id": "koe-1",
                "behandeldatum": date(2026, 1, 1),
                "notatie": "Linksachter Mortellaro",
            },
            {
                "animal_id": "koe-1",
                "behandeldatum": date(2026, 2, 1),
                "notatie": "Rechtsachter Mortellaro",
            },
        ]

        result = add_mortellaro_case_columns(rows)

        assert [row["mortellaro_case_key"] for row in result] == [
            ("koe-1", "LA"),
            ("koe-1", "RA"),
        ]
        assert [row["nieuwe_case"] for row in result] == [True, True]
        assert [row["herhaalde_case"] for row in result] == [False, False]

    def test_same_position_on_two_dates_is_new_plus_repeat(self):
        """Een koe met LA op twee datums telt als nieuw plus herhaling."""
        rows = [
            {
                "animal_id": "koe-1",
                "behandeldatum": date(2026, 1, 1),
                "notatie": "Linksachter Mortellaro",
            },
            {
                "animal_id": "koe-1",
                "behandeldatum": date(2026, 1, 22),
                "notatie": "Linksachter Mortellaro",
            },
        ]

        result = add_mortellaro_case_columns(rows)

        assert [row["nieuwe_case"] for row in result] == [True, False]
        assert [row["herhaalde_case"] for row in result] == [False, True]
        assert result[1]["eerste_datum"] == date(2026, 1, 1)
        assert result[1]["vorige_mortellaro_datum"] == date(2026, 1, 1)
        assert result[1]["dagen_sinds_vorige"] == 21
        assert result[1]["dagen_sinds_eerste"] == 21
        assert result[1]["herhaling_nummer"] == 1

    def test_non_mortellaro_rows_are_not_cases(self):
        """Niet-Mortellaro notities krijgen geen case key."""
        rows = [
            {
                "animal_id": "koe-1",
                "behandeldatum": date(2026, 1, 1),
                "notatie": "Linksachter Bont",
            }
        ]

        result = add_mortellaro_case_columns(rows)

        assert result[0]["mortellaro_case_key"] is None
        assert result[0]["nieuwe_case"] is False
        assert result[0]["herhaalde_case"] is False

    def test_followup_status_solved_by_later_vierkant(self):
        """Vierkant op een latere inspectie kan een case oplossen."""
        rows = [
            {
                "animal_id": "koe-1",
                "halsbandnummer": 12,
                "name": "IDA 1",
                "behandeldatum": date(2026, 1, 1),
                "notatie": "Linksachter Mortellaro",
            },
            {
                "animal_id": "koe-1",
                "halsbandnummer": 12,
                "name": "IDA 1",
                "behandeldatum": date(2026, 2, 1),
                "notatie": "Vierkant",
            },
        ]

        result = build_mortellaro_followup_status(rows)

        assert len(result) == 1
        assert result[0]["opvolgstatus"] == "Opgelost"
        assert result[0]["opgelost_op"] == date(2026, 2, 1)

    def test_followup_status_open_without_later_visit(self):
        """Geen latere inspectie betekent open of onbekend."""
        rows = [
            {
                "animal_id": "koe-1",
                "behandeldatum": date(2026, 1, 1),
                "notatie": "Linksachter Mortellaro",
            }
        ]

        result = build_mortellaro_followup_status(rows)

        assert result[0]["opvolgstatus"] == "Open/onbekend"
