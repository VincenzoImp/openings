"""The agent's tools: batch reads and writes, per-item results, versions and the 0.23 names."""

from openings.interfaces import OPERATIONS
from openings.removed import TOOLS

# The MCP tools of 0.23.0, frozen: each is a tool of 0.24 or answers with its replacement.
TOOLS_0_23 = [
    "applications_bulk",
    "applications_create",
    "applications_delete",
    "applications_get",
    "applications_history",
    "applications_list",
    "applications_ready",
    "applications_update",
    "capabilities_get",
    "career_import",
    "career_preview_import",
    "claims_create",
    "claims_delete",
    "claims_get",
    "claims_list",
    "claims_update",
    "collection_get",
    "collection_runs_cancel",
    "collection_runs_get",
    "collection_runs_list",
    "collection_update",
    "contexts_create",
    "contexts_get",
    "contexts_list",
    "documents_compare",
    "documents_create",
    "documents_delete",
    "documents_get",
    "documents_list",
    "documents_review",
    "events_list",
    "files_delete",
    "files_get",
    "files_list",
    "files_reserve_download",
    "files_reserve_upload",
    "insights_get",
    "instructions_get",
    "instructions_update",
    "jobs_bulk",
    "jobs_create",
    "jobs_delete",
    "jobs_distinct",
    "jobs_duplicates",
    "jobs_get",
    "jobs_list",
    "jobs_merge",
    "jobs_resolve",
    "jobs_triage",
    "jobs_update",
    "knowledge_create",
    "knowledge_delete",
    "knowledge_get",
    "knowledge_list",
    "knowledge_update",
    "notes_create",
    "notes_delete",
    "notes_get",
    "notes_list",
    "notes_pin",
    "notes_update",
    "overview_get",
    "owner_password_update",
    "policy_add",
    "policy_confirm",
    "policy_get",
    "policy_move",
    "policy_remove",
    "policy_reorder",
    "policy_rule_preview",
    "policy_update",
    "profile_get",
    "profile_update",
    "providers_list",
    "providers_update",
    "questions_answer",
    "questions_ask",
    "questions_get",
    "questions_list",
    "questions_withdraw",
    "requests_complete",
    "requests_create",
    "requests_decline",
    "requests_get",
    "requests_list",
    "requests_take",
    "requests_withdraw",
    "responses_create",
    "responses_delete",
    "responses_list",
    "responses_update",
    "runs_finish",
    "runs_get",
    "runs_list",
    "runs_start",
    "runs_update",
    "skill_notes_get",
    "skill_notes_update",
    "skills_get",
    "skills_list",
    "sources_bulk",
    "sources_create",
    "sources_delete",
    "sources_get",
    "sources_list",
    "sources_preview",
    "sources_run",
    "sources_schemas",
    "sources_update",
    "sources_yield",
    "staleness_get",
    "staleness_list",
    "tasks_cancel",
    "tasks_get",
    "tasks_list",
    "tasks_retry",
    "templates_create",
    "templates_delete",
    "templates_get",
    "templates_list",
    "templates_update",
    "timeline_get",
    "tokens_create",
    "tokens_list",
    "tokens_revoke",
    "workspace_backup",
    "workspace_export",
    "workspace_info",
    "workspace_restore",
]


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


async def test_every_0_23_tool_is_a_tool_or_names_its_replacement(app, mcp):
    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    assert len(TOOLS_0_23) == 129
    assert set(TOOLS_0_23) <= tools | set(TOOLS)
    assert not tools & set(TOOLS)
    owner = {op.name for op in OPERATIONS if op.access == "owner"}
    for name, gone in TOOLS.items():
        assert gone.code in ("renamed", "removed", "owner_only"), name
        assert not gone.use or gone.use in tools, name
        _, error = mcp.call(name, {})
        assert error["details"] == {"tool": name, "use": gone.use or None}, name
        assert error["code"] == ("owner_only" if name in owner else gone.code), name
        if name in owner:
            # An owner operation names its REST route instead of being a tool.
            assert "/api/v1/" in error["message"], name
    # A REST-only operation answers with the tool that does its work.
    _, error = mcp.call("jobs_read", {"job_id": "x"})
    assert (error["code"], error["details"]["use"]) == ("renamed", "jobs_get")


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
    assert new["result"]["created"] is True and new["result"]["status"] == "shortlisted"
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
                    {"application_id": "missing", "priority": 1},
                ]
            },
        )
    )
    applied, unclosed, unknown = updated["items"]
    assert applied["result"]["status"] == "applied" and applied["version"]
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
    assert (replied["status"], replied["last_reply"]) == ("interview", "interview")
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
