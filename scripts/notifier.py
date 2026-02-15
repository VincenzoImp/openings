"""
Notification system for Job Search Tool.

Sends alerts when new jobs are found via various channels (Telegram, etc.).
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from logger import get_logger

if TYPE_CHECKING:
    from config import Config, TelegramConfig
    from models import JobDBRecord


@dataclass
class NotificationData:
    """Data structure for notification content."""

    run_timestamp: datetime
    total_jobs_found: int
    new_jobs_count: int
    updated_jobs_count: int
    avg_score: float
    new_jobs: list[JobDBRecord]  # All new jobs, sorted by score descending
    top_jobs_overall: list[JobDBRecord]  # Top jobs from entire database, sorted by score
    total_jobs_in_db: int = 0  # Total number of jobs in database


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
        self.logger = get_logger("telegram_notifier")
        self.bot_token = config.bot_token or ""

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return (
            self.config.enabled
            and bool(self.bot_token)
            and len(self.config.chat_ids) > 0
            and self.config.chat_ids[0] != ""
        )

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
        emoji = position_emojis[index - 1] if index <= 10 else f"{index}\\."

        # Build message parts
        title = job.title if job.title else "Untitled"
        parts = [f"{emoji} *{self._escape_markdown(title)}*"]

        if job.company:
            parts.append(f"   🏢 {self._escape_markdown(job.company)}")

        if job.location:
            parts.append(f"   📍 {self._escape_markdown(job.location)}")

        score = job.relevance_score if job.relevance_score is not None else 0
        parts.append(f"   ⭐ Score: {score}")

        if job.is_remote:
            parts.append("   🏠 Remote")

        if job.job_url:
            parts.append(f"   [View Job →]({self._escape_url(job.job_url)})")

        return "\n".join(parts)

    # Precompiled regex for MarkdownV2 escaping (faster than loop)
    _MARKDOWN_ESCAPE_PATTERN = re.compile(r'([_*\[\]()~`>#+=|{}.!\-\\])')

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
        return self._MARKDOWN_ESCAPE_PATTERN.sub(r'\\\1', str(text))

    def _escape_url(self, url: str) -> str:
        """
        Escape URL for use inside Markdown link parentheses.

        In MarkdownV2 links [text](url), only ) and \\ need escaping in the URL.

        Args:
            url: URL to escape.

        Returns:
            Escaped URL safe for MarkdownV2 links.
        """
        if not url:
            return ""
        # Only escape ) and \ inside URLs for MarkdownV2
        return url.replace("\\", "\\\\").replace(")", "\\)")

    @property
    def jobs_per_chunk(self) -> int:
        """Get jobs per chunk from config (Telegram has 4096 char limit)."""
        return self.config.jobs_per_chunk

    def _build_header_message(
        self,
        data: NotificationData,
        total_new_jobs: int,
        total_top_overall: int,
    ) -> str:
        """
        Build the header/summary message (sent first).

        Args:
            data: Notification data.
            total_new_jobs: Number of new jobs that will be notified.
            total_top_overall: Number of top overall jobs that will be notified.

        Returns:
            Formatted header message string.
        """
        lines = [
            "🔔 *Job Search Tool \\- Run Complete*",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            "📊 *Run Summary*",
            f"• Date: {self._escape_markdown(data.run_timestamp.strftime('%Y-%m-%d %H:%M'))}",
            f"• Total found: {data.total_jobs_found}",
            f"• New: {data.new_jobs_count}",
            f"• Updated: {data.updated_jobs_count}",
            f"• Avg score: {self._escape_markdown(f'{data.avg_score:.1f}')}",
            f"• Jobs in DB: {data.total_jobs_in_db}",
        ]

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])

        if total_new_jobs > 0:
            lines.append(f"🆕 *{total_new_jobs} New Jobs* \\(score ≥ {self.config.min_score_for_notification}\\)")
        else:
            lines.append("ℹ️ No new jobs matching notification criteria\\.")

        if total_top_overall > 0:
            lines.append(f"🏆 *{total_top_overall} Top Jobs Overall* \\(from database\\)")

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            "🤖 Job Search Tool",
        ])

        return "\n".join(lines)

    def _build_section_header(self, title: str, emoji: str) -> str:
        """
        Build a section header message for job lists.

        Args:
            title: Section title (e.g., "New Jobs", "Top Jobs Overall").
            emoji: Emoji to use for the section.

        Returns:
            Formatted section header string.
        """
        return f"{emoji} *{self._escape_markdown(title)}*\n━━━━━━━━━━━━━━━━━━━━━"

    def _build_jobs_chunk_message(self, jobs: list, start_index: int, chunk_num: int, total_chunks: int) -> str:
        """
        Build a message for a chunk of jobs.

        Args:
            jobs: List of jobs for this chunk.
            start_index: Starting index for numbering (1-based).
            chunk_num: Current chunk number (1-based).
            total_chunks: Total number of chunks.

        Returns:
            Formatted jobs chunk message.
        """
        lines = []

        if total_chunks > 1:
            lines.append(f"📋 *Jobs \\({chunk_num}/{total_chunks}\\)*")
            lines.append("")

        for idx, job in enumerate(jobs, start_index):
            lines.append(self._format_job_message(job, idx))
            lines.append("")

        return "\n".join(lines)

    def _build_summary_message(self, data: NotificationData) -> str:
        """
        Build the summary notification message (legacy single-message format).

        This is kept for backward compatibility but send_notification now uses
        chunked messages for large job lists.

        Args:
            data: Notification data.

        Returns:
            Formatted message string.
        """
        # Filter jobs by minimum score
        filtered_jobs = [
            job for job in data.new_jobs
            if job.relevance_score >= self.config.min_score_for_notification
        ]
        jobs_to_send = filtered_jobs[:self.config.max_jobs_in_message]

        return self._build_header_message(data, len(jobs_to_send))

    async def send_notification(self, data: NotificationData) -> bool:
        """
        Send Telegram notification with chunked messages for large job lists.

        Sends a header message first, then jobs in chunks (configurable via jobs_per_chunk)
        to avoid hitting Telegram's 4096 character message limit.

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

            # Filter NEW jobs by minimum score
            filtered_new_jobs = [
                job for job in data.new_jobs
                if job.relevance_score >= self.config.min_score_for_notification
            ]
            new_jobs_to_send = filtered_new_jobs[:self.config.max_jobs_in_message]
            total_new_jobs = len(new_jobs_to_send)

            # Get TOP JOBS OVERALL (from entire database)
            top_overall_to_send = []
            if self.config.include_top_overall and data.top_jobs_overall:
                top_overall_to_send = data.top_jobs_overall[:self.config.max_top_overall]
            total_top_overall = len(top_overall_to_send)

            # Build header message
            header_message = self._build_header_message(data, total_new_jobs, total_top_overall)

            # Build NEW JOBS chunk messages
            new_job_messages = []
            if total_new_jobs > 0:
                chunk_size = self.jobs_per_chunk
                total_chunks = (total_new_jobs + chunk_size - 1) // chunk_size
                for chunk_idx in range(total_chunks):
                    start_idx = chunk_idx * chunk_size
                    end_idx = min(start_idx + chunk_size, total_new_jobs)
                    chunk_jobs = new_jobs_to_send[start_idx:end_idx]
                    chunk_message = self._build_jobs_chunk_message(
                        jobs=chunk_jobs,
                        start_index=start_idx + 1,  # 1-based indexing
                        chunk_num=chunk_idx + 1,
                        total_chunks=total_chunks,
                    )
                    new_job_messages.append(chunk_message)

            # Build TOP JOBS OVERALL chunk messages
            top_overall_messages = []
            if total_top_overall > 0:
                # Add section header for top jobs overall
                section_header = self._build_section_header("Top Jobs Overall", "🏆")
                top_overall_messages.append(section_header)

                chunk_size = self.jobs_per_chunk
                total_chunks = (total_top_overall + chunk_size - 1) // chunk_size
                for chunk_idx in range(total_chunks):
                    start_idx = chunk_idx * chunk_size
                    end_idx = min(start_idx + chunk_size, total_top_overall)
                    chunk_jobs = top_overall_to_send[start_idx:end_idx]
                    chunk_message = self._build_jobs_chunk_message(
                        jobs=chunk_jobs,
                        start_index=start_idx + 1,  # 1-based indexing
                        chunk_num=chunk_idx + 1,
                        total_chunks=total_chunks,
                    )
                    top_overall_messages.append(chunk_message)

            self.logger.info(
                f"Sending Telegram notification to {len(self.config.chat_ids)} recipient(s): "
                f"1 header + {len(new_job_messages)} new job chunk(s) + {len(top_overall_messages)} top overall chunk(s)"
            )

            success_count = 0
            for chat_id in self.config.chat_ids:
                if not chat_id:
                    continue

                try:
                    # Send header message first
                    await bot.send_message(
                        chat_id=chat_id,
                        text=header_message,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )

                    # Send NEW JOBS section header if there are new jobs
                    if new_job_messages:
                        new_jobs_header = self._build_section_header("New Jobs", "🆕")
                        await bot.send_message(
                            chat_id=chat_id,
                            text=new_jobs_header,
                            parse_mode=ParseMode.MARKDOWN_V2,
                            disable_web_page_preview=True,
                        )

                    # Send new job chunks
                    for chunk_idx, job_message in enumerate(new_job_messages, 1):
                        try:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=job_message,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                disable_web_page_preview=True,
                            )
                        except TelegramError as chunk_err:
                            self.logger.error(
                                f"Failed to send new jobs chunk {chunk_idx}/{len(new_job_messages)}: {chunk_err}"
                            )
                            self.logger.debug(f"Failed message length: {len(job_message)} chars")

                    # Send TOP JOBS OVERALL chunks (includes section header)
                    for chunk_idx, top_message in enumerate(top_overall_messages, 1):
                        try:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=top_message,
                                parse_mode=ParseMode.MARKDOWN_V2,
                                disable_web_page_preview=True,
                            )
                        except TelegramError as chunk_err:
                            self.logger.error(
                                f"Failed to send top overall chunk {chunk_idx}/{len(top_overall_messages)}: {chunk_err}"
                            )
                            self.logger.debug(f"Failed message length: {len(top_message)} chars")

                    success_count += 1
                    self.logger.info(f"Telegram notification sent to chat {chat_id}")
                except TelegramError as e:
                    # Log the full error for debugging MarkdownV2 issues
                    self.logger.error(f"Failed to send to chat {chat_id}: {e}")
                    self.logger.debug(f"Header message:\n{header_message[:500]}...")

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

        Handles both sync and async contexts correctly.

        Args:
            data: Notification data.

        Returns:
            Dictionary mapping channel name to success status.
        """
        try:
            # Check if we're already in an async context
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(self.send_all(data))

        # We're in an async context - run in a separate thread with its own loop
        import concurrent.futures

        def _run_in_new_loop() -> dict[str, bool]:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.send_all(data))
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_new_loop)
            return future.result(timeout=120)


def create_notification_data(
    new_jobs: list[JobDBRecord],
    updated_count: int,
    total_found: int,
    avg_score: float,
    top_jobs_overall: list[JobDBRecord] | None = None,
    total_jobs_in_db: int = 0,
) -> NotificationData:
    """
    Create NotificationData from search results.

    Args:
        new_jobs: List of newly found jobs.
        updated_count: Number of jobs that were updated (already existed).
        total_found: Total jobs found in this search.
        avg_score: Average relevance score.
        top_jobs_overall: Top jobs from the entire database (not just new).
        total_jobs_in_db: Total number of jobs in the database.

    Returns:
        NotificationData ready for sending.
    """
    # Sort by score for top jobs
    sorted_jobs = sorted(new_jobs, key=lambda j: j.relevance_score, reverse=True)

    # Sort top jobs overall by score (should already be sorted, but ensure)
    sorted_top_overall = []
    if top_jobs_overall:
        sorted_top_overall = sorted(
            top_jobs_overall, key=lambda j: j.relevance_score, reverse=True
        )

    return NotificationData(
        run_timestamp=datetime.now(),
        total_jobs_found=total_found,
        new_jobs_count=len(new_jobs),
        updated_jobs_count=updated_count,
        avg_score=avg_score,
        new_jobs=sorted_jobs,
        top_jobs_overall=sorted_top_overall,
        total_jobs_in_db=total_jobs_in_db,
    )
