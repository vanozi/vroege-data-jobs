"""Tests voor dashboard transforms module."""

from datetime import date

from dashboard.transforms import (
    add_mortellaro_case_columns,
    build_klauwbekap_protocol_rows,
    build_open_mortellaro_rows,
    build_uniform_agri_csv_download_rows,
    build_uniform_agri_csv_rows,
    build_uniform_agri_export_rows,
    build_mortellaro_case_key,
    build_mortellaro_followup_status,
    format_uniform_agri_date,
    get_position_sort_key,
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


class TestOpenMortellaroRows:
    """Tests voor de nieuwe open-Mortellaro tabeldefinitie."""

    def test_mortellaro_without_later_vierkant_is_open(self):
        result = build_open_mortellaro_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
            ]
        )

        assert len(result) == 1
        assert result[0]["Koe / naam"] == "Koe 1"
        assert result[0]["Laatste Mortellaro-datum"] == date(2026, 1, 1)
        assert result[0]["Laatste behandeling na Mortellaro"] is None
        assert result[0]["Laatste notatie(s)"] == "Linksachter Mortellaro"

    def test_later_vierkant_closes_mortellaro(self):
        result = build_open_mortellaro_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Vierkant",
                ),
            ]
        )

        assert result == []

    def test_vierkant_before_mortellaro_does_not_close_mortellaro(self):
        result = build_open_mortellaro_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Vierkant",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Rechtsachter Mortellaro",
                ),
            ]
        )

        assert len(result) == 1
        assert result[0]["Laatste Mortellaro-datum"] == date(2026, 2, 1)

    def test_mortellaro_on_multiple_feet_is_one_open_cow(self):
        result = build_open_mortellaro_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 15),
                    notatie="Rechtsachter Mortelaro",
                ),
            ]
        )

        assert len(result) == 1
        assert result[0]["Laatste Mortellaro-datum"] == date(2026, 1, 15)
        assert result[0]["Laatste notatie(s)"] == "Rechtsachter Mortelaro"

    def test_last_treatment_after_mortellaro_is_shown_when_not_vierkant(self):
        result = build_open_mortellaro_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 20),
                    notatie="Linksachter Verband",
                ),
            ]
        )

        assert len(result) == 1
        assert result[0]["Laatste behandeling na Mortellaro"] == date(2026, 1, 20)
        assert result[0]["Laatste notatie(s)"] == "Linksachter Verband"


