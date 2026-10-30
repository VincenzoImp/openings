"""Automatic scoring policies and compact contexts preserve deliberate archive control."""

import pytest

from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate
from openings.common import CONTEXT_BUILDER_VERSION, encode
from openings.discovery import RescoreRequest, ScoringWrite


@pytest.fixture
def app(tmp_path, monkeypatch):
    from openings import discovery

    instance = create_app(tmp_path / "scoring.sqlite", start_worker=False)
    instance.state.auth.setup("synthetic-password")
    instance.state.career.update_profile(
        {
            "expected_version": instance.state.career.get_profile()["version"],
            "summary": "Build Python APIs.",
            "roles": "Backend engineer",
        }
    )
    monkeypatch.setattr(
        discovery,
        "score_call",
        lambda config, state: {
            "score": 75.0,
            "model": "synthetic-model",
            "elapsed_seconds": 0,
            "response": {},
        },
    )
    return instance


def test_new_job_only_policy_preserves_scores_and_allows_explicit_rescore(app):
    workspace, service = app.state.workspace, app.state.discovery
    assert service.get_scoring()["auto_rescore_updates"] is True
    config = service.update_scoring(ScoringWrite(expected_version=0, enabled=True))
    original = {"posting": "Build APIs.", "url": "https://example.test/jobs/one"}
    job = workspace.ingest_job(original)
    task = service.claim_task("worker", kind="score")
    service.run_task(task, "worker")
    config = service.update_scoring(
        ScoringWrite(expected_version=config["version"], auto_rescore_updates=False)
    )
    assert not workspace.get_job(job["id"])["score_outdated"]
    revision = config["assessment_version"]
    refreshed = workspace.ingest_job({**original, "posting": "Build updated APIs."})
    workspace.update_job(
        refreshed["id"], {"expected_version": refreshed["version"], "posting": "User correction."}
    )
    assert not service.list_tasks(kind="score", state="queued")["items"]
    assert service.get_scoring()["assessment_version"] == revision
    added = workspace.ingest_job({"posting": "A new role.", "url": "https://example.test/jobs/two"})
    tasks = service.list_tasks(kind="score", state="queued")["items"]
    assert len(tasks) == 1 and tasks[0]["job_id"] == added["id"]
    service.cancel_task(tasks[0]["id"])
    assert service.queue_rescore(RescoreRequest(job_ids=[job["id"]]))["count"] == 1


def test_explicit_compact_profile_omits_knowledge_and_preserves_full_posting(app):
    career, service, workspace = app.state.career, app.state.discovery, app.state.workspace
    item = career.create_knowledge(
        KnowledgeCreate(kind="fact", title="Detailed fact", narrative="Evidence " * 1000)
    )
    claim = career.create_claim(
        ClaimCreate(knowledge_id=item["id"], text="A reviewed claim.", approved=True)
    )
    profile = career.get_profile()
    career.update_profile(
        {
            "expected_version": profile["version"],
            "scoring_summary": "Compact backend profile.",
            "email": "private@example.test",
        }
    )
    posting = "Complete job description. " * 1000
    job = workspace.ingest_job({"posting": posting})
    context = service.assessment_context(job["id"])
    assert context["state"]["candidate"]["profile"] == {
        "summary": "Compact backend profile.",
        "roles": "Backend engineer",
        "preferences": "",
    }
    assert context["state"]["candidate"]["knowledge"] == []
    assert "private@example.test" not in str(context)
    assert context["state"]["job"]["posting"] == posting.strip()
    assert workspace.get_job(job["id"])["posting"] == posting
    omissions = {entry["field"]: entry["ids"] for entry in context["context_omissions"]}
    assert omissions == {"knowledge": [item["id"]], "claims": [claim["id"]]}


