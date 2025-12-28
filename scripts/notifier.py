"""
Notification system for Job Search Tool.

Sends alerts when new jobs are found via various channels (Telegram, etc.).
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from logger import get_logger

if TYPE_CHECKING:
    from config import Config, TelegramConfig
    from models import JobDBRecord


# Base directory for templates
BASE_DIR = Path(__file__).parent.parent.resolve()
TEMPLATES_DIR = BASE_DIR / "templates"


@dataclass
class NotificationData:
    """Data structure for notification content."""

    run_timestamp: datetime
    total_jobs_found: int
    new_jobs_count: int
    updated_jobs_count: int
    avg_score: float
    top_jobs: list[JobDBRecord]
    all_new_jobs: list[JobDBRecord]


class BaseNotifier(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    async def send_notification(self, data: NotificationData) -> bool:
        """
        Send notification with job data.

        Args:
            data: Notification data containing job information.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if the notifier is properly configured.

        Returns:
            True if configured and ready to send, False otherwise.
        """
        pass


class TelegramNotifier(BaseNotifier):
    """Telegram notification channel using python-telegram-bot."""

    def __init__(self, config: TelegramConfig):
        """
        Initialize Telegram notifier.

        Args:
            config: Telegram configuration from settings.
        """
        self.config = config
        self._bot = None
        self._jinja_env = None
        self.logger = get_logger("telegram_notifier")

        # Use environment variable if available (safer than config file)
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", config.bot_token)

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return (
            self.config.enabled
            and bool(self.bot_token)
            and len(self.config.chat_ids) > 0
            and self.config.chat_ids[0] != ""
        )

    def _get_jinja_env(self) -> Environment:
        """Get Jinja2 environment for template rendering."""
        if self._jinja_env is None:
            if TEMPLATES_DIR.exists():
                self._jinja_env = Environment(
                    loader=FileSystemLoader(str(TEMPLATES_DIR)),
                    autoescape=select_autoescape(["html", "xml"]),
                )
            else:
                # Fallback: create environment without file loader
                self._jinja_env = Environment(autoescape=False)
        return self._jinja_env

    def _format_job_message(self, job: JobDBRecord, index: int) -> str:
        """
        Format a single job for Telegram message.

        Args:
            job: Job record to format.
            index: Position in the list (1-based).

        Returns:
            Formatted job string in Markdown.
        """
        # Emoji for position
        position_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        emoji = position_emojis[index - 1] if index <= 10 else f"{index}."

        # Build message parts
        parts = [f"{emoji} *{self._escape_markdown(job.title)}*"]

        if job.company:
            parts.append(f"   🏢 {self._escape_markdown(job.company)}")

        if job.location:
            parts.append(f"   📍 {self._escape_markdown(job.location)}")

        parts.append(f"   ⭐ Score: {job.relevance_score}")

        if job.is_remote:
            parts.append("   🏠 Remote")

        if job.job_url:
            parts.append(f"   [View Job →]({job.job_url})")

        return "\n".join(parts)

    def _escape_markdown(self, text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.

        Args:
            text: Text to escape.

        Returns:
            Escaped text safe for MarkdownV2.
        """
        if not text:
            return ""

        # Characters that need escaping in MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        result = str(text)
        for char in special_chars:
            result = result.replace(char, f"\\{char}")
        return result

    def _build_summary_message(self, data: NotificationData) -> str:
        """
        Build the summary notification message.

        Args:
            data: Notification data.

        Returns:
            Formatted message string.
        """
        lines = [
            "🔔 *Job Search Tool \\- New Jobs Found*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            "📊 *Run Summary*",
            f"• Date: {self._escape_markdown(data.run_timestamp.strftime('%Y-%m-%d %H:%M'))}",
            f"• Total found: {data.total_jobs_found}",
            f"• New: {data.new_jobs_count}",
            f"• Updated: {data.updated_jobs_count}",
            f"• Avg score: {self._escape_markdown(f'{data.avg_score:.1f}')}",
        ]

        if data.new_jobs_count == 0:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                "",
                "ℹ️ No new jobs found in this search\\.",
            ])
        else:
            # Filter jobs by minimum score
            filtered_jobs = [
                job for job in data.top_jobs
                if job.relevance_score >= self.config.min_score_for_notification
            ]

            if filtered_jobs:
                lines.extend([
                    "",
                    "━━━━━━━━━━━━━━━━━━━━━",
                    "",
                    f"🏆 *Top {min(len(filtered_jobs), self.config.max_jobs_in_message)} New Jobs*",
                    "",
                ])

                for idx, job in enumerate(filtered_jobs[:self.config.max_jobs_in_message], 1):
                    lines.append(self._format_job_message(job, idx))
                    lines.append("")

                if len(data.all_new_jobs) > self.config.max_jobs_in_message:
                    remaining = len(data.all_new_jobs) - self.config.max_jobs_in_message
                    lines.append(f"📋 \\.\\.\\. and {remaining} more jobs in database")

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "🤖 Job Search Tool",
        ])

        return "\n".join(lines)

    async def send_notification(self, data: NotificationData) -> bool:
        """
        Send Telegram notification.

        Args:
            data: Notification data.

        Returns:
            True if sent successfully to at least one recipient.
        """
        if not self.is_configured():
            return False

        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            from telegram.error import TelegramError

            bot = Bot(token=self.bot_token)
            message = self._build_summary_message(data)

            success_count = 0
            for chat_id in self.config.chat_ids:
                if not chat_id:
                    continue

                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                    success_count += 1
                    self.logger.debug(f"Successfully sent notification to chat {chat_id}")
                except TelegramError as e:
                    # Log error but continue with other recipients
                    self.logger.error(f"Failed to send to chat {chat_id}: {e}")

            return success_count > 0

        except ImportError:
            self.logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return False
        except Exception as e:
            self.logger.error(f"Telegram notification error: {e}")
            return False