class TestKlauwbekapProtocolRows:
    """Tests voor de klauwbekapprotocol aanbiedlijst."""

    def test_mortellaro_is_always_offered_even_when_dry(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                    status="Droog",
                    current_dim=10,
                )
            ],
            reference_date=date(2026, 1, 10),
        )

        assert result[0]["Aanbiedcategorie"] == "Actieve Mortellaro"
        assert result[0]["Moet aangeboden worden"] is True
        assert result[0]["Voergroep nummer"] == "7"
        assert result[0]["Voergroep naam"] == "Groep 1"

    def test_mortellaro_followed_by_later_vierkant_is_not_active(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Vierkant",
                ),
            ],
            reference_date=date(2026, 2, 2),
        )

        assert result[0]["Aanbiedcategorie"] != "Actieve Mortellaro"

    def test_mortellaro_followed_by_vierkant_and_other_condition_starts_followup(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Vierkant",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Linksvoor Zoolzweer",
                ),
            ],
            reference_date=date(2026, 4, 26),
        )

        assert result[0]["Aanbiedcategorie"] == "Hercontrole aandoening"
        assert "Zoolzweer" in result[0]["Aanbiedreden"]

    def test_mortellaro_followed_by_vierkant_and_mortellaro_stays_active(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksachter Mortellaro",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Vierkant",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 2, 1),
                    notatie="Rechtsachter Mortellaro",
                ),
            ],
            reference_date=date(2026, 2, 2),
        )

        assert result[0]["Aanbiedcategorie"] == "Actieve Mortellaro"

    def test_other_condition_is_offered_after_twelve_weeks(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksvoor Zoolzweer",
                )
            ],
            reference_date=date(2026, 3, 26),
        )

        assert result[0]["Aanbiedcategorie"] == "Hercontrole aandoening"
        assert result[0]["Moet aangeboden worden"] is True

    def test_other_condition_before_twelve_weeks_is_not_offered_yet(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksvoor Zoolzweer",
                )
            ],
            reference_date=date(2026, 3, 1),
        )

        assert result[0]["Aanbiedcategorie"] == "Tijdelijk niet aanbieden"
        assert result[0]["Moet aangeboden worden"] is False

    def test_pure_vierkant_after_183_days_is_preventive(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Vierkant",
                )
            ],
            reference_date=date(2026, 7, 3),
        )

        assert result[0]["Aanbiedcategorie"] == "Preventief bekappen"
        assert result[0]["Moet aangeboden worden"] is True

    def test_future_reference_date_can_make_preventive_due(self):
        rows = [
            build_klauw_row(
                animal_id="koe-1",
                behandeldatum=date(2026, 1, 1),
                notatie="Vierkant",
            )
        ]

        early = build_klauwbekap_protocol_rows(
            rows,
            reference_date=date(2026, 6, 30),
        )
        planned = build_klauwbekap_protocol_rows(
            rows,
            reference_date=date(2026, 7, 3),
        )

        assert early[0]["Moet aangeboden worden"] is False
        assert planned[0]["Moet aangeboden worden"] is True

    def test_vierkant_with_condition_is_not_preventive(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Vierkant",
                ),
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Linksvoor Zoolzweer",
                ),
            ],
            reference_date=date(2026, 7, 3),
        )

        assert result[0]["Aanbiedcategorie"] == "Hercontrole aandoening"

    def test_dry_cow_is_not_preventively_offered(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Vierkant",
                    status="Droog",
                )
            ],
            reference_date=date(2026, 7, 3),
        )

        assert result[0]["Aanbiedcategorie"] == "Tijdelijk niet aanbieden"
        assert result[0]["Moet aangeboden worden"] is False

    def test_low_dim_cow_is_not_preventively_offered(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=date(2026, 1, 1),
                    notatie="Vierkant",
                    current_dim=20,
                )
            ],
            reference_date=date(2026, 7, 3),
        )

        assert result[0]["Aanbiedcategorie"] == "Tijdelijk niet aanbieden"
        assert result[0]["Moet aangeboden worden"] is False

    def test_cow_without_hoof_data_is_preventive_from_thirty_dim(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=None,
                    notatie=None,
                    current_dim=30,
                )
            ],
            reference_date=date(2026, 7, 3),
        )

        assert result[0]["Aanbiedcategorie"] == "Preventief bekappen"
        assert result[0]["Moet aangeboden worden"] is True

    def test_young_stock_without_hoof_data_is_data_control(self):
        result = build_klauwbekap_protocol_rows(
            [
                build_klauw_row(
                    animal_id="koe-1",
                    behandeldatum=None,
                    notatie=None,
                    current_dim=30,
                    is_young_stock=True,
                )
            ],
            reference_date=date(2026, 7, 3),
        )

        assert result[0]["Aanbiedcategorie"] == "Onvoldoende data"
        assert result[0]["Moet aangeboden worden"] is False


