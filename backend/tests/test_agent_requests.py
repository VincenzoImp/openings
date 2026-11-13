"""Requests for the agent: owner instructions an agent takes, completes or declines."""

import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from openings.activity import ActivityService
from openings.actors import OWNER, acting_as, token_actor
from openings.agent_requests import RequestService
from openings.app import create_app
from openings.career import CareerService, KnowledgeCreate
from openings.errors import DomainError
from openings.workspace import Workspace
from schema_fixtures import make_schema_seven, table_names

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
AGENT = token_actor("token-agent", "Synthetic agent", "agent")
OTHER = token_actor("token-other", "Second synthetic agent", "agent")
OWNER_TOKEN = token_actor("token-owner", "Synthetic owner token", "owner")


@pytest.fixture
def services(tmp_path):
    workspace = Workspace(tmp_path / "requests.sqlite")
    return workspace, RequestService(workspace), ActivityService(workspace)


def add_job(workspace, title="Synthetic engineer"):
    return workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})


def refused(call, code, status=409):
    with pytest.raises(DomainError) as error:
        call()
    assert (error.value.status, error.value.code) == (status, code)
    return error.value


def test_request_lifecycle_versions_and_attribution(services):
    workspace, requests, activity = services
    job = add_job(workspace)
    with acting_as(OWNER):
        created = requests.create_request(
            {
                "text": "  Prepare this one too.  ",
                "subject_type": "job",
                "subject_id": job["id"],
                "idempotency_key": "prepare",
            }
        )
        again = requests.create_request(
            {"text": "Prepare this one too.", "idempotency_key": "prepare"}
        )
        general = requests.create_request({"text": "Stop applying to consultancies."})
        refused(
            lambda: requests.create_request({"text": "Another", "idempotency_key": "prepare"}),
            "conflict",
        )
        with pytest.raises(DomainError, match="Job was not found"):
            requests.create_request({"text": "Unknown", "subject_type": "job", "subject_id": "x"})
    assert again["id"] == created["id"]
    assert (created["text"], created["state"], created["version"]) == (
        "Prepare this one too.",
        "open",
        1,
    )
    assert created["created_by"]["kind"] == "owner" and created["result"] == ""
    assert (created["run_id"], created["taken_by"], created["resolved_by"]) == (None, None, None)
    assert created["subject"] == {
        "type": "job",
        "id": job["id"],
        "label": "Synthetic engineer · Example",
        "deleted": False,
        "job_id": job["id"],
    }
    assert general["subject"] is None and requests.count_open() == 2

    with acting_as(AGENT):
        run = activity.start_run({"workflow": "prepare-shortlist"})
        stale = refused(
            lambda: requests.take_request(created["id"], {"expected_version": 5}), "conflict"
        )
        assert stale.details == {"current_version": 1}
        taken = requests.take_request(created["id"], {"expected_version": 1})
    assert (taken["state"], taken["version"], taken["run_id"]) == ("taken", 2, run["id"])
    assert taken["taken_by"]["label"] == "Synthetic agent" and taken["taken_at"]
    assert requests.count_open() == 1
    with acting_as(OTHER):
        twice = refused(
            lambda: requests.take_request(created["id"], {"expected_version": 2}), "request_taken"
        )
        assert twice.details == {"state": "taken", "current_version": 2, "run_id": run["id"]}
    with acting_as(AGENT):
        done = requests.complete_request(
            created["id"], {"expected_version": 2, "result": "Draft prepared and marked ready."}
        )
        late = refused(
            lambda: requests.decline_request(
                created["id"], {"expected_version": 3, "reason": "Too late"}
            ),
            "request_closed",
        )
        assert late.details["state"] == "done"
        # A request can be declined without taking it first; the run is still recorded.
        declined = requests.decline_request(
            general["id"],
            {"expected_version": 1, "reason": "A preference belongs in the Profile policy."},
        )
    assert (done["state"], done["result"], done["version"]) == (
        "done",
        "Draft prepared and marked ready.",
        3,
    )
    assert done["resolved_by"]["token_kind"] == "agent" and done["resolved_at"]
    assert (declined["state"], declined["run_id"], declined["taken_by"]) == (
        "declined",
        run["id"],
        None,
    )
    assert declined["result"] == "A preference belongs in the Profile policy."
    with acting_as(OWNER):
        refused(
            lambda: requests.withdraw_request(created["id"], {"expected_version": 3}),
            "request_closed",
        )

    assert requests.list_requests({"state": "done"})["total"] == 1
    assert requests.list_requests({"subject_type": "job", "subject_id": job["id"]})["total"] == 1
    assert requests.list_requests({"run_id": run["id"]})["total"] == 2
    since = requests.list_requests({"updated_since": done["updated_at"]})
    assert [item["id"] for item in since["items"]] == [created["id"], general["id"]]
    assert [item["id"] for item in requests.list_requests()["items"]] == [
        general["id"],
        created["id"],
    ]
    # The run shows the requests it handled; the job's history shows each step with its actor.
    detail = activity.get_run(run["id"])
    assert detail["requests_count"] == 2
    assert [item["id"] for item in detail["requests"]] == [created["id"], general["id"]]
    history = activity.list_events({"job_id": job["id"], "subject_type": "request"})["items"]
    assert [(item["kind"], item["actor"]["kind"], item["run_id"]) for item in history] == [
        ("request_completed", "token", run["id"]),
        ("request_taken", "token", run["id"]),
        ("request_created", "owner", None),
    ]
    assert history[0]["subject"] == {
        "type": "request",
        "id": created["id"],
        "label": "Prepare this one too.",
    }
    assert all(item["payload"] == {"request_id": created["id"]} for item in history)


