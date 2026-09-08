"""Notifications: a Telegram digest of the postings a run discovered."""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from openings.logger import get_logger
from openings.models import utcnow

try:
    from telegram import Bot
    from telegram.constants import ParseMode
    from telegram.error import TelegramError
except ImportError:  # pragma: no cover - optional at import time, required at send time
    Bot = None  # type: ignore[assignment, misc]
    ParseMode = None  # type: ignore[assignment, misc]
    TelegramError = Exception  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from openings.config import Config, TelegramConfig
    from openings.db import ReconciliationReport
    from openings.models import Job, RunSummary

POSITION_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
_MARKDOWN_ESCAPE = re.compile(r"([_*\[\]()~`>#+=|{}.!\-\\])")
TELEGRAM_MESSAGE_LIMIT = 4096


def escape_markdown(text: str | None) -> str:
    """Escape for Telegram MarkdownV2."""
    if not text:
        return ""
    return _MARKDOWN_ESCAPE.sub(r"\\\1", str(text))


def escape_url(url: str | None) -> str:
    if not url:
        return ""
    return url.replace("\\", "\\\\").replace(")", "\\)")


@dataclass
class RunNotification:
    run_timestamp: datetime
    duration: str
    total_found: int
    unique_found: int
    saved: int
    new_count: int
    new_jobs: list[Job]
    notify_threshold: int
    total_in_db: int
    source_lines: list[str]
    errors: int
    timezone: str = "UTC"


def build_run_notification(
    summary: RunSummary,
    new_jobs: list[Job],
    notify_threshold: int,
    total_in_db: int,
    timezone: str = "UTC",
) -> RunNotification:
    return RunNotification(
        run_timestamp=summary.finished_at or utcnow(),
        duration=summary.duration_formatted,
        total_found=summary.total_found,
        unique_found=summary.unique_found,
        saved=summary.saved,
        new_count=summary.new_jobs,
        new_jobs=sorted(new_jobs, key=lambda job: job.relevance_score, reverse=True),
        notify_threshold=notify_threshold,
        total_in_db=total_in_db,
        source_lines=[
            f"{stat.name}: {stat.rows} rows, {stat.succeeded}/{stat.tasks} ok"
            for stat in summary.sources
        ],
        errors=len(summary.errors),
        timezone=timezone,
    )


