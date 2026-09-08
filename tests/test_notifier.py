from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from openings.config import TelegramConfig, parse_config
from openings.db import ReconciliationReport
from openings.models import RunSummary, SourceRunStats
from openings.notifier import (
    TELEGRAM_MESSAGE_LIMIT,
    NotificationManager,
    TelegramNotifier,
    build_run_notification,
    escape_markdown,
    format_reconcile_message,
)
from tests.conftest import make_job, minimal_settings


def test_escape_markdown_escapes_reserved_characters():
    assert (
        escape_markdown("C++ (Senior) - 100% remote!") == "C\\+\\+ \\(Senior\\) \\- 100% remote\\!"
    )


def test_build_run_notification_sorts_by_score_and_keeps_timezone():
    summary = RunSummary(
        started_at=datetime(2026, 9, 8, 6, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 8, 6, 5, tzinfo=timezone.utc),
    )
    summary.sources.append(SourceRunStats(name="linkedin", tasks=2, succeeded=2, rows=4))
    jobs = [make_job(title="Low", relevance_score=10), make_job(title="High", relevance_score=90)]
    data = build_run_notification(summary, jobs, 20, 7, timezone="Europe/Zurich")
    assert [job.title for job in data.new_jobs] == ["High", "Low"]
    assert data.source_lines == ["linkedin: 4 rows, 2/2 ok"]
    header = TelegramNotifier(TelegramConfig()).header(data, 2)
    assert "2026\\-09\\-08 08:05" in header  # rendered in Zurich time


def test_format_job_and_chunks():
    config = TelegramConfig(enabled=True, bot_token="t", chat_ids=["1"], jobs_per_chunk=2)
    notifier = TelegramNotifier(config)
    text = notifier.format_job(make_job(is_remote=True), 1)
    assert text.startswith("1️⃣ *Backend Engineer*")
    assert "🏠 Remote" in text
    assert "[Open posting →](https://www.linkedin.com/jobs/view/1000001)" in text
    chunks = notifier.chunks([make_job(title=f"J{i}") for i in range(5)])
    assert len(chunks) == 3
    assert chunks[0].startswith("📋 *New postings \\(1/3\\)*")


def test_chunks_stay_under_the_telegram_limit():
    notifier = TelegramNotifier(TelegramConfig(jobs_per_chunk=15))
    jobs = [make_job(title="X" * 600, company="Y" * 300) for _ in range(15)]
    chunks = notifier.chunks(jobs)
    assert len(chunks) > 1
    assert all(len(chunk) <= TELEGRAM_MESSAGE_LIMIT for chunk in chunks)


def test_is_configured_requires_token_and_chat():
    assert not TelegramNotifier(
        TelegramConfig(enabled=True, bot_token="", chat_ids=["1"])
    ).is_configured()
    assert not TelegramNotifier(
        TelegramConfig(enabled=True, bot_token="t", chat_ids=[])
    ).is_configured()
    assert TelegramNotifier(
        TelegramConfig(enabled=True, bot_token="t", chat_ids=["1"])
    ).is_configured()


@pytest.mark.asyncio
async def test_send_run_sends_header_and_chunks():
    config = TelegramConfig(
        enabled=True, bot_token="t", chat_ids=["1", "2"], max_jobs=3, jobs_per_chunk=2
    )
    notifier = TelegramNotifier(config)
    now = datetime.now(timezone.utc)
    summary = RunSummary(started_at=now, finished_at=now)
    data = build_run_notification(summary, [make_job(title=f"J{i}") for i in range(5)], 20, 5)
    with patch("openings.notifier.Bot") as bot_class:
        bot = AsyncMock()
        bot_class.return_value = bot
        assert await notifier.send_run(data) is True
    # header + 2 chunks (3 jobs at 2 per chunk), for each of 2 chats
    assert bot.send_message.await_count == 6


@pytest.mark.asyncio
async def test_send_run_skips_empty_digest_unless_asked():
    quiet = TelegramNotifier(TelegramConfig(enabled=True, bot_token="t", chat_ids=["1"]))
    data = build_run_notification(RunSummary(started_at=datetime.now(timezone.utc)), [], 20, 0)
    assert await quiet.send_run(data) is False
    chatty = TelegramNotifier(
        TelegramConfig(enabled=True, bot_token="t", chat_ids=["1"], send_empty=True)
    )
    with patch("openings.notifier.Bot") as bot_class:
        bot_class.return_value = AsyncMock()
        assert await chatty.send_run(data) is True


def test_manager_without_channels(data_dir):
    config = parse_config(minimal_settings(), data_dir=data_dir)
    manager = NotificationManager(config)
    assert not manager.has_channels()
    empty = build_run_notification(RunSummary(started_at=datetime.now(timezone.utc)), [], 20, 0)
    assert manager.send_run(empty) == {}


def test_manager_sends_reconcile(data_dir, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    data = minimal_settings()
    data["notifications"] = {
        "enabled": True,
        "telegram": {"enabled": True, "bot_token": "$TELEGRAM_BOT_TOKEN", "chat_ids": ["1"]},
    }
    manager = NotificationManager(parse_config(data, data_dir=data_dir))
    assert manager.has_channels()
    with patch("openings.notifier.Bot") as bot_class:
        bot_class.return_value = AsyncMock()
        report = ReconciliationReport(deleted_stale=2, protected=1)
        assert manager.send_reconcile(report) == {"telegram": True}
    assert "Stale: 2" in format_reconcile_message(ReconciliationReport(deleted_stale=2))
