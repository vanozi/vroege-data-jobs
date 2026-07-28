from collections.abc import Callable

from data_jobs.uniform_agri import transforms
from data_jobs.uniform_agri.collectors.models import (
    AnimalCollectionFailure,
    CollectionResult,
)
from database.models.koe import Koe, KoeDetail


def collect_animal_details(
    service,
    herd_id: str,
    koeien: list[Koe],
    continue_on_animal_error: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> CollectionResult[KoeDetail]:
    """Fetch and transform actual-tab details for each cow."""
    result: CollectionResult[KoeDetail] = CollectionResult()
    total = len(koeien)
    if progress_callback:
        progress_callback(0, total)

    for processed, koe in enumerate(koeien, start=1):
        try:
            raw_detail = service.fetch_animal_actual(herd_id, str(koe.animal_id))
            result.records.append(transforms.koe_detail_from_actual(raw_detail))
        except Exception as error:
            result.failures.append(
                _build_failure(koe, "animal_actual_collection", error)
            )
            if not continue_on_animal_error:
                raise

        if progress_callback and (processed % 50 == 0 or processed == total):
            progress_callback(processed, total)

    return result


def _build_failure(
    koe: Koe,
    stage: str,
    error: Exception,
) -> AnimalCollectionFailure:
    return AnimalCollectionFailure(
        animal_id=str(koe.animal_id),
        animal_name=koe.name,
        stage=stage,
        error_message=str(error),
    )
