"""Tests for healthcheck module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from healthcheck import (
    check_config,
    check_database,
    check_directories,
    check_imports,
    main,
)


# =============================================================================
# TEST check_imports
# =============================================================================


class TestCheckImports:
    """Tests for check_imports function."""

    def test_check_imports_success(self):
        """Test check_imports succeeds when all modules available."""
        # pandas, yaml, sqlite3 are available in test env; jobspy is mocked
        result = check_imports()

        assert result is True

    def test_check_imports_failure(self):
        """Test check_imports fails when a module is missing."""
        with patch.dict(sys.modules, {"pandas": None}):
            # Force re-import to trigger ImportError
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'pandas'"),
            ):
                result = check_imports()

                assert result is False


# =============================================================================
# TEST check_config
# =============================================================================


class TestCheckConfig:
    """Tests for check_config function."""

    def test_check_config_success(self):
        """Test check_config succeeds with valid config."""
        mock_config = MagicMock()

        with patch("config.load_config", return_value=mock_config):
            result = check_config()

            assert result is True

    def test_check_config_failure(self):
        """Test check_config fails when config loading raises."""
        with patch("config.load_config", side_effect=Exception("Bad YAML")):
            result = check_config()

            assert result is False

    def test_check_config_returns_none(self):
        """Test check_config fails when config is None."""
        with patch("config.load_config", return_value=None):
            result = check_config()

            assert result is False


# =============================================================================
# TEST check_database
# =============================================================================


class TestCheckDatabase:
    """Tests for check_database function."""

    def test_check_database_success(self):
        """Test check_database succeeds with working database."""
        mock_config = MagicMock()
        mock_db = MagicMock()
        mock_db.get_statistics.return_value = {"total_jobs": 5}

        with (
            patch("config.get_config", return_value=mock_config),
            patch("database.get_database", return_value=mock_db),
        ):
            result = check_database()

            assert result is True

    def test_check_database_failure(self):
        """Test check_database fails when database is broken."""
        mock_config = MagicMock()

        with (
            patch("config.get_config", return_value=mock_config),
            patch(
                "database.get_database", side_effect=Exception("DB connection failed")
            ),
        ):
            result = check_database()

            assert result is False

    def test_check_database_invalid_stats(self):
        """Test check_database fails when stats is not a dict."""
        mock_config = MagicMock()
        mock_db = MagicMock()
        mock_db.get_statistics.return_value = "not a dict"

        with (
            patch("config.get_config", return_value=mock_config),
            patch("database.get_database", return_value=mock_db),
        ):
            result = check_database()

            # isinstance("not a dict", dict) is False
            assert result is False


# =============================================================================
# TEST check_directories
# =============================================================================


class TestCheckDirectories:
    """Tests for check_directories function."""

    def test_check_directories_success(self, tmp_path):
        """Test check_directories succeeds when dirs exist and are writable."""
        mock_config = MagicMock()
        mock_config.results_path = tmp_path / "results"
        mock_config.data_path = tmp_path / "data"
        mock_config.log_path = tmp_path / "logs" / "search.log"

        # Create the directories
        mock_config.results_path.mkdir()
        mock_config.data_path.mkdir()
        mock_config.log_path.parent.mkdir()

        with patch("config.get_config", return_value=mock_config):
            result = check_directories()

            assert result is True

    def test_check_directories_missing(self, tmp_path):
        """Test check_directories fails when a directory is missing."""
        mock_config = MagicMock()
        mock_config.results_path = tmp_path / "nonexistent"
        mock_config.data_path = tmp_path / "data"
        mock_config.log_path = tmp_path / "logs" / "search.log"

        mock_config.data_path.mkdir()
        mock_config.log_path.parent.mkdir()

        with patch("config.get_config", return_value=mock_config):
            result = check_directories()

            assert result is False

    def test_check_directories_exception(self):
        """Test check_directories handles exceptions."""
        with patch("config.get_config", side_effect=Exception("Config error")):
            result = check_directories()

            assert result is False


# =============================================================================
# TEST main
# =============================================================================


class TestMain:
    """Tests for main function."""

    def test_main_all_pass(self):
        """Test main returns 0 when all checks pass."""
        with (
            patch("healthcheck.check_imports", return_value=True),
            patch("healthcheck.check_config", return_value=True),
            patch("healthcheck.check_database", return_value=True),
            patch("healthcheck.check_directories", return_value=True),
        ):
            result = main()

            assert result == 0

    def test_main_one_failure(self):
        """Test main returns 1 when any check fails."""
        with (
            patch("healthcheck.check_imports", return_value=True),
            patch("healthcheck.check_config", return_value=False),
            patch("healthcheck.check_database", return_value=True),
            patch("healthcheck.check_directories", return_value=True),
        ):
            result = main()

            assert result == 1

    def test_main_all_fail(self):
        """Test main returns 1 when all checks fail."""
        with (
            patch("healthcheck.check_imports", return_value=False),
            patch("healthcheck.check_config", return_value=False),
            patch("healthcheck.check_database", return_value=False),
            patch("healthcheck.check_directories", return_value=False),
        ):
            result = main()

            assert result == 1

    def test_main_handles_exceptions(self):
        """Test main handles exceptions from individual checks."""
        with (
            patch("healthcheck.check_imports", side_effect=RuntimeError("Boom")),
            patch("healthcheck.check_config", return_value=True),
            patch("healthcheck.check_database", return_value=True),
            patch("healthcheck.check_directories", return_value=True),
        ):
            result = main()

            assert result == 1
