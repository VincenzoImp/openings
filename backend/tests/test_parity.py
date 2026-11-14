"""One-way parity from the declarations: every API route is one operation or a listed
transport route; every operation is an MCP tool, owner-only, or REST-only naming the MCP
tool that does its work. An agent token is refused on every owner operation, and every
dashboard operation answers a minimal REST call."""

import re

from fastapi.testclient import TestClient

from discovery_fixtures import patch_discovery
from openings.documents import UploadReservation
from openings.interfaces import OPERATIONS, TRANSPORT_ONLY
from openings.interfaces.operation import without_empty


def key(method, path):
    return method.upper(), re.sub(r"\{[^}]+\}", "{}", path.replace(":path", "")).rstrip("/")


async def test_routes_and_tools_follow_the_operations(app):
    served = {key(m, path) for path, methods in app.openapi()["paths"].items() for m in methods}
    operations = [key(method, "/api/v1" + path) for op in OPERATIONS for method, path in op.routes]
    transport = [
        key(method, path if path in ("/health", "/mcp/") else "/api/v1" + path)
        for method, path, _ in TRANSPORT_ONLY
    ]
    api = {route for route in served if route[1].startswith(("/api/v1", "/health"))}
    assert len(operations + transport) == len(set(operations + transport)), "Declared twice"
    assert api == set(operations) | set(transport) - {key("POST", "/mcp/")}
    assert all(reason.strip() and "\n" not in reason for *_, reason in TRANSPORT_ONLY)

    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    assert tools == {op.name for op in OPERATIONS if op.on_mcp}
    for op in OPERATIONS:
        if op.covered_by:
            # A REST-only route's work is an MCP tool's; owner-only work is never one.
            assert op.access != "owner" and set(op.covered_by) <= tools, op.name
    assert len({op.name for op in OPERATIONS}) == len(OPERATIONS)
    assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", op.name) for op in OPERATIONS)


def test_a_read_and_a_write_answer_alike_over_rest_and_mcp(owner_token, mcp):
    """The same services serve both; MCP leaves out empty fields."""
    client = mcp.client
    client.headers.update(owner_token["headers"])
    job = client.post("/api/v1/jobs", json={"title": "Engineer", "posting": "Synthetic."}).json()
    over_mcp, error = mcp.call(
        "notes_create", {"job_id": job["id"], "body": "First.", "pinned": True}
    )
    over_rest = client.post(f"/api/v1/jobs/{job['id']}/notes", json={"body": "Second."}).json()
    assert error is None and set(over_mcp) - {"pinned_at"} == set(without_empty(over_rest))
    read, _ = mcp.call("jobs_get", {"ids": [job["id"]]})
    notes = client.get("/api/v1/jobs/batch", params={"ids": job["id"]}).json()["items"][0]["notes"]
    assert read["items"][0]["notes"] == without_empty(notes)
    listed, _ = mcp.call("jobs_list", {"q": "Engineer", "include_counts": True})
    rest = client.get("/api/v1/jobs?q=Engineer&include_counts=true").json()
    assert listed == without_empty(rest)


# One representative REST request per owner-only operation or transport route. An
# operation declared access=owner without an entry fails the test.
OWNER_ONLY_CALLS = {
    "owner_password_update": {"json": {"password": "another-synthetic-password"}},
    "tokens_list": {},
    "tokens_create": {"json": {"name": "Escalation"}},
    "tokens_revoke": {},
    "backups_list": {},
    "backups_delete": {},
    "workspace_export": {},
    "career_preview_import": {"json": {"text": "Synthetic notes."}},
    "career_import": {"json": {"entries": []}},
    "POST /backup/restore": {"content": b"SQLite format 3\x00"},
    "GET /backups/{name}": {},
    "GET /export": {},
}


def test_owner_only_operations_refuse_an_agent_token(app, agent_token, owner_token):
    owner_ops = {op.name: op for op in OPERATIONS if op.access == "owner"}
    routes = {
        **{name: (op.method, op.path) for name, op in owner_ops.items()},
        **{
            f"{method} {path}": (method, path)
            for method, path, reason in TRANSPORT_ONLY
            if reason.startswith("Owner only")
        },
    }
    assert set(routes) == set(OWNER_ONLY_CALLS)
    with TestClient(app, base_url="http://localhost:8080") as client:
        capabilities = client.get("/api/v1/capabilities", headers=agent_token["headers"]).json()
        assert capabilities["token_kind"] == "agent"
        access = {item["name"]: item["access"] for item in capabilities["operations"]}
        assert {name for name, kind in access.items() if kind == "owner"} == set(owner_ops)
        owner_view = client.get("/api/v1/capabilities", headers=owner_token["headers"])
        assert owner_view.json()["token_kind"] == "owner"
        assert len(owner_view.content) < 12_000
        for name, (method, path) in routes.items():
            response = client.request(
                method,
                "/api/v1" + re.sub(r"\{[^}]+\}", "missing", path),
                headers=agent_token["headers"],
                **OWNER_ONLY_CALLS[name],
            )
            assert response.status_code == 403, (name, response.text)
            assert response.json()["error"]["code"] == "forbidden", name
        # The owner's token is not refused for want of authority.
        for name in ("tokens_list", "backups_list"):
            method, path = routes[name]
            assert client.request(
                method, "/api/v1" + path, headers=owner_token["headers"]
            ).is_success


