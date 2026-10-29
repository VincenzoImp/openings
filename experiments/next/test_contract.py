"""Contract feasibility: real SQLite, REST, MCP, evidence validation and backup."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contract import Claim, Draft, Evidence, Job, Prepare, Profile, Template, Workspace, interfaces


@pytest.fixture
def case(tmp_path):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    profile = workspace.add_profile(Profile(name="Alex Example", headline="Backend engineer"))["id"]
    evidence = workspace.add_evidence(
        Evidence(
            profile_id=profile,
            kind="project",
            title="Example service",
            narrative="Built Python APIs; reduced latency by 20%.",
        )
    )["id"]
    claim = workspace.add_claim(
        Claim(evidence_id=evidence, text="Reduced API latency by 20%.", approved=True)
    )["id"]
    template = workspace.add_template(
        Template(
            name="Example",
            tex=Path(__file__).with_name("example.tex.j2").read_text(),
            prompt_append="Prefer concise, concrete bullets.",
        )
    )["id"]
    job = workspace.ingest(
        Job(
            source_key="manual:demo",
            title="Backend engineer",
            company="Example Co",
            posting="Build Python APIs.",
        )
    )["id"]
    request = Prepare(
        job_id=job,
        profile_id=profile,
        template_id=template,
        general_prompt="Use only the supplied evidence.",
        idempotency_key="demo-run",
    )
    yield workspace, request, evidence, claim
    workspace.close()


def output(evidence, claim):
    return Draft(
        bullets=[
            {
                "text": "Reduced API latency by 20%.",
                "evidence_ids": [evidence],
                "claim_ids": [claim],
            }
        ]
    )


def test_context_has_narrative_claims_template_and_layered_prompts(case):
    workspace, request, evidence, claim = case
    run = workspace.prepare(request)
    snapshot = run["snapshot"]
    assert snapshot["evidence"][0]["narrative"] == "Built Python APIs; reduced latency by 20%."
    assert snapshot["claims"][0]["id"] == claim
    assert snapshot["prompts"]["general"] == request.general_prompt
    assert snapshot["prompts"]["template_append"] == "Prefer concise, concrete bullets."


def test_run_stays_frozen_when_profile_changes(case):
    workspace, request, *_ = case
    run = workspace.prepare(request)
    with workspace.db:
        workspace.db.execute(
            "UPDATE profile SET basics=?,version=version+1 WHERE id=?",
            (json.dumps({"name": "Changed"}), request.profile_id),
        )
    assert (
        json.loads(workspace.get_run(run["id"])["snapshot"]["profile"]["basics"])["name"]
        == "Alex Example"
    )


def test_repeated_prepare_is_idempotent(case):
    workspace, request, *_ = case
    assert workspace.prepare(request)["id"] == workspace.prepare(request)["id"]
    assert workspace.db.execute("SELECT COUNT(*) FROM application").fetchone()[0] == 1


def test_idempotency_key_conflict_is_explicit(case):
    workspace, request, *_ = case
    workspace.prepare(request)
    with pytest.raises(ValueError, match="different inputs"):
        workspace.prepare(request.model_copy(update={"application_note": "Changed instruction"}))


def test_reingestion_keeps_identity(case):
    workspace, *_ = case
    job = Job(
        source_key="manual:demo", title="Updated title", company="Example Co", posting="Updated"
    )
    assert workspace.ingest(job)["id"] == workspace.ingest(job)["id"]
    assert workspace.db.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 1


def test_unknown_evidence_is_rejected(case):
    workspace, request, *_ = case
    run = workspace.prepare(request)
    with pytest.raises(ValueError, match="Evidence"):
        workspace.submit(
            run["id"], Draft(bullets=[{"text": "Invented", "evidence_ids": ["unknown"]}])
        )


def test_unapproved_claim_is_not_available(case):
    workspace, request, evidence, _ = case
    claim = workspace.add_claim(Claim(evidence_id=evidence, text="Not reviewed yet"))["id"]
    run = workspace.prepare(request)
    with pytest.raises(ValueError, match="unapproved"):
        workspace.submit(run["id"], output(evidence, claim))


def test_template_constraints_apply_to_all_writers(case):
    workspace, request, evidence, claim = case
    run = workspace.prepare(request)
    draft = Draft(bullets=[{"text": "x" * 181, "evidence_ids": [evidence], "claim_ids": [claim]}])
    with pytest.raises(ValueError, match="character limit"):
        workspace.submit(run["id"], draft)


def test_submission_requires_review_and_is_idempotent(case):
    workspace, request, evidence, claim = case
    run = workspace.prepare(request)
    first = workspace.submit(run["id"], output(evidence, claim))
    assert first == workspace.submit(run["id"], output(evidence, claim))
    assert first["review_state"] == "needs_review"


def test_backup_includes_pdf_bytes(case, tmp_path):
    workspace, request, evidence, claim = case
    run = workspace.prepare(request)
    artifact = workspace.submit(run["id"], output(evidence, claim))
    pdf = b"%PDF-1.4\nsynthetic bytes for storage test; real compilation tested separately"
    workspace.attach_pdf(artifact["id"], pdf)
    workspace.backup(tmp_path / "portable.sqlite")
    with sqlite3.connect(tmp_path / "portable.sqlite") as restored:
        assert restored.execute("SELECT content FROM blob").fetchone()[0] == pdf
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.asyncio
async def test_rest_and_mcp_share_the_same_frozen_context(case):
    workspace, request, *_ = case
    api, mcp = interfaces(workspace)
    with TestClient(api) as client:
        run = client.post("/runs", json=request.model_dump()).json()
        result = await mcp.call_tool("get_run", {"run_id": run["id"]})
        payload = json.loads(result[0].text)
        assert payload["snapshot_hash"] == run["snapshot_hash"]
        assert client.get("/runs/" + run["id"]).json()["snapshot"] == payload["snapshot"]


@pytest.mark.asyncio
async def test_rest_and_mcp_reject_the_same_bad_evidence(case):
    workspace, request, *_ = case
    api, mcp = interfaces(workspace)
    run = workspace.prepare(request)
    draft = {"bullets": [{"text": "Invented", "evidence_ids": ["unknown"]}]}
    with TestClient(api) as client:
        assert client.post("/runs/" + run["id"] + "/drafts", json=draft).status_code == 422
    with pytest.raises(Exception, match="Evidence"):
        await mcp.call_tool("submit", {"run_id": run["id"], "draft": draft})
