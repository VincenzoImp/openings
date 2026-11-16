"""The skills' calls, followed step by step over MCP with an agent token.

Each test walks one skill's method on a small synthetic workspace and checks that
the calls it names succeed, with no 409 or 422 the skill does not expect, and that
the critical actions undo as the core skill's table says.
"""

import hashlib
import sqlite3
from contextlib import closing

from document_fixtures import text_pdf


def ok(result):
    value, error = result
    assert error is None, error
    return value


def items(result):
    value = ok(result)
    for item in value["items"]:
        assert item["ok"], item
    return value["items"]


def put(mcp, grant, data):
    response = mcp.client.put(grant["url"], headers=grant["headers"], content=data)
    assert response.status_code == 200, response.text


def revision(mcp, application_id, kind, data, **extra):
    """documents_create, then the PDF at once with the grant it returns."""
    spec = {"name": f"{kind}.pdf", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    created = ok(
        mcp.call(
            "documents_create",
            {"application_id": application_id, "kind": kind, "pdf": spec, **extra},
        )
    )
    put(mcp, created["uploads"]["pdf"], data)
    return created


def test_triage_completes_postings_undoes_a_shortlist_with_work_and_links_duplicates(app, mcp):
    workspace = app.state.workspace
    partial = workspace.ingest_job(
        {
            "url": "https://jobs.example.org/partial",
            "title": "Platform engineer",
            "posting": "Apply",
            "metadata": {"description_complete": False},
        }
    )
    earlier = workspace.ingest_job(
        {
            "url": "https://jobs.example.org/1",
            "title": "Data Engineer",
            "company": "Northstar Labs",
            "location": "Zurich, Switzerland",
            "posting": "Build data pipelines in Python and SQL for a synthetic team. " * 12,
        }
    )
    copy = workspace.ingest_job(
        {
            "url": "https://jobs.example.org/2",
            "title": "Data Engineer",
            "company": "Northstar Labs AG",
            "location": "Zurich, Switzerland",
            "posting": "Build data pipelines in Python and SQL for a synthetic team. " * 12,
        }
    )
    worked = workspace.ingest_job({"title": "Backend engineer", "posting": "Build APIs."})
    application = workspace.create_application({"job_id": worked["id"]})
    ok(mcp.call("notes_create", {"job_id": worked["id"], "body": "Fit: strong."}))

    # §3 Complete partial postings: the page's text with the job's version.
    waiting = ok(mcp.call("jobs_list", {"triage": "new", "complete": False}))["items"]
    assert [job["id"] for job in waiting] == [partial["id"]]
    ok(
        mcp.call(
            "jobs_update",
            {
                "job_id": partial["id"],
                "expected_version": partial["version"],
                "posting": "Run Kubernetes clusters for a synthetic product. " * 10,
            },
        )
    )
    assert ok(mcp.call("jobs_list", {"triage": "new", "complete": False}))["total"] == 0

    # §6 A shortlist whose application has work: back to new is refused, so close it.
    refused = ok(mcp.call("jobs_triage", {"items": [{"job_id": worked["id"], "to": "new"}]}))
    assert refused["items"][0]["error"]["code"] == "application_has_work"
    closed = items(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {
                        "application_id": application["id"],
                        "stage": "closed",
                        "outcome": "not_pursued",
                    }
                ]
            },
        )
    )
    assert closed[0]["result"]["stage"] == "closed"
    # The core table's undo: any other stage reopens it.
    reopened = items(
        mcp.call(
            "applications_update",
            {"items": [{"application_id": application["id"], "stage": "shortlisted"}]},
        )
    )
    assert reopened[0]["result"]["stage"] == "shortlisted"

    # §7 Duplicates: the newer job, linked into the one its signal names.
    flagged = ok(mcp.call("jobs_list", {"signal": "likely_duplicate"}))["items"]
    assert [job["id"] for job in flagged] == [copy["id"]]
    signal = ok(mcp.call("jobs_get", {"ids": [copy["id"]]}))["items"][0]["signals"]["duplicate"]
    assert signal["job_id"] == earlier["id"]
    current = ok(mcp.call("jobs_get", {"ids": [copy["id"]]}))["items"][0]
    kept = ok(
        mcp.call(
            "jobs_link",
            {
                "job_id": copy["id"],
                "other_id": signal["job_id"],
                "decision": "same",
                "expected_version": current["version"],
            },
        )
    )
    assert kept["id"] == earlier["id"]

    # Shortlist with a priority through applications_create, no version read; dismiss
    # with a reason, and undo the dismissal.
    started = items(
        mcp.call(
            "applications_create",
            {"items": [{"job_id": earlier["id"], "priority": 2, "deadline": "2099-01-31"}]},
        )
    )
    started = ok(mcp.call("applications_get", {"ids": [started[0]["id"]]}))["items"][0]
    assert (started["priority"], started["deadline"]) == (2, "2099-01-31")
    dismissed = items(
        mcp.call(
            "jobs_triage",
            {"items": [{"job_id": partial["id"], "to": "dismissed", "reason": "On call 24/7."}]},
        )
    )
    assert dismissed[0]["result"]["triage"] == "dismissed"
    items(mcp.call("jobs_triage", {"items": [{"job_id": partial["id"], "to": "new"}]}))
    assert workspace.get_job(partial["id"])["triage"] == "new"


