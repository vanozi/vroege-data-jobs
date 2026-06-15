import logging
from typing import Optional

from database.models.behandeling import KlauwBehandeling
from database.repositories.behandelingen_repository import KlauwBehandelingenRepository
from database.repositories.koe_repository import KoeRepository


def save_klauw_behandelingen(
    rows: list[dict[str, object]],
    repository: Optional[KlauwBehandelingenRepository],
    koe_repository: Optional[KoeRepository] = None,
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert flattened Klauwscore rows and return the number processed."""
    if dry_run:
        _log_count(
            logger,
            "Dry run: would save %d klauw behandelingen.",
            len(rows),
        )
        return len(rows)

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    saved_count = 0
    for row in rows:
        treatment_data = _build_klauw_behandeling_data(row, koe_repository)
        repository.upsert_klauw_behandeling(treatment_data)
        saved_count += 1

    _log_count(logger, "Saved %d klauw behandelingen.", saved_count)
    return saved_count


def save_klauw_behandeling_models(
    models: list[KlauwBehandeling],
    repository: Optional[KlauwBehandelingenRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert KlauwBehandeling models and return the number processed."""
    if dry_run:
        _log_count(
            logger,
            "Dry run: would save %d klauw behandeling models.",
            len(models),
        )
        return len(models)

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    saved_count = 0
    for model in models:
        repository.upsert_klauw_behandeling(model)
        saved_count += 1

    _log_count(logger, "Saved %d klauw behandeling models.", saved_count)
    return saved_count


def _log_count(
    logger: Optional[logging.Logger],
    message: str,
    count: int,
) -> None:
    if logger is None:
        return

    logger.info(message, count)


def _build_klauw_behandeling_data(
    row: dict[str, object],
    koe_repository: Optional[KoeRepository],
) -> dict[str, object]:
    treatment_data = {
        "eartag_short": row["eartag_short"],
        "behandeldatum": row["behandeldatum"],
        "notatie": row["notatie"],
    }

    if koe_repository is None:
        return treatment_data

    koe = koe_repository.get_by_eartag_short_for_treatment_date(
        str(row["eartag_short"]),
        row["behandeldatum"],
    )
    if koe is None:
        return treatment_data

    return {
        **treatment_data,
        "animal_id": koe.animal_id,
        "eartag": koe.eartag,
    }
