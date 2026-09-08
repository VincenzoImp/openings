import base64
import json

import pytest

from openings.web import mcp


@pytest.fixture
def tools(env):
    return mcp


def test_every_tool_is_registered():
    server = mcp.create_mcp_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {tool.__name__ for tool in mcp.TOOLS}
    assert "set_bookmarked" not in names and "set_applied" not in names


def test_add_job_and_get_job(tools):
    created = json.loads(
        tools.add_job("Backend Engineer", "Acme", "Remote", description="Python", labels=["x"])
    )
    assert created["success"] and created["message"] == "created"
    job_id = created["job_ids"][0]
    detail = json.loads(tools.get_job(job_id))
    assert detail["status"] == "shortlisted"
    assert detail["labels"] == ["x"]
    assert detail["explain"]["matched"][0]["category"] == "role"
    assert "error" in json.loads(tools.get_job("0" * 64))


def test_set_status_validates_values(tools):
    job_id = json.loads(tools.add_job("T", "C", "L"))["job_ids"][0]
    assert json.loads(tools.set_status([job_id], "APPLIED"))["affected_count"] == 1
    assert json.loads(tools.set_status([job_id], "bookmarked"))["success"] is False


def test_notes_attachments_and_labels(tools):
    job_id = json.loads(tools.add_job("T", "C", "L"))["job_ids"][0]
    note = json.loads(tools.add_note(job_id, "Because.", kind="qa", title="Why?"))
    assert note["success"] and note["note"]["kind"] == "qa"
    attachment = json.loads(
        tools.add_attachment(job_id, "cv.pdf", base64.b64encode(b"%PDF").decode(), kind="cv")
    )
    assert attachment["success"] and attachment["attachment"]["size_bytes"] == 4
    assert (
        json.loads(tools.add_attachment(job_id, "x", "not-base64!", kind="cv"))["success"] is False
    )
    assert json.loads(tools.delete_attachment(job_id, attachment["attachment"]["id"]))["success"]
    assert json.loads(tools.add_labels([job_id], ["a"]))["affected_count"] == 1
    assert json.loads(tools.remove_labels([job_id], ["a"]))["affected_count"] == 1


def test_list_filters_and_export(tools):
    tools.add_job("Backend Engineer", "Acme", "Remote")
    tools.add_job("Sales", "Beta", "Berlin", status="new")
    listed = json.loads(tools.list_jobs(statuses=["shortlisted"]))
    assert listed["total"] == 1
    exported = json.loads(tools.export_jobs(statuses=["new"]))
    assert exported["row_count"] == 1
    assert exported["content"].startswith("job_id,title")
    assert json.loads(tools.export_jobs(format="json", limit=0))[0]["title"]


def test_read_tools(tools):
    tools.add_job("T", "C", "L")
    assert json.loads(tools.get_statistics())["by_status"]["shortlisted"] == 1
    assert json.loads(tools.get_facets())["sources"][0]["value"] == "manual"
    assert json.loads(tools.list_sources())[-1]["name"] == "manual"
    assert json.loads(tools.list_runs()) == []
    assert json.loads(tools.get_score_distribution(10))
    assert json.loads(tools.list_blacklist())["total"] == 0
    assert "settings.yaml" in tools.get_settings_reference()
    assert json.loads(tools.preview_cleanup())["protected"] == 1
    assert json.loads(tools.run_cleanup())["total_deleted"] == 0


def test_blacklist_and_delete(tools):
    job_id = json.loads(tools.add_job("T", "C", "L"))["job_ids"][0]
    assert json.loads(tools.blacklist_jobs([job_id]))["affected_count"] == 1
    assert json.loads(tools.list_blacklist())["total"] == 1
    assert json.loads(tools.unblacklist_jobs([job_id]))["affected_count"] == 1
    other = json.loads(tools.add_job("T2", "C", "L"))["job_ids"][0]
    assert json.loads(tools.delete_jobs([other]))["affected_count"] == 1


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
    assert "add_job" in tools_list.text and "set_status" in tools_list.text
