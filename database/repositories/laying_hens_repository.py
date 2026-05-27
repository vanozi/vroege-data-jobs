"""Repositories for laying hens registrations."""

from datetime import date, datetime
from typing import Optional, Union

from sqlmodel import select

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import EggRegistration
from database.models.laying_hens import FeedWaterRegistration
from database.models.laying_hens import Flock
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.base_repository import BaseRepository


class FlocksRepository(BaseRepository[Flock]):
    """Repository for laying hen flocks."""

    def __init__(self, session_factory):
        super().__init__(Flock, session_factory)

    def create_flock(self, flock_data: Union[dict[str, object], Flock]) -> Flock:
        """Create a flock after validating active date overlap per house."""
        if isinstance(flock_data, Flock):
            flock_data = flock_data.model_dump()

        normalized_data = self._normalize_model_data(flock_data)
        self.ensure_no_overlapping_active_flock(normalized_data)
        with self.get_session() as session:
            flock = Flock(**normalized_data)
            session.add(flock)
            session.flush()
            session.refresh(flock)
            session.expunge(flock)
            return flock

    def update_flock(
        self,
        flock_id: int,
        flock_data: Union[dict[str, object], Flock],
    ) -> Optional[Flock]:
        """Update a flock after validating active date overlap per house."""
        if isinstance(flock_data, Flock):
            flock_data = flock_data.model_dump()

        normalized_data = self._normalize_model_data(flock_data)
        normalized_data.pop("id", None)
        self.ensure_no_overlapping_active_flock(
            normalized_data,
            exclude_flock_id=flock_id,
        )
        with self.get_session() as session:
            flock = session.get(Flock, flock_id)
            if flock is None:
                return None

            self._update_instance(flock, normalized_data)
            session.add(flock)
            session.flush()
            session.refresh(flock)
            session.expunge(flock)
            return flock

    def get_flock_by_id(self, flock_id: int) -> Optional[Flock]:
        """Return one flock by primary key."""
        with self.get_session() as session:
            flock = session.get(Flock, flock_id)
            if flock is None:
                return None

            session.expunge(flock)
            return flock

    def list_flocks(self, *, house_id: Optional[str] = None) -> list[Flock]:
        """Return flocks ordered by placement date."""
        with self.get_session() as session:
            statement = select(Flock)
            if house_id is not None:
                statement = statement.where(Flock.house_id == house_id)

            statement = statement.order_by(Flock.placement_date.desc())
            flocks = list(session.exec(statement).all())
            for flock in flocks:
                session.expunge(flock)
            return flocks

    def list_active_flocks(
        self,
        *,
        house_id: Optional[str] = None,
        target_date: Optional[date] = None,
    ) -> list[Flock]:
        """Return active flocks, optionally scoped by house/date."""
        with self.get_session() as session:
            statement = self._active_flocks_statement(target_date=target_date)
            if house_id is not None:
                statement = statement.where(Flock.house_id == house_id)

            statement = statement.order_by(Flock.house_id, Flock.placement_date.desc())
            flocks = list(session.exec(statement).all())
            for flock in flocks:
                session.expunge(flock)
            return flocks

    def get_current_active_flock(self, *, house_id: str = "main") -> Optional[Flock]:
        """Return the current active flock for one house."""
        return self.get_active_flock_for_date(date.today(), house_id=house_id)

    def get_active_flock_for_date(
        self,
        target_date: date,
        *,
        house_id: str = "main",
    ) -> Optional[Flock]:
        """Return the active flock for a house/date."""
        with self.get_session() as session:
            statement = (
                self._active_flocks_statement(target_date=target_date)
                .where(Flock.house_id == house_id)
                .order_by(Flock.placement_date.desc())
            )
            flock = session.exec(statement).first()
            if flock is None:
                return None

            session.expunge(flock)
            return flock

    def archive_flock(self, flock_id: int) -> Optional[Flock]:
        """Archive a flock so it is no longer active."""
        with self.get_session() as session:
            flock = session.get(Flock, flock_id)
            if flock is None:
                return None

            flock.is_active = False
            flock.archived_at = datetime.utcnow()
            session.add(flock)
            session.flush()
            session.refresh(flock)
            session.expunge(flock)
            return flock

    def end_flock(self, flock_id: int, end_date: date) -> Optional[Flock]:
        """Set the date on which a flock leaves the house."""
        with self.get_session() as session:
            flock = session.get(Flock, flock_id)
            if flock is None:
                return None

            if end_date < flock.placement_date:
                raise ValueError("Flock end date cannot be before placement date.")

            flock.end_date = end_date
            session.add(flock)
            session.flush()
            session.refresh(flock)
            session.expunge(flock)
            return flock

    def delete_flock(self, flock_id: int) -> bool:
        """Delete a flock only when no registrations are linked."""
        if self._has_linked_registrations(flock_id):
            raise ValueError("Cannot delete a flock with linked registrations.")

        return self.delete(flock_id)

    def ensure_no_overlapping_active_flock(
        self,
        flock_data: dict[str, object],
        *,
        exclude_flock_id: Optional[int] = None,
    ) -> None:
        """Raise when an active flock overlaps another active flock in a house."""
        candidate = Flock.model_validate(flock_data)
        if not candidate.is_active or candidate.archived_at is not None:
            return

        candidate_end_date = candidate.end_date or date.max
        if candidate_end_date < candidate.placement_date:
            raise ValueError("Flock end date cannot be before placement date.")

        with self.get_session() as session:
            statement = select(Flock).where(
                Flock.house_id == candidate.house_id,
                Flock.is_active.is_(True),
                Flock.archived_at.is_(None),
            )
            if exclude_flock_id is not None:
                statement = statement.where(Flock.id != exclude_flock_id)

            existing_flocks = session.exec(statement).all()
            for existing_flock in existing_flocks:
                existing_end_date = existing_flock.end_date or date.max
                if (
                    existing_flock.placement_date <= candidate_end_date
                    and candidate.placement_date <= existing_end_date
                ):
                    raise ValueError(
                        "Active flock date range overlaps with another flock "
                        f"in house {candidate.house_id}."
                    )

    def _has_linked_registrations(self, flock_id: int) -> bool:
        with self.get_session() as session:
            daily_registration = session.exec(
                select(DailyLayingRegistration.id)
                .where(DailyLayingRegistration.flock_id == flock_id)
                .limit(1)
            ).first()
            if daily_registration is not None:
                return True

            egg_registration = session.exec(
                select(EggRegistration.id)
                .where(EggRegistration.flock_id == flock_id)
                .limit(1)
            ).first()
            if egg_registration is not None:
                return True

            feed_water_registration = session.exec(
                select(FeedWaterRegistration.id)
                .where(FeedWaterRegistration.flock_id == flock_id)
                .limit(1)
            ).first()
            if feed_water_registration is not None:
                return True

            dead_hen_registration = session.exec(
                select(DeadHenRegistration.id)
                .where(DeadHenRegistration.flock_id == flock_id)
                .limit(1)
            ).first()
            if dead_hen_registration is not None:
                return True

            outside_nest_round = session.exec(
                select(OutsideNestEggRound.id)
                .where(OutsideNestEggRound.flock_id == flock_id)
                .limit(1)
            ).first()
            return outside_nest_round is not None

    def _active_flocks_statement(self, *, target_date: Optional[date] = None):
        statement = select(Flock).where(
            Flock.is_active.is_(True),
            Flock.archived_at.is_(None),
        )
        if target_date is None:
            return statement

        return statement.where(
            Flock.placement_date <= target_date,
            (Flock.end_date.is_(None)) | (Flock.end_date >= target_date),
        )


