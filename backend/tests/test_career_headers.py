"""Typed career headers preserve precision and optional content."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from openings.app import create_app
from openings.career import (
    CareerDates,
    CareerService,
    ClaimCreate,
    ClaimUpdate,
    KnowledgeCreate,
)


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "single", "start": "2025"},
        {"kind": "single", "start": "2025-08"},
        {"kind": "period", "start": "2025-08", "current": True},
        {"kind": "period", "start": "2023", "end": "2025-08"},
        {"kind": "period", "start": "2025-08", "end": "2025"},
        {"kind": "period", "start": "2025", "end": "2025-02"},
    ],
)
def test_dates_preserve_only_supplied_precision(value):
    result = CareerDates.model_validate(value).model_dump()
    assert all(result[key] == item for key, item in value.items())


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "single", "start": "0000"},
        {"kind": "single", "start": "2025-13"},
        {"kind": "single", "start": "2025-00"},
        {"kind": "single", "start": "2025-01-01"},
        {"kind": "single", "start": "2025", "end": "2026"},
        {"kind": "single", "start": "2025", "current": True},
        {"kind": "period", "start": "2025"},
        {"kind": "period", "start": "2025", "end": "2026", "current": True},
        {"kind": "period", "start": "2025", "end": "2024"},
        {"kind": "period", "start": "2025-08", "end": "2025-07"},
    ],
)
def test_invalid_or_contradictory_dates_are_rejected(value):
    with pytest.raises(ValidationError):
        CareerDates.model_validate(value)


def test_skills_and_headers_normalize_without_alias_guessing():
    value = KnowledgeCreate(
        title="  Languages  ", skills=[" Python ", "python", "JS", "JavaScript"]
    )
    assert value.title == "Languages"
    assert value.skills == ["Python", "JS", "JavaScript"]
    for fields in [
        {"skills": [" "]},
        {"skills": [123]},
        {"title": " "},
        {"metadata": {"organization": "Duplicate"}},
    ]:
        with pytest.raises(ValidationError):
            KnowledgeCreate.model_validate({"title": "Entry", **fields})


def test_summary_claim_preview_is_ordered_bounded_and_independent_of_description(tmp_path):
    app = create_app(tmp_path / "preview.sqlite", start_worker=False)
    career = app.state.career
    owner = career.create_knowledge(KnowledgeCreate(title="Languages", narrative="User context."))
    assert career.list_knowledge(summary=True)["items"][0]["claim_preview"] is None
    first = career.create_claim(ClaimCreate(knowledge_id=owner["id"], text="Python, SQL."))
    later = career.create_claim(ClaimCreate(knowledge_id=owner["id"], text="Long wording " * 100))
    assert career.list_knowledge(summary=True)["items"][0]["claim_preview"] == first["text"]
    career.update_claim(first["id"], ClaimUpdate(expected_version=first["version"], position=2))
    row = career.list_knowledge(summary=True)["items"][0]
    assert row["claim_preview"] == later["text"][:240]
    assert row["narrative_preview"] == "User context."
    assert career.get_knowledge(owner["id"])["narrative"] == "User context."


def test_a_claim_is_always_included_or_not_and_keeps_other_hints_in_metadata(workspace):
    career = CareerService(workspace)
    entry = career.create_knowledge(KnowledgeCreate(title="Synthetic entry", narrative="Built."))
    claim = career.create_claim(
        ClaimCreate(knowledge_id=entry["id"], text="Built APIs.", metadata={"role": "core"})
    )
    assert claim["always_include"] is False and claim["metadata"] == {"role": "core"}
    claim = career.update_claim(
        claim["id"], ClaimUpdate(expected_version=claim["version"], always_include=True)
    )
    assert claim["always_include"] is True and claim["metadata"] == {"role": "core"}
    listed = career.list_claims()["items"][0]
    assert listed["always_include"] is True
    assert not {"role", "group", "default_in_cv"} & set(listed) & set(claim)
    for removed in ({"role": "core"}, {"group": "Scale"}, {"default_in_cv": True}):
        with pytest.raises(ValidationError):
            ClaimCreate.model_validate({"knowledge_id": entry["id"], "text": "X.", **removed})


@pytest.mark.parametrize("transport", ["rest", "mcp"])
def test_complete_entry_workflow_headers_and_order(tmp_path, transport):
    app = create_app(tmp_path / "headers.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic Career client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:

        def call(tool, method, path, arguments):
            if transport == "rest":
                # REST names the identifiers in the path and the rest in the body or query.
                body = {
                    k: v
                    for k, v in arguments.items()
                    if not (k.endswith("_id") and f"/{v}" in path)
                }
                response = client.request(
                    method,
                    "/api/v1" + path,
                    params=body if method == "GET" else None,
                    json=body if method != "GET" else None,
                )
                response.raise_for_status()
                return response.json()
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            response.raise_for_status()
            result = response.json()["result"]
            assert not result.get("isError"), result
            return result.get("structuredContent") or json.loads(result["content"][0]["text"])

        first = call(
            "knowledge_create",
            "POST",
            "/career/knowledge",
            {
                "title": "Engineer",
                "organization": "Example Cloud",
                "skills": ["Python", "python"],
                "dates": {"kind": "period", "start": "2024-08", "current": True},
            },
        )
        second = call(
            "knowledge_create",
            "POST",
            "/career/knowledge",
            {"title": "Languages", "kind": "skill", "position": 0},
        )
        assert first["narrative"] == "" and first["position"] == 0 and first["skills"] == ["Python"]
        summary = call(
            "knowledge_list", "GET", "/career/knowledge", {"q": "Cloud", "summary": True}
        )
        assert summary["total"] == 1
        row = summary["items"][0]
        assert row["organization"] == "Example Cloud" and row["dates"]["start"] == "2024-08"
        assert "metadata" not in row and "narrative" not in row

        c1 = call(
            "claims_create",
            "POST",
            "/career/claims",
            {"knowledge_id": first["id"], "text": "First wording.", "approved": True},
        )
        c2 = call(
            "claims_create",
            "POST",
            "/career/claims",
            {"knowledge_id": first["id"], "text": "Earlier wording.", "approved": True},
        )
        assert c2["position"] == c1["position"] + 1
        c1 = call(
            "claims_update",
            "PATCH",
            "/career/claims/" + c1["id"],
            {"claim_id": c1["id"], "expected_version": c1["version"], "position": 5},
        )
        rows = call("claims_list", "GET", "/career/claims", {"q": "Cloud", "summary": True})[
            "items"
        ]
        assert [row["id"] for row in rows] == [c2["id"], c1["id"]]
        assert rows[0]["knowledge_organization"] == "Example Cloud"

        changed = call(
            "knowledge_update",
            "PATCH",
            "/career/knowledge/" + first["id"],
            {
                "knowledge_id": first["id"],
                "expected_version": first["version"],
                "dates": None,
                "organization": "",
                "skills": [],
                "position": 4,
            },
        )
        assert (
            changed["dates"] is None and changed["skills"] == [] and changed["organization"] == ""
        )
        ordered = call("knowledge_list", "GET", "/career/knowledge", {})["items"]
        assert [row["id"] for row in ordered] == [second["id"], first["id"]]
        imported = call(
            "career_import",
            "POST",
            "/career/import",
            {
                "knowledge": [
                    {
                        "kind": "award",
                        "title": "Community award",
                        "organization": "Example",
                        "dates": {"kind": "single", "start": "2025"},
                    }
                ]
            },
        )
        assert imported["items"][0]["dates"]["start"] == "2025"
        assert imported["items"][0]["position"] == 5
