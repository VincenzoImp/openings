"""Small contract details of REST and MCP: defaults, schema names and the provider budget."""

import asyncio
import json

import pytest

from openings.collectors.jobspy import JobSpyConfig
from openings.discovery import network
from openings.outcomes import today


def schemas(value):
    """Every JSON-schema object inside ``value``."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from schemas(item)
    elif isinstance(value, list):
        for item in value:
            yield from schemas(item)


def test_a_reply_without_a_date_is_recorded_on_today(app, client):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": "Synthetic analyst", "posting": "Model data."})
    application = workspace.create_application({"job_id": job["id"]})
    application = workspace.update_application(
        application["id"], {"expected_version": application["version"], "status": "applied"}
    )
    tools = asyncio.run(app.state.mcp.list_tools())
    tool = next(item for item in tools if item.name == "applications_update")
    value = json.dumps(tool.input_schema)
    assert "today when omitted" in value
    required = [schema.get("required", []) for schema in schemas(tool.input_schema)]
    assert not any("date" in names for names in required)

    recorded = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={
            "expected_version": application["version"],
            "reply": {"kind": "interview", "note": "Call next week."},
        },
    )
    assert recorded.status_code == 200, recorded.text
    body = recorded.json()
    assert body["status"] == "interview" and body["replies"][0]["date"] == today()


def test_tool_schemas_have_no_titles_and_idempotency_keys_have_one_length(app):
    tools = asyncio.run(app.state.mcp.list_tools())
    for tool in tools:
        titles = [s["title"] for s in schemas(tool.input_schema) if isinstance(s.get("title"), str)]
        assert not titles, tool.name
    lengths = set()
    for name, schema in app.openapi()["components"]["schemas"].items():
        key = schema.get("properties", {}).get("idempotency_key")
        if key:
            for option in [key, *key.get("anyOf", [])]:
                if option.get("type") == "string":
                    lengths.add((name, option.get("maxLength")))
    assert lengths and {length for _, length in lengths} == {200}, sorted(lengths)


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
