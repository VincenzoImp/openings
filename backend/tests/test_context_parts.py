"""Content-addressed context storage: exact reads, shared parts, collection and upgrades."""

import hashlib
import json
import random
import shutil
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from context_fixtures import (
    insert_legacy_context,
    legacy_encode,
    legacy_prepare_context,
    make_schema_eight,
)
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
from openings.db import MIGRATIONS, SCHEMA_VERSION, Database
from openings.documents import ContextCreate, DocumentCreate, DocumentService
from openings.operations import remove_installation_credentials, restore_database
from openings.snapshots import payload_text, store_context
from openings.workspace import Workspace
from schema_fixtures import columns, index_names, make_schema_seven, table_names
from timeline_fixtures import guided_application

# The schema 8 list summary and input summary, as released.
OLD_SUMMARY = (
    "SELECT id,application_id,signature,created_at"
    ",json_extract(payload,'$.job.title') AS job_title"
    ",json_extract(payload,'$.job.company') AS company"
    ",substr(json_extract(payload,'$.instructions.application_note'),1,160) AS note_preview"
    ",json_array_length(payload,'$.knowledge') AS knowledge_count"
    ",json_array_length(payload,'$.claims') AS claim_count"
    ",json_extract(payload,'$.templates[0].name') AS template_name"
    ",(SELECT COUNT(*) FROM files WHERE context_id=contexts.id) AS file_count"
    ",(SELECT COUNT(*) FROM documents WHERE context_id=contexts.id) AS document_count"
    " FROM contexts ORDER BY created_at DESC,id"
)
OLD_INPUTS = (
    "SELECT id AS context_id,created_at,"
    "json_extract(payload,'$.profile.version') AS profile_version,"
    "json_extract(payload,'$.instructions.version') AS instructions_version,"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),json_extract(value,'$.name')))"
    " FROM json_each(contexts.payload,'$.templates')) AS templates,"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),json_extract(value,'$.title')))"
    " FROM json_each(contexts.payload,'$.knowledge')) AS knowledge,"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),substr(json_extract(value,'$.text'),1,120)))"
    " FROM json_each(contexts.payload,'$.claims')) AS claims "
    "FROM contexts ORDER BY id"
)
FILE_COLUMNS = "id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at"
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


def recorded(path):
    """What a schema 8 workspace returns for its contexts, read with the released SQL."""
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        return {
            "payloads": {
                row["id"]: (row["payload"], row["signature"], row["idempotency_key"])
                for row in conn.execute("SELECT * FROM contexts")
            },
            "summary": [dict(row) for row in conn.execute(OLD_SUMMARY)],
            "inputs": [dict(row) for row in conn.execute(OLD_INPUTS)],
            "files": [
                dict(row)
                for row in conn.execute(
                    f"SELECT {FILE_COLUMNS} FROM files WHERE context_id IS NOT NULL ORDER BY id"
                )
            ],
            "file_bytes": {
                row["id"]: bytes(row["content"])
                for row in conn.execute(
                    "SELECT f.id,b.content FROM files f JOIN blobs b ON b.sha256=f.sha256 "
                    "WHERE f.context_id IS NOT NULL"
                )
            },
        }


def assert_reproduced(workspace, before):
    """Every recorded context reads back exactly through the current services."""
    documents = DocumentService(workspace)
    with workspace.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert "payload" not in {row[1] for row in conn.execute("PRAGMA table_info(contexts)")}
        assert not conn.execute("SELECT 1 FROM files WHERE context_id IS NOT NULL").fetchall()
        for context_id, (payload, signature, key) in before["payloads"].items():
            assert payload_text(conn, context_id).encode() == payload.encode()
            record = documents.get_context(context_id)
            # Same value and the same key order as parsing the stored text returned.
            assert json.dumps(record["payload"]) == json.dumps(json.loads(payload))
            assert list(record) == [
                "id",
                "application_id",
                "payload",
                "signature",
                "idempotency_key",
                "created_at",
                "resource_uri",
            ]
            assert (record["signature"], record["idempotency_key"]) == (signature, key)
        assert [
            dict(row)
            for row in conn.execute(
                f"SELECT {FILE_COLUMNS} FROM all_files WHERE context_id IS NOT NULL ORDER BY id"
            )
        ] == before["files"]
        assert [
            dict(row)
            for row in conn.execute(
                "SELECT context_id,created_at,profile_version,instructions_version,"
                "templates,knowledge,claims FROM context_inputs ORDER BY context_id"
            )
        ] == before["inputs"]
        for file_id, content in before["file_bytes"].items():
            row = conn.execute(
                "SELECT b.content FROM all_files f JOIN blobs b ON b.sha256=f.sha256 WHERE f.id=?",
                (file_id,),
            ).fetchone()
            assert bytes(row[0]) == content
    listed = []
    while len(listed) < len(before["summary"]):
        listed += documents.list_contexts(limit=200, offset=len(listed), summary=True)["items"]
    assert listed == before["summary"]
    for row in before["files"]:
        assert documents.get_file(row["id"]) == {
            "id": row["id"],
            "sha256": row["sha256"],
            "name": row["name"],
            "media_type": row["media_type"],
            "size": row["size"],
            "created_at": row["created_at"],
            "owner_type": "context",
            "owner_id": row["context_id"],
            "source_sha256": None,
            "url": f"/api/v1/files/{row['id']}/content",
            "version": 1,
        }


