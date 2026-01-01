"""
Logging configuration for Job Search Tool.

Provides structured logging with file rotation and colored console output.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
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


def setup_logging(config: Config) -> logging.Logger:
    """
    Set up logging with console and file handlers.

    Args:
        config: Configuration object with logging settings.

    Returns:
        Configured logger instance.
    """
    # Create logger
    logger = logging.getLogger("job_search")
    logger.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = ColoredFormatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler with rotation
    log_path = config.log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.logging.max_size_mb * 1024 * 1024,
        backupCount=config.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = PlainFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


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