class NotificationManager:
    """
    Manages all notification channels.

    Provides a unified interface to send notifications across all configured channels.
    """

    def __init__(self, config: Config):
        """
        Initialize notification manager.

        Args:
            config: Main configuration object.
        """
        self.config = config
        self._notifiers: list[BaseNotifier] = []
        self.logger = get_logger("notification_manager")
        self._setup_notifiers()

    def _setup_notifiers(self) -> None:
        """Set up all configured notification channels."""
        if not self.config.notifications.enabled:
            return

        # Telegram
        if self.config.notifications.telegram.enabled:
            telegram = TelegramNotifier(self.config.notifications.telegram)
            if telegram.is_configured():
                self._notifiers.append(telegram)

    def has_configured_notifiers(self) -> bool:
        """Check if any notifier is configured and ready."""
        return len(self._notifiers) > 0

    async def send_all(self, data: NotificationData) -> dict[str, bool]:
        """
        Send notification to all configured channels.

        Args:
            data: Notification data.

        Returns:
            Dictionary mapping channel name to success status.
        """
        results = {}

        for notifier in self._notifiers:
            channel_name = notifier.__class__.__name__
            try:
                results[channel_name] = await notifier.send_notification(data)
            except Exception as e:
                self.logger.error(f"Error sending notification via {channel_name}: {e}")
                results[channel_name] = False

        return results

    def send_all_sync(self, data: NotificationData) -> dict[str, bool]:
        """
        Synchronous wrapper for send_all.

        Args:
            data: Notification data.

        Returns:
            Dictionary mapping channel name to success status.
        """
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
            # If we got here, we're in an async context - create task
            return loop.run_until_complete(self.send_all(data))
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(self.send_all(data))


def create_notification_data(
    new_jobs: list[JobDBRecord],
    updated_count: int,
    total_found: int,
    avg_score: float,
) -> NotificationData:
    """
    Create NotificationData from search results.

    Args:
        new_jobs: List of newly found jobs.
        updated_count: Number of jobs that were updated (already existed).
        total_found: Total jobs found in this search.
        avg_score: Average relevance score.

    Returns:
        NotificationData ready for sending.
    """
    # Sort by score for top jobs
    sorted_jobs = sorted(new_jobs, key=lambda j: j.relevance_score, reverse=True)

    return NotificationData(
        run_timestamp=datetime.now(),
        total_jobs_found=total_found,
        new_jobs_count=len(new_jobs),
        updated_jobs_count=updated_count,
        avg_score=avg_score,
        top_jobs=sorted_jobs,  # Pass all jobs, let notifier apply max_jobs_in_message
        all_new_jobs=sorted_jobs,
    )
