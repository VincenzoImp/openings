from unittest.mock import patch

import yaml

from openings.models import JobStatus
from openings.pipeline import prepare_runtime, run_collection
from tests.conftest import fake_vector

GREENHOUSE = {
    "jobs": [
        {
            "id": 1,
            "title": "Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/x/jobs/1",
            "location": {"name": "Remote"},
            "updated_at": "2026-09-07T10:00:00Z",
            "content": "<p>Python and PostgreSQL</p>",
            "metadata": [],
        },
        {
            "id": 2,
            "title": "Sales Manager",
            "absolute_url": "https://boards.greenhouse.io/x/jobs/2",
            "location": {"name": "Remote"},
            "updated_at": "2026-09-07T10:00:00Z",
            "content": "<p>Quota 10+ years</p>",
            "metadata": [],
        },
    ]
}


def with_company(runtime, settings_dict, **extra):
    settings_dict["sources"]["companies"] = [{"name": "X", "ats": "greenhouse", "slug": "x"}]
    settings_dict["scoring"]["save_threshold"] = -100
    settings_dict.update(extra)
    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    runtime.config(reload=True)


def test_run_collection_saves_scored_rows_records_run_and_postings(runtime, settings_dict):
    with_company(runtime, settings_dict)
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE):
        assert run_collection(runtime) is True
    db = runtime.db
    assert db.count_jobs() == 2
    runs = db.list_runs()
    assert len(runs) == 1 and runs[0].running is False
    assert runs[0].saved == 2 and runs[0].new_jobs == 2 and runs[0].success is True
    assert runs[0].sources[0].name == "greenhouse:x"
    backend = next(job for job in db.iter_jobs() if job.title == "Backend Engineer")
    assert backend.relevance_score == 35 and backend.postings_count == 1
    assert db.list_postings(backend.job_id)[0].key == "greenhouse:1"


def test_second_run_refreshes_without_resurrecting_blacklisted(runtime, settings_dict):
    with_company(runtime, settings_dict)
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE):
        run_collection(runtime)
        sales = next(job for job in runtime.db.iter_jobs() if job.title == "Sales Manager")
        runtime.db.set_status([sales.job_id], JobStatus.BLACKLISTED)
        run_collection(runtime)
    runs = runtime.db.list_runs()
    assert runs[0].new_jobs == 0 and runs[0].saved == 1
    assert runtime.db.get_job(sales.job_id).status is JobStatus.BLACKLISTED


def test_run_with_every_source_failed_is_recorded_as_failed(runtime, settings_dict):
    with_company(runtime, settings_dict)
    from openings.sources.base import SourceError

    with patch("openings.sources.ats.greenhouse.http_get_json", side_effect=SourceError("down")):
        assert run_collection(runtime) is False
    run = runtime.db.list_runs()[0]
    assert run.success is False and "every source failed" in run.errors[-1]


def test_run_collection_records_exception(runtime, settings_dict):
    with_company(runtime, settings_dict)
    with patch("openings.pipeline.collect_all", side_effect=RuntimeError("boom")):
        assert run_collection(runtime) is False
    run = runtime.db.list_runs()[0]
    assert run.success is False and run.errors == ["run: boom"]


def test_run_embeds_saved_jobs(runtime, settings_dict, fake_embedding_model):
    with_company(runtime, settings_dict, embeddings={"enabled": True})
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE):
        run_collection(runtime)
    assert runtime.embeddings.count() == 2
    hits = runtime.embeddings.search("Backend Engineer\nX\nRemote\nPython and PostgreSQL", n=1)
    assert hits and hits[0][1] > 0.99
    assert fake_vector("x").shape == (384,)


def test_prepare_runtime_reconciles_and_closes_stale_runs(runtime, settings_dict):
    from openings.models import RunSummary, utcnow

    settings_dict["scoring"]["save_threshold"] = 20
    settings_dict["retention"] = {"max_age_days": 5}
    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    runtime.config(reload=True)
    from tests.conftest import make_job

    runtime.db.upsert_jobs(
        [
            make_job(relevance_score=5),
            make_job(title="Keep", job_url="https://linkedin.com/jobs/view/9", relevance_score=50),
        ]
    )
    runtime.db.start_run(RunSummary(started_at=utcnow()))
    config = prepare_runtime(runtime, scheduled=True)
    assert config.scoring.save_threshold == 20
    assert runtime.db.count_jobs() == 1
    assert runtime.db.open_run() is None


def test_digest_only_when_new_postings(runtime, settings_dict, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    with_company(
        runtime,
        settings_dict,
        notifications={
            "enabled": True,
            "telegram": {"enabled": True, "bot_token": "$TELEGRAM_BOT_TOKEN", "chat_ids": ["1"]},
        },
    )
    sent: list[list[str]] = []

    async def fake_send(self, messages):
        sent.append(messages)
        return True

    monkeypatch.setattr("openings.notifier.TelegramNotifier._send_messages", fake_send)
    with patch("openings.sources.ats.greenhouse.http_get_json", return_value=GREENHOUSE):
        run_collection(runtime)
        run_collection(runtime)
    assert len(sent) == 1  # the second run found nothing new
    assert runtime.db.list_runs()[1].notified == 1  # only the 35-point job passes notify=20
