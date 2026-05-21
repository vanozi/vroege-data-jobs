import logging
from typing import Optional

from database.models.behandeling import KlauwBehandeling
from database.repositories.behandelingen_repository import KlauwBehandelingenRepository


def save_klauw_behandelingen(
    rows: list[dict[str, object]],
    repository: Optional[KlauwBehandelingenRepository],
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
        repository.upsert_klauw_behandeling(
            {
                "eartag_short": row["eartag_short"],
                "behandeldatum": row["behandeldatum"],
                "notatie": row["notatie"],
            }
        )
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