def test_only_the_owner_writes_and_withdraws_and_only_tokens_handle(services):
    _, requests, _ = services
    with acting_as(AGENT):
        error = refused(lambda: requests.create_request({"text": "For myself"}), "forbidden", 403)
        assert error.details == {"token_kind": "agent", "required": "owner"}
    # An owner token writes a request and may also handle it from an external session.
    with acting_as(OWNER_TOKEN):
        by_token = requests.create_request({"text": "Refresh the letter for Example."})
    assert by_token["created_by"]["token_kind"] == "owner"
    with acting_as(OWNER):
        for call in (
            lambda: requests.take_request(by_token["id"], {"expected_version": 1}),
            lambda: requests.complete_request(
                by_token["id"], {"expected_version": 1, "result": "Done"}
            ),
            lambda: requests.decline_request(
                by_token["id"], {"expected_version": 1, "reason": "No"}
            ),
        ):
            refused(call, "request_actor", 403)
    with acting_as(AGENT):
        # Without an open run the request is still taken; no run is recorded.
        taken = requests.take_request(by_token["id"], {"expected_version": 1})
        assert (taken["state"], taken["run_id"]) == ("taken", None)
        refused(
            lambda: requests.withdraw_request(by_token["id"], {"expected_version": 2}),
            "forbidden",
            403,
        )
    # The owner can still withdraw a request an agent took and never finished.
    with acting_as(OWNER):
        withdrawn = requests.withdraw_request(by_token["id"], {"expected_version": 2})
    assert (withdrawn["state"], withdrawn["resolved_by"]["kind"]) == ("withdrawn", "owner")
    assert withdrawn["taken_by"]["label"] == "Synthetic agent"
    with acting_as(AGENT):
        refused(
            lambda: requests.complete_request(
                by_token["id"], {"expected_version": 3, "result": "Done"}
            ),
            "request_closed",
        )
    with acting_as(OWNER):
        for invalid in ({"text": "   "}, {"text": "x", "subject_type": "job"}, {"text": ""}):
            with pytest.raises(ValueError):
                requests.create_request(invalid)
    with acting_as(OWNER_TOKEN), pytest.raises(ValueError):
        requests.complete_request(by_token["id"], {"expected_version": 3, "result": ""})
    with pytest.raises(DomainError, match="Request was not found"):
        requests.get_request("missing")