def test_a_reply_on_an_unsent_application_records_applied_first(app, mcp):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": "Data engineer", "posting": "Build pipelines."})
    application = workspace.create_application({"job_id": job["id"]})
    # "They invited me": one call, Applied with its day first, then the reply.
    recorded = items(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {
                        "application_id": application["id"],
                        "stage": "applied",
                        "applied_on": "2026-01-05",
                    },
                    {
                        "application_id": application["id"],
                        "reply": {"kind": "interview", "date": "2026-01-12", "note": "Monday."},
                    },
                ]
            },
        )
    )
    assert recorded[1]["result"]["stage"] == "interview"
    read = ok(mcp.call("applications_get", {"ids": [application["id"]]}))["items"][0]
    assert len(read["replies"]) == 1 and read["applied_at"].startswith("2026-01-05")
    # Undo: the reply by reply_fix, then Applied by going back to Shortlisted.
    items(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {
                        "application_id": application["id"],
                        "reply_fix": {"reply_id": read["replies"][0]["id"], "delete": True},
                    },
                    {"application_id": application["id"], "stage": "shortlisted"},
                ]
            },
        )
    )
    undone = ok(mcp.call("applications_get", {"ids": [application["id"]]}))["items"][0]
    assert undone["stage"] == "shortlisted" and undone.get("applied_at") is None


