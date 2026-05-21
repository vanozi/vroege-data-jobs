from datetime import date

from database.models.behandeling import KlauwBehandeling
from database.repositories.behandelingen_repository import KlauwBehandelingenRepository


def test_upsert_klauw_behandeling_preserves_unique_fields_for_dict():
    repository = KlauwBehandelingenRepository(lambda: None)
    calls = []

    def fake_upsert(data, unique_fields):
        calls.append((data, unique_fields))
        return "saved"

    repository.upsert = fake_upsert

    result = repository.upsert_klauw_behandeling(
        {
            "eartag_short": "101",
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Bekapt",
        }
    )

    assert result == "saved"
    assert calls == [
        (
            {
                "eartag_short": "101",
                "behandeldatum": date(2026, 5, 19),
                "notatie": "Bekapt",
            },
            ["eartag_short", "behandeldatum", "notatie"],
        )
    ]


def test_upsert_klauw_behandeling_accepts_model_at_repository_boundary():
    repository = KlauwBehandelingenRepository(lambda: None)
    calls = []

    def fake_upsert(data, unique_fields):
        calls.append((data, unique_fields))
        return "saved"

    repository.upsert = fake_upsert

    result = repository.upsert_klauw_behandeling(
        KlauwBehandeling(
            eartag_short="101",
            behandeldatum=date(2026, 5, 19),
            notatie="Bekapt",
        )
    )

    assert result == "saved"
    assert calls[0][0]["eartag_short"] == "101"
    assert calls[0][0]["behandeldatum"] == date(2026, 5, 19)
    assert calls[0][0]["notatie"] == "Bekapt"
    assert calls[0][1] == ["eartag_short", "behandeldatum", "notatie"]
