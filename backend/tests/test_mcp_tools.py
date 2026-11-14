"""The agent's tools: batch reads and writes, per-item results, versions and refusals."""

import json
from datetime import UTC, datetime, timedelta

from openings.interfaces import OPERATIONS


def ok(result):
    value, error = result
    assert error is None, error
    return value


def jobs(app, count, prefix="Synthetic role"):
    return [
        app.state.workspace.ingest_job(
            {"title": f"{prefix} {n}", "company": "Example", "posting": f"Build APIs {n}."}
        )
        for n in range(count)
    ]


async def test_a_name_that_is_not_a_tool_says_what_to_use(app, mcp):
    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    owner = [op.name for op in OPERATIONS if op.access == "owner"]
    for name in owner:
        # An owner operation names its REST route instead of being a tool.
        _, error = mcp.call(name, {})
        assert error["code"] == "owner_only" and "/api/v1/" in error["message"], name
    for op in OPERATIONS:
        if op.covered_by:
            _, error = mcp.call(op.name, {})
            assert error["code"] == "rest_only", op.name
            assert error["details"]["use"] == list(op.covered_by), op.name
            assert set(op.covered_by) <= tools, op.name
    # A bulk route names every tool that does its work, deleting included.
    _, error = mcp.call("applications_bulk", {})
    assert error["message"] == (
        "applications_bulk is REST only: use applications_update or applications_delete."
    )
    _, error = mcp.call("made_up_tool", {})
    assert (error["code"], error["status"]) == ("unknown_tool", 404)
    assert "tools/list" in error["message"]


def test_jobs_get_reads_many_and_names_the_missing(app, mcp):
    first, second = jobs(app, 2)
    app.state.workspace.add_note(first["id"], {"body": "Synthetic note."})
    read = ok(mcp.call("jobs_get", {"ids": [first["id"], "missing", second["id"]]}))
    assert [item["id"] for item in read["items"]] == [first["id"], second["id"]]
    assert read["missing"] == ["missing"] and read["items"][0]["posting"] == "Build APIs 0."
    assert read["items"][0]["notes"][0]["body"] == "Synthetic note."
    _, error = mcp.call("jobs_get", {"ids": [str(n) for n in range(21)]})
    assert error["code"] == "validation"

    note = ok(mcp.call("notes_create", {"job_id": first["id"], "body": "First."}))
    changed = ok(
        mcp.call(
            "notes_update",
            {
                "note_id": note["id"],
                "expected_version": note["version"],
                "body": "Edited.",
                "pinned": True,
            },
        )
    )
    assert changed["body"] == "Edited." and changed["pinned"] is True
    _, error = mcp.call(
        "notes_update", {"note_id": note["id"], "expected_version": changed["version"]}
    )
    assert error["code"] == "validation"


def test_jobs_triage_applies_each_item_on_its_own_in_one_batch(app, mcp):
    listed = jobs(app, 4)
    result = ok(
        mcp.call(
            "jobs_triage",
            {
                "items": [
                    {"job_id": listed[0]["id"], "to": "dismissed", "reason": "Too junior."},
                    {"job_id": listed[1]["id"], "to": "dismissed"},
                    {"job_id": "missing", "to": "dismissed", "reason": "Gone."},
                    {"job_id": listed[2]["id"], "to": "shortlisted"},
                    {"job_id": listed[3]["id"], "to": "new", "reason": "Not a dismissal."},
                ]
            },
        )
    )
    assert (result["total"], result["succeeded"], result["failed"]) == (5, 2, 3)
    items = result["items"]
    assert items[0]["ok"] and items[0]["result"]["triage"] == "dismissed"
    assert items[1]["error"]["code"] == "triage_reason"
    assert items[2]["error"]["status"] == 404
    assert items[3]["result"]["application_id"] and items[4]["error"]["code"] == "triage_reason"
    # Every change of the call shares its batch, and the reason is the owner's to read.
    changes = ok(mcp.call("changes_list", {"batch_id": result["batch_id"]}))
    assert {item["batch_id"] for item in changes["items"]} == {result["batch_id"]}
    dismissed = ok(mcp.call("jobs_list", {"triage": "dismissed", "dismissed_by": "agent"}))
    assert dismissed["items"][0]["dismissal"]["reason"] == "Too junior."
    by_url = ok(mcp.call("jobs_list", {"url": "https://example.org/unknown"}))
    assert by_url["total"] == 0


