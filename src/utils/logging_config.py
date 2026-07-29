"""
Shared logging configuration.

Every pipeline stage should call ``get_logger(__name__)`` rather than
configuring its own handlers, so log output is consistent and always
written to both the console and a rotating log file under ``logs/``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.config import LOG_DIR, LOG_LEVEL

_CONFIGURED = False


def _configure_root_logger() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = Path(LOG_DIR) / "pipeline.log"

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root.addHandler(console_handler)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with console + file handlers attached."""
    _configure_root_logger()
    return logging.getLogger(name)
