"""Repositories for shared authentication and authorization."""

from typing import Optional, Union

from sqlmodel import select

from database.models.auth import Application, Role, User, UserApplicationAccess
from database.models.auth import UserApplicationRole
from database.repositories.base_repository import BaseRepository


class UsersRepository(BaseRepository[User]):
    """Repository for shared users."""

    def __init__(self, session_factory):
        super().__init__(User, session_factory)

    def create_user(self, user_data: Union[dict[str, object], User]) -> User:
        """Create a user with normalized email address."""
        normalized_data = self._normalized_user_data(
            user_data,
            require_password_hash=True,
        )
        with self.get_session() as session:
            user = User(**normalized_data)
            session.add(user)
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user

    def update_user(
        self,
        user_id: int,
        user_data: Union[dict[str, object], User],
    ) -> Optional[User]:
        """Update a user by primary key."""
        normalized_data = self._normalized_user_data(
            user_data,
            require_password_hash=False,
        )
        normalized_data.pop("id", None)
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user is None:
                return None

            self._update_instance(user, normalized_data)
            session.add(user)
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Return one user by primary key."""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user is None:
                return None

            session.expunge(user)
            return user

    def get_user_by_email(self, email_address: str) -> Optional[User]:
        """Return one user by normalized email address."""
        normalized_email = _normalize_key(email_address)
        with self.get_session() as session:
            statement = select(User).where(User.email_address == normalized_email)
            user = session.exec(statement).first()
            if user is None:
                return None

            session.expunge(user)
            return user

    def list_users(self) -> list[User]:
        """Return users ordered by email address."""
        with self.get_session() as session:
            users = list(session.exec(select(User).order_by(User.email_address)).all())
            for user in users:
                session.expunge(user)
            return users

    def set_user_active(self, user_id: int, is_active: bool) -> Optional[User]:
        """Enable or disable one user."""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user is None:
                return None

            user.is_active = is_active
            session.add(user)
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user

    def set_user_password_hash(
        self,
        user_id: int,
        password_hash: str,
    ) -> Optional[User]:
        """Replace a user's password hash."""
        if password_hash.strip() == "":
            raise ValueError("Password hash is required.")

        with self.get_session() as session:
            user = session.get(User, user_id)
            if user is None:
                return None

            user.password_hash = password_hash
            session.add(user)
            session.flush()
            session.refresh(user)
            session.expunge(user)
            return user

    def _normalized_user_data(
        self,
        user_data: Union[dict[str, object], User],
        *,
        require_password_hash: bool,
    ) -> dict[str, object]:
        if isinstance(user_data, User):
            user_data = user_data.model_dump()

        normalized_data = dict(user_data)
        if "email_address" in normalized_data:
            normalized_data["email_address"] = _normalize_key(
                str(normalized_data.get("email_address", ""))
            )
        if normalized_data.get("email_address") == "":
            raise ValueError("Email address is required.")
        if (
            require_password_hash
            and str(normalized_data.get("password_hash", "")).strip() == ""
        ):
            raise ValueError("Password hash is required.")
        if (
            "password_hash" in normalized_data
            and str(normalized_data["password_hash"]).strip() == ""
        ):
            raise ValueError("Password hash is required.")

        return normalized_data


