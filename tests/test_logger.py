"""Tests for logger module.

Tests for logging functionality including:
- ColoredFormatter TTY detection
- PlainFormatter for file output
- ProgressLogger progress tracking
- Logger factory functions
- Log section formatting
"""

import io
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import Config, LoggingConfig
from logger import (
    ColoredFormatter,
    Colors,
    PlainFormatter,
    ProgressLogger,
    get_logger,
    log_section,
    log_subsection,
    setup_logging,
)


# =============================================================================
# TEST COLORS
# =============================================================================


class TestColors:
    """Tests for Colors class constants."""

    def test_color_codes_are_strings(self):
        """Test all color codes are strings."""
        assert isinstance(Colors.RESET, str)
        assert isinstance(Colors.BOLD, str)
        assert isinstance(Colors.RED, str)
        assert isinstance(Colors.GREEN, str)
        assert isinstance(Colors.YELLOW, str)
        assert isinstance(Colors.BLUE, str)
        assert isinstance(Colors.MAGENTA, str)
        assert isinstance(Colors.CYAN, str)
        assert isinstance(Colors.GRAY, str)

    def test_color_codes_are_ansi(self):
        """Test color codes are ANSI escape sequences."""
        assert Colors.RESET.startswith("\033[")
        assert Colors.RED.startswith("\033[")
        assert Colors.GREEN.startswith("\033[")


# =============================================================================
# TEST COLORED FORMATTER
# =============================================================================


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_format_with_tty(self):
        """Test that colors are applied when output is TTY."""
        formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")

        # Mock stdout.isatty() to return True
        with patch("sys.stdout.isatty", return_value=True):
            formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")
            assert formatter.use_colors is True

    def test_format_without_tty(self):
        """Test that colors are NOT applied when output is not TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")
            assert formatter.use_colors is False

    def test_format_adds_color_to_levelname(self):
        """Test that level name gets colored in TTY mode."""
        with patch("sys.stdout.isatty", return_value=True):
            formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            formatted = formatter.format(record)

            # Should contain color codes
            assert Colors.GREEN in record.levelname or Colors.RESET in formatted

    def test_format_no_color_without_tty(self):
        """Test that no color codes are added without TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            formatter = ColoredFormatter(fmt="%(levelname)s: %(message)s")

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            formatted = formatter.format(record)

            # Should NOT contain ANSI escape sequences
            assert "\033[" not in formatted

    def test_level_colors_mapping(self):
        """Test that different log levels have different colors."""
        with patch("sys.stdout.isatty", return_value=True):
            formatter = ColoredFormatter(fmt="%(levelname)s")

            assert ColoredFormatter.LEVEL_COLORS[logging.DEBUG] == Colors.GRAY
            assert ColoredFormatter.LEVEL_COLORS[logging.INFO] == Colors.GREEN
            assert ColoredFormatter.LEVEL_COLORS[logging.WARNING] == Colors.YELLOW
            assert ColoredFormatter.LEVEL_COLORS[logging.ERROR] == Colors.RED
            assert Colors.BOLD in ColoredFormatter.LEVEL_COLORS[logging.CRITICAL]


# =============================================================================
# TEST PLAIN FORMATTER
# =============================================================================


class TestPlainFormatter:
    """Tests for PlainFormatter class."""

    def test_plain_formatter_no_colors(self):
        """Test PlainFormatter doesn't add colors."""
        formatter = PlainFormatter(fmt="%(levelname)s: %(message)s")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        # Should NOT contain ANSI escape sequences
        assert "\033[" not in formatted
        assert "Test message" in formatted


# =============================================================================
# TEST PROGRESS LOGGER
# =============================================================================


class TestProgressLogger:
    """Tests for ProgressLogger class."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    def test_init(self, mock_logger):
        """Test ProgressLogger initialization."""
        progress = ProgressLogger(mock_logger, 10, "Processing")

        assert progress.total == 10
        assert progress.operation == "Processing"
        assert progress.completed == 0
        assert progress.success == 0
        assert progress.failed == 0

    def test_update_success(self, mock_logger):
        """Test update() increments success counter."""
        progress = ProgressLogger(mock_logger, 10, "Processing")

        progress.update(success=True, message="Item 1 done")

        assert progress.completed == 1
        assert progress.success == 1
        assert progress.failed == 0

    def test_update_failure(self, mock_logger):
        """Test update() increments failed counter on failure."""
        progress = ProgressLogger(mock_logger, 10, "Processing")

        progress.update(success=False, message="Item 1 failed")

        assert progress.completed == 1
        assert progress.success == 0
        assert progress.failed == 1

    def test_update_logs_message(self, mock_logger):
        """Test update() logs the progress message."""
        progress = ProgressLogger(mock_logger, 10, "Processing")

        progress.update(success=True, message="Completed item")

        mock_logger.info.assert_called_once()
        call_msg = mock_logger.info.call_args[0][0]
        assert "[1/10]" in call_msg
        assert "(10%)" in call_msg
        assert "Completed item" in call_msg

    def test_update_without_message(self, mock_logger):
        """Test update() without message doesn't log."""
        progress = ProgressLogger(mock_logger, 10, "Processing")

        progress.update(success=True)

        mock_logger.info.assert_not_called()

    def test_update_percentage_calculation(self, mock_logger):
        """Test percentage is calculated correctly."""
        progress = ProgressLogger(mock_logger, 4, "Processing")

        progress.update(success=True, message="1")  # 25%
        progress.update(success=True, message="2")  # 50%
        progress.update(success=True, message="3")  # 75%

        calls = mock_logger.info.call_args_list
        assert "(25%)" in calls[0][0][0]
        assert "(50%)" in calls[1][0][0]
        assert "(75%)" in calls[2][0][0]

    def test_update_zero_total(self, mock_logger):
        """Test update() handles zero total gracefully."""
        progress = ProgressLogger(mock_logger, 0, "Processing")

        # Should not raise
        progress.update(success=True, message="Item")

        call_msg = mock_logger.info.call_args[0][0]
        assert "(0%)" in call_msg

    def test_summary(self, mock_logger):
        """Test summary() logs final statistics."""
        progress = ProgressLogger(mock_logger, 10, "Processing items")
        progress.success = 7
        progress.failed = 3

        progress.summary()

        mock_logger.info.assert_called_once()
        call_msg = mock_logger.info.call_args[0][0]
        assert "Processing items" in call_msg
        assert "7 succeeded" in call_msg
        assert "3 failed" in call_msg
        assert "10 total" in call_msg


