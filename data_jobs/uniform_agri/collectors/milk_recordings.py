from database.models.koe import Koe
from database.models.melking import Melking
from data_jobs.uniform_agri import transforms
from data_jobs.uniform_agri.collectors.models import (
    AnimalCollectionFailure,
    CollectionResult,
)


def collect_milk_recordings(
    service,
    herd_id: str,
    koeien: list[Koe],
    continue_on_animal_error: bool = True,
) -> CollectionResult[Melking]:
    """Fetch and transform milk recordings for each cow."""
    result: CollectionResult[Melking] = CollectionResult()

    for koe in koeien:
        try:
            raw_recordings = service.fetch_milk_recordings(herd_id, str(koe.animal_id))
            if not raw_recordings:
                result.skipped_count += 1
                continue

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
