"""Service helpers for shared authentication and authorization."""

from typing import Iterable, Optional

from werkzeug import security

from database.models.auth import Application, User
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from shared_auth.exceptions import ApplicationAccessDeniedError
from shared_auth.exceptions import ApplicationRoleDeniedError
from shared_auth.exceptions import AuthenticationRequiredError


def hash_password(password: str) -> str:
    """Return a Werkzeug password hash for a raw password."""
    if password.strip() == "":
        raise ValueError("Password is required.")

    return security.generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return whether a raw password matches a Werkzeug hash."""
    if password_hash.strip() == "":
        return False

    return security.check_password_hash(password_hash, password)


class SharedAuthService:
    """Shared authentication and authorization service."""

    def __init__(
        self,
        *,
        users_repository: UsersRepository,
        applications_repository: ApplicationsRepository,
        roles_repository: RolesRepository,
        access_repository: UserApplicationAccessRepository,
    ):
        self.users_repository = users_repository
        self.applications_repository = applications_repository
        self.roles_repository = roles_repository
        self.access_repository = access_repository

    def authenticate_user(self, email_address: str, password: str) -> Optional[User]:
        """Return the active user when credentials are valid."""
        user = self.users_repository.get_user_by_email(email_address)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not verify_password(user.password_hash, password):
            return None

        return user

    def get_active_user(self, user_id: Optional[int]) -> Optional[User]:
        """Return an active user by ID."""
        if user_id is None:
            return None

        user = self.users_repository.get_user_by_id(user_id)
        if user is None:
            return None
        if not user.is_active:
            return None

        return user

    def user_can_access_application(self, user_id: int, application_key: str) -> bool:
        """Return whether a user has active access to an active application."""
        access_context = self._get_active_access_context(user_id, application_key)
        return access_context is not None

    def user_has_application_role(
        self,
        user_id: int,
        application_key: str,
        role_key: str,
    ) -> bool:
        """Return whether a user has one active role in one application."""
        return self.user_has_any_application_role(
            user_id,
            application_key,
            [role_key],
        )

    def user_has_any_application_role(
        self,
        user_id: int,
        application_key: str,
        role_keys: Iterable[str],
    ) -> bool:
        """Return whether a user has at least one active role in an application."""
        wanted_role_keys = {_normalize_key(role_key) for role_key in role_keys}
        if not wanted_role_keys:
            return False

        access_context = self._get_active_access_context(user_id, application_key)
        if access_context is None:
            return False

        access_id = access_context[1]
        roles = self.access_repository.list_user_application_roles(access_id)
        return any(role.is_active and role.key in wanted_role_keys for role in roles)

    def list_accessible_applications(self, user_id: Optional[int]) -> list[Application]:
        """Return active applications the active user can open."""
        user = self.get_active_user(user_id)
        if user is None:
            return []

        return self.access_repository.list_user_applications(
            user.id,
            active_only=True,
        )

    def require_application_access(
        self,
        user_id: Optional[int],
        application_key: str,
    ) -> Application:
        """Return the application or raise when access is not allowed."""
        user = self.get_active_user(user_id)
        if user is None:
            raise AuthenticationRequiredError("An active user session is required.")

        access_context = self._get_active_access_context(user.id, application_key)
        if access_context is None:
            raise ApplicationAccessDeniedError(
                f"User cannot access application: {application_key}"
            )

        return access_context[0]

    def require_application_role(
        self,
        user_id: Optional[int],
        application_key: str,
        role_key: str,
    ) -> Application:
        """Return the application or raise when the required role is missing."""
        application = self.require_any_application_role(
            user_id,
            application_key,
            [role_key],
        )
        return application

    def require_any_application_role(
        self,
        user_id: Optional[int],
        application_key: str,
        role_keys: Iterable[str],
    ) -> Application:
        """Return the application or raise when all required roles are missing."""
        application = self.require_application_access(user_id, application_key)
        if user_id is None:
            raise AuthenticationRequiredError("An active user session is required.")
        if self.user_has_any_application_role(user_id, application_key, role_keys):
            return application

        raise ApplicationRoleDeniedError(
            f"User lacks a required role for application: {application_key}"
        )

    def _get_active_access_context(
        self,
        user_id: int,
        application_key: str,
    ) -> Optional[tuple[Application, int]]:
        user = self.get_active_user(user_id)
        if user is None:
            return None

        application = self.applications_repository.get_application_by_key(
            application_key
        )
        if application is None:
            return None
        if not application.is_active:
            return None

        access = self.access_repository.get_user_application_access(
            user_id=user.id,
            application_id=application.id,
        )
        if access is None:
            return None
        if not access.is_active:
            return None

        return application, access.id


def _normalize_key(value: str) -> str:
    return value.strip().lower()