def legacy_workspace(path):
    """A schema 8 file whose contexts were written by the released preparation code."""
    workspace, knowledge, claims, templates, applications = seed(path)
    approved = [
        row["id"] for row in workspace.db.all("SELECT id FROM claims WHERE approved=1 ORDER BY id")
    ]
    career = CareerService(workspace)
    del workspace
    make_schema_eight(path)
    first, second, third = applications
    legacy_prepare_context(path, first, key="first-key")
    legacy_prepare_context(path, first, note="Second pass\nwith “unicode” ✓")
    legacy_prepare_context(path, second, knowledge_ids=knowledge[:2], claim_ids=approved[:1])
    legacy_prepare_context(path, second, knowledge_ids=[], template_ids=templates[:1])
    legacy_prepare_context(path, third, knowledge_ids=knowledge[1:2], claim_ids=[])
    # A later Career edit: only the changed entry may be stored again.
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "UPDATE knowledge SET narrative=?,version=version+1 WHERE id=?",
            ("Edited narrative " + AWKWARD[3] * 400, knowledge[0]),
        )
        conn.commit()
    legacy_prepare_context(path, third)
    return career, knowledge, claims, templates, applications


def test_schema_eight_contexts_read_back_byte_for_byte_after_upgrade(tmp_path):
    path = tmp_path / "legacy.sqlite"
    legacy_workspace(path)
    before = recorded(path)
    assert len(before["payloads"]) == 6 and len(before["files"]) >= 12
    assert any(row["knowledge_count"] == 0 for row in before["summary"])
    for payload, signature, _ in before["payloads"].values():
        assert hashlib.sha256(payload.encode()).hexdigest() == signature

    workspace = Workspace(path)
    assert_reproduced(workspace, before)
    with workspace.db.connect() as conn:
        # Six entries frozen by six contexts are stored once each, plus the edited one.
        entries = conn.execute(
            "SELECT count(*) FROM snapshot_parts WHERE instr(content,'\"narrative\":')"
        ).fetchone()[0]
        assert entries == 6 + 1
        assert conn.execute("SELECT count(*) FROM snapshot_parts WHERE kind='asset'").fetchone()[
            0
        ] == len({(row["name"], row["sha256"]) for row in before["files"]})
    # Opening again changes nothing.
    assert_reproduced(Workspace(path), before)


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