class EggRegistrationsRepository(BaseRepository[EggRegistration]):
    """Repository for egg registrations."""

    def __init__(self, session_factory):
        super().__init__(EggRegistration, session_factory)

    def upsert_egg_registration(
        self,
        registration_data: Union[dict[str, object], EggRegistration],
    ) -> EggRegistration:
        """Insert or update an egg registration by house and date."""
        if isinstance(registration_data, EggRegistration):
            registration_data = registration_data.model_dump()

        self._ensure_flock_id(registration_data)
        return self.upsert(
            registration_data,
            unique_fields=["house_id", "registration_date"],
        )

    def update_egg_registration(
        self,
        registration_id: int,
        registration_data: Union[dict[str, object], EggRegistration],
    ) -> Optional[EggRegistration]:
        """Update an egg registration by primary key."""
        if isinstance(registration_data, EggRegistration):
            registration_data = registration_data.model_dump()

        normalized_data = self._normalize_model_data(registration_data)
        self._ensure_flock_id(normalized_data)
        normalized_data.pop("id", None)
        with self.get_session() as session:
            registration = session.get(EggRegistration, registration_id)
            if registration is None:
                return None

            self._update_instance(registration, normalized_data)
            session.add(registration)
            session.flush()
            session.refresh(registration)
            session.expunge(registration)
            return registration

    def get_egg_registration_by_id(
        self,
        registration_id: int,
    ) -> Optional[EggRegistration]:
        """Return one egg registration by primary key."""
        with self.get_session() as session:
            registration = session.get(EggRegistration, registration_id)
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def get_by_house_and_date(
        self,
        registration_date: date,
        *,
        house_id: str = "main",
    ) -> Optional[EggRegistration]:
        """Return one egg registration by house/date."""
        with self.get_session() as session:
            statement = select(EggRegistration).where(
                EggRegistration.house_id == house_id,
                EggRegistration.registration_date == registration_date,
            )
            registration = session.exec(statement).first()
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def list_recent(self, *, limit: int = 7) -> list[EggRegistration]:
        """Return recent egg registrations."""
        with self.get_session() as session:
            statement = (
                select(EggRegistration)
                .order_by(EggRegistration.registration_date.desc())
                .limit(limit)
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def list_between(
        self,
        start_date: date,
        end_date: date,
        *,
        house_id: str = "main",
    ) -> list[EggRegistration]:
        """Return egg registrations for an inclusive date range."""
        with self.get_session() as session:
            statement = (
                select(EggRegistration)
                .where(
                    EggRegistration.house_id == house_id,
                    EggRegistration.registration_date >= start_date,
                    EggRegistration.registration_date <= end_date,
                )
                .order_by(EggRegistration.registration_date.asc())
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def list_all(self) -> list[EggRegistration]:
        """Return all egg registrations ordered by date."""
        with self.get_session() as session:
            statement = select(EggRegistration).order_by(
                EggRegistration.registration_date.asc(),
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def delete_egg_registration(self, registration_id: int) -> bool:
        """Delete one egg registration by primary key."""
        return self.delete(registration_id)

    def _ensure_flock_id(self, registration_data: dict[str, object]) -> None:
        if registration_data.get("flock_id") is None:
            raise ValueError("Egg registration requires a flock_id.")


class FeedWaterRegistrationsRepository(BaseRepository[FeedWaterRegistration]):
    """Repository for feed and water registrations."""

    def __init__(self, session_factory):
        super().__init__(FeedWaterRegistration, session_factory)

    def upsert_feed_water_registration(
        self,
        registration_data: Union[dict[str, object], FeedWaterRegistration],
    ) -> FeedWaterRegistration:
        """Insert or update a feed/water registration by house and date."""
        if isinstance(registration_data, FeedWaterRegistration):
            registration_data = registration_data.model_dump()

        self._ensure_flock_id(registration_data)
        return self.upsert(
            registration_data,
            unique_fields=["house_id", "registration_date"],
        )

    def update_feed_water_registration(
        self,
        registration_id: int,
        registration_data: Union[dict[str, object], FeedWaterRegistration],
    ) -> Optional[FeedWaterRegistration]:
        """Update a feed/water registration by primary key."""
        if isinstance(registration_data, FeedWaterRegistration):
            registration_data = registration_data.model_dump()

        normalized_data = self._normalize_model_data(registration_data)
        self._ensure_flock_id(normalized_data)
        normalized_data.pop("id", None)
        with self.get_session() as session:
            registration = session.get(FeedWaterRegistration, registration_id)
            if registration is None:
                return None

            self._update_instance(registration, normalized_data)
            session.add(registration)
            session.flush()
            session.refresh(registration)
            session.expunge(registration)
            return registration

    def get_feed_water_registration_by_id(
        self,
        registration_id: int,
    ) -> Optional[FeedWaterRegistration]:
        """Return one feed/water registration by primary key."""
        with self.get_session() as session:
            registration = session.get(FeedWaterRegistration, registration_id)
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def get_by_house_and_date(
        self,
        registration_date: date,
        *,
        house_id: str = "main",
    ) -> Optional[FeedWaterRegistration]:
        """Return one feed/water registration by house/date."""
        with self.get_session() as session:
            statement = select(FeedWaterRegistration).where(
                FeedWaterRegistration.house_id == house_id,
                FeedWaterRegistration.registration_date == registration_date,
            )
            registration = session.exec(statement).first()
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def list_recent(self, *, limit: int = 7) -> list[FeedWaterRegistration]:
        """Return recent feed/water registrations."""
        with self.get_session() as session:
            statement = (
                select(FeedWaterRegistration)
                .order_by(FeedWaterRegistration.registration_date.desc())
                .limit(limit)
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def list_between(
        self,
        start_date: date,
        end_date: date,
        *,
        house_id: str = "main",
    ) -> list[FeedWaterRegistration]:
        """Return feed/water registrations for an inclusive date range."""
        with self.get_session() as session:
            statement = (
                select(FeedWaterRegistration)
                .where(
                    FeedWaterRegistration.house_id == house_id,
                    FeedWaterRegistration.registration_date >= start_date,
                    FeedWaterRegistration.registration_date <= end_date,
                )
                .order_by(FeedWaterRegistration.registration_date.asc())
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def list_all(self) -> list[FeedWaterRegistration]:
        """Return all feed/water registrations ordered by date."""
        with self.get_session() as session:
            statement = select(FeedWaterRegistration).order_by(
                FeedWaterRegistration.registration_date.asc(),
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def delete_feed_water_registration(self, registration_id: int) -> bool:
        """Delete one feed/water registration by primary key."""
        return self.delete(registration_id)

    def _ensure_flock_id(self, registration_data: dict[str, object]) -> None:
        if registration_data.get("flock_id") is None:
            raise ValueError("Feed/water registration requires a flock_id.")


class DailyLayingRegistrationsRepository(BaseRepository[DailyLayingRegistration]):
    """Repository for daily laying calendar registrations."""

    def __init__(self, session_factory):
        super().__init__(DailyLayingRegistration, session_factory)

    def upsert_daily_registration(
        self,
        registration_data: Union[dict[str, object], DailyLayingRegistration],
    ) -> DailyLayingRegistration:
        """Insert or update a daily registration by house and date."""
        if isinstance(registration_data, DailyLayingRegistration):
            registration_data = registration_data.model_dump()

        self._ensure_flock_id(registration_data)
        return self.upsert(
            registration_data,
            unique_fields=["house_id", "registration_date"],
        )

    def update_daily_registration(
        self,
        registration_id: int,
        registration_data: Union[dict[str, object], DailyLayingRegistration],
    ) -> Optional[DailyLayingRegistration]:
        """Update a daily registration by primary key."""
        if isinstance(registration_data, DailyLayingRegistration):
            registration_data = registration_data.model_dump()

        normalized_data = self._normalize_model_data(registration_data)
        self._ensure_flock_id(normalized_data)
        normalized_data.pop("id", None)
        with self.get_session() as session:
            registration = session.get(DailyLayingRegistration, registration_id)
            if registration is None:
                return None

            self._update_instance(registration, normalized_data)
            session.add(registration)
            session.flush()
            session.refresh(registration)
            session.expunge(registration)
            return registration

    def list_recent(self, *, limit: int = 7) -> list[DailyLayingRegistration]:
        """Return recent daily registrations."""
        with self.get_session() as session:
            statement = (
                select(DailyLayingRegistration)
                .order_by(DailyLayingRegistration.registration_date.desc())
                .limit(limit)
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def _ensure_flock_id(self, registration_data: dict[str, object]) -> None:
        if registration_data.get("flock_id") is None:
            raise ValueError("Daily laying registration requires a flock_id.")

    def list_all(self) -> list[DailyLayingRegistration]:
        """Return all daily registrations ordered by date."""
        with self.get_session() as session:
            statement = select(DailyLayingRegistration).order_by(
                DailyLayingRegistration.registration_date.asc(),
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def get_daily_registration_by_id(
        self,
        registration_id: int,
    ) -> Optional[DailyLayingRegistration]:
        """Return one daily registration by primary key."""
        with self.get_session() as session:
            registration = session.get(DailyLayingRegistration, registration_id)
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def get_by_house_and_date(
        self,
        registration_date: date,
        *,
        house_id: str = "main",
    ) -> Optional[DailyLayingRegistration]:
        """Return one daily registration by house/date."""
        with self.get_session() as session:
            statement = select(DailyLayingRegistration).where(
                DailyLayingRegistration.house_id == house_id,
                DailyLayingRegistration.registration_date == registration_date,
            )
            registration = session.exec(statement).first()
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def list_between(
        self,
        start_date: date,
        end_date: date,
        *,
        house_id: str = "main",
    ) -> list[DailyLayingRegistration]:
        """Return daily registrations for an inclusive date range."""
        with self.get_session() as session:
            statement = (
                select(DailyLayingRegistration)
                .where(
                    DailyLayingRegistration.house_id == house_id,
                    DailyLayingRegistration.registration_date >= start_date,
                    DailyLayingRegistration.registration_date <= end_date,
                )
                .order_by(DailyLayingRegistration.registration_date.asc())
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations


class DeadHenRegistrationsRepository(BaseRepository[DeadHenRegistration]):
    """Repository for dead hen registrations."""

    def __init__(self, session_factory):
        super().__init__(DeadHenRegistration, session_factory)

    def create_dead_hen_registration(
        self,
        registration_data: Union[dict[str, object], DeadHenRegistration],
    ) -> DeadHenRegistration:
        """Create a dead hen registration."""
        if isinstance(registration_data, DeadHenRegistration):
            registration_data = registration_data.model_dump()

        normalized_data = self._normalize_model_data(registration_data)
        if normalized_data.get("flock_id") is None:
            raise ValueError("Dead hen registration requires a flock_id.")
        with self.get_session() as session:
            registration = DeadHenRegistration(**normalized_data)
            session.add(registration)
            session.flush()
            session.refresh(registration)
            session.expunge(registration)
            return registration

    def get_dead_hen_registration_by_id(
        self,
        registration_id: int,
    ) -> Optional[DeadHenRegistration]:
        """Return one dead hen registration by primary key."""
        with self.get_session() as session:
            registration = session.get(DeadHenRegistration, registration_id)
            if registration is None:
                return None

            session.expunge(registration)
            return registration

    def delete_dead_hen_registration(self, registration_id: int) -> bool:
        """Delete one dead hen registration by primary key."""
        return self.delete(registration_id)

    def list_recent(self, *, limit: int = 10) -> list[DeadHenRegistration]:
        """Return recent dead hen registrations."""
        with self.get_session() as session:
            statement = (
                select(DeadHenRegistration)
                .order_by(DeadHenRegistration.found_at.desc())
                .limit(limit)
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def list_all(self) -> list[DeadHenRegistration]:
        """Return all dead hen registrations ordered by found time."""
        with self.get_session() as session:
            statement = select(DeadHenRegistration).order_by(
                DeadHenRegistration.found_at.asc(),
            )
            registrations = list(session.exec(statement).all())
            for registration in registrations:
                session.expunge(registration)
            return registrations

    def count_for_date(
        self,
        registration_date: date,
        *,
        house_id: str = "main",
    ) -> int:
        """Return dead hen count for one house/date."""
        day_start = datetime.combine(registration_date, datetime.min.time())
        day_end = datetime.combine(registration_date, datetime.max.time())
        with self.get_session() as session:
            statement = select(DeadHenRegistration).where(
                DeadHenRegistration.house_id == house_id,
                DeadHenRegistration.found_at >= day_start,
                DeadHenRegistration.found_at <= day_end,
            )
            registrations = session.exec(statement).all()
            return sum(registration.count for registration in registrations)


class OutsideNestEggRoundsRepository(BaseRepository[OutsideNestEggRound]):
    """Repository for outside-nest egg rounds."""

    def __init__(self, session_factory):
        super().__init__(OutsideNestEggRound, session_factory)

    def create_outside_nest_egg_round(
        self,
        round_data: Union[dict[str, object], OutsideNestEggRound],
    ) -> OutsideNestEggRound:
        """Create an outside-nest egg round."""
        if isinstance(round_data, OutsideNestEggRound):
            round_data = round_data.model_dump()

        normalized_data = self._normalize_model_data(round_data)
        if normalized_data.get("flock_id") is None:
            raise ValueError("Outside-nest egg round requires a flock_id.")
        with self.get_session() as session:
            egg_round = OutsideNestEggRound(**normalized_data)
            session.add(egg_round)
            session.flush()
            session.refresh(egg_round)
            session.expunge(egg_round)
            return egg_round

    def get_outside_nest_egg_round_by_id(
        self,
        round_id: int,
    ) -> Optional[OutsideNestEggRound]:
        """Return one outside-nest egg round by primary key."""
        with self.get_session() as session:
            egg_round = session.get(OutsideNestEggRound, round_id)
            if egg_round is None:
                return None

            session.expunge(egg_round)
            return egg_round

    def delete_outside_nest_egg_round(self, round_id: int) -> bool:
        """Delete one outside-nest egg round by primary key."""
        return self.delete(round_id)

    def list_recent(self, *, limit: int = 10) -> list[OutsideNestEggRound]:
        """Return recent outside-nest egg rounds."""
        with self.get_session() as session:
            statement = (
                select(OutsideNestEggRound)
                .order_by(OutsideNestEggRound.round_at.desc())
                .limit(limit)
            )
            rounds = list(session.exec(statement).all())
            for egg_round in rounds:
                session.expunge(egg_round)
            return rounds

    def list_all(self) -> list[OutsideNestEggRound]:
        """Return all outside-nest egg rounds ordered by round time."""
        with self.get_session() as session:
            statement = select(OutsideNestEggRound).order_by(
                OutsideNestEggRound.round_at.asc(),
            )
            rounds = list(session.exec(statement).all())
            for egg_round in rounds:
                session.expunge(egg_round)
            return rounds

    def count_for_date(
        self,
        registration_date: date,
        *,
        house_id: str = "main",
    ) -> int:
        """Return outside-nest egg count for one house/date."""
        day_start = datetime.combine(registration_date, datetime.min.time())
        day_end = datetime.combine(registration_date, datetime.max.time())
        with self.get_session() as session:
            statement = select(OutsideNestEggRound).where(
                OutsideNestEggRound.house_id == house_id,
                OutsideNestEggRound.round_at >= day_start,
                OutsideNestEggRound.round_at <= day_end,
            )
            rounds = session.exec(statement).all()
            return sum(egg_round.egg_count for egg_round in rounds)