class TestUniformAgriExport:
    """Tests voor Uniform Agri Hoof Supervisor exporttransforms."""

    def test_format_uniform_agri_date(self):
        assert format_uniform_agri_date(date(2026, 6, 9)) == "09/06/2026"
        assert format_uniform_agri_date(date(2026, 5, 26)) == "26/05/2026"
        assert format_uniform_agri_date(None) == ""

    def test_condition_mappings_include_position_without_hoof_zone(self):
        rows = build_uniform_agri_export_rows(
            [
                build_uniform_row("Linksachter Mortellaro"),
                build_uniform_row("Rechtsvoor Wittelijndefect"),
                build_uniform_row("Linksvoor Zoolzweer"),
                build_uniform_row("Rechtsachter Tyloom"),
                build_uniform_row("Rechtsvoor Tussenklauwontsteking"),
                build_uniform_row("Rechtsachter Stinkpoot"),
                build_uniform_row("Linksachter Chronisch bevangen"),
            ]
        )

        assert [row["health_conditions_location"] for row in rows] == [
            "D7",
            "W1",
            "U3",
            "K5",
            "I1",
            "F5",
            "O7",
        ]
        assert [row["treatment"] for row in rows] == ["", "", "", "", "", "", ""]
        assert all(row["exportable"] for row in rows)

    def test_action_and_trim_mappings(self):
        rows = build_uniform_agri_export_rows(
            [
                build_uniform_row("Linksachter Verband"),
                build_uniform_row("Linksachter Klos"),
                build_uniform_row("Behandeling"),
                build_uniform_row("Vierkant"),
            ]
        )

        assert [row["health_conditions_location"] for row in rows] == ["", "", "", ""]
        assert [row["treatment"] for row in rows] == ["W", "B", "T", "R"]
        assert rows[3]["trim_type_code"] == "R"
        assert all(row["exportable"] for row in rows)

    def test_condition_without_action_does_not_get_default_treatment(self):
        row = build_uniform_agri_export_rows(
            [build_uniform_row("Linksachter Mortellaro")]
        )[0]

        assert row["health_conditions_location"] == "D7"
        assert row["treatment"] == ""
        assert row["exportable"] is True

    def test_unknown_notatie_is_not_exportable(self):
        row = build_uniform_agri_export_rows([build_uniform_row("Onbekend probleem")])[
            0
        ]

        assert row["exportable"] is False
        assert row["validation_status"] == "error"
        assert "Onbekende" in row["validation_message"]

    def test_condition_without_position_is_not_exportable(self):
        row = build_uniform_agri_export_rows([build_uniform_row("Mortellaro")])[0]

        assert row["exportable"] is False
        assert row["condition_code"] == "D"
        assert row["health_conditions_location"] == ""
        assert "Geen pootpositie" in row["validation_message"]

    def test_missing_cow_link_is_not_exportable(self):
        row = build_uniform_agri_export_rows(
            [build_uniform_row("Vierkant", animal_id=None)]
        )[0]

        assert row["exportable"] is False
        assert "Geen gekoppelde koe" in row["validation_message"]

    def test_missing_collar_number_is_not_exportable(self):
        row = build_uniform_agri_export_rows(
            [build_uniform_row("Vierkant", collar_number=None)]
        )[0]

        assert row["exportable"] is False
        assert "Geen werknummer" in row["validation_message"]

    def test_cow_outside_current_herd_is_not_exportable(self):
        row = build_uniform_agri_export_rows(
            [build_uniform_row("Vierkant", in_current_herd=False)]
        )[0]

        assert row["exportable"] is False
        assert "huidige kudde" in row["validation_message"]

    def test_missing_joined_koe_record_is_not_exportable(self):
        row = build_uniform_agri_export_rows(
            [build_uniform_row("Vierkant", koe_animal_id=None)]
        )[0]

        assert row["exportable"] is False
        assert "niet gevonden" in row["validation_message"]

    def test_group_csv_rows_by_animal_no_and_treatment_date(self):
        grouped_rows = build_uniform_agri_csv_rows(
            [
                build_uniform_row(
                    "Rechtsachter Tyloom",
                    behandeling_id=1,
                    collar_number=70,
                ),
                build_uniform_row(
                    "Linksachter Mortellaro",
                    behandeling_id=2,
                    collar_number=70,
                ),
                build_uniform_row("Vierkant", behandeling_id=3, collar_number=70),
            ]
        )

        assert len(grouped_rows) == 1
        assert grouped_rows[0]["animal_no"] == "70"
        assert grouped_rows[0]["date"] == "26/05/2026"
        assert grouped_rows[0]["health_conditions_location"] == "K5D7"
        assert grouped_rows[0]["treatment"] == "R"
        assert grouped_rows[0]["behandeling_ids"] == "1, 2, 3"
        assert grouped_rows[0]["row_count"] == 3
        assert grouped_rows[0]["exportable"] is True

    def test_csv_download_rows_include_only_four_header_columns(self):
        csv_rows = build_uniform_agri_csv_download_rows(
            [
                build_uniform_row("Rechtsachter Tyloom", collar_number=70),
                build_uniform_row("Vierkant", collar_number=70),
                build_uniform_row("Onbekend probleem", collar_number=71),
            ]
        )

        assert csv_rows == [
            {
                "animal no.": "70",
                "date": "26/05/2026",
                "health conditions and location": "K5",
                "treatment": "R",
            }
        ]


def build_uniform_row(
    notatie: str,
    *,
    animal_id: object = "animal-1",
    koe_animal_id: object = "animal-1",
    behandeling_id: int = 1,
    collar_number: object = 70,
    in_current_herd: bool = True,
) -> dict[str, object]:
    return {
        "behandeling_id": behandeling_id,
        "animal_id": animal_id,
        "koe_animal_id": koe_animal_id,
        "collar_number": collar_number,
        "in_current_herd": in_current_herd,
        "behandeldatum": date(2026, 5, 26),
        "notatie": notatie,
        "eartag": "NL 123",
        "eartag_short": "0123",
        "name": "Koe 1",
    }


def build_klauw_row(
    *,
    animal_id: str,
    behandeldatum: object,
    notatie: object,
    name: str = "Koe 1",
    collar_number: int = 70,
    eartag_short: str = "0123",
    eartag: str = "NL 123",
    feeding_group_number: int = 7,
    feeding_group_name: str = "Groep 1",
    current_dim: object = 100,
    lactation_number: object = 2,
    status: object = "Lacterend",
    status_days: object = 10,
    is_young_stock: bool = False,
) -> dict[str, object]:
    return {
        "animal_id": animal_id,
        "name": name,
        "collar_number": collar_number,
        "eartag_short": eartag_short,
        "eartag": eartag,
        "feeding_group_number": feeding_group_number,
        "feeding_group_name": feeding_group_name,
        "current_dim": current_dim,
        "lactation_number": lactation_number,
        "status": status,
        "status_days": status_days,
        "is_young_stock": is_young_stock,
        "behandeldatum": behandeldatum,
        "notatie": notatie,
    }
