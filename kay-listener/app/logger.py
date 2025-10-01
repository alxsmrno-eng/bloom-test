from __future__ import annotations

from loguru import logger
from pathlib import Path
import sys

from .utils import logs_dir


def configure_logging(level: str = "INFO") -> None:
    logs_directory = logs_dir()
    logs_directory.mkdir(parents=True, exist_ok=True)
    log_path = logs_directory / "app.log"

    logger.remove()
    logger.add(sys.stderr, level=level)
    logger.add(
        log_path,
        level=level,
        rotation="1 week",
        retention="30 days",
        enqueue=True,
        encoding="utf-8",
        backtrace=False,
    )
    logger.info("Logging inicializado en %s", log_path)


__all__ = ["configure_logging", "logger"]
