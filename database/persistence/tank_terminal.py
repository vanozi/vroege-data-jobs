"""Persistence helpers for Tank Terminal data."""

import logging
from typing import Optional

from database.models.tank_transaction import TankTransaction
from database.repositories.tank_transactions_repository import (
    TankTransactionsRepository,
)


def save_tank_transactions(
    rows: list[dict[str, object]],
    repository: Optional[TankTransactionsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Tank Terminal transactions and return the number processed."""
    if dry_run:
        _log_count(logger, "Dry run: would save %d tank transactions.", len(rows))
        return len(rows)

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    saved_count = 0
    for row in rows:
        repository.upsert_tank_transaction(row)
        saved_count += 1

    _log_count(logger, "Saved %d tank transactions.", saved_count)
    return saved_count


def save_tank_transaction_models(
    models: list[TankTransaction],
    repository: Optional[TankTransactionsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert TankTransaction models and return the number processed."""
    if dry_run:
        _log_count(
            logger,
            "Dry run: would save %d tank transaction models.",
            len(models),
        )
        return len(models)

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    saved_count = 0
    for model in models:
        repository.upsert_tank_transaction(model)
        saved_count += 1

    _log_count(logger, "Saved %d tank transaction models.", saved_count)
    return saved_count


def _log_count(
    logger: Optional[logging.Logger],
    message: str,
    count: int,
) -> None:
    if logger is None:
        return

    logger.info(message, count)