def test_requests_outlive_their_subject_and_follow_a_merge(tmp_path):
    workspace = Workspace(tmp_path / "subjects.sqlite")
    career, requests = CareerService(workspace), RequestService(workspace)
    job, duplicate = add_job(workspace), add_job(workspace, "Synthetic engineer copy")
    application = workspace.create_application({"job_id": job["id"]})
    entry = career.create_knowledge(KnowledgeCreate(title="Synthetic role", organization="Labs"))
    with acting_as(OWNER):
        on_job = requests.create_request(
            {"text": "Job", "subject_type": "job", "subject_id": duplicate["id"]}
        )
        on_application = requests.create_request(
            {"text": "Attempt", "subject_type": "application", "subject_id": application["id"]}
        )
        on_entry = requests.create_request(
            {"text": "Entry", "subject_type": "knowledge", "subject_id": entry["id"]}
        )
    assert on_application["subject"]["job_id"] == job["id"]
    history = ActivityService(workspace).list_events({"application_id": application["id"]})
    assert history["items"][0]["kind"] == "request_created"
    job = workspace.get_job(job["id"])
    workspace.merge_jobs(duplicate["id"], job["id"], duplicate["version"], job["version"])
    merged = requests.get_request(on_job["id"])["subject"]
    assert (merged["id"], merged["label"]) == (job["id"], "Synthetic engineer · Example")
    career.delete_knowledge(entry["id"], entry["version"])
    workspace.forget_job(job["id"], workspace.get_job(job["id"])["version"])
    labels = {
        on_job["id"]: "Synthetic engineer copy · Example",
        on_application["id"]: "Synthetic engineer · Example",
        on_entry["id"]: "Synthetic role · Labs",
    }
    for identifier, label in labels.items():
        request = requests.get_request(identifier)
        assert request["state"] == "open"
        assert (request["subject"]["id"], request["subject"]["deleted"]) == (None, True)
        assert request["subject"]["label"] == label
    assert requests.list_requests({"state": "open"})["total"] == 3
    with acting_as(AGENT):
        declined = requests.decline_request(
            on_job["id"], {"expected_version": 1, "reason": "The job no longer exists."}
        )
    assert declined["state"] == "declined"