# =============================================================================
# TEST GET LOGGER
# =============================================================================


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self):
        """Test get_logger returns child logger with name."""
        logger = get_logger("test_module")

        assert logger.name == "job_search.test_module"

    def test_get_logger_without_name(self):
        """Test get_logger returns root logger without name."""
        logger = get_logger()

        assert logger.name == "job_search"

    def test_get_logger_none_name(self):
        """Test get_logger with None returns root logger."""
        logger = get_logger(None)

        assert logger.name == "job_search"

    def test_get_logger_returns_logger_instance(self):
        """Test get_logger returns a Logger instance."""
        logger = get_logger("test")

        assert isinstance(logger, logging.Logger)


# =============================================================================
# TEST LOG SECTION AND SUBSECTION
# =============================================================================


class TestLogSections:
    """Tests for log_section and log_subsection functions."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    def test_log_section(self, mock_logger):
        """Test log_section creates visual separator."""
        log_section(mock_logger, "Test Section")

        # Should call info 3 times: separator, title, separator
        assert mock_logger.info.call_count == 3

        calls = [c[0][0] for c in mock_logger.info.call_args_list]

        # First and last should be separator
        assert "=" * 60 in calls[0]
        assert "=" * 60 in calls[2]

        # Middle should contain title
        assert "Test Section" in calls[1]

    def test_log_subsection(self, mock_logger):
        """Test log_subsection creates smaller separator."""
        log_subsection(mock_logger, "Test Subsection")

        mock_logger.info.assert_called_once()
        call_msg = mock_logger.info.call_args[0][0]

        assert "---" in call_msg
        assert "Test Subsection" in call_msg


# =============================================================================
# TEST SETUP LOGGING
# =============================================================================


class TestSetupLogging:
    """Tests for setup_logging function."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_setup_logging_returns_logger(self, temp_log_dir):
        """Test setup_logging returns a logger instance."""
        config = Config(
            logging=LoggingConfig(
                level="INFO",
                file=str(temp_log_dir / "test.log"),
                max_size_mb=1,
                backup_count=3,
            )
        )

        # Patch the config path properties
        with patch.object(Config, "log_path", temp_log_dir / "test.log"):
            logger = setup_logging(config)

            assert isinstance(logger, logging.Logger)
            assert logger.name == "job_search"

    def test_setup_logging_creates_handlers(self, temp_log_dir):
        """Test setup_logging creates console and file handlers."""
        config = Config(
            logging=LoggingConfig(
                level="DEBUG",
                file=str(temp_log_dir / "test.log"),
            )
        )

        with patch.object(Config, "log_path", temp_log_dir / "test.log"):
            logger = setup_logging(config)

            # Should have at least 2 handlers (console + file)
            assert len(logger.handlers) >= 2

    def test_setup_logging_sets_level(self, temp_log_dir):
        """Test setup_logging sets the log level from config."""
        config = Config(
            logging=LoggingConfig(
                level="WARNING",
                file=str(temp_log_dir / "test.log"),
            )
        )

        with patch.object(Config, "log_path", temp_log_dir / "test.log"):
            logger = setup_logging(config)

            assert logger.level == logging.WARNING

    def test_setup_logging_creates_log_directory(self, temp_log_dir):
        """Test setup_logging creates log directory if needed."""
        log_path = temp_log_dir / "subdir" / "test.log"
        config = Config(
            logging=LoggingConfig(
                level="INFO",
                file=str(log_path),
            )
        )

        with patch.object(Config, "log_path", log_path):
            setup_logging(config)

            assert log_path.parent.exists()

    def test_setup_logging_clears_existing_handlers(self, temp_log_dir):
        """Test setup_logging clears existing handlers."""
        config = Config(
            logging=LoggingConfig(
                level="INFO",
                file=str(temp_log_dir / "test.log"),
            )
        )

        with patch.object(Config, "log_path", temp_log_dir / "test.log"):
            # First setup
            logger1 = setup_logging(config)
            handler_count1 = len(logger1.handlers)

            # Second setup should not duplicate handlers
            logger2 = setup_logging(config)
            handler_count2 = len(logger2.handlers)

            assert handler_count1 == handler_count2
