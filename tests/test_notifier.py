"""Tests for notifier module.

Tests for Telegram notification functionality including:
- Message formatting and escaping
- Notification data creation
- Telegram API integration (mocked)
- NotificationManager coordination
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import Config, NotificationsConfig, TelegramConfig
from models import JobDBRecord
from notifier import (
    NotificationData,
    NotificationManager,
    TelegramNotifier,
    create_notification_data,
    create_reconcile_notification_data,
    format_reconcile_message,
)


# =============================================================================
# TEST NOTIFICATION DATA
# =============================================================================


class TestNotificationData:
    """Tests for NotificationData dataclass."""

    def test_create_notification_data(self, sample_job_db_record):
        """Test create_notification_data helper function."""
        new_jobs = [sample_job_db_record]

        data = create_notification_data(
            new_jobs=new_jobs,
            updated_count=5,
            total_found=20,
            avg_score=25.5,
        )

        assert data.new_jobs_count == 1
        assert data.updated_jobs_count == 5
        assert data.total_jobs_found == 20
        assert data.avg_score == 25.5
        assert len(data.new_jobs) == 1
        assert isinstance(data.run_timestamp, datetime)

    def test_create_notification_data_empty(self):
        """Test create_notification_data with no jobs."""
        data = create_notification_data(
            new_jobs=[],
            updated_count=0,
            total_found=0,
            avg_score=0.0,
        )

        assert data.new_jobs_count == 0
        assert data.new_jobs == []

    def test_create_notification_data_sorts_by_score(self):
        """Test that jobs are sorted by relevance score."""
        jobs = [
            JobDBRecord(
                job_id="1",
                title="Low",
                company="A",
                location="NYC",
                relevance_score=10,
                first_seen=datetime.now().date(),
                last_seen=datetime.now().date(),
            ),
            JobDBRecord(
                job_id="2",
                title="High",
                company="B",
                location="NYC",
                relevance_score=50,
                first_seen=datetime.now().date(),
                last_seen=datetime.now().date(),
            ),
            JobDBRecord(
                job_id="3",
                title="Mid",
                company="C",
                location="NYC",
                relevance_score=30,
                first_seen=datetime.now().date(),
                last_seen=datetime.now().date(),
            ),
        ]

        data = create_notification_data(
            new_jobs=jobs,
            updated_count=0,
            total_found=3,
            avg_score=30.0,
        )

        # Should be sorted descending by score
        assert data.new_jobs[0].relevance_score == 50
        assert data.new_jobs[1].relevance_score == 30
        assert data.new_jobs[2].relevance_score == 10


# =============================================================================
# TEST TELEGRAM NOTIFIER - CONFIGURATION
# =============================================================================


class TestTelegramNotifierConfiguration:
    """Tests for TelegramNotifier configuration checking."""

    def test_is_configured_true(self, telegram_config):
        """Test is_configured returns True when properly configured."""
        notifier = TelegramNotifier(telegram_config)

        assert notifier.is_configured() is True

    def test_is_configured_false_when_disabled(self, telegram_config):
        """Test is_configured returns False when disabled."""
        telegram_config.enabled = False
        notifier = TelegramNotifier(telegram_config)

        assert notifier.is_configured() is False

    def test_is_configured_false_no_token(self, telegram_config):
        """Test is_configured returns False when token is missing."""
        telegram_config.bot_token = ""
        notifier = TelegramNotifier(telegram_config)

        assert notifier.is_configured() is False

    def test_is_configured_false_no_chat_ids(self, telegram_config):
        """Test is_configured returns False when no chat IDs."""
        telegram_config.chat_ids = []
        notifier = TelegramNotifier(telegram_config)

        assert notifier.is_configured() is False

    def test_is_configured_false_empty_chat_id(self, telegram_config):
        """Test is_configured returns False when chat ID is empty string."""
        telegram_config.chat_ids = [""]
        notifier = TelegramNotifier(telegram_config)

        assert notifier.is_configured() is False


# =============================================================================
# TEST TELEGRAM NOTIFIER - MARKDOWN ESCAPING
# =============================================================================


class TestTelegramNotifierEscaping:
    """Tests for Telegram MarkdownV2 escaping functions."""

    @pytest.fixture
    def notifier(self, telegram_config):
        """Create a TelegramNotifier instance."""
        return TelegramNotifier(telegram_config)

    def test_escape_markdown_special_chars(self, notifier):
        """Test that special markdown characters are escaped."""
        text = "Test *bold* _italic_ [link](url) `code`"
        escaped = notifier._escape_markdown(text)

        assert "\\*" in escaped
        assert "\\_" in escaped
        assert "\\[" in escaped
        assert "\\]" in escaped
        assert "\\(" in escaped
        assert "\\)" in escaped
        assert "\\`" in escaped

    def test_escape_markdown_preserves_text(self, notifier):
        """Test that regular text is preserved."""
        text = "Software Engineer at TechCorp"
        escaped = notifier._escape_markdown(text)

        assert "Software" in escaped
        assert "Engineer" in escaped
        assert "TechCorp" in escaped

    def test_escape_markdown_empty_string(self, notifier):
        """Test escaping empty string returns empty."""
        assert notifier._escape_markdown("") == ""
        assert notifier._escape_markdown(None) == ""

    def test_escape_url_parentheses(self, notifier):
        """Test URL escaping handles parentheses."""
        url = "https://example.com/job(123)"
        escaped = notifier._escape_url(url)

        assert "\\)" in escaped
        assert "https://example.com/job" in escaped

    def test_escape_url_backslash(self, notifier):
        """Test URL escaping handles backslashes."""
        url = "https://example.com\\path"
        escaped = notifier._escape_url(url)

        assert "\\\\" in escaped

    def test_escape_url_empty(self, notifier):
        """Test escaping empty URL returns empty."""
        assert notifier._escape_url("") == ""
        assert notifier._escape_url(None) == ""


# =============================================================================
# TEST TELEGRAM NOTIFIER - MESSAGE FORMATTING
# =============================================================================


class TestTelegramNotifierFormatting:
    """Tests for Telegram message formatting functions."""

    @pytest.fixture
    def notifier(self, telegram_config):
        """Create a TelegramNotifier instance."""
        return TelegramNotifier(telegram_config)

    def test_format_job_message(self, notifier, sample_job_db_record):
        """Test job message formatting."""
        message = notifier._format_job_message(sample_job_db_record, 1)

        # Should contain job details (escaped)
        assert "Software Engineer" in message or "Software\\ Engineer" in message
        assert "Test Corp" in message or "Test\\ Corp" in message
        # Should contain position emoji
        assert "1️⃣" in message

    def test_format_job_message_position_emojis(self, notifier, sample_job_db_record):
        """Test that position emojis are used for first 10 jobs."""
        expected_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, emoji in enumerate(expected_emojis, 1):
            message = notifier._format_job_message(sample_job_db_record, i)
            assert emoji in message

    def test_format_job_message_beyond_10(self, notifier, sample_job_db_record):
        """Test formatting for jobs beyond position 10."""
        message = notifier._format_job_message(sample_job_db_record, 15)
        assert "15" in message

    def test_format_job_message_with_url(self, notifier):
        """Test that job URL is included as link."""
        job = JobDBRecord(
            job_id="test123",
            title="Software Engineer",
            company="Test Corp",
            location="New York, NY",
            job_url="https://example.com/job/123",
            first_seen=datetime.now().date(),
            last_seen=datetime.now().date(),
            relevance_score=25,
        )
        message = notifier._format_job_message(job, 1)

        assert "View Job" in message
        assert "https://example.com/job/123" in message

    def test_format_job_message_remote_badge(self, notifier):
        """Test that remote badge is shown for remote jobs."""
        job = JobDBRecord(
            job_id="test123",
            title="Software Engineer",
            company="Test Corp",
            location="New York, NY",
            is_remote=True,
            first_seen=datetime.now().date(),
            last_seen=datetime.now().date(),
            relevance_score=25,
        )
        message = notifier._format_job_message(job, 1)

        assert "🏠" in message or "Remote" in message

    def test_build_header_message(self, notifier, sample_notification_data):
        """Test header message building."""
        header = notifier._build_header_message(sample_notification_data, 5, 3)

        assert "Job Search Tool" in header
        assert "Run Summary" in header
        assert "New:" in header
        assert "Total found:" in header
        assert "Jobs in DB:" in header

    def test_build_header_message_no_jobs(self, notifier, empty_notification_data):
        """Test header message when no jobs found."""
        header = notifier._build_header_message(empty_notification_data, 0, 0)

        assert "No new jobs" in header or "notification criteria" in header

    def test_build_header_message_with_top_overall(
        self, notifier, sample_notification_data
    ):
        """Test header message shows top overall section."""
        header = notifier._build_header_message(sample_notification_data, 3, 5)

        assert "5 Top Jobs Overall" in header or "Top Jobs Overall" in header

    def test_build_jobs_chunk_message(self, notifier, sample_job_db_record):
        """Test jobs chunk message building."""
        jobs = [sample_job_db_record]
        message = notifier._build_jobs_chunk_message(jobs, 1, 1, 1)

        # Should contain job details
        assert "Software Engineer" in message or "Software\\ Engineer" in message

    def test_build_jobs_chunk_message_with_pagination(
        self, notifier, sample_job_db_record
    ):
        """Test chunk message includes pagination when multiple chunks."""
        jobs = [sample_job_db_record]
        message = notifier._build_jobs_chunk_message(jobs, 1, 2, 3)

        assert "2/3" in message


# =============================================================================
# TEST TELEGRAM NOTIFIER - SEND NOTIFICATION
# =============================================================================


class TestTelegramNotifierSend:
    """Tests for TelegramNotifier.send_notification method."""

    @pytest.fixture
    def notifier(self, telegram_config):
        """Create a TelegramNotifier instance."""
        return TelegramNotifier(telegram_config)

    @pytest.mark.asyncio
    async def test_send_notification_not_configured(self, telegram_config):
        """Test send_notification returns False when not configured."""
        telegram_config.enabled = False
        notifier = TelegramNotifier(telegram_config)

        result = await notifier.send_notification(
            NotificationData(
                run_timestamp=datetime.now(),
                total_jobs_found=0,
                new_jobs_count=0,
                updated_jobs_count=0,
                avg_score=0,
                new_jobs=[],
                top_jobs_overall=[],
                total_jobs_in_db=0,
            )
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_success(self, notifier, sample_notification_data):
        """Test successful notification sending."""
        with patch("notifier.Bot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(return_value=MagicMock())
            mock_bot_class.return_value = mock_bot

            result = await notifier.send_notification(sample_notification_data)

            assert result is True
            # Should have sent at least one message (header)
            assert mock_bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_notification_telegram_error(
        self, notifier, sample_notification_data
    ):
        """Test handling of Telegram API errors."""
        with patch("notifier.Bot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(side_effect=Exception("API Error"))
            mock_bot_class.return_value = mock_bot

            result = await notifier.send_notification(sample_notification_data)

            # Should return False on error
            assert result is False

    def test_reconcile_notification_formatting(self):
        """ReconcileNotificationData → Telegram-safe MarkdownV2 text."""
        from database import ReconciliationReport

        report = ReconciliationReport(
            deleted_below_score=4,
            deleted_stale=3,
            purged_blacklist=2,
        )
        data = create_reconcile_notification_data(report)

        msg = format_reconcile_message(data)

        assert "Startup cleanup" in msg
        assert "Total removed: 9" in msg
        assert "Below save threshold: 4" in msg
        assert "Stale" in msg
        assert "Blacklist" in msg

    @pytest.mark.asyncio
    async def test_send_notification_respects_send_summary_flag(
        self, notifier, telegram_config, sample_notification_data
    ):
        """Test summary header is skipped when send_summary is disabled."""
        telegram_config.send_summary = False
        notifier = TelegramNotifier(telegram_config)

        with patch("notifier.Bot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(return_value=MagicMock())
            mock_bot_class.return_value = mock_bot

            result = await notifier.send_notification(sample_notification_data)

        assert result is True
        sent_texts = [
            call.kwargs["text"] for call in mock_bot.send_message.call_args_list
        ]
        assert all("Run Summary" not in text for text in sent_texts)

    @pytest.mark.asyncio
    async def test_send_notification_returns_false_when_nothing_to_send(
        self, telegram_config
    ):
        """Test disabling all output paths does not report a fake success."""
        telegram_config.send_summary = False
        telegram_config.include_top_overall = False
        notifier = TelegramNotifier(telegram_config)

        empty_data = NotificationData(
            run_timestamp=datetime.now(),
            total_jobs_found=0,
            new_jobs_count=0,
            updated_jobs_count=0,
            avg_score=0,
            new_jobs=[],
            top_jobs_overall=[],
            total_jobs_in_db=0,
        )

        with patch("notifier.Bot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(return_value=MagicMock())
            mock_bot_class.return_value = mock_bot

            result = await notifier.send_notification(empty_data)

        assert result is False
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_returns_false_on_partial_chunk_failure(
        self,
        telegram_config,
    ):
        """A chat should not count as successful if the job chunks fail to deliver."""
        telegram_config.chat_ids = ["12345"]
        notifier = TelegramNotifier(telegram_config)

        data = NotificationData(
            run_timestamp=datetime.now(),
            total_jobs_found=1,
            new_jobs_count=1,
            updated_jobs_count=0,
            avg_score=50.0,
            new_jobs=[
                JobDBRecord(
                    job_id="1",
                    title="Job 1",
                    company="Corp",
                    location="Remote",
                    relevance_score=50,
                    first_seen=datetime.now().date(),
                    last_seen=datetime.now().date(),
                )
            ],
            top_jobs_overall=[],
            total_jobs_in_db=1,
        )

        with (
            patch("notifier.TelegramError", Exception),
            patch("notifier.Bot") as mock_bot_class,
        ):
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(
                side_effect=[
                    MagicMock(),  # summary header
                    MagicMock(),  # new jobs section header
                    Exception("chunk failed"),  # actual content chunk
                ]
            )
            mock_bot_class.return_value = mock_bot

            result = await notifier.send_notification(data)

        assert result is False


# =============================================================================
# TEST NOTIFICATION MANAGER
# =============================================================================


class TestNotificationManager:
    """Tests for NotificationManager class."""

    def test_init_no_notifiers_when_disabled(self):
        """Test no notifiers are set up when notifications disabled."""
        config = Config(notifications=NotificationsConfig(enabled=False))
        manager = NotificationManager(config)

        assert manager.has_configured_notifiers() is False

    def test_init_with_telegram_notifier(self, telegram_config):
        """Test Telegram notifier is set up when configured."""
        config = Config(
            notifications=NotificationsConfig(
                enabled=True,
                telegram=telegram_config,
            )
        )
        manager = NotificationManager(config)

        assert manager.has_configured_notifiers() is True

    def test_has_configured_notifiers_false_when_not_configured(self):
        """Test has_configured_notifiers when Telegram not properly configured."""
        config = Config(
            notifications=NotificationsConfig(
                enabled=True,
                telegram=TelegramConfig(
                    enabled=True,
                    bot_token="",  # Missing token
                    chat_ids=[],
                ),
            )
        )
        manager = NotificationManager(config)

        assert manager.has_configured_notifiers() is False

    @pytest.mark.asyncio
    async def test_send_all_returns_results(
        self, telegram_config, sample_notification_data
    ):
        """Test send_all returns dict of results."""
        config = Config(
            notifications=NotificationsConfig(
                enabled=True,
                telegram=telegram_config,
            )
        )
        manager = NotificationManager(config)

        with patch.object(
            TelegramNotifier, "send_notification", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            results = await manager.send_all(sample_notification_data)

            assert isinstance(results, dict)
            assert "TelegramNotifier" in results

    def test_send_all_sync_wrapper(self, telegram_config, sample_notification_data):
        """Test send_all_sync works as synchronous wrapper."""
        config = Config(
            notifications=NotificationsConfig(
                enabled=True,
                telegram=telegram_config,
            )
        )
        manager = NotificationManager(config)

        with patch.object(
            TelegramNotifier, "send_notification", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            results = manager.send_all_sync(sample_notification_data)

            assert isinstance(results, dict)


# =============================================================================
# TEST CHUNKING
# =============================================================================


class TestTelegramNotifierChunking:
    """Tests for message chunking functionality."""

    @pytest.fixture
    def notifier(self, telegram_config):
        """Create a TelegramNotifier with small chunk size for testing."""
        return TelegramNotifier(telegram_config)

    def test_jobs_per_chunk_property(self, notifier):
        """Test jobs_per_chunk property returns config value."""
        assert notifier.jobs_per_chunk == 10

    @pytest.mark.asyncio
    async def test_multiple_chunks_sent(self, notifier):
        """Test that multiple chunks are sent for many jobs."""
        # Create 15 jobs (should result in 2 chunks)
        jobs = [
            JobDBRecord(
                job_id=str(i),
                title=f"Job {i}",
                company="Corp",
                location="NYC",
                relevance_score=50,
                first_seen=datetime.now().date(),
                last_seen=datetime.now().date(),
            )
            for i in range(15)
        ]

        data = NotificationData(
            run_timestamp=datetime.now(),
            total_jobs_found=15,
            new_jobs_count=15,
            updated_jobs_count=0,
            avg_score=50.0,
            new_jobs=jobs,
            top_jobs_overall=[],
            total_jobs_in_db=100,
        )

        with patch("notifier.Bot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock(return_value=MagicMock())
            mock_bot_class.return_value = mock_bot

            await notifier.send_notification(data)

            # Should send: 1 header + 1 section header + 2 job chunks = 4 messages per chat
            # With 2 chat_ids, that's 8 total calls
            assert mock_bot.send_message.call_count >= 4
