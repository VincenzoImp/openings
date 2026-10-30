"""Applicable adapter options and honest public-board failures across interfaces."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from openings import discovery as module
from openings.app import create_app
from openings.discovery import DiscoveryService, SourceCreate
from openings.errors import DomainError
from openings.workspace import Workspace


@pytest.fixture
def service(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "adapters.sqlite")
    discovery = DiscoveryService(workspace)
    workspace.discovery = discovery
    monkeypatch.setattr(module, "public_url", lambda url: url)
    return discovery


def transport(monkeypatch, send):
    original = httpx.Client
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(send), **kwargs),
    )


def run(service, source):
    service.queue_collection(source["id"])
    task = service.claim_task("test", kind="collect")
    service.run_task(task, "test")
    return service.get_task(task["id"])


def test_source_options_follow_actual_adapter_workflow(service):
    schemas = {row["kind"]: row for row in service.source_schemas()["items"]}
    for kind in ["lever", "ashby", "recruitee", "personio", "workable", "breezy"]:
        assert "max_details" not in schemas[kind]["config_schema"]["properties"]
        assert not schemas[kind]["capabilities"]["details"]
    assert schemas["greenhouse"]["capabilities"]["description_mode"] == "separate"
    assert schemas["breezy"]["capabilities"]["description_mode"] == "metadata"
    assert "max_details" in schemas["greenhouse"]["config_schema"]["properties"]
    assert "region" in schemas["lever"]["config_schema"]["properties"]
    assert "region" not in schemas["greenhouse"]["config_schema"]["properties"]
    with pytest.raises(DomainError) as invalid:
        service.create_source(
            SourceCreate(
                name="Example", kind="lever", config={"board": "example", "max_details": 3}
            )
        )
    assert invalid.value.code == "source_config"
    inline = service.create_source(
        SourceCreate(name="Example", kind="lever", config={"board": "example"})
    )
    with pytest.raises(DomainError) as invalid_run:
        service.queue_collection(inline["id"], overrides={"max_details": 1})
    assert invalid_run.value.code == "run_options"
    assert not service.list_tasks()["items"]


def test_metadata_only_source_finishes_partial_without_retrying_missing_bodies(
    service, monkeypatch
):
    transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, json=[{"id": "1", "name": "Engineer", "url": "https://example.com/1"}]
        ),
    )
    source = service.create_source(
        SourceCreate(name="Example", kind="breezy", config={"board": "example"})
    )
    task = run(service, source)
    assert task["state"] == "succeeded" and task["result"]["created"] == 1
    assert task["result"]["pending_descriptions"] == 0
    assert task["result"]["unavailable_descriptions"] == 1
    assert task["result"]["http_requests"] == 1
    assert service.get_run(task["run_id"])["partial"]
    job = service.workspace.list_jobs()["items"][0]
    assert not job["complete"] and job["metadata"]["description_status"] == "unavailable"


@pytest.mark.parametrize(
    "status,body,state,code",
    [
        (404, None, "failed", "ashby_board_unavailable"),
        (200, {"jobs": []}, "succeeded", None),
        (503, None, "queued", "source_http"),
        (429, None, "queued", "provider_cooldown"),
    ],
)
def test_ashby_unavailable_board_empty_board_and_transient_failure_are_distinct(
    service, monkeypatch, status, body, state, code
):
    calls = []

    def send(request):
        calls.append(str(request.url))
        return httpx.Response(
            status, json=body, headers={"Retry-After": "60"} if status == 429 else {}
        )

    transport(monkeypatch, send)
    source = service.create_source(
        SourceCreate(name="Example", kind="ashby", config={"board": "example"})
    )
    task = run(service, source)
    assert task["state"] == state
    assert len(calls) == 1 and task["result"]["http_requests"] == 1
    assert service.workspace.list_jobs()["total"] == 0
    if code:
        assert task["result"]["attempt_history"][-1]["reason"] == code
    if status == 404:
        assert "Check the exact board URL" in task["error"]
        assert task["attempts"] == 1
    if status == 200:
        assert task["error"] is None


def test_discovered_adapter_options_match_rest_and_mcp_validation(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic check")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://localhost:8080") as client:
        schemas = client.get("/api/v1/sources/schemas", headers=headers).json()
        response = client.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "sources_schemas", "arguments": {}},
            },
        )
        result = response.json()["result"]
        assert not result.get("isError")
        assert (
            result.get("structuredContent") or json.loads(result["content"][0]["text"])
        ) == schemas
        bad = {"name": "Example", "kind": "lever", "config": {"board": "example", "max_details": 1}}
        assert client.post("/api/v1/sources", headers=headers, json=bad).status_code == 422
        response = client.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "sources_create", "arguments": {"value": bad}},
            },
        )
        assert response.json()["result"]["isError"]
