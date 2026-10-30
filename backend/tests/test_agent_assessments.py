"""External reviews and automatic acquisition use explicit, versioned scoring policies."""

from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient
import pytest

from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate
from openings.common import CONTEXT_BUILDER_VERSION, encode, now
from openings.discovery import AssessmentCreate, RescoreRequest, ScoringWrite


@pytest.fixture
def app(tmp_path, monkeypatch):
    from openings import discovery

    instance = create_app(tmp_path / "assessments.sqlite", start_worker=False)
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


def review(service, job_id, **changes):
    return AssessmentCreate(
        **{
            "job_id": job_id,
            "expected_signature": service.assessment_context(job_id)["signature"],
            "score": 0,
            "rationale": "Reviewed the available posting against the stated career evidence.",
            **changes,
        }
    )


@pytest.mark.parametrize("transport", ["rest", "mcp"])
def test_external_review_works_when_disabled_with_idempotence_and_context_conflicts(app, transport):
    workspace, service = app.state.workspace, app.state.discovery
    job = workspace.ingest_job(
        {
            "title": "Partial role",
            "company": "Example",
            "posting": "Short preview",
            "metadata": {"description_complete": False},
        }
    )
    workspace.set_triage(job["id"], "dismissed", job["version"])
    for index, state in enumerate(("queued", "running")):
        workspace.db.execute(
            "INSERT INTO tasks(id,kind,job_id,state,lease_owner,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (f"task-{index}", "score", job["id"], state, "worker", now(), now(), now()),
        )
    value = review(service, job["id"], rationale="Partial posting; no matching evidence found.")
    token = app.state.auth.create_token("Synthetic reviewer")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:
        if transport == "mcp":
            client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "synthetic", "version": "1"},
                    },
                },
            ).raise_for_status()

        def record(body, conflict=False):
            if transport == "rest":
                response = client.post("/api/v1/scoring/assessments", json=body)
                assert response.status_code == (409 if conflict else 200)
                return response.json()
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "scoring_record_assessment", "arguments": {"value": body}},
                },
            )
            assert response.status_code == 200
            result = response.json()["result"]
            assert bool(result.get("isError")) is conflict
            if conflict:
                return result
            return result.get("structuredContent") or json.loads(result["content"][0]["text"])

        first = record(value.model_dump())
        assert first["score"] == 0 and first["model"] == "external-agent"
        assert first["payload"]["provider"] == "external_review"
        assert first["payload"]["rationale"] == value.rationale
        assert first["payload"]["context"]["signature"] == value.expected_signature
        assert first["payload"]["criteria"] == service.get_scoring()["criteria"]
        assert record(value.model_dump()) == first
        changed = record({**value.model_dump(), "score": 43, "source": "reviewer"})
        assert changed["id"] != first["id"] and changed["model"] == "reviewer"
        assert (
            workspace.db.one("SELECT score FROM assessments WHERE id=?", (first["id"],))["score"]
            == 0
        )
        assert all(task["state"] == "cancelled" for task in service.list_tasks()["items"])
        assert workspace.get_job(job["id"])["score"] == 43
        assert not service.get_scoring()["enabled"]
        job = workspace.get_job(job["id"])
        workspace.update_job(
            job["id"], {"expected_version": job["version"], "posting": "New evidence."}
        )
        record(value.model_dump(), conflict=True)
        assert workspace.db.one("SELECT count(*) n FROM assessments")["n"] == 2


def test_identical_concurrent_reviews_create_one_assessment(app):
    workspace, service = app.state.workspace, app.state.discovery
    job = workspace.ingest_job({"posting": "Build Python APIs."})
    value = review(service, job["id"], score=81)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.record_assessment(value), range(8)))
    assert len({result["id"] for result in results}) == 1
    assert workspace.db.one("SELECT count(*) n FROM assessments")["n"] == 1


def test_external_review_cancels_in_flight_model_result(app, monkeypatch):
    from openings import discovery

    workspace, service = app.state.workspace, app.state.discovery
    service.update_scoring(ScoringWrite(expected_version=0, enabled=True))
    job = workspace.ingest_job({"posting": "Build APIs."})
    task = service.claim_task("synthetic-worker", kind="score")

    def reviewed_during_inference(config, state):
        service.record_assessment(review(service, job["id"], score=0, source="external-reviewer"))
        return {"score": 99, "model": "synthetic-model", "elapsed_seconds": 0, "response": {}}

    monkeypatch.setattr(discovery, "score_call", reviewed_during_inference)
    service.run_task(task, "synthetic-worker")
    assert service.get_task(task["id"])["state"] == "cancelled"
    assert workspace.get_job(job["id"])["score"] == 0
    assert workspace.db.one("SELECT count(*) n FROM assessments")["n"] == 1


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
    assert context["state"]["job"]["posting"] == workspace.get_job(job["id"])["posting"] == posting
    omissions = {entry["field"]: entry["ids"] for entry in context["context_omissions"]}
    assert omissions == {"knowledge": [item["id"]], "claims": [claim["id"]]}


def test_context_builder_freshness_matches_detail_lists_overview_and_batch(app):
    workspace, service = app.state.workspace, app.state.discovery
    jobs = [workspace.ingest_job({"posting": "Build APIs."}) for _ in range(3)]
    for index, job in enumerate(jobs):
        assessment = service.record_assessment(review(service, job["id"], score=80))
        if index < 2:
            payload = assessment["payload"]
            if index == 0:
                payload["context"]["versions"].pop("context_builder")
            else:
                payload["context"]["versions"]["context_builder"] = 1
            workspace.db.execute(
                "UPDATE assessments SET payload=? WHERE id=?", (encode(payload), assessment["id"])
            )
    assert CONTEXT_BUILDER_VERSION == 2
    assert [workspace.get_job(job["id"])["score_outdated"] for job in jobs] == [True, True, False]
    assert (
        workspace.list_jobs(score_state="outdated")["total"]
        == workspace.overview()["outdated"]
        == 2
    )
    assert workspace.list_jobs(score_state="current")["total"] == 1
    assert not service.list_tasks(kind="score", state="queued")["items"]
    service.update_scoring(
        ScoringWrite(expected_version=0, enabled=True, auto_rescore_updates=False)
    )
    assert service.queue_rescore(RescoreRequest(limit=1))["count"] == 1
    task = service.list_tasks(kind="score", state="queued")["items"][0]
    assert task["job_id"] in {jobs[0]["id"], jobs[1]["id"]}
