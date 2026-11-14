"""Staleness by part: only the Profile parts and Preferences documents use make a Draft stale."""

import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from openings.actors import OWNER, acting_as, token_actor
from openings.app import create_app
from openings.career import (
    CareerService,
    ClaimCreate,
    ClaimUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.documents import ContextCreate, DocumentCreate, DocumentService
from openings.preferences import PreferencesService
from test_context_parts import seed

AGENT = token_actor("token-agent", "Synthetic agent", "agent")


class Services:
    def __init__(self, workspace):
        self.workspace = workspace
        self.career = CareerService(workspace)
        self.preferences = PreferencesService(workspace)
        self.documents = DocumentService(workspace)

    def profile(self, **fields):
        current = self.career.get_profile()
        return self.career.update_profile(
            ProfileUpdate(expected_version=current["version"], **fields)
        )

    def section(self, name):
        return next(
            item
            for item in self.preferences.get_preferences()["sections"]
            if item["section"] == name
        )

    def write(self, name, items, actor=OWNER):
        with acting_as(actor):
            current = self.section(name)
            return self.preferences.update_preferences(
                name, {"expected_version": current["version"], "items": items}
            )

    def add(self, name, text, actor=OWNER, **fields):
        self.write(name, [*self.section(name)["items"], {"text": text, **fields}], actor)

    def replace(self, name, old, new, actor=OWNER):
        self.write(
            name,
            [
                {**item, "text": new} if item["text"] == old else item
                for item in self.section(name)["items"]
            ],
            actor,
        )

    def remove(self, name, text):
        self.write(name, [item for item in self.section(name)["items"] if item["text"] != text])

    def report(self, application_id):
        return self.documents.application_staleness(application_id)

    def draft(self, application_id):
        """A CV and a letter written from one new context."""
        context = self.documents.prepare_context(ContextCreate(application_id=application_id))
        for kind in ("cv", "letter"):
            self.documents.create_document(
                DocumentCreate(
                    application_id=application_id,
                    context_id=context["id"],
                    kind=kind,
                    title=kind,
                )
            )
        return context


def changed(report):
    return [(item["input"], item["label"], item["state"]) for item in report["changes"]]


def per_document(report):
    return {
        document["kind"]: [(item["input"], item["label"]) for item in document["changes"]]
        for document in report["documents"]
    }


@pytest.fixture
def drafted(tmp_path):
    workspace, *_, applications = seed(tmp_path / "parts.sqlite", applications=2)
    services = Services(workspace)
    services.profile(metadata={"notes": "Synthetic"}, email="alex@example.test")
    services.write(
        "facts",
        [{"text": "Work authorization: EU citizen."}, {"text": "Notice period: one month."}],
    )
    services.write(
        "writing",
        [
            {"text": "One page.", "scope": "cv"},
            {"text": "Sign off with Kind regards.", "scope": "letter"},
            {"text": "British spelling.", "scope": "all"},
        ],
    )
    services.write("looking_for", [{"text": "Prefer remote roles."}])
    context = services.draft(applications[0])
    assert services.report(applications[0])["stale"] is False
    return services, applications[0], context


def test_edits_documents_never_use_leave_drafts_current(drafted):
    services, application_id, _ = drafted
    services.profile(
        metadata={"notes": "Changed", "search": {"queries": ["python"]}},
    )
    # The sections that choose jobs and guide the agent do not reach a document.
    services.replace("looking_for", "Prefer remote roles.", "Remote or hybrid.")
    services.add("ruled_out", "No agencies.")
    services.add("working_with_me", "Ask before a bulk dismissal.", actor=AGENT)
    # Order and spacing are not content, and a new default template leaves the old one alone.
    facts = services.section("facts")["items"]
    services.write("facts", [*reversed(facts)])
    services.replace("writing", "British spelling.", "British   spelling. ")
    services.career.create_template(
        TemplateCreate(name="Second CV", kind="cv", tex="Synthetic", is_default=True)
    )
    report = services.report(application_id)
    assert report["stale"] is False, report["changes"]
    assert all(
        document["comparison"] == {"profile": "parts", "preferences": "items"}
        for document in report["documents"]
    )
    assert services.workspace.get_application(application_id)["stale_inputs"] == []


def test_a_used_profile_part_is_named_and_a_reverted_one_is_current_again(drafted):
    services, application_id, _ = drafted
    before = services.career.get_profile()
    services.profile(summary="A different synthetic summary.")
    services.profile(phone="+00 000 0000")
    report = services.report(application_id)
    assert report["inputs"] == ["profile"]
    assert changed(report) == [
        ("profile", "Contact details", "changed"),
        ("profile", "Summary", "changed"),
    ]
    summary = report["changes"][1]
    assert summary["id"] == "summary"
    assert (summary["frozen_version"], summary["current_version"]) == (
        before["version"],
        before["version"] + 2,
    )
    services.profile(summary=before["summary"], phone=before["phone"])
    assert services.report(application_id)["stale"] is False


def test_statements_are_compared_by_content_and_scope(drafted):
    services, application_id, _ = drafted
    services.replace("facts", "Work authorization: EU citizen.", "Work authorization: EU, no visa.")
    report = services.report(application_id)
    assert changed(report) == [
        ("preferences", "Work authorization: EU, no visa.", "added"),
        ("preferences", "Work authorization: EU citizen.", "removed"),
    ]
    change = report["changes"][0]
    assert change["section"] == "facts" and change["id"].startswith("facts:")
    assert (change["frozen_version"], change["current_version"]) == (1, 2)
    assert per_document(report) == {
        "letter": [
            ("preferences", "Work authorization: EU, no visa."),
            ("preferences", "Work authorization: EU citizen."),
        ],
        "cv": [
            ("preferences", "Work authorization: EU, no visa."),
            ("preferences", "Work authorization: EU citizen."),
        ],
    }
    # A writing rule scoped to the CV concerns the CV only.
    services.replace("writing", "One page.", "One page, no photo.")
    documents = per_document(services.report(application_id))
    assert ("preferences", "One page, no photo.") in documents["cv"]
    assert ("preferences", "One page, no photo.") not in documents["letter"]
    # A rule moved from the letter to all documents concerns both.
    services.remove("writing", "Sign off with Kind regards.")
    services.add("writing", "Sign off with Kind regards.", scope="all")
    states = {(item["label"], item["state"]) for item in services.report(application_id)["changes"]}
    assert {
        ("Sign off with Kind regards.", "removed"),
        ("Sign off with Kind regards.", "added"),
    } <= states
    documents = per_document(services.report(application_id))
    assert ("preferences", "Sign off with Kind regards.") in documents["cv"]


@pytest.mark.asyncio
async def test_rest_mcp_and_application_summaries_report_the_same_parts(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    services = Services(app.state.workspace)
    services.career.create_template(
        TemplateCreate(name="MASTER CV", kind="cv", tex="Synthetic", is_default=True)
    )
    services.write("facts", [{"text": "Work authorization: EU citizen."}])
    job = services.workspace.ingest_job({"title": "Synthetic role", "posting": "Build APIs."})
    application_id = services.workspace.create_application({"job_id": job["id"]})["id"]
    services.draft(application_id)
    services.profile(summary="Changed.", headline="Engineer", metadata={"x": 1})
    services.replace("facts", "Work authorization: EU citizen.", "Work authorization: changed.")
    template = services.career.list_templates()["items"][0]
    services.career.update_template(
        template["id"], TemplateUpdate(expected_version=template["version"], guidance="New.")
    )
    report = services.report(application_id)
    assert changed(report) == [
        ("profile", "Headline", "changed"),
        ("profile", "Summary", "changed"),
        ("preferences", "Work authorization: changed.", "added"),
        ("preferences", "Work authorization: EU citizen.", "removed"),
        ("template", "MASTER CV", "changed"),
    ]
    summary = services.workspace.get_application(application_id)
    assert summary["stale_inputs"] == ["profile", "preferences", "template"]
    assert summary["stale_changes"] == report["changes"][:3]
    assert summary["stale_changes_total"] == 5
    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        assert client.get(f"/api/v1/applications/{application_id}/staleness").json() == report
        listed = client.get("/api/v1/staleness").json()["items"][0]
        assert {key: listed[key] for key in report} == report
        row = client.get("/api/v1/applications").json()["items"][0]
        assert [row[key] for key in ("stale_inputs", "stale_changes", "stale_changes_total")] == [
            summary[key] for key in ("stale_inputs", "stale_changes", "stale_changes_total")
        ]
    result = await app.state.mcp.call_tool("staleness_get", {"application_id": application_id})
    assert json.loads(result.content[0].text) == report


def _parts(path):
    with closing(sqlite3.connect(path)) as conn:
        return {
            context_id: json.loads(parts) if parts else None
            for context_id, parts in conn.execute("SELECT context_id,parts FROM context_inputs")
        }


def test_records_are_compared_by_the_content_documents_use(tmp_path):
    app = create_app(tmp_path / "records.sqlite", start_worker=False)
    services = Services(app.state.workspace)
    career = services.career
    template = career.create_template(
        TemplateCreate(name="MASTER CV", kind="cv", tex="Synthetic", is_default=True)
    )
    entry = career.create_knowledge(
        KnowledgeCreate(title="Backend Engineer", narrative="Built services.")
    )
    claim = career.create_claim(
        ClaimCreate(knowledge_id=entry["id"], text="Reduced latency by 20%.", approved=True)
    )
    job = services.workspace.ingest_job({"title": "Synthetic role", "posting": "Build APIs."})
    application_id = services.workspace.create_application({"job_id": job["id"]})["id"]
    services.draft(application_id)

    def edit_entry(**fields):
        current = career.get_knowledge(entry["id"])
        career.update_knowledge(
            entry["id"], KnowledgeUpdate(expected_version=current["version"], **fields)
        )

    def edit_claim(**fields):
        current = career.get_claim(claim["id"])
        career.update_claim(claim["id"], ClaimUpdate(expected_version=current["version"], **fields))

    def edit_writing(text):
        services.write("writing", [{"text": text}])

    # New versions that change nothing documents use.
    edit_entry(metadata={"source": "https://example.test/synthetic"}, position=4)
    edit_claim(metadata={"source": "synthetic", "role": "core"}, always_include=True)
    general = services.section("writing")["items"][0]["text"]
    edit_writing("Changed for a moment.")
    edit_writing(general)
    edit_writing(general.replace(". ", ".  \n"))  # spacing only
    edit_entry(narrative="Built   services.\n")
    current = career.get_template(template["id"])
    career.update_template(
        template["id"], TemplateUpdate(expected_version=current["version"], name="Renamed CV")
    )
    # Records the context never froze.
    career.create_knowledge(KnowledgeCreate(title="Later entry", narrative="Synthetic."))
    career.create_claim(ClaimCreate(knowledge_id=entry["id"], text="A later claim.", approved=True))
    report = services.report(application_id)
    assert report["stale"] is False, report["changes"]

    # Content documents use.
    edit_entry(narrative="Built and operated services.")
    edit_claim(text="Reduced latency by 25%.")
    edit_writing("Be concise.")
    current = career.get_template(template["id"])
    career.update_template(
        template["id"], TemplateUpdate(expected_version=current["version"], tex="Changed")
    )
    assert changed(services.report(application_id)) == [
        ("preferences", "Be concise.", "added"),
        ("preferences", general[:120], "removed"),
        ("template", "MASTER CV", "changed"),
        ("knowledge", "Backend Engineer", "changed"),
        ("claim", "Reduced latency by 20%.", "changed"),
    ]


def test_part_hashes_of_an_earlier_format_are_derived_again(drafted):
    services, application_id, context = drafted
    path = services.workspace.db.path
    expected = _parts(path)
    with services.workspace.db.transaction() as conn:
        conn.execute(
            "UPDATE context_inputs SET parts=? WHERE context_id=?",
            (
                json.dumps({"format": 2, "profile": None, "templates": {}}),
                context["id"],
            ),
        )
    assert services.report(application_id)["stale"] is False
    assert _parts(path) == expected