def test_awkward_and_non_canonical_payloads_survive_the_upgrade_exactly(tmp_path):
    path = tmp_path / "awkward.sqlite"
    workspace, _, _, _, applications = seed(path, entries=1, claims=1, applications=1)
    blob = add_asset(
        workspace, "job_id", workspace.db.one("SELECT id FROM jobs")["id"], "x", b"bytes"
    )
    del workspace
    make_schema_eight(path)
    rng = random.Random(143)

    def asset(**changes):
        file_id = new_id()
        entry = {
            "id": file_id,
            "sha256": blob,
            "name": "x",
            "path": "template/t/x",
            "media_type": "image/png",
            "size": 5,
            "owner_type": "template",
            "owner_id": "t",
            "original_file_id": "o",
            "url": f"/api/v1/files/{file_id}/content",
        }
        return {**entry, **changes}

    with closing(sqlite3.connect(path)) as conn:
        for _ in range(60):
            payload = awkward_payload(rng)
            if isinstance(payload.get("files"), list):
                payload["files"] = [asset() for _ in range(rng.randrange(4))]
            files = payload["files"] if isinstance(payload.get("files"), list) else []
            insert_legacy_context(conn, applications[0], legacy_encode(payload), files)
        canonical = awkward_payload(random.Random(1))
        variants = [
            json.dumps,  # default separators, ASCII escapes
            lambda value: json.dumps(value, indent=2, sort_keys=True),
            lambda value: json.dumps(
                value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ),
            lambda value: legacy_encode(value) + "\n",
            lambda value: "[1,2,3]",
            lambda value: '"text"',
            lambda value: "{}",
            lambda value: (
                '{"knowledge":[],"claims":[{}],"templates":[[]],"files":[],"job":{},"profile":null}'
            ),
        ]
        for render in variants:
            files = [asset(), asset()]
            text = render({**canonical, "files": files})
            insert_legacy_context(conn, applications[0], text, files)
        # File entries of an older or inconsistent shape stay in the frame as written.
        odd_files = [
            lambda entry: {**entry, "url": "/elsewhere"},
            lambda entry: {**entry, "size": 6},
            lambda entry: {**entry, "size": 5.0},
            lambda entry: {**entry, "path": "template/t/other"},
            lambda entry: {**entry, "zz": 1},
            lambda entry: {key: value for key, value in entry.items() if key != "url"},
        ]
        for change in odd_files:
            rows = [asset(), asset()]
            payload = {**awkward_payload(rng), "files": [dict(rows[0]), change(dict(rows[1]))]}
            insert_legacy_context(conn, applications[0], legacy_encode(payload), rows)
        # A file row older than its context, and one the payload never mentions.
        rows = [asset(created_at="2020-01-01T00:00:00+00:00"), asset()]
        mentioned = {key: value for key, value in rows[0].items() if key != "created_at"}
        insert_legacy_context(
            conn, applications[0], legacy_encode({**canonical, "files": [mentioned]}), rows
        )
        # A stored signature is returned as stored, even if it never matched.
        insert_legacy_context(conn, applications[0], legacy_encode(canonical), signature="unsigned")
        conn.commit()
    before = recorded(path)
    assert len(before["payloads"]) == 60 + len(variants) + len(odd_files) + 2
    assert sum(row["created_at"].startswith("2020") for row in before["files"]) == 1
    workspace = Workspace(path)
    assert_reproduced(workspace, before)
    with workspace.db.connect() as conn:
        # Both storage forms were exercised: shared parts, and payloads kept whole with
        # their files listed beside them.
        assert conn.execute("SELECT count(*) FROM snapshot_parts WHERE kind='list'").fetchone()[0]
        whole = conn.execute(
            "SELECT count(*) FROM contexts c WHERE json_array_length(frame)=1 AND length(frame)>99"
        ).fetchone()[0]
        assert whole >= 4
        beside = conn.execute("SELECT count(*) FROM context_parts WHERE position<0").fetchone()[0]
        assert beside >= 20
        rendered = conn.execute(
            "SELECT count(*) FROM context_parts WHERE position>=0 AND file_id IS NOT NULL"
        ).fetchone()[0]
        assert rendered >= 20


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


def test_context_files_keep_their_ids_through_rest_and_stay_immutable(tmp_path):
    path = tmp_path / "files.sqlite"
    legacy_workspace(path)
    before = recorded(path)
    client = context_files_app(path)
    with client:
        row = before["files"][0]
        assert client.get(f"/api/v1/files/{row['id']}").json()["owner_id"] == row["context_id"]
        content = client.get(f"/api/v1/files/{row['id']}/content")
        assert content.content == before["file_bytes"][row["id"]]
        grant = client.post(f"/api/v1/files/{row['id']}/download").json()
        assert client.get(grant["url"], headers=grant["headers"]).content == content.content
        assert client.delete(f"/api/v1/files/{row['id']}?expected_version=1").status_code == 409
        refused = client.post(
            "/api/v1/files/uploads",
            json={"owner_type": "context", "owner_id": row["context_id"], "name": "x", "size": 1},
        )
        assert refused.status_code == 422
        listed = client.get("/api/v1/files", params={"owner_type": "context", "limit": 200}).json()
        assert listed["total"] == len(before["files"])
        named = client.get("/api/v1/files", params={"q": "Ünï", "owner_type": "context"}).json()
        assert named["total"] and all("Ünï" in item["name"] for item in named["items"])
        archive = client.get("/api/v1/export").json()
        assert {item["id"]: item["payload"] for item in archive["contexts"]} == {
            key: json.loads(value[0]) for key, value in before["payloads"].items()
        }
        assert list(archive["contexts"][0]) == [
            "id",
            "application_id",
            "payload",
            "signature",
            "idempotency_key",
            "created_at",
        ]
        exported = [item for item in archive["files"] if item["context_id"]]
        # Only a revision's PDF names a source.
        assert all(item.pop("source_sha256") is None for item in exported)
        assert sorted(exported, key=lambda item: item["id"]) == before["files"]


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


