"""Content-addressed context storage: exact reads, shared parts and collection."""

import hashlib
import json
import random
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.career import (
    CareerService,
    ClaimCreate,
    InstructionsUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
)
from openings.common import new_id, now
from openings.db import Database
from openings.documents import ContextCreate, DocumentCreate, DocumentService
from openings.operations import remove_installation_credentials, restore_database
from openings.snapshots import payload_text, store_context
from openings.workspace import Workspace
from timeline_fixtures import guided_application


def legacy_encode(value):
    """The serialisation of a context payload: canonical, compact JSON."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


AWKWARD = [
    "naïve café — “quotes” and 'apostrophes'",
    "数据管道 と 日本語 и кириллица",
    "emoji outside the BMP: \U0001f680 \U0001d11e",
    'escapes: \\ / " \b \f \n \r \t \x00 \x1f \x7f',
    "  line separators   and ﻿ marks",
    "",
    "</script><!-- & -->",
]


def words(rng, size):
    return " ".join(rng.choice(AWKWARD[:3] + ["service", "latency", "ledger"]) for _ in range(size))


def add_asset(workspace, column, owner, name, data, media="image/png"):
    digest = hashlib.sha256(data).hexdigest()
    with workspace.db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
            (digest, data, len(data)),
        )
        conn.execute(
            f"INSERT INTO files(id,sha256,name,media_type,size,{column},created_at) VALUES(?,?,?,?,?,?,?)",
            (new_id(), digest, name, media, len(data), owner, now()),
        )
    return digest


def seed(path, *, entries=6, claims=4, applications=3, narrative=60, seed=3):
    """A workspace with Career evidence, templates, assets and applications, no contexts."""
    rng = random.Random(seed)
    workspace = Workspace(path)
    career = CareerService(workspace)
    career.update_profile(
        ProfileUpdate(
            expected_version=career.get_profile()["version"],
            name="Alex Example",
            headline="Backend engineer",
            summary=words(rng, 80),
        )
    )
    career.update_instructions(
        InstructionsUpdate(
            expected_version=career.get_instructions()["version"], general=words(rng, 120)
        )
    )
    knowledge, claim_ids = [], []
    for index in range(entries):
        entry = career.create_knowledge(
            KnowledgeCreate(
                kind="project",
                title=f"Entry {index} {AWKWARD[index % len(AWKWARD)]}"[:150],
                narrative=words(rng, narrative),
            )
        )
        knowledge.append(entry["id"])
        for number in range(claims):
            claim = career.create_claim(
                ClaimCreate(
                    knowledge_id=entry["id"],
                    text=f"Claim {index}.{number} " + words(rng, 12),
                    approved=number != 1,
                )
            )
            claim_ids.append(claim["id"])
    templates = [
        career.create_template(
            TemplateCreate(
                name=name, kind=kind, tex=words(rng, 150), guidance=words(rng, 60), is_default=True
            )
        )["id"]
        for name, kind in (("MASTER CV", "resume"), ("MASTER letter", "cover_letter"))
    ]
    add_asset(workspace, "template_id", templates[0], "assets/logo.png", b"synthetic logo")
    add_asset(workspace, "template_id", templates[0], "fonts/Ünï cödé.ttf", b"synthetic font")
    add_asset(workspace, "template_id", templates[1], "assets/logo.png", b"synthetic logo")
    add_asset(
        workspace, "knowledge_id", knowledge[0], "proof.pdf", b"%PDF-1.4 proof", "application/pdf"
    )
    application_ids = []
    for index in range(applications):
        job = workspace.ingest_job(
            {
                "title": f"Synthetic role {index}",
                "company": f"Example {index}",
                "posting": words(rng, 80),
            }
        )
        application_ids.append(guided_application(workspace, job["id"], f"Note {index} ✓")["id"])
    return workspace, knowledge, claim_ids, templates, application_ids


def awkward_value(rng, depth=0):
    kind = rng.randrange(9 if depth < 3 else 6)
    if kind == 0:
        return rng.choice(AWKWARD)
    if kind == 1:
        return rng.choice([0, -1, 2**53 + 1, -(2**70), 1e-7, 3.14159, 1e300, -0.0])
    if kind == 2:
        return rng.choice([True, False, None])
    if kind == 3:
        return "".join(
            chr(rng.choice([rng.randrange(32), rng.randrange(0x80, 0x3000)])) for _ in range(40)
        )
    if kind == 4:
        return rng.choice(AWKWARD) * rng.randrange(1, 300)
    if kind == 5:
        return rng.choice([[], {}, ""])
    if kind == 6:
        return [awkward_value(rng, depth + 1) for _ in range(rng.randrange(4))]
    return {
        rng.choice(AWKWARD + ["id", "url", "name", "z", "A"])[:12] + str(index): awkward_value(
            rng, depth + 1
        )
        for index in range(rng.randrange(5))
    }


def awkward_payload(rng):
    """A payload with the released top-level shape and hostile content in every section."""

    def records(count):
        return [
            {
                "id": new_id(),
                "version": rng.randrange(1, 9),
                "text": awkward_value(rng),
                "x": awkward_value(rng),
            }
            for _ in range(count)
        ]

    payload = {
        "request": awkward_value(rng),
        "profile": {"version": rng.randrange(1, 5), "summary": awkward_value(rng)},
        "job": {
            "title": rng.choice(AWKWARD),
            "company": awkward_value(rng),
            "posting": AWKWARD[1] * 50,
        },
        "application": awkward_value(rng),
        "knowledge": records(rng.choice([0, 1, 2, 40])),
        "claims": records(rng.choice([0, 1, 3, 400])),
        "templates": records(rng.choice([0, 1, 2])),
        "instructions": {
            "general": rng.choice(AWKWARD) * rng.choice([0, 1, 200]),
            "version": rng.randrange(1, 5),
            "template_append": {
                new_id(): rng.choice(AWKWARD) * 60 for _ in range(rng.randrange(3))
            },
            "application_note": rng.choice(AWKWARD) * rng.choice([1, 100]),
        },
        "questions": awkward_value(rng),
        "files": [],
    }
    for key in rng.sample(sorted(payload), rng.randrange(3)):
        # Sections of an unexpected type or missing altogether. The released input
        # summary could not read text where it expected records, so lists avoid it.
        records_expected = key in ("knowledge", "claims", "templates")
        payload[key] = rng.choice([None, 7, [], {}]) if records_expected else awkward_value(rng)
    if rng.random() < 0.2:
        del payload[rng.choice(sorted(payload))]
    return payload


def test_new_contexts_store_the_released_serialisation(tmp_path):
    workspace, knowledge, _, _, applications = seed(tmp_path / "new.sqlite")
    documents = DocumentService(workspace)
    requests = [
        ContextCreate(application_id=applications[0], idempotency_key="once", note="Ünïcode ✓"),
        ContextCreate(application_id=applications[1], knowledge_ids=[], claim_ids=[]),
        ContextCreate(application_id=applications[2], knowledge_ids=knowledge[:1]),
    ]
    for request in requests:
        context = documents.prepare_context(request)
        expected = legacy_encode(context["payload"])
        with workspace.db.connect() as conn:
            assert payload_text(conn, context["id"]) == expected
            assert not conn.execute("SELECT 1 FROM files WHERE context_id IS NOT NULL").fetchall()
        assert context["signature"] == hashlib.sha256(expected.encode()).hexdigest()
        assert documents.get_context(context["id"]) == context
        files = documents.list_files(owner_type="context", owner_id=context["id"])
        assert files["total"] == len(context["payload"]["files"])
        assert {item["id"] for item in files["items"]} == {
            item["id"] for item in context["payload"]["files"]
        }
        summary = documents.list_contexts(context["application_id"], summary=True)["items"][0]
        assert summary["file_count"] == files["total"]
        assert summary["knowledge_count"] == len(context["payload"]["knowledge"])
        assert summary["claim_count"] == len(context["payload"]["claims"])
        assert summary["job_title"] == context["payload"]["job"]["title"]
    # A retry with the same key returns the same frozen record.
    assert (
        documents.prepare_context(requests[0])["id"]
        == documents.list_contexts(applications[0])["items"][0]["id"]
    )
    assert documents.list_files(application_id=applications[0])["total"] == 4
    document = documents.create_document(
        DocumentCreate(
            application_id=applications[2],
            context_id=documents.list_contexts(applications[2])["items"][0]["id"],
            kind="answers",
            content={"sections": [{"evidence_ids": knowledge[:1]}]},
        )
    )
    assert document["context_id"]


def test_random_payloads_round_trip_through_the_current_write_path(tmp_path):
    workspace, _, _, _, applications = seed(tmp_path / "random.sqlite", entries=1, applications=1)
    rng = random.Random(9)
    with workspace.db.transaction() as conn:
        for _ in range(80):
            text = legacy_encode(awkward_payload(rng))
            context_id = new_id()
            conn.execute(
                "INSERT INTO contexts(id,application_id,signature,created_at) VALUES(?,?,?,?)",
                (context_id, applications[0], "s", now()),
            )
            store_context(conn, context_id, text)
            assert payload_text(conn, context_id) == text
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def context_files_app(path):
    app = create_app(path, start_worker=False)
    client = TestClient(app)
    session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
    client.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    return client


def counts(workspace):
    with workspace.db.connect() as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        return {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "contexts",
                "context_parts",
                "snapshot_parts",
                "snapshot_list_items",
                "blobs",
            )
        }


def test_unreferenced_parts_and_bytes_are_collected_with_their_last_context(tmp_path, monkeypatch):
    workspace, knowledge, _, templates, applications = seed(tmp_path / "collect.sqlite")
    career, documents = CareerService(workspace), DocumentService(workspace)
    contexts = [
        documents.prepare_context(ContextCreate(application_id=item)) for item in applications
    ]
    shared = counts(workspace)
    # Three contexts over one Career record store its parts once.
    assert shared["snapshot_parts"] < 2 * counts_for_one(tmp_path)
    # Live records change or disappear; the frozen parts and bytes stay.
    entry = career.get_knowledge(knowledge[0])
    career.update_knowledge(
        knowledge[0], KnowledgeUpdate(expected_version=entry["version"], narrative="Edited.")
    )
    template = workspace.db.one("SELECT version FROM templates WHERE id=?", (templates[0],))
    career.delete_template(templates[0], template["version"])
    assert counts(workspace)["blobs"] == shared["blobs"]
    assert documents.get_context(contexts[0]["id"]) == contexts[0]
    file_id = contexts[0]["payload"]["files"][0]["id"]
    assert documents.get_file(file_id)["sha256"] == contexts[0]["payload"]["files"][0]["sha256"]

    version = workspace.get_application(applications[0])["version"]
    workspace.delete_application(applications[0], version)
    after_one = counts(workspace)
    assert after_one["contexts"] == 2 and after_one["blobs"] == shared["blobs"]
    assert after_one["context_parts"] < shared["context_parts"]
    assert documents.get_context(contexts[1]["id"]) == contexts[1]
    with pytest.raises(Exception, match="not found"):
        documents.get_file(file_id)

    # A bulk run deletes each item without collecting and collects once at the end.
    calls = {"each": 0, "once": 0}
    original = Database.collect_blobs
    monkeypatch.setattr(
        "openings.workspace.application_changes.collect_unused",
        lambda conn: calls.__setitem__("each", calls["each"] + 1),
    )
    monkeypatch.setattr(
        Database,
        "collect_blobs",
        lambda self: (calls.__setitem__("once", calls["once"] + 1), original(self))[1],
    )
    result = workspace.bulk_applications(
        {
            "action": "delete",
            "items": [
                {"id": item, "expected_version": workspace.get_application(item)["version"]}
                for item in applications[1:]
            ],
        }
    )
    assert result["succeeded"] == 2 and calls == {"each": 0, "once": 1}
    final = counts(workspace)
    assert final["contexts"] == final["context_parts"] == final["snapshot_parts"] == 0
    assert final["snapshot_list_items"] == 0
    # Only the bytes live records still own remain.
    live = workspace.db.one("SELECT count(DISTINCT sha256) AS n FROM files")["n"]
    assert final["blobs"] == live


def counts_for_one(tmp_path):
    workspace, _, _, _, applications = seed(tmp_path / "one.sqlite")
    DocumentService(workspace).prepare_context(ContextCreate(application_id=applications[0]))
    return counts(workspace)["snapshot_parts"]


def test_forgetting_a_job_collects_its_context_parts_in_the_same_transaction(tmp_path):
    workspace, _, _, _, applications = seed(tmp_path / "forget.sqlite", applications=1)
    DocumentService(workspace).prepare_context(ContextCreate(application_id=applications[0]))
    assert counts(workspace)["snapshot_parts"] > 0
    job = workspace.db.one("SELECT id,version FROM jobs")
    workspace.forget_job(job["id"], job["version"])
    final = counts(workspace)
    assert final["snapshot_parts"] == final["context_parts"] == final["snapshot_list_items"] == 0
    assert final["blobs"] == workspace.db.one("SELECT count(DISTINCT sha256) AS n FROM files")["n"]


def test_questions_and_requests_do_not_keep_deleted_contexts_alive(tmp_path):
    app = create_app(tmp_path / "subjects.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents
    career = app.state.career
    entry = career.create_knowledge(KnowledgeCreate(title="Backend engineer", narrative="Built."))
    career.create_template(TemplateCreate(name="CV", kind="resume", tex="x", is_default=True))
    add_asset(workspace, "knowledge_id", entry["id"], "proof.pdf", b"%PDF-1.4 proof")
    applications = []
    for index in range(2):
        job = workspace.ingest_job({"title": f"Synthetic role {index}", "posting": "Build."})
        application = workspace.create_application({"job_id": job["id"]})
        context = documents.prepare_context(ContextCreate(application_id=application["id"]))
        for subject in (("job", job["id"]), ("application", application["id"])):
            app.state.activity.ask_question(
                {"question": "Which team?", "subject_type": subject[0], "subject_id": subject[1]}
            )
            app.state.requests.create_request(
                {"text": "Prepare this.", "subject_type": subject[0], "subject_id": subject[1]}
            )
        applications.append((job, application, context))
    assert counts(workspace)["snapshot_parts"] > 0

    job, application, context = applications[0]
    workspace.delete_application(
        application["id"], workspace.get_application(application["id"])["version"]
    )
    remaining = counts(workspace)
    assert remaining["contexts"] == 1 and remaining["blobs"] == 1
    assert documents.get_context(applications[1][2]["id"]) == applications[1][2]
    job = applications[1][0]
    workspace.forget_job(job["id"], workspace.get_job(job["id"])["version"])
    final = counts(workspace)
    assert final["contexts"] == final["context_parts"] == final["snapshot_parts"] == 0
    assert final["snapshot_list_items"] == 0
    # The live Career file still owns its bytes; questions and requests survive unlinked.
    assert final["blobs"] == 1
    assert workspace.db.one("SELECT count(*) AS n FROM questions")["n"] == 4
    assert workspace.db.one("SELECT count(*) AS n FROM requests")["n"] == 4
    with workspace.db.connect() as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def prepared(path):
    """A workspace with one frozen context per application, prepared by the current code."""
    workspace, _, _, _, applications = seed(path)
    documents = DocumentService(workspace)
    contexts = [
        documents.prepare_context(ContextCreate(application_id=application))
        for application in applications
    ]
    return workspace, contexts


def test_context_files_keep_their_ids_through_rest_and_stay_immutable(tmp_path):
    path = tmp_path / "files.sqlite"
    _, contexts = prepared(path)
    files = [item for context in contexts for item in context["payload"]["files"]]
    assert files
    client = context_files_app(path)
    with client:
        row, context = files[0], contexts[0]
        assert client.get(f"/api/v1/files/{row['id']}").json()["owner_id"] == context["id"]
        content = client.get(f"/api/v1/files/{row['id']}/content")
        grant = client.post(f"/api/v1/files/{row['id']}/download").json()
        assert client.get(grant["url"], headers=grant["headers"]).content == content.content
        assert client.delete(f"/api/v1/files/{row['id']}?expected_version=1").status_code == 409
        refused = client.post(
            "/api/v1/files/uploads",
            json={"owner_type": "context", "owner_id": context["id"], "name": "x", "size": 1},
        )
        assert refused.status_code == 422
        listed = client.get("/api/v1/files", params={"owner_type": "context", "limit": 200}).json()
        assert listed["total"] == len(files)
        named = client.get("/api/v1/files", params={"q": "Ünï", "owner_type": "context"}).json()
        assert named["total"] and all("Ünï" in item["name"] for item in named["items"])
        archive = client.get("/api/v1/export").json()
        assert {item["id"]: item["payload"] for item in archive["contexts"]} == {
            context["id"]: context["payload"] for context in contexts
        }


def test_backups_and_credential_free_backups_restore_every_context(tmp_path):
    workspace, contexts = prepared(tmp_path / "source.sqlite")
    for strip in (False, True):
        backup = tmp_path / f"backup-{strip}.sqlite"
        workspace.db.backup(backup)
        if strip:
            remove_installation_credentials(backup)
            with closing(sqlite3.connect(backup)) as conn:
                assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert not conn.execute("SELECT 1 FROM api_tokens").fetchall()
        target = Workspace(tmp_path / f"target-{strip}" / "live.sqlite")
        restore_database(target, backup)
        documents = DocumentService(target)
        for context in contexts:
            assert documents.get_context(context["id"]) == context
            with target.db.connect() as conn:
                assert payload_text(conn, context["id"]) == legacy_encode(context["payload"])
