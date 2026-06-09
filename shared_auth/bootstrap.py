"""Bootstrap core shared authentication data."""

from dataclasses import dataclass, field
from typing import Optional

from database.models.auth import Application, Role, User
from database.repositories.auth_repository import ApplicationsRepository
from database.repositories.auth_repository import RolesRepository
from database.repositories.auth_repository import UserApplicationAccessRepository
from database.repositories.auth_repository import UsersRepository
from shared_auth import service


@dataclass(frozen=True)
class CoreApplication:
    """Core application registry seed data."""

    key: str
    name: str
    url: str
    category: str
    description: str
    display_order: int


@dataclass(frozen=True)
class CoreRole:
    """Core role seed data."""

    key: str
    name: str
    description: str


@dataclass(frozen=True)
class BootstrapAdminConfig:
    """Optional first-admin bootstrap input."""

    username: Optional[str] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    reset_existing_password: bool = False


@dataclass
class BootstrapResult:
    """Summary of shared auth bootstrap work."""

    applications_seeded: int = 0
    roles_seeded: int = 0
    admin_user_created: bool = False
    admin_user_updated: bool = False
    admin_access_grants: int = 0
    admin_role_grants: int = 0
    messages: list[str] = field(default_factory=list)


CORE_APPLICATIONS = [
    CoreApplication(
        key="kippen",
        name="Kippen",
        url="/kippen",
        category="app",
        description="Leghennenregistratie en weekoverzichten.",
        display_order=10,
    ),
    CoreApplication(
        key="dashboard_kippen",
        name="Kippen dashboard",
        url="/kippen-dashboard",
        category="dashboard",
        description="Analyse en trends van leghennenproductie per koppel.",
        display_order=15,
    ),
    CoreApplication(
        key="dashboard_klauwgezondheid",
        name="Klauwgezondheid",
        url="/klauwgezondheid",
        category="dashboard",
        description="Mortellaro en klauwgezondheid van de actieve koppel.",
        display_order=20,
    ),
    CoreApplication(
        key="dashboard_tank_terminal",
        name="Tanken",
        url="/tank-terminal",
        category="dashboard",
        description="Dieseltransacties per voertuig, chauffeur en CSV-import.",
        display_order=30,
    ),
    CoreApplication(
        key="user_administration",
        name="Gebruikersbeheer",
        url="/admin/users",
        category="admin",
        description="Gebruikers, applicatietoegang en rollen beheren.",
        display_order=100,
    ),
]

CORE_ROLES = [
    CoreRole(
        key="admin",
        name="Admin",
        description="Beheerrechten binnen een applicatie.",
    ),
    CoreRole(
        key="worker",
        name="Worker",
        description="Dagelijkse invoerrechten binnen een applicatie.",
    ),
    CoreRole(
        key="viewer",
        name="Viewer",
        description="Alleen-lezen toegang tot een applicatie of dashboard.",
    ),
]

ADMIN_ROLE_GRANTS = {
    "user_administration": ["admin"],
    "kippen": ["admin", "worker"],
    "dashboard_kippen": ["viewer"],
    "dashboard_klauwgezondheid": ["viewer"],
    "dashboard_tank_terminal": ["viewer"],
}


def bootstrap_shared_auth(
    session_factory,
    admin_config: Optional[BootstrapAdminConfig] = None,
) -> BootstrapResult:
    """Seed core auth rows and optionally create/grant a bootstrap admin."""
    users_repository = UsersRepository(session_factory)
    applications_repository = ApplicationsRepository(session_factory)
    roles_repository = RolesRepository(session_factory)
    access_repository = UserApplicationAccessRepository(session_factory)
    result = BootstrapResult()

    applications = _seed_core_applications(applications_repository, result)
    roles = _seed_core_roles(roles_repository, result)
    _bootstrap_admin_user(
        users_repository,
        access_repository,
        applications,
        roles,
        admin_config or BootstrapAdminConfig(),
        result,
    )

    return result


