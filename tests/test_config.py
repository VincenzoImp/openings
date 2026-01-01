"""Tests for config module."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import (
    Config,
    LoggingConfig,
    ParallelConfig,
    PostFilterConfig,
    RetryConfig,
    ScoringConfig,
    SearchConfig,
    ThrottlingConfig,
    TelegramConfig,
    _parse_parallel_config,
    _parse_retry_config,
    _parse_throttling_config,
    _parse_post_filter_config,
    _parse_logging_config,
    _parse_scheduler_config,
    _parse_telegram_config,
)


class TestParallelConfigValidation:
    """Tests for parallel config validation."""

    def test_valid_max_workers(self):
        """Test valid max_workers values."""
        config = _parse_parallel_config({"parallel": {"max_workers": 5}})
        assert config.max_workers == 5

    def test_max_workers_minimum(self):
        """Test max_workers must be at least 1."""
        with pytest.raises(ValueError, match="max_workers must be at least 1"):
            _parse_parallel_config({"parallel": {"max_workers": 0}})

    def test_max_workers_negative(self):
        """Test max_workers cannot be negative."""
        with pytest.raises(ValueError, match="max_workers must be at least 1"):
            _parse_parallel_config({"parallel": {"max_workers": -1}})


class TestRetryConfigValidation:
    """Tests for retry config validation."""

    def test_valid_retry_config(self):
        """Test valid retry configuration."""
        config = _parse_retry_config({
            "retry": {
                "max_attempts": 5,
                "base_delay": 3.0,
                "backoff_factor": 2.5,
            }
        })
        assert config.max_attempts == 5
        assert config.base_delay == 3.0
        assert config.backoff_factor == 2.5

    def test_max_attempts_minimum(self):
        """Test max_attempts must be at least 1."""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            _parse_retry_config({"retry": {"max_attempts": 0}})

    def test_base_delay_negative(self):
        """Test base_delay cannot be negative."""
        with pytest.raises(ValueError, match="base_delay cannot be negative"):
            _parse_retry_config({"retry": {"base_delay": -1}})

    def test_backoff_factor_minimum(self):
        """Test backoff_factor must be at least 1.0."""
        with pytest.raises(ValueError, match="backoff_factor must be at least 1.0"):
            _parse_retry_config({"retry": {"backoff_factor": 0.5}})


class TestThrottlingConfigValidation:
    """Tests for throttling config validation."""

    def test_valid_throttling_config(self):
        """Test valid throttling configuration."""
        config = _parse_throttling_config({
            "throttling": {
                "enabled": True,
                "default_delay": 2.0,
                "jitter": 0.5,
            }
        })
        assert config.enabled is True
        assert config.default_delay == 2.0
        assert config.jitter == 0.5

    def test_default_delay_negative(self):
        """Test default_delay cannot be negative."""
        with pytest.raises(ValueError, match="default_delay cannot be negative"):
            _parse_throttling_config({"throttling": {"default_delay": -1}})

    def test_jitter_range_low(self):
        """Test jitter must be >= 0."""
        with pytest.raises(ValueError, match="jitter must be between 0 and 1.0"):
            _parse_throttling_config({"throttling": {"jitter": -0.1}})

    def test_jitter_range_high(self):
        """Test jitter must be <= 1.0."""
        with pytest.raises(ValueError, match="jitter must be between 0 and 1.0"):
            _parse_throttling_config({"throttling": {"jitter": 1.5}})

    def test_site_delay_negative(self):
        """Test site delays cannot be negative."""
        with pytest.raises(ValueError, match="site_delays"):
            _parse_throttling_config({
                "throttling": {
                    "site_delays": {"linkedin": -1.0}
                }
            })


class TestPostFilterConfigValidation:
    """Tests for post-filter config validation."""

    def test_valid_post_filter_config(self):
        """Test valid post-filter configuration."""
        config = _parse_post_filter_config({
            "post_filter": {
                "enabled": True,
                "min_similarity": 85,
            }
        })
        assert config.enabled is True
        assert config.min_similarity == 85

    def test_min_similarity_range_low(self):
        """Test min_similarity must be >= 0."""
        with pytest.raises(ValueError, match="min_similarity must be between 0 and 100"):
            _parse_post_filter_config({"post_filter": {"min_similarity": -10}})

    def test_min_similarity_range_high(self):
        """Test min_similarity must be <= 100."""
        with pytest.raises(ValueError, match="min_similarity must be between 0 and 100"):
            _parse_post_filter_config({"post_filter": {"min_similarity": 150}})


class TestLoggingConfigValidation:
    """Tests for logging config validation."""

    def test_valid_logging_config(self):
        """Test valid logging configuration."""
        config = _parse_logging_config({
            "logging": {
                "level": "DEBUG",
                "max_size_mb": 20,
                "backup_count": 3,
                "timezone": "America/New_York",
            }
        })
        assert config.level == "DEBUG"
        assert config.max_size_mb == 20
        assert config.backup_count == 3
        assert config.timezone == "America/New_York"

    def test_max_size_mb_positive(self):
        """Test max_size_mb must be positive."""
        with pytest.raises(ValueError, match="max_size_mb must be positive"):
            _parse_logging_config({"logging": {"max_size_mb": 0}})

    def test_backup_count_non_negative(self):
        """Test backup_count cannot be negative."""
        with pytest.raises(ValueError, match="backup_count cannot be negative"):
            _parse_logging_config({"logging": {"backup_count": -1}})


class TestSchedulerConfigValidation:
    """Tests for scheduler config validation."""

    def test_valid_scheduler_config(self):
        """Test valid scheduler configuration."""
        config = _parse_scheduler_config({
            "scheduler": {
                "enabled": True,
                "interval_hours": 12,
                "retry_delay_minutes": 15,
            }
        })
        assert config.enabled is True
        assert config.interval_hours == 12
        assert config.retry_delay_minutes == 15

    def test_interval_hours_positive(self):
        """Test interval_hours must be positive."""
        with pytest.raises(ValueError, match="interval_hours must be positive"):
            _parse_scheduler_config({"scheduler": {"interval_hours": 0}})

    def test_retry_delay_non_negative(self):
        """Test retry_delay_minutes cannot be negative."""
        with pytest.raises(ValueError, match="retry_delay_minutes cannot be negative"):
            _parse_scheduler_config({"scheduler": {"retry_delay_minutes": -1}})


class TestTelegramConfigValidation:
    """Tests for telegram config validation."""

    def test_valid_telegram_config(self):
        """Test valid telegram configuration."""
        config = _parse_telegram_config({
            "telegram": {
                "enabled": True,
                "bot_token": "123456:ABC",
                "chat_ids": ["12345", "67890"],
                "max_jobs_in_message": 20,
            }
        })
        assert config.enabled is True
        assert config.bot_token == "123456:ABC"
        assert config.chat_ids == ["12345", "67890"]
        assert config.max_jobs_in_message == 20

    def test_min_score_non_negative(self):
        """Test min_score_for_notification cannot be negative."""
        with pytest.raises(ValueError, match="min_score_for_notification cannot be negative"):
            _parse_telegram_config({"telegram": {"min_score_for_notification": -5}})

    def test_max_jobs_minimum(self):
        """Test max_jobs_in_message must be at least 1."""
        with pytest.raises(ValueError, match="max_jobs_in_message must be at least 1"):
            _parse_telegram_config({"telegram": {"max_jobs_in_message": 0}})

    def test_jobs_per_chunk_minimum(self):
        """Test jobs_per_chunk must be at least 1."""
        with pytest.raises(ValueError, match="jobs_per_chunk must be at least 1"):
            _parse_telegram_config({"telegram": {"jobs_per_chunk": 0}})

    def test_jobs_per_chunk_maximum(self):
        """Test jobs_per_chunk must be at most 15 (Telegram limit)."""
        with pytest.raises(ValueError, match="jobs_per_chunk must be at most 15"):
            _parse_telegram_config({"telegram": {"jobs_per_chunk": 20}})

    def test_jobs_per_chunk_valid(self):
        """Test valid jobs_per_chunk values."""
        config = _parse_telegram_config({"telegram": {"jobs_per_chunk": 10}})
        assert config.jobs_per_chunk == 10

        config = _parse_telegram_config({"telegram": {"jobs_per_chunk": 15}})
        assert config.jobs_per_chunk == 15

    def test_chat_ids_normalized(self):
        """Test chat_ids are normalized to strings."""
        config = _parse_telegram_config({
            "telegram": {
                "chat_ids": [12345, "67890", "", None, "  99999  "],
            }
        })
        # Empty and None values should be filtered out
        assert "12345" in config.chat_ids
        assert "67890" in config.chat_ids
        assert "99999" in config.chat_ids
        assert "" not in config.chat_ids


class TestConfigPaths:
    """Tests for Config path properties."""

    def test_path_properties(self):
        """Test that path properties return Path objects."""
        config = Config()

        assert isinstance(config.results_path, Path)
        assert isinstance(config.data_path, Path)
        assert isinstance(config.database_path, Path)
        assert isinstance(config.log_path, Path)

    def test_database_path_composition(self):
        """Test database_path is composed correctly."""
        config = Config()

        assert config.database_path == config.data_path / config.output.database_file


class TestConfigQueries:
    """Tests for Config query methods."""

    def test_get_all_queries_empty(self):
        """Test get_all_queries with no queries."""
        config = Config(queries={})

        assert config.get_all_queries() == []

    def test_get_all_queries_flattened(self):
        """Test get_all_queries flattens all categories."""
        config = Config(queries={
            "category1": ["query1", "query2"],
            "category2": ["query3"],
        })

        queries = config.get_all_queries()

        assert len(queries) == 3
        assert "query1" in queries
        assert "query2" in queries
        assert "query3" in queries