def test_context_builder_freshness_matches_detail_lists_overview_and_batch(app, monkeypatch):
    from openings import discovery

    workspace, service = app.state.workspace, app.state.discovery
    config = service.update_scoring(
        ScoringWrite(expected_version=0, enabled=True, auto_rescore_updates=False)
    )
    jobs = []
    for index in range(3):
        with monkeypatch.context() as legacy:
            legacy.setattr(
                discovery, "CONTEXT_BUILDER_VERSION", 1 if index < 2 else CONTEXT_BUILDER_VERSION
            )
            job = workspace.ingest_job({"posting": "Build APIs."})
            jobs.append(job)
            task = service.claim_task("worker", kind="score")
            service.run_task(task, "worker")
        if index == 0:
            assessment = workspace.get_job(job["id"])["assessment"]
            payload = assessment["payload"]
            payload["context"]["versions"].pop("context_builder")
            workspace.db.execute(
                "UPDATE assessments SET payload=? WHERE id=?", (encode(payload), assessment["id"])
            )
    assert CONTEXT_BUILDER_VERSION == 3
    assert [workspace.get_job(job["id"])["score_outdated"] for job in jobs] == [True, True, False]
    assert (
        workspace.list_jobs(score_state="outdated")["total"]
        == workspace.overview()["outdated"]
        == 2
    )
    assert workspace.list_jobs(score_state="current")["total"] == 1
    assert not service.list_tasks(kind="score", state="queued")["items"]
    assert service.get_scoring()["version"] == config["version"]
    assert service.queue_rescore(RescoreRequest(limit=1))["count"] == 1
    task = service.list_tasks(kind="score", state="queued")["items"][0]
    assert task["job_id"] in {jobs[0]["id"], jobs[1]["id"]}


def test_scoring_projection_cleans_copies_and_excludes_raw_metadata(app, monkeypatch):
    from openings import discovery

    career, service, workspace = app.state.career, app.state.discovery, app.state.workspace
    career.update_profile(
        {
            "expected_version": career.get_profile()["version"],
            "summary": "Python\t engineer.\r\n\r\n\r\nC++ and C#.",
            "metadata": {"raw_cv": "private original " * 1000},
        }
    )
    fact = career.create_knowledge(
        KnowledgeCreate(
            kind="fact",
            title="API experience",
            narrative="Python APIs.",
            skills=["Python"],
            metadata={"raw": "duplicated original " * 1000},
        )
    )
    config = service.update_scoring(
        ScoringWrite(expected_version=0, enabled=True, auto_rescore_updates=False)
    )
    posting = "<h2>Requirements</h2><p>Python &amp; C++.</p><p>5 years.</p>"
    job = workspace.ingest_job(
        {
            "posting": posting,
            "metadata": {"is_remote": True, "raw": {"body": posting * 1000}},
        }
    )
    snapshot = service.assessment_context(job["id"])
    assert snapshot["state"]["job"]["posting"] == "Requirements\nPython & C++.\n5 years."
    assert snapshot["state"]["candidate"]["profile"]["summary"] == (
        "Python engineer.\n\nC++ and C#."
    )
    assert snapshot["state"]["job"]["metadata"] == {"is_remote": True}
    assert snapshot["state"]["candidate"]["knowledge"][0]["skills"] == ["Python"]
    assert snapshot["state"]["candidate"]["knowledge"][0]["metadata"] == {}
    assert workspace.get_job(job["id"])["posting"] == posting
    assert career.get_knowledge(fact["id"])["metadata"]["raw"].startswith("duplicated original")
    assert "raw_cv" in career.get_profile()["metadata"]
    assert discovery.scoring_text("C++: a < b and x > y\nC# / 5 years") == (
        "C++: a < b and x > y\nC# / 5 years"
    )

    prepared = {"version": 1, "state": "Exact prepared model input", "shortened": True}

    def classify(config, state):
        return {
            "score": 50,
            "model": "synthetic",
            "elapsed_seconds": 0,
            "request": {"state": state, "questions": {"fit": config["rubric"]}},
            "response": {"input_preparation": prepared, "usage": {"truncated": True}},
        }

    monkeypatch.setattr(discovery, "score_call", classify)
    task = service.claim_task("worker", kind="score")
    service.run_task(task, "worker")
    assessment = workspace.get_job(job["id"])["assessment"]["payload"]
    assert assessment["request"]["state"] == snapshot["state"]
    assert assessment["response"]["input_preparation"] == prepared
    assert workspace.get_job(job["id"])["posting"] == posting
    assert not service.list_tasks(kind="score", state="queued")["items"]
    assert service.get_scoring()["version"] == config["version"]
