"""
Shared logging utilities for data collection jobs.

Each job run gets its own log file under data_jobs/logs/<script_name>/ with a
timestamped filename so runs are separated cleanly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def get_job_logger(script_path: str, logger_name: str | None = None) -> logging.Logger:
    """
    Create or retrieve a logger for a job script.

    Args:
        script_path: Usually __file__ from the calling script.
        logger_name: Optional logger namespace. Defaults to the script stem.

    Returns:
        Configured logger instance.
    """
    script = Path(script_path)
    script_name = script.stem
    logger = logging.getLogger(logger_name or script_name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_root = Path(__file__).resolve().parent / "logs" / script_name
    log_root.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_root / f"{script_name}_{run_timestamp}.log"

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
