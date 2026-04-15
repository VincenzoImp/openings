"""
Logging configuration for Job Search Tool.

Provides structured logging with file rotation and colored console output.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Config


# ANSI color codes for console output
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels in console output (only if TTY)."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.RED + Colors.BOLD,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if output is a TTY (terminal)
        self.use_colors = sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors (only if TTY)."""
        if self.use_colors:
            # Save original levelname and restore after formatting
            original_levelname = record.levelname
            color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
            record.levelname = f"{color}{record.levelname}{Colors.RESET}"
            try:
                return super().format(record)
            finally:
                record.levelname = original_levelname
        return super().format(record)


class PlainFormatter(logging.Formatter):
    """Plain formatter for file output without colors."""

    pass


class DedupeFilter(logging.Filter):
    """Collapse repeated identical records from noisy third-party loggers.

    Emits the first record for each ``(logger_name, level, message)`` tuple
    verbatim and drops subsequent duplicates for the remainder of the process.
    Useful for third-party libraries (JobSpy, ChromaDB, ...) that spam the
    same error for every item in a batch — we keep one sample instead of 24.
    """

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


# Known JobSpy per-site logger names. JobSpy uses colons as separators, which
# are *not* hierarchical in Python logging, so each site gets its own
# independent logger. We pre-configure them at setup time to (a) strip any
# handlers JobSpy attached at import, (b) force propagation to the root
# logger where our DedupeFilter lives, and (c) set a sensible level.
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
    """Purge and reconfigure every JobSpy per-site logger.

    JobSpy attaches its own StreamHandler at import time, which bypasses
    our root-level ``DedupeFilter``. By removing those handlers and forcing
    propagation back to the root logger, all JobSpy records flow through
    our filter chain and get deduped like any other noisy third-party log.
    """
    for name in _JOBSPY_LOGGER_NAMES:
        jl = logging.getLogger(name)
        for handler in list(jl.handlers):
            jl.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        jl.propagate = True
        jl.setLevel(logging.WARNING)


def setup_logging(config: Config) -> logging.Logger:
    """Configure application-wide logging with console and file handlers.

    The tool owns both its own ``job_search`` logger (with a compact coloured
    format) and the root logger (where third-party libraries like JobSpy log
    via ``logging.basicConfig``). Both routes share a ``DedupeFilter`` that
    collapses repeated identical records from ``JobSpy:*`` per-site loggers —
    typically the ``Glassdoor: location not parsed`` error that otherwise
    fires 24 times per run.

    Args:
        config: Configuration object with logging settings.

    Returns:
        Configured ``job_search`` logger instance.
    """
    level = getattr(logging, config.logging.level.upper(), logging.INFO)

    # Dedupe filter shared between all handlers so the same (name, level,
    # message) tuple is suppressed everywhere after the first occurrence.
    jobspy_dedupe = DedupeFilter(name_prefix="JobSpy")

    console_format = ColoredFormatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    file_format = PlainFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Our application logger (job_search) ------------------------------
    logger = logging.getLogger("job_search")
    logger.setLevel(level)
    logger.propagate = False  # keep application logs off the root handlers

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_format)
    console_handler.addFilter(jobspy_dedupe)
    logger.addHandler(console_handler)

    # File handler with rotation (skip if the directory is not writable).
    log_path = config.log_path
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
        file_handler.addFilter(jobspy_dedupe)
        logger.addHandler(file_handler)
    except PermissionError:
        logger.warning(
            "Cannot write to log file %s (permission denied). "
            "Continuing with console-only logging.",
            log_path,
        )

    # --- Root logger (third-party libraries) ------------------------------
    # Install a root handler with the same dedupe filter so records from
    # JobSpy / ChromaDB / ... that never touch our application logger are
    # still deduped. Without this, JobSpy's ``logging.basicConfig`` call
    # would attach an unfiltered StreamHandler at first import.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    _purge_dedupe_filters(root_logger)
    for handler in list(root_logger.handlers):
        # Close every existing handler — libraries may attach non-StreamHandler
        # variants at import time. We replace them with our own deduped one.
        try:
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)

    root_console = logging.StreamHandler(sys.stdout)
    root_console.setLevel(logging.WARNING)
    root_console.setFormatter(file_format)
    root_console.addFilter(jobspy_dedupe)
    root_logger.addHandler(root_console)

    # Reroute JobSpy's per-site loggers through the root handler we just
    # installed so they inherit the DedupeFilter and uniform format.
    _reroute_jobspy_loggers()

    # ChromaDB occasionally emits noisy WARNING-level telemetry failures —
    # keep them at WARNING so anything at or above that level still flows.
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return logger


def _purge_dedupe_filters(target: logging.Logger | logging.Handler) -> None:
    """Remove previously attached ``DedupeFilter`` instances from ``target``.

    Prevents filter accumulation when ``setup_logging`` is called multiple
    times in the same process (tests, re-loads, config reloads).
    """
    for existing in list(target.filters):
        if isinstance(existing, DedupeFilter):
            target.removeFilter(existing)


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Optional name for the logger. If None, returns the main logger.

    Returns:
        Logger instance.
    """
    if name:
        return logging.getLogger(f"job_search.{name}")
    return logging.getLogger("job_search")


class ProgressLogger:
    """
    Helper class for logging progress of long-running operations.

    Provides methods for tracking progress with counts and percentages.
    """

    def __init__(self, logger: logging.Logger, total: int, operation: str):
        """
        Initialize progress logger.

        Args:
            logger: Logger instance to use.
            total: Total number of items to process.
            operation: Description of the operation.
        """
        self.logger = logger
        self.total = total
        self.operation = operation
        self.completed = 0
        self.success = 0
        self.failed = 0

    def update(self, success: bool = True, message: str = "") -> None:
        """
        Update progress counter.

        Args:
            success: Whether the current item succeeded.
            message: Optional message to log.
        """
        self.completed += 1
        if success:
            self.success += 1
        else:
            self.failed += 1

        percentage = (self.completed / self.total) * 100 if self.total > 0 else 0

        if message:
            self.logger.info(
                f"[{self.completed}/{self.total}] ({percentage:.0f}%) {message}"
            )

    def summary(self) -> None:
        """Log final summary of the operation."""
        self.logger.info(
            f"{self.operation} complete: "
            f"{self.success} succeeded, {self.failed} failed "
            f"out of {self.total} total"
        )


def log_section(logger: logging.Logger, title: str) -> None:
    """
    Log a section header for visual separation.

    Args:
        logger: Logger instance.
        title: Section title.
    """
    separator = "=" * 60
    logger.info(separator)
    logger.info(f"  {title}")
    logger.info(separator)


def log_subsection(logger: logging.Logger, title: str) -> None:
    """
    Log a subsection header.

    Args:
        logger: Logger instance.
        title: Subsection title.
    """
    logger.info(f"--- {title} ---")
