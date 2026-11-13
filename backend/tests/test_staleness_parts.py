"""Staleness by part: only the Profile parts and policy items documents use make a Draft stale."""

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
    InstructionsUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.documents import ContextCreate, DocumentCreate, DocumentService
from openings.policy import PolicyService
from test_context_parts import seed

AGENT = token_actor("token-agent", "Synthetic agent", "agent")


class Services:
    def __init__(self, workspace):
        self.workspace = workspace
        self.career = CareerService(workspace)
        self.policy = PolicyService(workspace)
        self.documents = DocumentService(workspace)

    def profile(self, **fields):
        current = self.career.get_profile()
        return self.career.update_profile(
            ProfileUpdate(expected_version=current["version"], **fields)
        )

    def version(self, section):
        return self.policy.get_policy(section)["version"]

    def add(self, section, label, actor=OWNER, **fields):
        with acting_as(actor):
            return self.policy.add_item(
                section, {"expected_version": self.version(section), "label": label, **fields}
            )["item"]

    def update(self, item, actor=OWNER, **fields):
        with acting_as(actor):
            current = next(
                entry
                for part in self.policy.get_policy()["sections"]
                for entry in part["items"]
                if entry["id"] == item["id"]
            )
            return self.policy.update_item(
                item["id"],
                {"expected_version": self.version(current["section"]), **fields},
            )["item"]

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
    items = {
        "authorization": services.add("eligibility", "Work authorization", statement="EU citizen."),
        "one_page": services.add("writing", "One page", statement="Keep it short.", scope="cv"),
        "sign_off": services.add("writing", "Sign-off", statement="Kind regards.", scope="letter"),
        "notice": services.add("facts", "Notice period", value="One month"),
        "remote": services.add("decision", "Remote first", statement="Prefer remote roles."),
        "proposal": services.add("facts", "Languages", actor=AGENT, value=["English"]),
    }
    context = services.draft(applications[0])
    assert services.report(applications[0])["stale"] is False
    return services, applications[0], items, context


def test_edits_documents_never_use_leave_drafts_current(drafted):
    services, application_id, items, _ = drafted
    services.profile(
        metadata={"notes": "Changed", "search": {"queries": ["python"]}},
    )
    services.update(items["remote"], statement="Remote or hybrid.")
    services.add("decision", "No agencies")
    # An agent's proposal is not used until the owner confirms it.
    services.add("eligibility", "Driving licence", actor=AGENT, value=True)
    services.update(items["proposal"], actor=AGENT, value=["English", "Italian"])
    # Order is not content, and a new default template leaves the old one's content alone.
    eligibility = services.policy.get_policy("eligibility")
    services.policy.reorder_items(
        "eligibility",
        {
            "expected_version": eligibility["version"],
            "item_ids": [item["id"] for item in reversed(eligibility["items"])],
        },
    )
    services.career.create_template(
        TemplateCreate(name="Second CV", kind="cv", tex="Synthetic", is_default=True)
    )
    report = services.report(application_id)
    assert report["stale"] is False, report["changes"]
    assert all(
        document["comparison"] == {"profile": "parts", "policy": "items"}
        for document in report["documents"]
    )
    assert services.workspace.get_application(application_id)["stale_inputs"] == []


def test_a_used_profile_part_is_named_and_a_reverted_one_is_current_again(drafted):
    services, application_id, _, _ = drafted
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