def test_a_policy_resolves_an_ai_clause_and_a_redo_keeps_the_application_ready(app, mcp):
    workspace = app.state.workspace
    job = workspace.ingest_job(
        {"title": "Analyst", "posting": "Applications written with AI tools are not accepted."}
    )
    application = items(
        mcp.call(
            "applications_create",
            {"items": [{"job_id": job["id"], "priority": 3, "idempotency_key": "start-1"}]},
        )
    )[0]["result"]
    questions = [{"id": "notice", "label": "Notice period", "type": "text"}]
    read = ok(mcp.call("applications_get", {"ids": [application["id"]]}))["items"][0]
    # Working with me states the owner's policy: resolved, not blocking, with a note.
    items(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {
                        "application_id": application["id"],
                        "expected_version": read["version"],
                        "requirements": [
                            {
                                "kind": "authorship",
                                "text": "Applications written with AI tools are not accepted.",
                                "resolved": True,
                                "note": "Working with me: prepare even when an employer bans AI.",
                            }
                        ],
                        "questions": questions,
                        "answers": {"notice": "One month."},
                    }
                ]
            },
        )
    )
    cv = revision(mcp, application["id"], "cv", text_pdf("Alex Example", "CV one"))
    revision(mcp, application["id"], "letter", text_pdf("Dear team,", "Letter one"))
    before = ok(mcp.call("applications_get", {"ids": [application["id"]]}))["items"][0]
    assert before["ready"] is True

    # Redo after a template change: a new revision replacing the current one.
    key = f"cv-{application['id']}-2-{cv['id']}"
    redone = revision(
        mcp,
        application["id"],
        "cv",
        text_pdf("Alex Example", "CV two"),
        previous_id=cv["id"],
        idempotency_key=key,
        note="Template Main CV, version 2.",
    )
    after = ok(mcp.call("applications_get", {"ids": [application["id"]]}))["items"][0]
    assert after["ready"] is True
    assert redone["revision_number"] == cv["revision_number"] + 1
    for field in ("requirements", "answers", "questions", "priority", "deadline"):
        assert after.get(field) == before.get(field), field
    # A second run with the same key creates nothing new.
    again = ok(
        mcp.call(
            "documents_create",
            {
                "application_id": application["id"],
                "kind": "cv",
                "pdf": {
                    "name": "cv.pdf",
                    "size": len(text_pdf("Alex Example", "CV two")),
                    "sha256": hashlib.sha256(text_pdf("Alex Example", "CV two")).hexdigest(),
                },
                "previous_id": cv["id"],
                "idempotency_key": key,
                "note": "Template Main CV, version 2.",
            },
        )
    )
    assert again["id"] == redone["id"]


def test_a_run_repeated_on_the_same_state_changes_nothing(app, mcp):
    workspace = app.state.workspace
    for number in range(3):
        workspace.ingest_job(
            {"title": f"Engineer {number}", "posting": f"Build services {number}. " * 5}
        )

    def run():
        """The run's cohorts come from the current state; keys come from the records."""
        new = ok(mcp.call("jobs_list", {"triage": "new"})).get("items", [])
        if new:
            items(
                mcp.call(
                    "applications_create",
                    {"items": [{"job_id": job["id"], "priority": 2} for job in new]},
                )
            )
        waiting = ok(mcp.call("applications_list", {"needs": "documents", "sort": "priority"}))
        for application in waiting.get("items", []):
            ok(
                mcp.call(
                    "notes_create",
                    {
                        "job_id": application["job_id"],
                        "application_id": application["id"],
                        "body": "Not prepared: the posting asks for a work sample.",
                        "idempotency_key": f"fit-{application['id']}",
                    },
                )
            )
        return ok(mcp.call("changes_list", {"actor": "agent", "limit": 200}))["total"]

    first = run()
    assert first > 0
    assert run() == first


def test_a_backup_is_checked_and_an_agent_run_is_undone(app, mcp, tmp_path):
    workspace = app.state.workspace
    jobs = [
        workspace.ingest_job({"title": f"Role {number}", "posting": "Sell things."})
        for number in range(3)
    ]
    run = ok(
        mcp.call(
            "jobs_triage",
            {
                "items": [
                    {"job_id": job["id"], "to": "dismissed", "reason": "A sales role."}
                    for job in jobs
                ]
            },
        )
    )
    grant = ok(mcp.call("workspace_backup"))
    assert grant["curl"].startswith("curl ")
    copy = tmp_path / "openings-backup.sqlite"
    copy.write_bytes(mcp.client.get(grant["url"], headers=grant["headers"]).content)
    with closing(sqlite3.connect(copy)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    # Undo the run: the jobs its batch dismissed go back to new.
    found = ok(mcp.call("jobs_list", {"triage": "dismissed", "batch_id": run["batch_id"]}))
    assert found["total"] == 3
    items(
        mcp.call(
            "jobs_triage",
            {"items": [{"job_id": job["id"], "to": "new"} for job in found["items"]]},
        )
    )
    assert {workspace.get_job(job["id"])["triage"] for job in jobs} == {"new"}