# Operations the dashboard calls that no other backend test reaches over REST.
WALKED = {
    "stats_get", "timeline_get", "jobs_distinct", "jobs_merge", "notes_delete",
    "templates_list", "templates_create", "templates_update", "templates_delete",
    "career_delete", "highlights_delete", "sources_preview", "sources_update", "sources_bulk",
    "sources_delete", "tasks_retry", "documents_get", "documents_delete", "files_list",
    "files_delete", "preferences_update", "GET /examples", "GET /examples/{name}",
}  # fmt: skip


def test_every_dashboard_operation_answers_one_minimal_call(app, client, monkeypatch):
    """One call each, on the route the operation declares: its binding reaches the service."""
    workspace, documents, discovery = app.state.workspace, app.state.documents, app.state.discovery
    patch_discovery(monkeypatch, "public_url", lambda url: url)
    patch_discovery(monkeypatch, "fetch_postings", lambda source, *args, **kwargs: [])
    routes = {op.name: op.routes for op in OPERATIONS}
    routes |= {f"{method} {path}": [(method, path)] for method, path, _ in TRANSPORT_ONLY}
    called = set()

    def call(name, method, path, **request):
        response = client.request(method, "/api/v1" + path, **request)
        assert response.is_success, (name, response.text)
        declared = [(m, re.sub(r"\{[^}]+\}", "[^/]+", route)) for m, route in routes[name]]
        assert any(m == method and re.fullmatch(route, path) for m, route in declared), name
        called.add(name)
        return response.json() if response.headers["content-type"] == "application/json" else None

    def version(record):
        return {"params": {"expected_version": record["version"]}}

    first, second, third = (
        workspace.ingest_job({"title": f"Synthetic role {n}", "posting": f"Build APIs {n}."})
        for n in range(3)
    )
    call("stats_get", "GET", "/stats", params={"period": "all"})
    call("timeline_get", "GET", f"/jobs/{first['id']}/timeline")
    call("jobs_distinct", "POST", f"/jobs/{first['id']}/distinct", json={"other_id": second["id"]})
    second = workspace.get_job(second["id"])
    merge = {"target_id": third["id"], "expected_version": second["version"], "target_version": 1}
    call("jobs_merge", "POST", f"/jobs/{second['id']}/merge", json=merge)
    note = workspace.add_note(first["id"], {"body": "Synthetic note."})
    call("notes_delete", "DELETE", f"/notes/{note['id']}", **version(note))

    call("templates_list", "GET", "/templates")
    template = call("templates_create", "POST", "/templates", json={"name": "Synthetic CV"})
    patch = {"expected_version": template["version"], "name": "Renamed CV"}
    template = call("templates_update", "PATCH", f"/templates/{template['id']}", json=patch)
    call("templates_delete", "DELETE", f"/templates/{template['id']}", **version(template))
    entry = call("career_create", "POST", "/career/entries", json={"title": "Synthetic entry"})
    highlight = {"career_id": entry["id"], "text": "Built APIs."}
    highlight = call("highlights_create", "POST", "/career/highlights", json=highlight)
    path = f"/career/highlights/{highlight['id']}"
    call("highlights_delete", "DELETE", path, **version(highlight))
    entry = call("career_get", "GET", "/career/batch", params={"ids": entry["id"]})["items"][0]
    call("career_delete", "DELETE", f"/career/entries/{entry['id']}", **version(entry))

    board = {"name": "Synthetic board", "kind": "greenhouse", "config": {"board": "example"}}
    call("sources_preview", "POST", "/sources/preview", json=board)
    source = call("sources_create", "POST", "/sources", json=board)
    patch = {"expected_version": source["version"], "name": "Renamed board"}
    source = call("sources_update", "PATCH", f"/sources/{source['id']}", json=patch)
    task = discovery.queue_collection(source["id"])
    discovery.cancel_task(task["id"])
    call("tasks_retry", "POST", f"/tasks/{task['id']}/retry")
    source = discovery.get_source(source["id"])
    items = [{"id": source["id"], "expected_version": source["version"]}]
    call("sources_bulk", "POST", "/sources/bulk", json={"action": "pause", "items": items})
    source = discovery.get_source(source["id"])
    call("sources_delete", "DELETE", f"/sources/{source['id']}", **version(source))

    application = workspace.create_application({"job_id": first["id"]})
    document = documents.create_document(
        {"application_id": application["id"], "kind": "answers", "content": {"a": 1}}
    )
    call("documents_get", "GET", f"/documents/{document['id']}")
    call("documents_delete", "DELETE", f"/documents/{document['id']}", **version(document))
    grant = documents.reserve_upload(
        UploadReservation(owner_type="job", owner_id=first["id"], name="notes.txt", size=3)
    )
    file = client.put(grant["url"], headers=grant["headers"], content=b"abc").json()
    call("files_list", "GET", "/files", params={"owner_type": "job", "owner_id": first["id"]})
    call("files_delete", "DELETE", f"/files/{file['id']}", **version(file))
    section = {"expected_version": 0, "items": [{"text": "Remote work."}]}
    call("preferences_update", "PUT", "/preferences/looking_for", json=section)
    example = call("GET /examples", "GET", "/examples")["items"][0]
    call("GET /examples/{name}", "GET", "/examples/" + example["name"])
    assert WALKED <= called
