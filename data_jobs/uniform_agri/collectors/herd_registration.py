from datetime import datetime
from typing import Optional

from database.models.koe import Koe
from data_jobs.uniform_agri import transforms
from data_jobs.uniform_agri.collectors.models import (
    AnimalCollectionFailure,
    CollectionResult,
)

EXCLUDED_CALF_NAME_PREFIXES = ("VAARSKALF", "STIERKALF")


def collect_herd_registration(
    service,
    herd_id: str,
    date: Optional[datetime] = None,
    continue_on_record_error: bool = True,
) -> CollectionResult[Koe]:
    """Fetch herd registration and return active cows, excluding calf records."""
    result: CollectionResult[Koe] = CollectionResult()
    raw_records = service.fetch_herd_registration(herd_id, date)

    for raw_record in raw_records:
        if is_excluded_calf_record(raw_record):
            continue

        try:
            result.records.append(transforms.koe_from_registration(raw_record))
        except Exception as error:
            result.failures.append(
                _build_failure(raw_record, "herd_registration_transform", error)
            )
            if not continue_on_record_error:
                raise

    return result


def is_excluded_calf_record(raw_record: dict) -> bool:
    """Return whether a herd registration item should be skipped as calf data."""
    return is_excluded_calf_name(raw_record.get("name"))


def is_excluded_calf_name(name: Optional[str]) -> bool:
    """Return whether an animal name matches Uniform Agri calf placeholders."""
    if not name:
        return False

    normalized_name = name.upper()
    return normalized_name.startswith(EXCLUDED_CALF_NAME_PREFIXES)


def _build_failure(
    raw_record: dict,
    stage: str,
    error: Exception,
) -> AnimalCollectionFailure:
    return AnimalCollectionFailure(
        animal_id=str(raw_record.get("animalId", "")),
        animal_name=raw_record.get("name"),
        stage=stage,
        error_message=str(error),
    )