def test_backup_restore_and_older_backups_reproduce_every_context(tmp_path):
    old = tmp_path / "schema8-backup.sqlite"
    legacy_workspace(old)
    before = recorded(old)
    original = old.read_bytes()

    # Restoring a schema 8 backup upgrades a copy and leaves the upload unchanged.
    target = Workspace(tmp_path / "data" / "live.sqlite")
    restore_database(target, old)
    assert old.read_bytes() == original
    assert_reproduced(target, before)

    # A schema 9 backup restores into another workspace with the same contexts.
    backup = tmp_path / "schema9-backup.sqlite"
    target.db.backup(backup)
    other = Workspace(tmp_path / "other" / "live.sqlite")
    restore_database(other, backup)
    assert_reproduced(other, before)
    DocumentService(other).prepare_context(
        ContextCreate(application_id=other.db.one("SELECT id FROM applications")["id"])
    )


@pytest.mark.parametrize("version", [7, 6, 5])
def test_older_schemas_chain_through_the_context_upgrade(tmp_path, version):
    path = tmp_path / "chain.sqlite"
    legacy_workspace(path)
    before = recorded(path)
    with closing(sqlite3.connect(path)) as conn:
        # make_schema_seven starts from a current file.
        conn.execute("PRAGMA journal_mode=DELETE")
    Workspace(path)
    make_schema_seven(path)
    with closing(sqlite3.connect(path)) as conn:
        if version <= 6:
            conn.execute("DROP INDEX applications_deadline")
            for column in ("requirements", "deadline", "priority"):
                conn.execute(f"ALTER TABLE applications DROP COLUMN {column}")
        if version == 5:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN initial_score_pending INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(f"PRAGMA user_version={version}")
        conn.commit()
        payloads = dict(conn.execute("SELECT id,payload FROM contexts"))
    assert payloads == {key: value[0] for key, value in before["payloads"].items()}
    workspace = Workspace(path)
    with workspace.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        for context_id, (payload, _, _) in before["payloads"].items():
            assert payload_text(conn, context_id) == payload
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_a_failed_upgrade_leaves_the_schema_eight_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite"
    legacy_workspace(path)
    before = recorded(path)

    def broken(conn, context_id, frame=None):
        return "different"

    monkeypatch.setattr("openings.snapshots.payload_text", broken)
    with pytest.raises(sqlite3.IntegrityError, match="not reproduced"):
        Workspace(path)
    monkeypatch.undo()
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 8
        assert not conn.execute(
            "SELECT name FROM sqlite_master WHERE name='snapshot_parts'"
        ).fetchall()
    assert recorded(path) == before
    assert_reproduced(Workspace(path), before)


