"""Logging: a coloured console, a rotating file, timestamps in the configured zone."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from openings.config import Config


def _timezone_converter(tz_name: str) -> Callable[[float | None], time.struct_time]:
    """A ``logging.Formatter.converter`` that renders timestamps in ``tz_name``."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return time.localtime

    def convert(timestamp: float | None) -> time.struct_time:
        return datetime.fromtimestamp(timestamp or 0.0, tz).timetuple()

    return convert


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Colour the level name when writing to a terminal."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.RED + Colors.BOLD,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_colors = sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_colors:
            return super().format(record)
        original = record.levelname
        record.levelname = (
            f"{self.LEVEL_COLORS.get(record.levelno, Colors.RESET)}{original}{Colors.RESET}"
        )
        try:
            return super().format(record)
        finally:
            record.levelname = original


class DedupeFilter(logging.Filter):
    """Emit the first of identical records from a noisy logger family, drop the rest."""

    def __init__(self, name_prefix: str = "") -> None:
        super().__init__()
        self._prefix = name_prefix
        self._seen: set[tuple[str, int, str]] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        if self._prefix and not record.name.startswith(self._prefix):
            return True
        key = (record.name, record.levelno, record.getMessage())
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


# JobSpy names its per-site loggers with colons, which are not hierarchical
# in Python logging, so each one is configured explicitly.
_JOBSPY_LOGGER_NAMES = (
    "JobSpy",
    "JobSpy:Indeed",
    "JobSpy:LinkedIn",
    "JobSpy:Glassdoor",
    "JobSpy:Google",
    "JobSpy:ZipRecruiter",
    "JobSpy:Bayt",
    "JobSpy:Naukri",
    "JobSpy:BDJobs",
)


def _reroute_jobspy_loggers() -> None:
    """Drop JobSpy's own handlers so its records flow through the root handler."""
    for name in _JOBSPY_LOGGER_NAMES:
        jobspy_logger = logging.getLogger(name)
        for handler in list(jobspy_logger.handlers):
            jobspy_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:  # noqa: BLE001
                pass
        jobspy_logger.propagate = True
        jobspy_logger.setLevel(logging.WARNING)


def _purge_dedupe_filters(target: logging.Logger | logging.Handler) -> None:
    for existing in list(target.filters):
        if isinstance(existing, DedupeFilter):
            target.removeFilter(existing)


def setup_logging(config: Config, *, console_only: bool = False) -> logging.Logger:
    """Configure the ``openings`` logger and the root logger once per process.

    The web process passes ``console_only`` so two processes never rotate the
    same file.
    """
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    dedupe = DedupeFilter(name_prefix="JobSpy")
    converter = _timezone_converter(config.logging.timezone)

    console_format = ColoredFormatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"
    )
    console_format.converter = converter
    file_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_format.converter = converter

    logger = logging.getLogger("openings")
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(console_format)
    console.addFilter(dedupe)
    logger.addHandler(console)

    if not console_only:
        log_path = config.log_file
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=config.logging.max_size_mb * 1024 * 1024,
                backupCount=config.logging.backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_format)
            file_handler.addFilter(dedupe)
            logger.addHandler(file_handler)
        except PermissionError:
            logger.warning(
                "Cannot write to log file %s (permission denied); console only", log_path
            )

    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    _purge_dedupe_filters(root)
    for handler in list(root.handlers):
        try:
            handler.close()
        except Exception:  # noqa: BLE001
            pass
        root.removeHandler(handler)
    root_console = logging.StreamHandler(sys.stdout)
    root_console.setLevel(logging.WARNING)
    root_console.setFormatter(file_format)
    root_console.addFilter(dedupe)
    root.addHandler(root_console)
    _reroute_jobspy_loggers()
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"openings.{name}")
    return logging.getLogger("openings")


class ProgressLogger:
    """Counts and percentages for a long operation."""

    def __init__(self, logger: logging.Logger, total: int, operation: str):
        self.logger = logger
        self.total = total
        self.operation = operation
        self.completed = 0
        self.success = 0
        self.failed = 0

    def update(self, success: bool = True, message: str = "") -> None:
        self.completed += 1
        if success:
            self.success += 1
        else:
            self.failed += 1
        percentage = (self.completed / self.total) * 100 if self.total > 0 else 0
        if message:
            self.logger.info("[%d/%d] (%.0f%%) %s", self.completed, self.total, percentage, message)

    def summary(self) -> None:
        self.logger.info(
            "%s complete: %d succeeded, %d failed out of %d total",
            self.operation,
            self.success,
            self.failed,
            self.total,
        )


def log_section(logger: logging.Logger, title: str) -> None:
    separator = "=" * 60
    logger.info(separator)
    logger.info("  %s", title)
    logger.info(separator)
