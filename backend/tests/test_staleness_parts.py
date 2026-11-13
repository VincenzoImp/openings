"""Staleness by part: only the Profile parts and policy items documents use make a Draft stale."""

import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from context_fixtures import insert_legacy_context, legacy_prepare_context, make_schema_eight
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
from openings.db import MIGRATIONS, SCHEMA_VERSION
from openings.documents import ContextCreate, DocumentCreate, DocumentService
from openings.policy import PolicyService
from openings.snapshots import payload_text
from openings.staleness import PARTS_FORMAT, frozen_parts
from openings.workspace import Workspace
from outcome_fixtures import make_schema_ten
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
        for kind in ("resume", "cover_letter"):
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
        TemplateCreate(name="Second CV", kind="resume", tex="Synthetic", is_default=True)
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
        "cover_letter": [("policy", "Work authorization")],
        "resume": [("policy", "Work authorization")],
    }

    # A writing item scoped to the CV concerns the CV only.
    services.update(items["one_page"], statement="One page, no photo.")
    documents = per_document(services.report(application_id))
    assert ("policy", "One page") in documents["resume"]
    assert ("policy", "One page") not in documents["cover_letter"]

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
        TemplateCreate(name="MASTER CV", kind="resume", tex="Synthetic", is_default=True)
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


def test_a_schema_ten_workspace_is_backfilled_from_its_frozen_payloads(tmp_path):
    path = tmp_path / "schema10.sqlite"
    workspace, *_, applications = seed(path, applications=2)
    services = Services(workspace)
    services.profile(metadata={"notes": "Synthetic"})
    services.add("eligibility", "Work authorization", statement="EU citizen.")
    services.add("writing", "One page", statement="Keep it short.", scope="cv")
    contexts = [services.draft(application_id)["id"] for application_id in applications]
    services.profile(summary="Changed after the first contexts.")
    expected = {application_id: services.report(application_id) for application_id in applications}
    del workspace, services
    make_schema_ten(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 10
        assert "parts" not in {row[1] for row in conn.execute("PRAGMA table_info(context_inputs)")}
        derived = {
            context_id: frozen_parts(payload_text(conn, context_id)) for context_id in contexts
        }

    upgraded = Services(Workspace(path))
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert _parts(path) == derived
    assert all(parts["profile"] and parts["policy"] for parts in derived.values())
    for application_id in applications:
        assert upgraded.report(application_id) == expected[application_id]
        assert changed(expected[application_id]) == [("profile", "Summary", "changed")]
    # Deriving again gives the same rows: the backfill is deterministic.
    with upgraded.workspace.db.transaction() as conn:
        conn.execute("UPDATE context_inputs SET parts=NULL")
    assert upgraded.report(applications[0]) == expected[applications[0]]
    Workspace(path)
    assert _parts(path) == derived
    # A schema 11 file written before part hashes existed gains the column and them.
    with upgraded.workspace.db.transaction() as conn:
        conn.execute("ALTER TABLE context_inputs DROP COLUMN parts")
    Workspace(path)
    assert _parts(path) == derived


def test_older_contexts_compare_what_they_froze_and_say_what_they_cannot(tmp_path):
    path = tmp_path / "legacy.sqlite"
    workspace, knowledge, _, _, applications = seed(path, applications=3)
    services = Services(workspace)
    services.profile(metadata={"rules": "Synthetic rules"})
    del workspace, services
    make_schema_eight(path)
    legacy = legacy_prepare_context(path, applications[0], knowledge_ids=knowledge[:1])["id"]
    with closing(sqlite3.connect(path)) as conn:
        unreadable = insert_legacy_context(conn, applications[1], "not a JSON payload")
        profile_version = conn.execute(
            "SELECT version FROM settings WHERE key='profile'"
        ).fetchone()[0]
        for number, (application_id, context_id) in enumerate(
            ((applications[0], legacy), (applications[1], unreadable))
        ):
            conn.execute(
                "INSERT INTO documents(id,application_id,context_id,kind,title,content,created_at) "
                "VALUES(?,?,?,'resume','CV','{}','2026-01-01T00:00:00+00:00')",
                (f"document-{number}", application_id, context_id),
            )
        conn.commit()
    # The released 8 -> 9 step, then the current chain from schema 9.
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        MIGRATIONS[8](conn)
        conn.execute("PRAGMA user_version=9")
        conn.commit()
    services = Services(Workspace(path))
    parts = _parts(path)
    assert parts[legacy]["policy"] is None and parts[legacy]["profile"]
    assert parts[unreadable] == {
        "format": PARTS_FORMAT,
        "profile": None,
        "policy": None,
        "instructions": None,
        "templates": {},
        "knowledge": {},
        "claims": {},
    }
    first, second = (services.report(application_id) for application_id in applications[:2])
    assert first["stale"] is False
    assert first["documents"][0]["comparison"] == {"profile": "parts", "policy": "not_frozen"}
    # The unreadable payload records no version: compared as a whole, it differs.
    assert second["documents"][0]["comparison"] == {"profile": "whole", "policy": "not_frozen"}
    assert changed(second) == [
        ("profile", "Profile", "changed"),
        ("instructions", "Instructions", "changed"),
    ]
    assert second["changes"][0]["id"] is None
    assert second["changes"][0]["current_version"] == profile_version

    # The Profile's own rules and later policy changes are not compared for these.
    services.profile(metadata={})
    services.add("eligibility", "Work authorization", statement="EU citizen.")
    assert services.report(applications[0])["stale"] is False
    services.profile(summary="Changed summary.")
    assert changed(services.report(applications[0])) == [("profile", "Summary", "changed")]


def test_records_are_compared_by_the_content_documents_use(tmp_path):
    app = create_app(tmp_path / "records.sqlite", start_worker=False)
    services = Services(app.state.workspace)
    career = services.career
    template = career.create_template(
        TemplateCreate(name="MASTER CV", kind="resume", tex="Synthetic", is_default=True)
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
