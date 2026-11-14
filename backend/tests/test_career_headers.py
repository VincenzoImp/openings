"""Typed career headers preserve precision and optional content."""

import pytest
from pydantic import ValidationError

from openings.career import (
    CareerDates,
    CareerService,
    ClaimCreate,
    ClaimUpdate,
    KnowledgeCreate,
)

VALID_DATES = [
    {"kind": "single", "start": "2025"},
    {"kind": "single", "start": "2025-08"},
    {"kind": "period", "start": "2025-08", "current": True},
    {"kind": "period", "start": "2023", "end": "2025-08"},
    {"kind": "period", "start": "2025-08", "end": "2025"},
    {"kind": "period", "start": "2025", "end": "2025-02"},
]
INVALID_DATES = [
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
]


def test_dates_keep_only_supplied_precision_and_refuse_contradictions():
    for value in VALID_DATES:
        result = CareerDates.model_validate(value).model_dump()
        assert all(result[key] == item for key, item in value.items()), value
    for value in INVALID_DATES:
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


def test_summary_claim_preview_is_ordered_bounded_and_independent_of_description(workspace):
    career = CareerService(workspace)
    owner = career.create_knowledge(KnowledgeCreate(title="Languages", narrative="User context."))
    assert career.list_knowledge(summary=True)["items"][0]["highlight_preview"] is None
    first = career.create_claim(ClaimCreate(career_id=owner["id"], text="Python, SQL."))
    later = career.create_claim(ClaimCreate(career_id=owner["id"], text="Long wording " * 100))
    assert career.list_knowledge(summary=True)["items"][0]["highlight_preview"] == first["text"]
    career.update_claim(first["id"], ClaimUpdate(expected_version=first["version"], position=2))
    row = career.list_knowledge(summary=True)["items"][0]
    assert row["highlight_preview"] == later["text"][:240]
    assert row["narrative_preview"] == "User context."
    assert career.get_knowledge(owner["id"])["narrative"] == "User context."


def test_a_claim_is_always_included_or_not_and_keeps_other_hints_in_metadata(workspace):
    career = CareerService(workspace)
    entry = career.create_knowledge(KnowledgeCreate(title="Synthetic entry", narrative="Built."))
    claim = career.create_claim(
        ClaimCreate(career_id=entry["id"], text="Built APIs.", metadata={"role": "core"})
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
            ClaimCreate.model_validate({"career_id": entry["id"], "text": "X.", **removed})


def test_complete_entry_workflow_headers_and_order(client):
    """The one-record career routes the dashboard uses, and the owner's import (REST only)."""

    def call(method, path, body=None):
        response = client.request(
            method,
            "/api/v1" + path,
            params=body if method == "GET" else None,
            json=body if method != "GET" else None,
        )
        response.raise_for_status()
        return response.json()

    first = call(
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
        "POST", "/career/knowledge", {"title": "Languages", "kind": "skill", "position": 0}
    )
    assert first["narrative"] == "" and first["position"] == 0 and first["skills"] == ["Python"]
    summary = call("GET", "/career/knowledge", {"q": "Cloud", "summary": True})
    assert summary["total"] == 1
    row = summary["items"][0]
    assert row["organization"] == "Example Cloud" and row["dates"]["start"] == "2024-08"
    assert "metadata" not in row and "narrative" not in row

    c1 = call(
        "POST",
        "/career/claims",
        {"career_id": first["id"], "text": "First wording.", "approved": True},
    )
    c2 = call(
        "POST",
        "/career/claims",
        {"career_id": first["id"], "text": "Earlier wording.", "approved": True},
    )
    assert c2["position"] == c1["position"] + 1
    c1 = call(
        "PATCH",
        "/career/claims/" + c1["id"],
        {"expected_version": c1["version"], "position": 5},
    )
    rows = call("GET", "/career/claims", {"q": "Cloud", "summary": True})["items"]
    assert [row["id"] for row in rows] == [c2["id"], c1["id"]]
    assert rows[0]["career_organization"] == "Example Cloud"

    changed = call(
        "PATCH",
        "/career/knowledge/" + first["id"],
        {
            "expected_version": first["version"],
            "dates": None,
            "organization": "",
            "skills": [],
            "position": 4,
        },
    )
    assert changed["dates"] is None and changed["skills"] == [] and changed["organization"] == ""
    ordered = call("GET", "/career/knowledge")["items"]
    assert [row["id"] for row in ordered] == [second["id"], first["id"]]
    imported = call(
        "POST",
        "/career/import",
        {
            "entries": [
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
