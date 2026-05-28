"""Bootstrap core shared auth records and an optional first admin."""

import os
from typing import Optional

from database import database
from shared_auth import bootstrap


def main() -> int:
    """Run the shared auth bootstrap command."""
    admin_config = bootstrap.BootstrapAdminConfig(
        email_address=_optional_env("AUTH_BOOTSTRAP_EMAIL"),
        password=_optional_env("AUTH_BOOTSTRAP_PASSWORD"),
        first_name=_optional_env("AUTH_BOOTSTRAP_FIRST_NAME"),
        last_name=_optional_env("AUTH_BOOTSTRAP_LAST_NAME"),
        reset_existing_password=_bool_env("AUTH_BOOTSTRAP_RESET_PASSWORD"),
    )
    result = bootstrap.bootstrap_shared_auth(
        database.get_session,
        admin_config,
    )
    _print_result(result)
    return 0


def _optional_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    if value == "":
        return None

    return value


def _bool_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _print_result(result: bootstrap.BootstrapResult) -> None:
    print(f"applications_seeded={result.applications_seeded}")
    print(f"roles_seeded={result.roles_seeded}")
    print(f"admin_user_created={result.admin_user_created}")
    print(f"admin_user_updated={result.admin_user_updated}")
    print(f"admin_access_grants={result.admin_access_grants}")
    print(f"admin_role_grants={result.admin_role_grants}")
    for message in result.messages:
        print(message)


if __name__ == "__main__":
    raise SystemExit(main())
