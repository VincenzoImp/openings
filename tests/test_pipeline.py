from unittest.mock import patch

import yaml

from openings.config import get_config
from openings.database import get_database
from openings.models import JobStatus
from openings.pipeline import prepare_runtime, run_collection
from tests.conftest import minimal_settings

FEED = {
    "jobs": [
        {
            "id": 1,
            "title": "Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/x/jobs/1",
            "location": {"name": "Remote"},
            "content": "Python and PostgreSQL",
        },
        {
            "id": 2,
            "title": "Sales Lead",
            "absolute_url": "https://boards.greenhouse.io/x/jobs/2",
            "location": {"name": "Remote"},
            "content": "10+ years selling",
        },
    ]
}


def _write_settings(settings_file, **overrides):
    data = minimal_settings()
    data["sources"]["companies"] = [{"name": "X", "ats": "greenhouse", "slug": "x"}]
    for key, value in overrides.items():
        data[key] = value
    settings_file.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_run_collection_saves_scores_and_records_run(env, settings_file):
    _write_settings(settings_file)
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=FEED):
        prepare_runtime(scheduled=False)
        assert run_collection() is True
    db = get_database(get_config())
    jobs = {job.title: job for job in db.iter_jobs()}
    assert set(jobs) == {"Backend Engineer"}  # the -40 row is below save_threshold 0
    assert jobs["Backend Engineer"].relevance_score == 35
    assert jobs["Backend Engineer"].status is JobStatus.NEW
    run = db.list_runs()[0]
    assert run.success and run.new_jobs == 1 and run.saved == 1
    assert run.sources[0].name == "greenhouse:x"


def test_second_run_updates_without_new(env, settings_file):
    _write_settings(settings_file)
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=FEED):
        prepare_runtime(scheduled=False)
        run_collection()
        run_collection()
    runs = get_database(get_config()).list_runs()
    assert [run.new_jobs for run in runs] == [0, 1]


def test_source_failure_is_recorded_not_fatal(env, settings_file):
    from openings.sources.base import SourceError

    _write_settings(settings_file)
    with patch("openings.sources.ats.greenhouse.http_get_json", side_effect=SourceError("down")):
        prepare_runtime(scheduled=False)
        assert run_collection() is True
    run = get_database(get_config()).list_runs()[0]
    assert run.success is True
    assert run.errors == ["greenhouse:x: down"]


def test_prepare_runtime_reconciles_against_new_threshold(env, settings_file):
    _write_settings(settings_file)
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=FEED):
        prepare_runtime(scheduled=False)
        run_collection()
    db = get_database(get_config())
    assert db.count_jobs() == 1
    _write_settings(
        settings_file,
        scoring={**minimal_settings()["scoring"], "save_threshold": 50, "notify_threshold": 50},
    )
    from openings.config import set_config

    set_config(None)
    prepare_runtime(scheduled=False)
    assert db.count_jobs() == 0


def test_notification_receives_only_new_rows_above_threshold(env, settings_file, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    _write_settings(
        settings_file,
        notifications={
            "enabled": True,
            "telegram": {"enabled": True, "bot_token": "$TELEGRAM_BOT_TOKEN", "chat_ids": ["1"]},
        },
    )
    sent = []

    def fake_send_run(self, data):
        sent.append(data)
        return {"telegram": True}

    with (
        patch("openings.sources.ats.greenhouse.http_get_json", return_value=FEED),
        patch("openings.pipeline.NotificationManager.send_run", fake_send_run),
    ):
        prepare_runtime(scheduled=False)
        run_collection()
        run_collection()
    assert [len(data.new_jobs) for data in sent] == [1, 0]
    assert sent[0].new_jobs[0].title == "Backend Engineer"
