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
    progress_interval: int = 500,
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
    koe_lookup_cache: dict[tuple[str, object], object] = {}
    total_rows = len(rows)
    for row in rows:
        treatment_data = _build_klauw_behandeling_data(
            row,
            koe_repository,
            koe_lookup_cache,
        )
        repository.upsert_klauw_behandeling(treatment_data)
        saved_count += 1
        _log_progress(logger, saved_count, total_rows, progress_interval)

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


def _log_progress(
    logger: Optional[logging.Logger],
    saved_count: int,
    total_rows: int,
    progress_interval: int,
) -> None:
    if logger is None:
        return

    if progress_interval <= 0:
        return

    if saved_count % progress_interval != 0 and saved_count != total_rows:
        return

    logger.info(
        "Saving klauw behandelingen: %d/%d processed.",
        saved_count,
        total_rows,
    )


def _build_klauw_behandeling_data(
    row: dict[str, object],
    koe_repository: Optional[KoeRepository],
    koe_lookup_cache: Optional[dict[tuple[str, object], object]] = None,
) -> dict[str, object]:
    treatment_data = {
        "eartag_short": row["eartag_short"],
        "behandeldatum": row["behandeldatum"],
        "notatie": row["notatie"],
    }
    pdf_href = row.get("pdf_href")
    if isinstance(pdf_href, str) and pdf_href:
        treatment_data["pdf_href"] = pdf_href

    if koe_repository is None:
        return treatment_data

    koe = _get_cached_koe_for_treatment_row(row, koe_repository, koe_lookup_cache)
    if koe is None:
        return treatment_data

    return {
        **treatment_data,
        "animal_id": koe.animal_id,
        "eartag": koe.eartag,
    }


def _get_cached_koe_for_treatment_row(
    row: dict[str, object],
    koe_repository: KoeRepository,
    koe_lookup_cache: Optional[dict[tuple[str, object], object]],
):
    eartag_short = str(row["eartag_short"])
    behandeldatum = row["behandeldatum"]
    cache_key = (eartag_short, behandeldatum)

    if koe_lookup_cache is None:
        return koe_repository.get_by_eartag_short_for_treatment_date(
            eartag_short,
            behandeldatum,
        )

    if cache_key not in koe_lookup_cache:
        koe_lookup_cache[cache_key] = (
            koe_repository.get_by_eartag_short_for_treatment_date(
                eartag_short,
                behandeldatum,
            )
        )

    return koe_lookup_cache[cache_key]
