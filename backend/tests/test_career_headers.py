"""Typed career headers and categories preserve precision and optional content."""

import json

import pytest
from pydantic import ValidationError

from openings.career import (
    CareerDates,
    CareerImport,
    CareerService,
    EntryCreate,
    HighlightCreate,
    HighlightUpdate,
    ImportPreview,
)
from openings.errors import DomainError

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
    value = EntryCreate(title="  Languages  ", skills=[" Python ", "python", "JS", "JavaScript"])
    assert value.title == "Languages"
    assert value.skills == ["Python", "JS", "JavaScript"]
    for fields in [
        {"skills": [" "]},
        {"skills": [123]},
        {"title": " "},
        {"metadata": {"organization": "Duplicate"}},
    ]:
        with pytest.raises(ValidationError):
            EntryCreate.model_validate({"title": "Entry", **fields})


def test_summary_claim_preview_is_ordered_bounded_and_independent_of_description(workspace):
    career = CareerService(workspace)
    owner = career.create_entry(EntryCreate(title="Languages", narrative="User context."))
    assert career.list_entries(summary=True)["items"][0]["highlight_preview"] is None
    first = career.create_highlight(HighlightCreate(career_id=owner["id"], text="Python, SQL."))
    later = career.create_highlight(
        HighlightCreate(career_id=owner["id"], text="Long wording " * 100)
    )
    assert career.list_entries(summary=True)["items"][0]["highlight_preview"] == first["text"]
    career.update_highlight(
        first["id"], HighlightUpdate(expected_version=first["version"], position=2)
    )
    row = career.list_entries(summary=True)["items"][0]
    assert row["highlight_preview"] == later["text"][:240]
    assert row["narrative_preview"] == "User context."
    assert career.get_entry(owner["id"])["narrative"] == "User context."


def test_a_claim_is_always_included_or_not_and_keeps_other_hints_in_metadata(workspace):
    career = CareerService(workspace)
    entry = career.create_entry(EntryCreate(title="Synthetic entry", narrative="Built."))
    claim = career.create_highlight(
        HighlightCreate(career_id=entry["id"], text="Built APIs.", metadata={"role": "core"})
    )
    assert claim["always_include"] is False and claim["metadata"] == {"role": "core"}
    claim = career.update_highlight(
        claim["id"], HighlightUpdate(expected_version=claim["version"], always_include=True)
    )
    assert claim["always_include"] is True and claim["metadata"] == {"role": "core"}
    listed = career.list_highlights()["items"][0]
    assert listed["always_include"] is True
    assert not {"role", "group", "default_in_cv"} & set(listed) & set(claim)
    for removed in ({"role": "core"}, {"group": "Scale"}, {"default_in_cv": True}):
        with pytest.raises(ValidationError):
            HighlightCreate.model_validate({"career_id": entry["id"], "text": "X.", **removed})


@pytest.fixture
def call(client):
    """A REST call of the dashboard: the body is the query of a GET."""

    def call(method, path, body=None):
        response = client.request(
            method,
            "/api/v1" + path,
            params=body if method == "GET" else None,
            json=body if method != "GET" else None,
        )
        response.raise_for_status()
        return response.json()

    return call


def test_complete_entry_workflow_headers_and_order(call):
    """The one-record career routes the dashboard uses, and the owner's import (REST only)."""
    first = call(
        "POST",
        "/career/entries",
        {
            "title": "Engineer",
            "organization": "Example Cloud",
            "skills": ["Python", "python"],
            "dates": {"kind": "period", "start": "2024-08", "current": True},
        },
    )
    second = call("POST", "/career/entries", {"title": "Languages", "kind": "skill", "position": 0})
    assert first["narrative"] == "" and first["position"] == 0 and first["skills"] == ["Python"]
    summary = call("GET", "/career/entries", {"q": "Cloud", "summary": True})
    assert summary["total"] == 1
    row = summary["items"][0]
    assert row["organization"] == "Example Cloud" and row["dates"]["start"] == "2024-08"
    assert "metadata" not in row and "narrative" not in row

    c1 = call(
        "POST",
        "/career/highlights",
        {"career_id": first["id"], "text": "First wording.", "approved": True},
    )
    c2 = call(
        "POST",
        "/career/highlights",
        {"career_id": first["id"], "text": "Earlier wording.", "approved": True},
    )
    assert c2["position"] == c1["position"] + 1
    c1 = call(
        "PATCH",
        "/career/highlights/" + c1["id"],
        {"expected_version": c1["version"], "position": 5},
    )
    rows = call("GET", "/career/highlights", {"q": "Cloud", "summary": True})["items"]
    assert [row["id"] for row in rows] == [c2["id"], c1["id"]]
    assert rows[0]["career_organization"] == "Example Cloud"

    changed = call(
        "PATCH",
        "/career/entries/" + first["id"],
        {
            "expected_version": first["version"],
            "dates": None,
            "organization": "",
            "skills": [],
            "position": 4,
        },
    )
    assert changed["dates"] is None and changed["skills"] == [] and changed["organization"] == ""
    ordered = call("GET", "/career/entries")["items"]
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


