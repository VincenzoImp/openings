import base64
import json

import pytest

from openings.web import mcp


@pytest.fixture
def tools(runtime):
    return mcp


def test_every_tool_is_registered():
    server = mcp.create_mcp_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {tool.__name__ for tool in mcp.TOOLS}
    for gone in ("set_bookmarked", "set_applied", "purge_blacklist"):
        assert gone not in names
    for present in ("update_job", "merge_jobs", "run_now", "get_attachment", "list_attachments"):
        assert present in names


def test_add_job_and_get_job(tools):
    created = json.loads(
        tools.add_job("Backend Engineer", "Acme", "Remote", description="Python", labels=["x"])
    )
    assert created["success"] and created["message"] == "created"
    job_id = created["job_ids"][0]
    detail = json.loads(tools.get_job(job_id))
    assert detail["status"] == "shortlisted"
    assert detail["labels"] == ["x"]
    assert "raw_json" not in detail
    assert detail["explain"]["matched"][0]["category"] == "role"
    assert "raw_json" in json.loads(tools.get_job(job_id, include_raw=True))
    short = json.loads(tools.get_job(job_id, max_description_chars=3))
    assert short["description"] == "Pyt…" and short["description_truncated"] is True
    assert json.loads(tools.get_job("0" * 64))["success"] is False


def test_update_job_and_set_status_validate(tools):
    job_id = json.loads(tools.add_job("T", "C", "L"))["job_ids"][0]
    updated = json.loads(tools.update_job(job_id, job_level="senior", bogus=1))
    assert updated["success"] and updated["job"]["job_level"] == "senior"
    assert json.loads(tools.update_job(job_id))["success"] is False
    assert json.loads(tools.set_status([job_id], "APPLIED"))["affected_count"] == 1
    assert json.loads(tools.set_status([job_id], "bookmarked"))["success"] is False
    assert json.loads(tools.list_jobs(statuses=["bookmarked"]))["success"] is False


def test_notes_attachments_and_labels(tools):
    job_id = json.loads(tools.add_job("T", "C", "L"))["job_ids"][0]
    note = json.loads(tools.add_note(job_id, "Because.", kind="qa", title="Why?"))
    assert note["success"] and note["note"]["kind"] == "qa"
    edited = json.loads(tools.update_note(job_id, note["note"]["id"], body="Better."))
    assert edited["note"]["body"] == "Better."
    attachment = json.loads(
        tools.add_attachment(job_id, "cv.pdf", base64.b64encode(b"%PDF").decode(), kind="cv")
    )
    assert attachment["success"] and attachment["attachment"]["size_bytes"] == 4
    attachment_id = attachment["attachment"]["id"]
    fetched = json.loads(tools.get_attachment(job_id, attachment_id))
    assert base64.b64decode(fetched["attachment"]["content_base64"]) == b"%PDF"
    listed = json.loads(tools.list_attachments(kind="cv"))
    assert listed["total"] == 1 and listed["items"][0]["job_title"] == "T"
    changed = json.loads(tools.update_attachment(job_id, attachment_id, kind="other"))
    assert changed["attachment"]["kind"] == "other"
    assert (
        json.loads(tools.add_attachment(job_id, "x", "not-base64!", kind="cv"))["success"] is False
    )
    assert json.loads(tools.delete_attachment(job_id, attachment_id))["success"]
    assert json.loads(tools.add_labels([job_id], ["a"]))["affected_count"] == 1
    assert json.loads(tools.list_labels()) == [{"value": "a", "count": 1}]
    assert json.loads(tools.rename_label("a", "b"))["affected_count"] == 1
    assert json.loads(tools.remove_labels([job_id], ["b"]))["affected_count"] == 1
    assert json.loads(tools.delete_note(job_id, note["note"]["id"]))["success"]


def test_list_filters_and_export(tools):
    tools.add_job("Backend Engineer", "Acme", "Remote")
    tools.add_job("Sales", "Beta", "Berlin", status="new")
    listed = json.loads(tools.list_jobs(statuses=["shortlisted"]))
    assert listed["total"] == 1
    ascending = json.loads(tools.list_jobs(sort="score", direction="asc"))
    assert [item["title"] for item in ascending["items"]] == ["Sales", "Backend Engineer"]
    exported = json.loads(tools.export_jobs(statuses=["new"]))
    assert exported["row_count"] == 1 and exported["format"] == "csv"
    assert exported["content"].startswith("job_id,title")
    as_json = json.loads(tools.export_jobs(format="json", limit=0))
    assert as_json["content"][0]["title"] and as_json["total"] == 2


def test_read_tools(tools):
    tools.add_job("T", "C", "L")
    assert json.loads(tools.get_statistics())["by_status"]["shortlisted"] == 1
    assert json.loads(tools.get_facets())["sources"][0]["value"] == "manual"
    assert json.loads(tools.list_sources())[-1]["name"] == "manual"
    runs = json.loads(tools.list_runs())
    assert runs["runs"] == [] and runs["status"]["running"] is False
    assert json.loads(tools.get_score_distribution(10))
    assert json.loads(tools.list_blacklist())["total"] == 0
    assert "settings.yaml" in tools.get_settings_reference()
    assert json.loads(tools.get_settings())["scoring"]["notify_threshold"] == 20
    assert json.loads(tools.preview_cleanup())["protected"] == 1
    assert json.loads(tools.run_cleanup())["total_deleted"] == 0
    assert json.loads(tools.run_now())["requested"] is True
    assert json.loads(tools.search_similar("x"))["success"] is False


def test_blacklist_merge_and_delete(tools):
    job_id = json.loads(tools.add_job("T", "C", "L", job_url="https://linkedin.com/jobs/view/1"))[
        "job_ids"
    ][0]
    assert json.loads(tools.blacklist_jobs([job_id], note="closed"))["affected_count"] == 1
    assert json.loads(tools.list_blacklist())["total"] == 1
    assert json.loads(tools.unblacklist_jobs([job_id]))["affected_count"] == 1
    other = json.loads(
        tools.add_job("T (mirror)", "C", "L", job_url="https://ch.indeed.com/viewjob?jk=1")
    )["job_ids"][0]
    assert json.loads(tools.merge_jobs(job_id, [other]))["affected_count"] == 1
    assert json.loads(tools.delete_jobs([job_id]))["affected_count"] == 1


def test_mcp_over_http(client):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    init = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"},
            },
        },
        headers=headers,
    )
    assert init.status_code == 200
    headers["Mcp-Session-Id"] = init.headers["mcp-session-id"]
    client.post(
        "/mcp/", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers
    )
    tools_list = client.post(
        "/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers
    )
    assert "add_job" in tools_list.text and "merge_jobs" in tools_list.text
