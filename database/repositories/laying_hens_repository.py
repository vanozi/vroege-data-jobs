"""Repositories for laying hens registrations."""

from datetime import date, datetime
from typing import Optional, Union

from sqlmodel import select

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.base_repository import BaseRepository


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