def test_jobs_link_merges_into_the_other_or_marks_them_different(app, mcp):
    first, second, third = jobs(app, 3)
    _, error = mcp.call(
        "jobs_link", {"job_id": first["id"], "other_id": second["id"], "decision": "same"}
    )
    assert error["code"] == "validation"
    kept = ok(
        mcp.call(
            "jobs_link",
            {
                "job_id": first["id"],
                "other_id": second["id"],
                "decision": "same",
                "expected_version": first["version"],
            },
        )
    )
    assert kept["id"] == second["id"]
    assert ok(mcp.call("jobs_get", {"ids": [first["id"]]}))["missing"] == [first["id"]]
    different = ok(
        mcp.call(
            "jobs_link", {"job_id": third["id"], "other_id": second["id"], "decision": "different"}
        )
    )
    assert different["id"] == third["id"]


def test_applications_create_and_update_in_batches(app, mcp):
    first, second, dismissed = jobs(app, 3)
    workspace = app.state.workspace
    workspace.set_triage(second["id"], "shortlisted", second["version"])
    workspace.set_triage(dismissed["id"], "dismissed", dismissed["version"], "Not for me.")
    created = ok(
        mcp.call(
            "applications_create",
            {
                "items": [
                    {"job_id": first["id"], "priority": 2, "idempotency_key": "first"},
                    {"job_id": second["id"], "required_documents": ["cv"]},
                    {"job_id": dismissed["id"]},
                ]
            },
        )
    )
    new, started, refused = created["items"]
    assert new["result"]["created"] is True and new["result"]["stage"] == "shortlisted"
    # Shortlisting started this one: it is returned with the item's fields, not doubled.
    assert started["result"]["created"] is False and started["result"]["missing"] == ["cv"]
    assert refused["ok"] is False and refused["error"]["status"] == 409
    again = ok(
        mcp.call(
            "applications_create",
            {"items": [{"job_id": first["id"], "priority": 2, "idempotency_key": "first"}]},
        )
    )
    assert again["items"][0]["id"] == new["id"]

    updated = ok(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {"application_id": new["id"], "stage": "applied", "applied_on": "2026-01-05"},
                    {"application_id": started["id"], "stage": "closed"},
                    {"application_id": "missing", "expected_version": 1, "priority": 1},
                ]
            },
        )
    )
    applied, unclosed, unknown = updated["items"]
    assert applied["result"]["stage"] == "applied" and applied["version"]
    assert unclosed["error"]["code"] == "application_outcome" and unknown["error"]["status"] == 404
    replied = ok(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {"application_id": new["id"], "reply": {"kind": "interview", "note": "Monday."}}
                ]
            },
        )
    )["items"][0]["result"]
    assert (replied["stage"], replied["last_reply"]) == ("interview", "interview")
    read = ok(mcp.call("applications_get", {"ids": [new["id"]]}))["items"][0]
    assert read["applied_at"].startswith("2026-01-05") and read["replies"][0]["note"] == "Monday."
    fixed = ok(
        mcp.call(
            "applications_update",
            {
                "items": [
                    {
                        "application_id": new["id"],
                        "reply_fix": {"reply_id": read["replies"][0]["id"], "delete": True},
                    }
                ]
            },
        )
    )
    assert fixed["items"][0]["ok"]
    # Ready is computed: it cannot be set.
    _, error = mcp.call(
        "applications_update", {"items": [{"application_id": new["id"], "ready": True}]}
    )
    assert error["code"] == "validation"