class TelegramNotifier:
    name = "telegram"

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.logger = get_logger("telegram")

    def is_configured(self) -> bool:
        return (
            self.config.enabled
            and bool(self.config.bot_token)
            and any(chat_id for chat_id in self.config.chat_ids)
        )

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_job(job: Job, index: int) -> str:
        marker = POSITION_EMOJIS[index - 1] if index <= len(POSITION_EMOJIS) else f"{index}\\."
        lines = [f"{marker} *{escape_markdown(job.title or 'Untitled')}*"]
        if job.company:
            lines.append(f"   🏢 {escape_markdown(job.company)}")
        if job.location:
            lines.append(f"   📍 {escape_markdown(job.location)}")
        lines.append(f"   ⭐ Score {job.relevance_score} · {escape_markdown(job.source)}")
        if job.is_remote:
            lines.append("   🏠 Remote")
        if job.job_url:
            lines.append(f"   [Open posting →]({escape_url(job.job_url)})")
        return "\n".join(lines)

    def header(self, data: RunNotification, shown: int) -> str:
        try:
            stamp = data.run_timestamp.astimezone(ZoneInfo(data.timezone))
        except (ValueError, KeyError):
            stamp = data.run_timestamp
        lines = [
            "🔔 *Openings \\- run complete*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"• {escape_markdown(stamp.strftime('%Y-%m-%d %H:%M'))} · {escape_markdown(data.duration)}",
            f"• Collected {data.total_found}, unique {data.unique_found}, saved {data.saved}",
            f"• New: {data.new_count} · In database: {data.total_in_db}",
        ]
        for line in data.source_lines:
            lines.append(f"• {escape_markdown(line)}")
        if data.errors:
            lines.append(f"• ⚠️ {data.errors} source error\\(s\\), see the run log")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        if shown:
            lines.append(f"🆕 *{shown} new postings* \\(score ≥ {data.notify_threshold}\\)")
        else:
            lines.append("ℹ️ No new postings above the notify threshold\\.")
        return "\n".join(lines)

    def chunks(self, jobs: list[Job]) -> list[str]:
        """Messages of at most ``jobs_per_chunk`` postings, each under Telegram's limit."""
        size = self.config.jobs_per_chunk
        groups: list[list[tuple[int, Job]]] = [
            list(enumerate(jobs[start : start + size], start + 1))
            for start in range(0, len(jobs), size)
        ]
        # Split any group whose rendering would exceed the message limit.
        index = 0
        while index < len(groups):
            group = groups[index]
            if (
                len(self._render(group, index + 1, len(groups))) > TELEGRAM_MESSAGE_LIMIT
                and len(group) > 1
            ):
                half = len(group) // 2
                groups[index : index + 1] = [group[:half], group[half:]]
                continue
            index += 1
        return [
            self._render(group, position + 1, len(groups))[:TELEGRAM_MESSAGE_LIMIT]
            for position, group in enumerate(groups)
        ]

    def _render(self, group: list[tuple[int, Job]], position: int, total: int) -> str:
        lines: list[str] = []
        if total > 1:
            lines.append(f"📋 *New postings \\({position}/{total}\\)*\n")
        for number, job in group:
            lines.append(self.format_job(job, number))
            lines.append("")
        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def _send_messages(self, messages: list[str]) -> bool:
        if Bot is None:
            self.logger.error("python-telegram-bot is not installed")
            return False
        bot = Bot(token=self.config.bot_token)
        delivered = 0
        for chat_id in self.config.chat_ids:
            if not chat_id:
                continue
            ok = True
            for message in messages:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                except TelegramError as exc:
                    ok = False
                    self.logger.error("Telegram send to %s failed: %s", chat_id, exc)
                    self.logger.debug("Failed message (%d chars): %s", len(message), message[:300])
            delivered += int(ok)
        return delivered > 0

    async def send_run(self, data: RunNotification) -> bool:
        if not self.is_configured():
            return False
        jobs = data.new_jobs[: self.config.max_jobs]
        if not jobs and not self.config.send_empty:
            self.logger.info("Nothing new; digest skipped")
            return False
        messages: list[str] = []
        if self.config.send_summary:
            messages.append(self.header(data, len(jobs)))
        messages.extend(self.chunks(jobs))
        if not messages:
            return False
        self.logger.info(
            "Sending %d Telegram message(s) to %d chat(s)", len(messages), len(self.config.chat_ids)
        )
        return await self._send_messages(messages)

    async def send_text(self, text: str) -> bool:
        if not self.is_configured():
            return False
        return await self._send_messages([text])


def format_reconcile_message(report: ReconciliationReport) -> str:
    return (
        "🧹 *Startup cleanup*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Removed: {report.total_deleted}\n"
        f"• Below save threshold: {report.deleted_below_score}\n"
        f"• Stale: {report.deleted_stale}\n"
        f"• Protected \\(acted on\\): {report.protected}"
    )


def _run_async(coro):
    """Run a coroutine from sync code, even inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(runner).result(timeout=120)


class NotificationManager:
    """All configured channels behind one call."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger("notifications")
        self._channels: list[TelegramNotifier] = []
        if config.notifications.enabled and config.notifications.telegram.enabled:
            telegram = TelegramNotifier(config.notifications.telegram)
            if telegram.is_configured():
                self._channels.append(telegram)

    def has_channels(self) -> bool:
        return bool(self._channels)

    def send_run(self, data: RunNotification) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for channel in self._channels:
            try:
                results[channel.name] = _run_async(channel.send_run(data))
            except Exception as exc:  # noqa: BLE001
                self.logger.error("%s notification failed: %s", channel.name, exc)
                results[channel.name] = False
        return results

    def send_reconcile(self, report: ReconciliationReport) -> dict[str, bool]:
        text = format_reconcile_message(report)
        results: dict[str, bool] = {}
        for channel in self._channels:
            try:
                results[channel.name] = _run_async(channel.send_text(text))
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("%s reconcile message failed: %s", channel.name, exc)
                results[channel.name] = False
        return results