class ApplicationsRepository(BaseRepository[Application]):
    """Repository for application registry records."""

    def __init__(self, session_factory):
        super().__init__(Application, session_factory)

    def create_application(
        self,
        application_data: Union[dict[str, object], Application],
    ) -> Application:
        """Create an application with normalized key."""
        normalized_data = self._normalized_application_data(application_data)
        with self.get_session() as session:
            application = Application(**normalized_data)
            session.add(application)
            session.flush()
            session.refresh(application)
            session.expunge(application)
            return application

    def update_application(
        self,
        application_id: int,
        application_data: Union[dict[str, object], Application],
    ) -> Optional[Application]:
        """Update an application by primary key."""
        normalized_data = self._normalized_application_data(
            application_data,
            require_required_fields=False,
        )
        normalized_data.pop("id", None)
        with self.get_session() as session:
            application = session.get(Application, application_id)
            if application is None:
                return None

            self._update_instance(application, normalized_data)
            session.add(application)
            session.flush()
            session.refresh(application)
            session.expunge(application)
            return application

    def get_application_by_key(self, key: str) -> Optional[Application]:
        """Return one application by normalized key."""
        normalized_key = _normalize_key(key)
        with self.get_session() as session:
            statement = select(Application).where(Application.key == normalized_key)
            application = session.exec(statement).first()
            if application is None:
                return None

            session.expunge(application)
            return application

    def list_applications(
        self,
        *,
        active_only: bool = False,
    ) -> list[Application]:
        """Return applications ordered for portal display."""
        with self.get_session() as session:
            statement = select(Application)
            if active_only:
                statement = statement.where(Application.is_active.is_(True))

            statement = statement.order_by(
                Application.display_order.asc(),
                Application.name.asc(),
            )
            applications = list(session.exec(statement).all())
            for application in applications:
                session.expunge(application)
            return applications

    def _normalized_application_data(
        self,
        application_data: Union[dict[str, object], Application],
        *,
        require_required_fields: bool = True,
    ) -> dict[str, object]:
        if isinstance(application_data, Application):
            application_data = application_data.model_dump()

        normalized_data = dict(application_data)
        if "key" in normalized_data:
            normalized_data["key"] = _normalize_key(str(normalized_data.get("key", "")))
        if normalized_data.get("key") == "":
            raise ValueError("Application key is required.")
        if (
            require_required_fields
            and str(normalized_data.get("key", "")).strip() == ""
        ):
            raise ValueError("Application key is required.")
        if (
            require_required_fields
            and str(normalized_data.get("name", "")).strip() == ""
        ):
            raise ValueError("Application name is required.")
        if "name" in normalized_data and str(normalized_data["name"]).strip() == "":
            raise ValueError("Application name is required.")
        if (
            require_required_fields
            and str(normalized_data.get("url", "")).strip() == ""
        ):
            raise ValueError("Application URL is required.")
        if "url" in normalized_data and str(normalized_data["url"]).strip() == "":
            raise ValueError("Application URL is required.")

        return normalized_data


class RolesRepository(BaseRepository[Role]):
    """Repository for role definitions."""

    def __init__(self, session_factory):
        super().__init__(Role, session_factory)

    def create_role(self, role_data: Union[dict[str, object], Role]) -> Role:
        """Create a role with normalized key."""
        normalized_data = self._normalized_role_data(role_data)
        with self.get_session() as session:
            role = Role(**normalized_data)
            session.add(role)
            session.flush()
            session.refresh(role)
            session.expunge(role)
            return role

    def update_role(
        self,
        role_id: int,
        role_data: Union[dict[str, object], Role],
    ) -> Optional[Role]:
        """Update a role by primary key."""
        normalized_data = self._normalized_role_data(
            role_data,
            require_required_fields=False,
        )
        normalized_data.pop("id", None)
        with self.get_session() as session:
            role = session.get(Role, role_id)
            if role is None:
                return None

            self._update_instance(role, normalized_data)
            session.add(role)
            session.flush()
            session.refresh(role)
            session.expunge(role)
            return role

    def get_role_by_key(self, key: str) -> Optional[Role]:
        """Return one role by normalized key."""
        normalized_key = _normalize_key(key)
        with self.get_session() as session:
            statement = select(Role).where(Role.key == normalized_key)
            role = session.exec(statement).first()
            if role is None:
                return None

            session.expunge(role)
            return role

    def list_roles(self, *, active_only: bool = False) -> list[Role]:
        """Return roles ordered by key."""
        with self.get_session() as session:
            statement = select(Role)
            if active_only:
                statement = statement.where(Role.is_active.is_(True))

            roles = list(session.exec(statement.order_by(Role.key)).all())
            for role in roles:
                session.expunge(role)
            return roles

    def _normalized_role_data(
        self,
        role_data: Union[dict[str, object], Role],
        *,
        require_required_fields: bool = True,
    ) -> dict[str, object]:
        if isinstance(role_data, Role):
            role_data = role_data.model_dump()

        normalized_data = dict(role_data)
        if "key" in normalized_data:
            normalized_data["key"] = _normalize_key(str(normalized_data.get("key", "")))
        if normalized_data.get("key") == "":
            raise ValueError("Role key is required.")
        if (
            require_required_fields
            and str(normalized_data.get("key", "")).strip() == ""
        ):
            raise ValueError("Role key is required.")
        if (
            require_required_fields
            and str(normalized_data.get("name", "")).strip() == ""
        ):
            raise ValueError("Role name is required.")
        if "name" in normalized_data and str(normalized_data["name"]).strip() == "":
            raise ValueError("Role name is required.")

        return normalized_data