def test_application_fields_change_only_with_the_version_read(app, mcp):
    """Requirements, questions and answers are never overwritten blind."""
    (job,) = jobs(app, 1)
    workspace = app.state.workspace
    application = workspace.create_application({"job_id": job["id"]})
    requirement = {"text": "Synthetic portfolio link.", "blocking": True}
    _, error = mcp.call(
        "applications_update",
        {"items": [{"application_id": application["id"], "requirements": [requirement]}]},
    )
    assert error["code"] == "validation" and "expected_version" in error["details"][0]["message"]
    # The owner resolves something meanwhile: the agent's stale version is refused per item.
    owner = workspace.update_application(
        application["id"], {"expected_version": application["version"], "priority": 1}
    )
    item = {"application_id": application["id"], "requirements": [requirement]}
    stale = ok(mcp.call("applications_update", {"items": [item | {"expected_version": 1}]}))
    assert stale["items"][0]["error"]["code"] == "conflict"
    assert stale["items"][0]["error"]["details"]["current_version"] == owner["version"]
    fresh = ok(
        mcp.call("applications_update", {"items": [item | {"expected_version": owner["version"]}]})
    )
    assert fresh["items"][0]["ok"] and fresh["items"][0]["result"]["missing"][-1].startswith(
        "requirement:"
    )
    # Stage and replies stay version-free.
    moved = ok(
        mcp.call(
            "applications_update",
            {"items": [{"application_id": application["id"], "stage": "applied"}]},
        )
    )
    assert moved["items"][0]["result"]["stage"] == "applied"


def test_career_and_highlights_are_saved_in_batches_with_versions(app, mcp):
    saved = ok(
        mcp.call(
            "career_save",
            {
                "items": [
                    {
                        "kind": "experience",
                        "title": "Engineer",
                        "narrative": "Built APIs.",
                        "idempotency_key": "e1",
                    },
                    {"title": ""},
                ]
            },
        )
    )
    entry, invalid = saved["items"]
    # A failed create has no id; MCP leaves empty fields out.
    assert entry["ok"] and invalid["error"]["code"] == "validation" and "id" not in invalid
    highlights = ok(
        mcp.call(
            "highlights_save",
            {
                "items": [
                    {"career_id": entry["id"], "text": "Reduced latency by 20%.", "approved": True},
                    {"career_id": entry["id"], "text": "Wrote docs.", "always_include": True},
                ]
            },
        )
    )
    first = highlights["items"][0]
    stale = ok(
        mcp.call(
            "highlights_save",
            {"items": [{"highlight_id": first["id"], "expected_version": 9, "approved": False}]},
        )
    )["items"][0]
    assert stale["error"]["details"] == {"current_version": first["version"], "id": first["id"]}
    read = ok(mcp.call("career_get", {"ids": [entry["id"], "missing"]}))
    assert read["missing"] == ["missing"]
    assert [item["text"] for item in read["items"][0]["highlights"]] == [
        "Reduced latency by 20%.",
        "Wrote docs.",
    ]
    updated = ok(
        mcp.call(
            "career_save",
            {
                "items": [
                    {
                        "career_id": entry["id"],
                        "expected_version": entry["version"],
                        "title": "Lead",
                    }
                ]
            },
        )
    )
    assert updated["items"][0]["result"]["title"] == "Lead"
    # An update item without its version fails alone.
    result = ok(mcp.call("career_save", {"items": [{"career_id": entry["id"], "title": "X"}]}))
    assert result["items"][0]["error"]["details"][0]["field"] == ["expected_version"]
    template = ok(
        mcp.call("templates_save", {"name": "CV", "kind": "cv", "tex": "\\documentclass{article}"})
    )
    changed = ok(
        mcp.call(
            "templates_save",
            {
                "template_id": template["id"],
                "expected_version": template["version"],
                "guidance": "Short.",
            },
        )
    )
    assert changed["guidance"] == "Short."
    assert ok(mcp.call("templates_get", {"template_id": template["id"]}))["tex"].startswith("\\doc")


