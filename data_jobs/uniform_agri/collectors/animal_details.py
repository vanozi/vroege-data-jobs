from database.models.koe import Koe
from database.models.koe import KoeDetail
from data_jobs.uniform_agri import transforms
from data_jobs.uniform_agri.collectors.models import (
    AnimalCollectionFailure,
    CollectionResult,
)


def collect_animal_details(
    service,
    herd_id: str,
    koeien: list[Koe],
    continue_on_animal_error: bool = True,
) -> CollectionResult[KoeDetail]:
    """Fetch and transform actual-tab details for each cow."""
    result: CollectionResult[KoeDetail] = CollectionResult()

    for koe in koeien:
        try:
            raw_detail = service.fetch_animal_actual(herd_id, str(koe.animal_id))
            result.records.append(transforms.koe_detail_from_actual(raw_detail))
        except Exception as error:
            result.failures.append(
                _build_failure(koe, "animal_actual_collection", error)
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
