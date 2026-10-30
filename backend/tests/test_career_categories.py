"""Career categories use the same archive and frozen context through REST and MCP."""

import json

from fastapi.testclient import TestClient
import pytest

from openings.app import create_app


@pytest.mark.parametrize("transport", ["rest", "mcp"])
def test_awards_and_publications_survive_import_filtering_and_frozen_context(tmp_path, transport):
    app = create_app(tmp_path / f"categories-{transport}.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic category client")["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:
        def call(tool, method, path, arguments):
            if transport == "rest":
                response = client.request(
                    method,
                    "/api/v1" + path,
                    params=arguments if method == "GET" else None,
                    json=arguments.get("value") if method != "GET" else None,
                )
                response.raise_for_status()
                return response.json()
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            response.raise_for_status()
            result = response.json()["result"]
            assert not result.get("isError"), result
            return result.get("structuredContent") or json.loads(result["content"][0]["text"])

        entries = [
            {
                "kind": kind,
                "title": f"Example {kind}",
                "narrative": f"Synthetic supporting evidence for an example {kind}.",
                "metadata": {"year": 2024, "url": "https://example.org/evidence"},
            }
            for kind in ("award", "publication")
        ]
        created = [
            call("knowledge_create", "POST", "/career/knowledge", {"value": entry})
            for entry in entries
        ]
        preview = call(
            "career_preview_import", "POST", "/career/import/preview",
            {"value": {"text": json.dumps(entries)}},
        )
        assert [row["kind"] for row in preview["knowledge"]] == ["award", "publication"]
        before_import = call("knowledge_list", "GET", "/career/knowledge", {})
        assert before_import["total"] == 2
        imported = call(
            "career_import", "POST", "/career/import", {"value": {"knowledge": preview["knowledge"]}}
        )
        assert imported["total"] == 2
        for entry, record in zip(entries, created):
            listed = call(
                "knowledge_list", "GET", "/career/knowledge",
                {"kind": entry["kind"], "summary": True},
            )
            assert listed["total"] == 2
            assert {row["kind"] for row in listed["items"]} == {entry["kind"]}
            read = call(
                "knowledge_get", "GET", f"/career/knowledge/{record['id']}",
                {"knowledge_id": record["id"]},
            )
            assert all(read[key] == value for key, value in entry.items())

        template = call(
            "templates_create", "POST", "/templates",
            {"value": {"name": "Example CV", "tex": "Synthetic template", "is_default": True}},
        )
        job = call(
            "job_ingest", "POST", "/jobs",
            {"value": {"title": "Engineer", "company": "Example", "posting": "Build APIs."}},
        )
        application = call(
            "application_create", "POST", "/applications", {"value": {"job_id": job["id"]}}
        )
        context = call(
            "application_prepare_context", "POST", "/contexts",
            {"value": {"application_id": application["id"], "template_id": template["id"]}},
        )
        frozen = {row["id"]: row for row in context["payload"]["knowledge"]}
        assert len(frozen) == 4
        assert {row["kind"] for row in frozen.values()} == {"award", "publication"}
        for record in created + imported["items"]:
            assert frozen[record["id"]]["narrative"] == record["narrative"]
            assert frozen[record["id"]]["metadata"] == record["metadata"]

        award = created[0]
        changed = call(
            "knowledge_update", "PATCH", f"/career/knowledge/{award['id']}",
            {"knowledge_id": award["id"], "value": {
                "expected_version": award["version"], "kind": "publication",
                "narrative": "Revised live evidence.",
            }},
        )
        assert changed["kind"] == "publication"
        saved = call(
            "contexts_get", "GET", f"/contexts/{context['id']}",
            {"context_id": context["id"]},
        )
        retained = next(row for row in saved["payload"]["knowledge"] if row["id"] == award["id"])
        assert retained["kind"] == "award" and retained["narrative"] == award["narrative"]

        invalid = {"kind": "unsupported", "title": "Invalid category"}
        if transport == "rest":
            assert client.post("/api/v1/career/knowledge", json=invalid).status_code == 422
        else:
            response = client.post("/mcp", json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "knowledge_create", "arguments": {"value": invalid}},
            })
            assert response.json()["result"]["isError"]
