"""REST and MCP are two doors to one service: the same command leaves the same state."""

import base64
import json

from openings.web import mcp


def test_add_status_note_attachment_through_both_surfaces(client, runtime):
    rest = client.post(
        "/api/jobs",
        json={
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "labels": ["rest"],
        },
    ).json()
    via_mcp = json.loads(mcp.add_job("Backend Engineer", "Acme", "Remote", labels=["mcp"]))
    assert via_mcp["message"] == "updated" and via_mcp["job_ids"] == rest["job_ids"]
    job_id = rest["job_ids"][0]

    client.post("/api/jobs/status", json={"job_ids": [job_id], "status": "applied", "note": "rest"})
    assert json.loads(mcp.get_job(job_id))["status"] == "applied"
    json.loads(mcp.set_status([job_id], "interviewing", note="mcp"))
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "interviewing"

    mcp.add_note(job_id, "Because.", kind="qa", title="Why?")
    client.post(f"/api/jobs/{job_id}/notes", json={"kind": "note", "body": "Remember."})
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert sorted(note["kind"] for note in detail["notes"]) == ["note", "qa"]
    assert sorted(detail["labels"]) == ["mcp", "rest"]

    mcp.add_attachment(job_id, "cv.pdf", base64.b64encode(b"%PDF").decode(), kind="cv")
    client.post(
        f"/api/jobs/{job_id}/attachments",
        files={"file": ("letter.md", b"# Hi", "text/markdown")},
        data={"kind": "cover_letter"},
    )
    listed = json.loads(mcp.list_attachments())
    assert listed["total"] == 2
    rest_listed = client.get("/api/attachments").json()
    assert {item["filename"] for item in rest_listed["items"]} == {"cv.pdf", "letter.md"}

    events = [event["kind"] for event in json.loads(mcp.get_job(job_id))["events"]]
    assert events.count("status") == 3 and events.count("attachment") == 2


def test_blacklist_restore_and_lists_agree(client, runtime):
    job_id = client.post(
        "/api/jobs", json={"title": "T", "company": "C", "location": "L", "status": "new"}
    ).json()["job_ids"][0]
    json.loads(mcp.blacklist_jobs([job_id], note="closed"))
    assert client.get("/api/jobs").json()["total"] == 0
    assert json.loads(mcp.list_jobs())["total"] == 0
    assert client.get("/api/blacklist").json()["total"] == 1
    assert json.loads(mcp.list_blacklist())["total"] == 1
    client.post("/api/blacklist/remove", json={"job_ids": [job_id]})
    assert json.loads(mcp.get_job(job_id))["status"] == "new"
    assert json.loads(mcp.get_statistics()) == client.get("/api/stats").json()


def test_export_and_facets_agree(client, runtime):
    for index in range(3):
        mcp.add_job(
            f"Job {index}", "Acme", "Remote", job_url=f"https://linkedin.com/jobs/view/{index}"
        )
    rest_rows = client.get("/api/export/jobs", params={"format": "json", "limit": 0}).json()
    mcp_rows = json.loads(mcp.export_jobs(format="json", limit=0))["content"]
    assert [row["job_id"] for row in rest_rows] == [row["job_id"] for row in mcp_rows]
    assert client.get("/api/jobs/facets").json() == json.loads(mcp.get_facets())
    assert client.get("/api/settings").json() == json.loads(mcp.get_settings())