def test_policy_items_are_compared_by_content_confirmation_and_scope(drafted):
    services, application_id, items, _ = drafted
    services.update(items["authorization"], statement="EU citizen, no sponsorship needed.")
    report = services.report(application_id)
    assert changed(report) == [("policy", "Work authorization", "changed")]
    change = report["changes"][0]
    assert (change["id"], change["section"]) == (items["authorization"]["id"], "eligibility")
    assert (change["frozen_version"], change["current_version"]) == (1, 2)
    assert per_document(report) == {
        "letter": [("policy", "Work authorization")],
        "cv": [("policy", "Work authorization")],
    }

    # A writing item scoped to the CV concerns the CV only.
    services.update(items["one_page"], statement="One page, no photo.")
    documents = per_document(services.report(application_id))
    assert ("policy", "One page") in documents["cv"]
    assert ("policy", "One page") not in documents["letter"]

    # An agent edit unconfirms; the owner's confirmation of a frozen proposal counts.
    services.update(items["notice"], actor=AGENT, value="Two months")
    with acting_as(OWNER):
        services.policy.confirm_item(
            items["proposal"]["id"], {"expected_version": services.version("facts")}
        )
    services.add("eligibility", "Work permit", statement="Valid until 2030.")
    with acting_as(OWNER):
        services.policy.remove_item(items["sign_off"]["id"], services.version("writing"))
    states = {(item["label"], item["state"]) for item in services.report(application_id)["changes"]}
    assert {
        ("Notice period", "unconfirmed"),
        ("Languages", "confirmed"),
        ("Work permit", "added"),
        ("Sign-off", "removed"),
    } <= states
    # A frozen item moved to decision is no longer used: removed as well.
    with acting_as(OWNER):
        services.policy.move_item(
            items["authorization"]["id"],
            {
                "expected_version": services.version("eligibility"),
                "section": "decision",
                "target_version": services.version("decision"),
            },
        )
    states = {(item["label"], item["state"]) for item in services.report(application_id)["changes"]}
    assert ("Work authorization", "removed") in states


@pytest.mark.asyncio
async def test_rest_mcp_and_application_summaries_report_the_same_parts(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    services = Services(app.state.workspace)
    services.career.create_template(
        TemplateCreate(name="MASTER CV", kind="cv", tex="Synthetic", is_default=True)
    )
    item = services.add("eligibility", "Work authorization", statement="EU citizen.")
    job = services.workspace.ingest_job({"title": "Synthetic role", "posting": "Build APIs."})
    application_id = services.workspace.create_application({"job_id": job["id"]})["id"]
    services.draft(application_id)
    services.profile(summary="Changed.", headline="Engineer", metadata={"x": 1})
    services.update(item, statement="EU citizen, changed.")
    template = services.career.list_templates()["items"][0]
    services.career.update_template(
        template["id"], TemplateUpdate(expected_version=template["version"], guidance="New.")
    )
    report = services.report(application_id)
    assert changed(report) == [
        ("profile", "Headline", "changed"),
        ("profile", "Summary", "changed"),
        ("policy", "Work authorization", "changed"),
        ("template", "MASTER CV", "changed"),
    ]
    summary = services.workspace.get_application(application_id)
    assert summary["stale_inputs"] == ["profile", "policy", "template"]
    assert summary["stale_changes"] == report["changes"][:3]
    assert summary["stale_changes_total"] == 4
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

    def edit_instructions(general):
        current = career.get_instructions()
        career.update_instructions(
            InstructionsUpdate(expected_version=current["version"], general=general)
        )

    # New versions that change nothing documents use.
    edit_entry(metadata={"source": "https://example.test/synthetic"}, position=4)
    edit_claim(metadata={"source": "synthetic"}, role="core", group="Scale", default_in_cv=True)
    general = career.get_instructions()["general"]
    edit_instructions("Changed for a moment.")
    edit_instructions(general)
    edit_instructions(general + "\n\n  ")  # spacing only
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
    edit_instructions("Be concise.")
    current = career.get_template(template["id"])
    career.update_template(
        template["id"], TemplateUpdate(expected_version=current["version"], tex="Changed")
    )
    assert changed(services.report(application_id)) == [
        ("instructions", "Instructions", "changed"),
        ("template", "MASTER CV", "changed"),
        ("knowledge", "Backend Engineer", "changed"),
        ("claim", "Reduced latency by 20%.", "changed"),
    ]


def test_part_hashes_of_an_earlier_format_are_derived_again(drafted):
    services, application_id, _, context = drafted
    path = services.workspace.db.path
    expected = _parts(path)
    with services.workspace.db.transaction() as conn:
        conn.execute(
            "UPDATE context_inputs SET parts=? WHERE context_id=?",
            (
                json.dumps({"format": 1, "profile": None, "policy": None, "templates": {}}),
                context["id"],
            ),
        )
    assert services.report(application_id)["stale"] is False
    assert _parts(path) == expected