def test_awards_and_publications_survive_import_filtering_and_citation(client, call):
    entries = [
        {
            "kind": kind,
            "title": f"Example {kind}",
            "narrative": f"Synthetic supporting evidence for an example {kind}.",
            "metadata": {"year": 2024, "url": "https://example.org/evidence"},
        }
        for kind in ("award", "publication")
    ]
    created = [call("POST", "/career/entries", entry) for entry in entries]
    preview = call("POST", "/career/import/preview", {"text": json.dumps(entries)})
    assert [row["kind"] for row in preview["entries"]] == ["award", "publication"]
    assert call("GET", "/career/entries")["total"] == 2
    imported = call("POST", "/career/import", {"entries": preview["entries"]})
    assert imported["total"] == 2
    for entry, record in zip(entries, created):
        listed = call("GET", "/career/entries", {"kind": entry["kind"], "summary": True})
        assert listed["total"] == 2
        assert {row["kind"] for row in listed["items"]} == {entry["kind"]}
        read = call("GET", "/career/batch", {"ids": [record["id"]]})["items"][0]
        assert all(read[key] == value for key, value in entry.items())

    job = call("POST", "/jobs", {"title": "Engineer", "company": "Example", "posting": "Build."})
    started = call("POST", "/applications/batch", {"items": [{"job_id": job["id"]}]})
    application = started["items"][0]["result"]
    cited = [record["id"] for record in created + imported["items"]]
    document = call(
        "POST",
        "/documents",
        {
            "application_id": application["id"],
            "kind": "other",
            "content": {"text": "Synthetic notes."},
            "career_ids": cited,
        },
    )
    assert document["career_ids"] == cited
    award = created[0]
    changed = call(
        "PATCH",
        f"/career/entries/{award['id']}",
        {"expected_version": award["version"], "kind": "publication", "narrative": "Revised."},
    )
    assert changed["kind"] == "publication"
    # The revision keeps citing the entry by id.
    assert call("GET", f"/documents/{document['id']}")["career_ids"] == cited
    invalid = {"kind": "unsupported", "title": "Invalid category"}
    assert client.post("/api/v1/career/entries", json=invalid).status_code == 422


def test_an_import_preview_reads_text_entries_or_a_profile_and_changes_nothing(workspace):
    career = CareerService(workspace)
    entry = {"kind": "project", "title": "Synthetic project"}
    version = career.get_profile()["version"]

    def preview(text):
        return career.preview_import(ImportPreview(text=text, title="Synthetic notes"))

    plain = preview("Led a synthetic migration.")
    assert [(item["kind"], item["title"], item["narrative"]) for item in plain["entries"]] == [
        ("other", "Synthetic notes", "Led a synthetic migration.")
    ]
    assert plain["warnings"] and "profile" not in plain
    for text in (json.dumps([entry]), json.dumps(entry), json.dumps({"entries": [entry]})):
        read = preview(text)
        assert [item["title"] for item in read["entries"]] == ["Synthetic project"], text
        assert read["warnings"] == [], text
    profile = preview(json.dumps({"headline": "Synthetic engineer"}))
    assert profile["profile"] == {"headline": "Synthetic engineer"}
    assert profile["entries"] == [] and profile["expected_profile_version"] == version
    both = preview(json.dumps({"profile": {"name": "Alex"}, "entries": [entry], "notes": "x"}))
    assert both["profile"] == {"name": "Alex"} and len(both["entries"]) == 1
    assert len(both["warnings"]) == 2 and "'notes'" in both["warnings"][0]
    for text, code in (
        ("42", "import_format"),
        (json.dumps({"entries": "x"}), "import_format"),
        (json.dumps({"profile": "x"}), "import_format"),
        (json.dumps([{"kind": "unsupported", "title": "X"}]), "import_validation"),
    ):
        with pytest.raises(DomainError) as refused:
            preview(text)
        assert refused.value.code == code, text
    assert career.list_entries()["total"] == 0 and career.get_profile()["version"] == version
    # The profile of a preview applies only with the version it showed.
    with pytest.raises(DomainError) as unconfirmed:
        career.import_entries(CareerImport(profile={"headline": "Synthetic engineer"}))
    assert unconfirmed.value.code == "profile_version"
    applied = career.import_entries(
        CareerImport(profile=profile["profile"], expected_profile_version=version, entries=[entry])
    )
    assert applied["profile"]["headline"] == "Synthetic engineer" and len(applied["items"]) == 1