def test_sources_and_collection_through_the_agent_tools(app, mcp):
    saved = ok(
        mcp.call(
            "sources_save",
            {
                "items": [
                    {
                        "name": "Engineer searches",
                        "kind": "jobspy",
                        "config": {"query": "engineer", "providers": ["linkedin"]},
                    },
                    {"source_id": "missing", "expected_version": 1, "enabled": False},
                ]
            },
        )
    )
    source, unknown = saved["items"]
    assert (
        source["ok"] and source["result"]["enabled"] is False and unknown["error"]["status"] == 404
    )
    detail = ok(mcp.call("sources_get", {"source_id": source["id"]}))
    assert detail["config"]["query"] == "engineer"
    _, error = mcp.call("sources_run", {"source_id": source["id"]})
    assert error["code"] == "validation"
    collection = ok(mcp.call("collection_get", {"include": ["kinds", "providers", "fetches"]}))
    assert collection["kinds"]["items"] and collection["providers"]
    changed = ok(
        mcp.call(
            "collection_update",
            {"expected_version": collection["version"], "enabled": False, "cancel": ["missing"]},
        )
    )
    assert changed["enabled"] is False and changed["results"]["items"][0]["error"]["status"] == 404
    _, stale = mcp.call("collection_update", {"expected_version": collection["version"]})
    assert stale["status"] == 409 and stale["details"]["id"] == "collection"


def test_agent_reads_and_writes_say_what_to_do_next(app, mcp, monkeypatch):
    # A URL whose posting cannot be read keeps the job and says the text is needed.
    async def unreadable(body, discovery):
        return body.model_copy(update={"metadata": {"extraction": "needs_text"}})

    monkeypatch.setattr("openings.fetching.complete_input", unreadable)
    bare = ok(mcp.call("jobs_create", {"url": "https://example.test/jobs/1"}))
    assert bare["needs_text"] is True
    full = ok(mcp.call("jobs_create", {"title": "Synthetic role 2", "posting": "Build APIs."}))
    assert full["needs_text"] is False
    # Skills are listed with the description an agent chooses by.
    context = ok(mcp.call("workspace_context"))
    skills = {item["name"]: item["use"] for item in context["skills"]}
    listed = {item["name"]: item for item in app.state.workspace.skills.list()}
    assert skills["triage-jobs"] == listed["triage-jobs"]["description"]
    # A skill's link to another skill's file resolves.
    linked = ok(
        mcp.call(
            "skills_get",
            {"name": "maintain-career", "path": "../prepare-applications/references/writing.md"},
        )
    )
    assert linked["name"] == "prepare-applications"
    _, error = mcp.call("sources_list", {"limit": 0})
    assert error["code"] == "validation"


def test_a_provider_pause_is_lifted_over_rest_and_mcp(app, mcp):
    client = mcp.client
    client.headers.update(mcp.token["headers"])
    discovery = app.state.workspace.discovery
    later = (datetime.now(UTC) + timedelta(hours=2)).isoformat(timespec="microseconds")
    app.state.workspace.db.execute(
        "UPDATE providers SET runtime=? WHERE id IN ('linkedin','indeed')",
        (json.dumps({"cooldown_until": later}),),
    )
    providers = client.get("/api/v1/providers").json()["items"]
    linkedin = next(item for item in providers if item["id"] == "linkedin")
    assert linkedin["runtime"]["cooldown_until"] == later
    lifted = client.patch(
        "/api/v1/providers/linkedin",
        json={"expected_version": linkedin["version"], "clear_cooldown": True},
    ).json()
    assert lifted["runtime"]["cooldown_until"] is None
    change = {
        "provider_id": "indeed",
        "expected_version": discovery.providers.get("indeed")["version"],
        "clear_cooldown": True,
    }
    version = discovery.get_collection()["version"]
    result = ok(mcp.call("collection_update", {"expected_version": version, "providers": [change]}))
    assert result["results"]["items"][0]["ok"]
    assert discovery.providers.get("indeed")["runtime"]["cooldown_until"] is None
