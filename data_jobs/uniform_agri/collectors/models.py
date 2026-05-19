from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar


CollectedItem = TypeVar("CollectedItem")


@dataclass(frozen=True)
class AnimalCollectionFailure:
    animal_id: str
    animal_name: Optional[str]
    stage: str
    error_message: str


@dataclass
class CollectionResult(Generic[CollectedItem]):
    records: list[CollectedItem] = field(default_factory=list)
    failures: list[AnimalCollectionFailure] = field(default_factory=list)
    skipped_count: int = 0

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def record_count(self) -> int:
        return len(self.records)
