"""Small contract details of REST and MCP: defaults, prompt arguments, schema names, wording."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.collectors.jobspy import JobSpyConfig
from openings.discovery import network
from openings.outcomes import today

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "details.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    return app


def schemas(value):
    """Every JSON-schema object inside ``value``."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from schemas(item)
    elif isinstance(value, list):
        for item in value:
            yield from schemas(item)


def test_a_reply_without_a_date_is_recorded_on_today(app):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": "Synthetic analyst", "posting": "Model data."})
    application = workspace.create_application({"job_id": job["id"]})
    application = workspace.update_application(
        application["id"], {"expected_version": application["version"], "status": "applied"}
    )
    tools = asyncio.run(app.state.mcp.list_tools())
    assert not any(item.name.startswith("responses_") for item in tools)
    tool = next(item for item in tools if item.name == "applications_update")
    value = json.dumps(tool.input_schema)
    assert "today (UTC) for a new reply when omitted" in value
    required = [schema.get("required", []) for schema in schemas(tool.input_schema)]
    assert not any("date" in names for names in required)

    token = app.state.auth.create_token("Synthetic agent")["token"]
    with TestClient(app, base_url="http://localhost:8080") as client:
        headers = {"Authorization": "Bearer " + token}
        gone = client.post(
            f"/api/v1/applications/{application['id']}/responses",
            json={"kind": "other"},
            headers=headers,
        )
        assert gone.status_code == 410
        recorded = client.patch(
            f"/api/v1/applications/{application['id']}",
            json={
                "expected_version": application["version"],
                "reply": {"kind": "interview", "note": "Call next week."},
            },
            headers=headers,
        )
        assert recorded.status_code == 200, recorded.text
        body = recorded.json()
        assert body["status"] == "interview" and body["replies"][0]["date"] == today()


def test_skill_prompts_declare_no_arguments_and_return_their_own_skill(app):
    async def read():
        prompts = await app.state.mcp.list_prompts()
        texts = {}
        for prompt in prompts:
            result = await app.state.mcp.get_prompt(prompt.name, {})
            texts[prompt.name] = result.messages[0].content.text
        return prompts, texts

    prompts, texts = asyncio.run(read())
    assert prompts
    for prompt in prompts:
        assert not prompt.arguments, prompt.name
        assert texts[prompt.name].startswith(f"Follow the Openings `{prompt.name}` skill")


def test_tool_schemas_are_named_after_their_tools_and_keys_have_one_length(app):
    tools = asyncio.run(app.state.mcp.list_tools())
    lengths = set()
    for tool in tools:
        assert tool.input_schema.get("title") in (None, f"{tool.name}Arguments"), tool.name
        for schema in schemas(tool.input_schema):
            key = schema.get("properties", {}).get("idempotency_key")
            if key:
                for option in [key, *key.get("anyOf", [])]:
                    if option.get("type") == "string":
                        lengths.add((tool.name, option.get("maxLength")))
    assert lengths and {length for _, length in lengths} == {200}, sorted(lengths)


def test_tokens_default_to_the_scoped_agent_kind(app):
    assert app.state.auth.create_token("Synthetic default")["kind"] == "agent"
    owner = app.state.auth.create_token("Synthetic owner", "owner")["token"]
    with TestClient(app, base_url="http://localhost:8080") as client:
        created = client.post(
            "/api/v1/tokens",
            json={"name": "Synthetic REST default"},
            headers={"Authorization": "Bearer " + owner},
        )
        assert created.status_code == 200, created.text
        assert created.json()["kind"] == "agent"


def test_workspace_info_says_document_revisions_are_saved_never_submitted(app):
    token = app.state.auth.create_token("Synthetic agent")["token"]
    with TestClient(app, base_url="http://localhost:8080") as client:
        response = client.post(
            "/mcp",
            headers={**MCP_HEADERS, "Authorization": "Bearer " + token},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "workspace_info", "arguments": {}},
            },
        )
    info = json.loads(response.json()["result"]["content"][0]["text"])
    assert "save CV and letter revisions" in info["workflow"]
    assert "submit" not in info["workflow"].lower()


def test_a_public_fetch_without_a_provider_budget_fails_closed(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("No connection may be attempted without a budget.")

    monkeypatch.setattr(network.httpx, "Client", unexpected)
    assert network.HTTP_BUDGET.get() is None
    with pytest.raises(RuntimeError, match="no provider budget"):
        network.fetch_bytes("https://example.org/jobs")


def test_a_search_has_no_country_unless_one_is_chosen():
    linkedin = JobSpyConfig.model_validate({"query": "engineer", "providers": ["linkedin"]})
    assert linkedin.country == ""
    chosen = JobSpyConfig.model_validate(
        {"query": "engineer", "country": "switzerland", "providers": ["indeed"]}
    )
    assert chosen.country == "switzerland"
    for providers in (["indeed"], ["linkedin", "glassdoor"]):
        with pytest.raises(ValueError, match="search one country's site"):
            JobSpyConfig.model_validate({"query": "engineer", "providers": providers})