def _seed_core_applications(
    repository: ApplicationsRepository,
    result: BootstrapResult,
) -> dict[str, Application]:
    applications = {}
    for core_application in CORE_APPLICATIONS:
        application = repository.get_application_by_key(core_application.key)
        application_data = {
            "key": core_application.key,
            "name": core_application.name,
            "description": core_application.description,
            "url": core_application.url,
            "category": core_application.category,
            "display_order": core_application.display_order,
            "is_active": True,
        }
        if application is None:
            application = repository.create_application(application_data)
        else:
            application = repository.update_application(
                application.id, application_data
            )

        applications[core_application.key] = application
        result.applications_seeded += 1

    return applications


def _seed_core_roles(
    repository: RolesRepository,
    result: BootstrapResult,
) -> dict[str, Role]:
    roles = {}
    for core_role in CORE_ROLES:
        role = repository.get_role_by_key(core_role.key)
        role_data = {
            "key": core_role.key,
            "name": core_role.name,
            "description": core_role.description,
            "is_active": True,
        }
        if role is None:
            role = repository.create_role(role_data)
        else:
            role = repository.update_role(role.id, role_data)

        roles[core_role.key] = role
        result.roles_seeded += 1

    return roles


def _bootstrap_admin_user(
    users_repository: UsersRepository,
    access_repository: UserApplicationAccessRepository,
    applications: dict[str, Application],
    roles: dict[str, Role],
    admin_config: BootstrapAdminConfig,
    result: BootstrapResult,
) -> None:
    existing_users = users_repository.list_users()
    if not admin_config.username:
        if existing_users:
            result.messages.append(
                "Core applications and roles were seeded; admin user skipped."
            )
            return

        raise ValueError("AUTH_BOOTSTRAP_USERNAME is required when no users exist.")

    user = users_repository.get_user_by_username(admin_config.username)
    if user is None:
        if not admin_config.password:
            raise ValueError("AUTH_BOOTSTRAP_PASSWORD is required for a new user.")

        user = users_repository.create_user(
            User(
                username=admin_config.username,
                first_name=admin_config.first_name,
                last_name=admin_config.last_name,
                password_hash=service.hash_password(admin_config.password),
                must_change_password=False,
                is_active=True,
            )
        )
        result.admin_user_created = True
    else:
        user = _update_existing_admin_user(
            users_repository,
            user,
            admin_config,
            result,
        )

    _grant_admin_access(access_repository, applications, roles, user, result)


def _update_existing_admin_user(
    users_repository: UsersRepository,
    user: User,
    admin_config: BootstrapAdminConfig,
    result: BootstrapResult,
) -> User:
    update_data = {
        "is_active": True,
    }
    if admin_config.first_name is not None:
        update_data["first_name"] = admin_config.first_name
    if admin_config.last_name is not None:
        update_data["last_name"] = admin_config.last_name

    updated_user = users_repository.update_user(user.id, update_data)
    if admin_config.reset_existing_password:
        if not admin_config.password:
            raise ValueError(
                "AUTH_BOOTSTRAP_PASSWORD is required when resetting a password."
            )
        updated_user = users_repository.set_user_password_hash(
            user.id,
            service.hash_password(admin_config.password),
        )

    result.admin_user_updated = True
    return updated_user


def _grant_admin_access(
    access_repository: UserApplicationAccessRepository,
    applications: dict[str, Application],
    roles: dict[str, Role],
    user: User,
    result: BootstrapResult,
) -> None:
    for application_key, role_keys in ADMIN_ROLE_GRANTS.items():
        application = applications[application_key]
        access = access_repository.grant_application_access(
            user_id=user.id,
            application_id=application.id,
        )
        result.admin_access_grants += 1
        for role_key in role_keys:
            role = roles[role_key]
            access_repository.grant_application_role(
                access_id=access.id,
                role_id=role.id,
            )
            result.admin_role_grants += 1
