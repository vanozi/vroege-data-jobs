"""
Centralized logging configuration for the uniform_agri project.

Creates a separate log file per module with daily rotation.
Each module gets its own log file: logs/module_name/YYYY-MM-DD.log

Usage:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("This is an info message")
    logger.error("This is an error message")
"""

import logging
from datetime import datetime
from pathlib import Path


def get_logger(module_name: str) -> logging.Logger:
    """
    Get or create a logger for a specific module.

    Args:
        module_name: Name of the module (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(module_name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Extract clean module name for log file
        clean_name = module_name.replace(".", "_")

        # Create logs directory structure: logs/module_name/
        log_dir = Path("logs") / clean_name
        log_dir.mkdir(parents=True, exist_ok=True)

        # Daily log file: logs/module_name/YYYY-MM-DD.log
        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