def vacuumed_size(path, tmp_path, *, contexts=True, inputs=True):
    """Bytes of a compact copy, optionally without contexts or their derived input summaries."""
    copy = tmp_path / "measure.sqlite"
    shutil.copyfile(path, copy)
    with closing(sqlite3.connect(copy)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        if not inputs:
            conn.execute("DELETE FROM context_inputs")
        if not contexts:
            conn.execute("DELETE FROM files WHERE context_id IS NOT NULL")
            conn.execute("DELETE FROM contexts")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='snapshot_parts'").fetchone():
                conn.execute("DELETE FROM snapshot_list_items")
                conn.execute("DELETE FROM snapshot_parts")
        conn.commit()
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("VACUUM")
    size = copy.stat().st_size
    copy.unlink()
    return size


def context_storage(path, tmp_path):
    """(frozen snapshots and their files, the same plus derived input summaries), in bytes."""
    empty = vacuumed_size(path, tmp_path, contexts=False)
    return (
        vacuumed_size(path, tmp_path, inputs=False) - empty,
        vacuumed_size(path, tmp_path) - empty,
    )


def test_five_hundred_contexts_sharing_one_career_record_shrink_by_seventy_percent(tmp_path):
    """Issue #143 acceptance: the full 500 contexts over a Career record of reduced size.

    The record here is about 120 KB per context instead of the 313 KB measured on a real
    workspace, which keeps the test fast; a larger shared record only improves the ratio.
    """
    path = tmp_path / "benchmark.sqlite"
    workspace, _, _, _, applications = seed(
        path, entries=12, claims=5, applications=500, narrative=250
    )
    del workspace
    make_schema_eight(path)
    for application in applications:
        legacy_prepare_context(path, application)
    with closing(sqlite3.connect(path)) as conn:
        # A released workspace also holds the derived input summary of each context.
        conn.execute("INSERT INTO context_inputs " + OLD_INPUTS)
        conn.commit()
    before = recorded(path)
    assert len(before["payloads"]) == 500
    old, old_with_inputs = context_storage(path, tmp_path)
    assert old > 500 * 100_000  # the fixture is not trivially small

    workspace = Workspace(path)
    with workspace.db.connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for context_id, (payload, _, _) in before["payloads"].items():
            assert payload_text(conn, context_id) == payload
        assert conn.execute(
            "SELECT count(*) FROM all_files WHERE context_id IS NOT NULL"
        ).fetchone()[0] == len(before["files"])
    new, new_with_inputs = context_storage(path, tmp_path)
    print(
        f"context storage: {old} -> {new} bytes; with input summaries: "
        f"{old_with_inputs} -> {new_with_inputs} bytes"
    )
    assert new <= 0.30 * old, (old, new)
    assert new_with_inputs <= 0.30 * old_with_inputs, (old_with_inputs, new_with_inputs)


def test_the_schema_eight_fixture_is_the_schema_the_released_upgrade_produces(tmp_path):
    """Schema 8 as 0.17.0 shipped it: the fixture equals a schema 7 file after the 7 to 8 step."""
    fixture, upgraded = tmp_path / "fixture.sqlite", tmp_path / "upgraded.sqlite"
    for path in (fixture, upgraded):
        seed(path, entries=1, applications=1)
    make_schema_eight(fixture)
    make_schema_seven(upgraded)
    with closing(sqlite3.connect(upgraded)) as conn:
        MIGRATIONS[7](conn)
        conn.execute("PRAGMA user_version=8")
        conn.commit()
    with closing(sqlite3.connect(fixture)) as left, closing(sqlite3.connect(upgraded)) as right:
        assert left.execute("PRAGMA user_version").fetchone()[0] == 8
        tables = table_names(left)
        assert tables == table_names(right)
        assert {"requests", "runs", "questions"} <= tables
        assert not tables & {"snapshot_parts", "snapshot_list_items", "context_parts"}
        assert not left.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()
        # Indexes the schema file adds on any start are not part of the upgrade step.
        assert index_names(right) <= index_names(left)
        for table in tables:
            if not table.startswith("jobs_fts"):
                assert sorted(columns(left, table)) == sorted(columns(right, table)), table
        assert [row[0] for row in columns(left, "contexts")] == [
            "id",
            "application_id",
            "payload",
            "signature",
            "idempotency_key",
            "created_at",
        ]
        assert "ready_at" in {row[0] for row in columns(left, "applications")}
        assert "kind" in {row[0] for row in columns(left, "api_tokens")}
        assert "actor_token_kind" in {row[0] for row in columns(left, "events")}


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


def test_a_backup_without_installation_credentials_restores_every_context(tmp_path):
    path = tmp_path / "source.sqlite"
    legacy_workspace(path)
    before = recorded(path)
    source = Workspace(path)
    backup = tmp_path / "agent-backup.sqlite"
    source.db.backup(backup)
    remove_installation_credentials(backup)
    with closing(sqlite3.connect(backup)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("SELECT 1 FROM api_tokens").fetchall()
    target = Workspace(tmp_path / "target" / "live.sqlite")
    restore_database(target, backup)
    assert_reproduced(target, before)
