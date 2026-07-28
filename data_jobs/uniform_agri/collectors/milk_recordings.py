from collections.abc import Callable

from data_jobs.uniform_agri import transforms
from data_jobs.uniform_agri.collectors.models import (
    AnimalCollectionFailure,
    CollectionResult,
)
from database.models.koe import Koe
from database.models.melking import Melking


def collect_milk_recordings(
    service,
    herd_id: str,
    koeien: list[Koe],
    continue_on_animal_error: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> CollectionResult[Melking]:
    """Fetch and transform milk recordings for each cow."""
    result: CollectionResult[Melking] = CollectionResult()
    total = len(koeien)
    if progress_callback:
        progress_callback(0, total)

    for processed, koe in enumerate(koeien, start=1):
        try:
            raw_recordings = service.fetch_milk_recordings(herd_id, str(koe.animal_id))
            if not raw_recordings:
                result.skipped_count += 1
            else:
                result.records.extend(
                    transforms.melking_from_recording(raw_recording)
                    for raw_recording in raw_recordings
                )
        except Exception as error:
            result.failures.append(
                _build_failure(koe, "milk_recordings_collection", error)
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