def tool(client, token, name, arguments=None):
    response = client.post(
        "/mcp",
        headers={**MCP_HEADERS, "Authorization": "Bearer " + token["token"]},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    result = response.json()["result"]
    if result.get("isError"):
        return None, json.loads(result["content"][0]["text"])["error"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"]), None


def test_a_dashboard_request_reaches_the_agent_and_its_result_comes_back(tmp_path):
    app = create_app(tmp_path / "exchange.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    agent = app.state.auth.create_token("Synthetic agent", "agent")
    owner_token = app.state.auth.create_token("Synthetic owner token", "owner")
    job = add_job(app.state.workspace)
    owner = TestClient(app)
    session = owner.post("/api/v1/auth/login", json={"password": "synthetic-password"})
    owner.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    headers = {"Authorization": "Bearer " + agent["token"]}
    with TestClient(app, base_url="http://localhost:8080") as client:
        written = owner.post(
            "/api/v1/requests",
            json={"text": "Rewrite the letter.", "subject_type": "job", "subject_id": job["id"]},
        )
        assert written.status_code == 201
        request = written.json()
        # Writing and withdrawing are refused for the agent on both interfaces, with one error.
        body = {"text": "For myself"}
        rest_refusal = client.post("/api/v1/requests", json=body, headers=headers)
        _, mcp_refusal = tool(client, agent, "requests_create", {"value": body})
        assert rest_refusal.status_code == 403
        assert rest_refusal.json()["error"]["code"] == mcp_refusal["code"] == "forbidden"
        withdraw = {"expected_version": 1}
        rest_refusal = client.post(
            f"/api/v1/requests/{request['id']}/withdraw", json=withdraw, headers=headers
        )
        _, mcp_refusal = tool(
            client, agent, "requests_withdraw", {"request_id": request["id"], "value": withdraw}
        )
        assert rest_refusal.json()["error"]["code"] == mcp_refusal["code"] == "forbidden"
        assert owner.post(f"/api/v1/requests/{request['id']}/take", json=withdraw).json()["error"][
            "code"
        ] == ("request_actor")

        info, error = tool(client, agent, "workspace_info")
        assert error is None and info["open_requests"] == 1
        assert client.get("/api/v1/workspace", headers=headers).json()["open_requests"] == 1
        run, _ = tool(client, agent, "runs_start", {"value": {"workflow": "prepare-shortlist"}})
        waiting, error = tool(client, agent, "requests_list", {"value": {"state": "open"}})
        assert error is None and [item["id"] for item in waiting["items"]] == [request["id"]]
        assert waiting["items"][0]["text"] == "Rewrite the letter."
        taken, error = tool(
            client, agent, "requests_take", {"request_id": request["id"], "value": withdraw}
        )
        assert error is None and taken["run_id"] == run["id"]
        _, error = tool(
            client, agent, "requests_take", {"request_id": request["id"], "value": withdraw}
        )
        conflict = client.post(
            f"/api/v1/requests/{request['id']}/take", json=withdraw, headers=headers
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == error["code"] == "request_taken"
        assert conflict.json()["error"]["details"] == error["details"]
        done = client.post(
            f"/api/v1/requests/{request['id']}/complete",
            json={"expected_version": taken["version"], "result": "New letter revision approved."},
            headers=headers,
        ).json()
        assert done["state"] == "done"
        # Every read returns the same record over REST, MCP and the owner's session.
        for path, name, arguments in (
            (f"/api/v1/requests/{request['id']}", "requests_get", {"request_id": request["id"]}),
            ("/api/v1/requests", "requests_list", {}),
            ("/api/v1/requests?state=done", "requests_list", {"value": {"state": "done"}}),
            (
                f"/api/v1/requests?subject_type=job&subject_id={job['id']}",
                "requests_list",
                {"value": {"subject_type": "job", "subject_id": job["id"]}},
            ),
            ("/api/v1/requests/missing", "requests_get", {"request_id": "missing"}),
        ):
            over_rest = client.get(path, headers=headers)
            over_mcp, error = tool(client, agent, name, arguments)
            if error:
                assert over_rest.json()["error"]["code"] == error["code"] == "not_found"
            else:
                assert over_rest.json() == over_mcp == owner.get(path).json(), path
        seen = owner.get(f"/api/v1/requests/{request['id']}").json()
        assert (seen["result"], seen["run_id"]) == ("New letter revision approved.", run["id"])
        assert seen["resolved_by"]["label"] == "Synthetic agent"
        detail = owner.get(f"/api/v1/runs/{run['id']}").json()
        assert [item["id"] for item in detail["requests"]] == [request["id"]]
        assert detail["change_counts"] == {"request_completed": 1, "request_taken": 1}
        # An owner token writes and withdraws over MCP.
        second, error = tool(
            client, owner_token, "requests_create", {"value": {"text": "Check the deadlines."}}
        )
        assert error is None and second["created_by"]["token_kind"] == "owner"
        gone, error = tool(
            client,
            owner_token,
            "requests_withdraw",
            {"request_id": second["id"], "value": {"expected_version": 1}},
        )
        assert error is None and gone["state"] == "withdrawn"
        invalid = client.get("/api/v1/requests?state=waiting", headers=headers)
        assert invalid.status_code == 422
        exported = owner.get("/api/v1/export").json()
        assert {item["id"] for item in exported["requests"]} == {request["id"], second["id"]}


def test_requests_exist_after_a_schema_seven_upgrade(tmp_path):
    path = tmp_path / "schema7.sqlite"
    workspace = Workspace(path)
    job = add_job(workspace)
    make_schema_seven(path)
    with closing(sqlite3.connect(path)) as conn:
        assert "requests" not in table_names(conn)
    upgraded = Workspace(path)
    requests = RequestService(upgraded)
    assert requests.list_requests() == {"items": [], "total": 0, "limit": 50, "offset": 0}
    with acting_as(OWNER):
        created = requests.create_request(
            {"text": "Prepare this one.", "subject_type": "job", "subject_id": job["id"]}
        )
    assert created["subject"]["label"] == "Synthetic engineer · Example"
    assert ActivityService(upgraded).list_runs()["total"] == 0