class UserApplicationAccessRepository(BaseRepository[UserApplicationAccess]):
    """Repository for application access grants and role assignments."""

    def __init__(self, session_factory):
        super().__init__(UserApplicationAccess, session_factory)

    def grant_application_access(
        self,
        *,
        user_id: int,
        application_id: int,
        is_active: bool = True,
    ) -> UserApplicationAccess:
        """Create or reactivate access for one user/application pair."""
        with self.get_session() as session:
            access = self._find_access(session, user_id, application_id)
            if access is None:
                access = UserApplicationAccess(
                    user_id=user_id,
                    application_id=application_id,
                    is_active=is_active,
                )
                session.add(access)
            else:
                access.is_active = is_active

            session.flush()
            session.refresh(access)
            session.expunge(access)
            return access

    def update_application_access(
        self,
        access_id: int,
        *,
        is_active: bool,
    ) -> Optional[UserApplicationAccess]:
        """Update active status for one access grant."""
        with self.get_session() as session:
            access = session.get(UserApplicationAccess, access_id)
            if access is None:
                return None

            access.is_active = is_active
            session.add(access)
            session.flush()
            session.refresh(access)
            session.expunge(access)
            return access

    def revoke_application_access(
        self, access_id: int
    ) -> Optional[UserApplicationAccess]:
        """Deactivate an access grant without deleting historical role rows."""
        return self.update_application_access(access_id, is_active=False)

    def get_user_application_access(
        self,
        *,
        user_id: int,
        application_id: int,
    ) -> Optional[UserApplicationAccess]:
        """Return one access grant by user/application."""
        with self.get_session() as session:
            access = self._find_access(session, user_id, application_id)
            if access is None:
                return None

            session.expunge(access)
            return access

    def list_user_applications(
        self,
        user_id: int,
        *,
        active_only: bool = False,
    ) -> list[Application]:
        """Return applications a user has access rows for."""
        with self.get_session() as session:
            statement = (
                select(Application)
                .join(
                    UserApplicationAccess,
                    UserApplicationAccess.application_id == Application.id,
                )
                .where(UserApplicationAccess.user_id == user_id)
            )
            if active_only:
                statement = statement.where(
                    UserApplicationAccess.is_active.is_(True),
                    Application.is_active.is_(True),
                )

            statement = statement.order_by(
                Application.display_order.asc(),
                Application.name.asc(),
            )
            applications = list(session.exec(statement).all())
            for application in applications:
                session.expunge(application)
            return applications

    def grant_application_role(
        self,
        *,
        access_id: int,
        role_id: int,
    ) -> UserApplicationRole:
        """Assign a role to an access grant, idempotently."""
        with self.get_session() as session:
            role_assignment = self._find_role_assignment(session, access_id, role_id)
            if role_assignment is None:
                role_assignment = UserApplicationRole(
                    user_application_access_id=access_id,
                    role_id=role_id,
                )
                session.add(role_assignment)

            session.flush()
            session.refresh(role_assignment)
            session.expunge(role_assignment)
            return role_assignment

    def revoke_application_role(self, *, access_id: int, role_id: int) -> bool:
        """Delete one role assignment from an access grant."""
        with self.get_session() as session:
            role_assignment = self._find_role_assignment(session, access_id, role_id)
            if role_assignment is None:
                return False

            session.delete(role_assignment)
            return True

    def list_user_application_roles(self, access_id: int) -> list[Role]:
        """Return roles assigned to one access grant."""
        with self.get_session() as session:
            statement = (
                select(Role)
                .join(UserApplicationRole, UserApplicationRole.role_id == Role.id)
                .where(UserApplicationRole.user_application_access_id == access_id)
                .order_by(Role.key.asc())
            )
            roles = list(session.exec(statement).all())
            for role in roles:
                session.expunge(role)
            return roles

    def _find_access(
        self,
        session,
        user_id: int,
        application_id: int,
    ) -> Optional[UserApplicationAccess]:
        statement = select(UserApplicationAccess).where(
            UserApplicationAccess.user_id == user_id,
            UserApplicationAccess.application_id == application_id,
        )
        return session.exec(statement).first()

    def _find_role_assignment(
        self,
        session,
        access_id: int,
        role_id: int,
    ) -> Optional[UserApplicationRole]:
        statement = select(UserApplicationRole).where(
            UserApplicationRole.user_application_access_id == access_id,
            UserApplicationRole.role_id == role_id,
        )
        return session.exec(statement).first()


def _normalize_key(value: str) -> str:
    return value.strip().lower()
