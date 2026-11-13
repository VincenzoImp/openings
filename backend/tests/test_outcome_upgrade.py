"""The 10 -> 11 upgrade: the applications table built again, row for row, and the response backfill."""

import json
import sqlite3
from contextlib import closing

import pytest

from openings.activity import ActivityService
from openings.actors import OWNER, acting_as
from openings.agent_requests import RequestService
from openings.career import CareerService, TemplateCreate
from openings.db import APPLICATIONS, SCHEMA_VERSION, Database
from openings.documents import ContextCreate, DocumentCreate, DocumentService
from openings.operations import restore_database
from openings.workspace import Workspace
from outcome_fixtures import make_schema_ten
from schema_fixtures import columns, index_names, table_names

CHILDREN = ("events", "notes", "documents", "contexts", "questions", "requests")


def make(workspace, title, *moves):
    job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})
    application = workspace.create_application(
        {"job_id": job["id"], "note": f"Guidance for {title}", "priority": 2}
    )
    for move in moves:
        current = workspace.get_application(application["id"])
        application = workspace.update_application(
            application["id"], {"expected_version": current["version"], **move}
        )
    return application


def at(conn, application_id, to, stamp, source=None):
    """Date the stage-change events that moved an application to ``to``."""
    conn.execute(
        "UPDATE events SET created_at=? WHERE application_id=? AND kind='application_updated' "
        "AND json_extract(payload,'$.to')=? AND (? IS NULL OR json_extract(payload,'$.from')=?)",
        (stamp, application_id, to, source, source),
    )


def schema_ten_workspace(path):
    workspace = Workspace(path)
    documents = DocumentService(workspace)
    activity = ActivityService(workspace)
    ids = {
        "draft": make(workspace, "Draft"),
        "applied": make(workspace, "Applied", {"status": "applied"}),
        "interview": make(workspace, "Interview", {"status": "applied"}, {"status": "interview"}),
        "offer": make(workspace, "Offer", {"status": "applied"}),
        "rejected": make(
            workspace,
            "Rejected",
            {"status": "applied"},
            {"status": "closed", "outcome": "rejected"},
        ),
        "rejected_unsent": make(
            workspace, "Rejected unsent", {"status": "closed", "outcome": "rejected"}
        ),
        "not_pursued": make(
            workspace, "Not pursued", {"status": "closed", "outcome": "not_pursued"}
        ),
        "accepted": make(
            workspace,
            "Accepted",
            {"status": "applied"},
            {"status": "closed", "outcome": "accepted"},
        ),
    }
    ids = {key: value["id"] for key, value in ids.items()}
    # Records that reference applications, which the rebuild must keep.
    CareerService(workspace).create_template(
        TemplateCreate(name="Synthetic CV", tex="Synthetic TeX", is_default=True)
    )
    context = documents.prepare_context(ContextCreate(application_id=ids["interview"]))
    documents.create_document(
        DocumentCreate(application_id=ids["interview"], context_id=context["id"], kind="resume")
    )
    job_id = workspace.get_application(ids["rejected"])["job_id"]
    workspace.add_note(job_id, {"body": "Synthetic note", "application_id": ids["rejected"]})
    activity.ask_question(
        {"question": "Synthetic?", "subject_type": "application", "subject_id": ids["offer"]}
    )
    with acting_as(OWNER):
        RequestService(workspace).create_request(
            {
                "text": "Synthetic request",
                "subject_type": "application",
                "subject_id": ids["applied"],
            }
        )
    with workspace.db.transaction() as conn:
        at(conn, ids["interview"], "interview", "2026-09-01T10:00:00.000000+00:00")
        # A later edit inside Interview does not move it there.
        conn.execute(
            "INSERT INTO events(id,job_id,application_id,kind,payload,created_at) "
            "SELECT 'later',job_id,id,'application_updated',?,? FROM applications WHERE id=?",
            (
                json.dumps({"from": "interview", "to": "interview", "fields": ["note"]}),
                "2026-10-01T10:00:00.000000+00:00",
                ids["interview"],
            ),
        )
        at(conn, ids["rejected"], "closed", "2026-09-05T23:30:00.000000+00:00", "applied")
        # An Offer reached without a recorded stage change: its day is estimated.
        conn.execute(
            "UPDATE applications SET status='offer',updated_at='2026-09-20T08:00:00.000000+00:00' "
            "WHERE id=?",
            (ids["offer"],),
        )
    make_schema_ten(path)
    return ids


def snapshot(conn):
    """Every row a schema 10 file holds that the upgrade must keep, with its rowid."""
    names = ",".join(f'"{row[0]}"' for row in columns(conn, "applications"))
    return {
        "applications": conn.execute(
            f"SELECT rowid,{names} FROM applications ORDER BY rowid"
        ).fetchall(),
        **{
            table: conn.execute(f"SELECT rowid,* FROM {table} ORDER BY rowid").fetchall()
            for table in CHILDREN
        },
        "indexes": sorted(
            conn.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='applications'"
            ).fetchall()
        ),
        "references": {
            table: conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            for table in (*CHILDREN, "applications")
        },
    }


def test_upgrade_keeps_every_row_and_backfills_exactly(tmp_path):
    path = tmp_path / "schema10.sqlite"
    ids = schema_ten_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 10
        assert "responses" not in table_names(conn)
        assert "concluded_on" not in {row[0] for row in columns(conn, "applications")}
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='applications'").fetchone()[0]
        assert "'not_pursued')" in sql and "no_response" not in sql
        before = snapshot(conn)
        updated = dict(conn.execute("SELECT id,updated_at FROM applications"))
    assert len(before["applications"]) == 8
    assert all(before[table] for table in CHILDREN)

    workspace = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with closing(sqlite3.connect(path)) as conn, closing(sqlite3.connect(fresh.path)) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 12
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert table_names(conn) == table_names(reference)
        assert index_names(conn) == index_names(reference)
        assert columns(conn, "applications") == columns(reference, "applications")
        assert columns(conn, "responses") == columns(reference, "responses")
        after = snapshot(conn)
        # Every application row keeps its rowid and every value; concluded_on is new and empty.
        for old, new in zip(before["applications"], after["applications"], strict=True):
            assert tuple(new)[: len(old)] == tuple(old)
            assert new[-1] is None
        for table in CHILDREN:
            assert after[table] == before[table], table
        assert after["indexes"] == before["indexes"]
        assert after["references"] == before["references"]
        # The table holds the new definition and accepts the new outcome.
        assert conn.execute("SELECT sql FROM sqlite_master WHERE name='applications'").fetchone()[
            0
        ] == APPLICATIONS.format(name='"applications"')
        backfilled = conn.execute(
            "SELECT application_id,kind,date,estimated,origin,note,created_by_kind,version "
            "FROM responses ORDER BY kind"
        ).fetchall()
    assert sorted(backfilled) == sorted(
        [
            (ids["interview"], "interview", "2026-09-01", 0, "upgrade", "", "system", 1),
            (ids["offer"], "offer", updated[ids["offer"]][:10], 1, "upgrade", "", "system", 1),
            (ids["rejected"], "rejection", "2026-09-05", 0, "upgrade", "", "system", 1),
        ]
    )
    assert updated[ids["offer"]][:10] == "2026-09-20"
    # The upgrade writes no event.
    assert not workspace.db.all("SELECT 1 FROM events WHERE subject_type='response'")
    # The new outcome works straight away.
    applied = workspace.get_application(ids["applied"])
    closed = workspace.update_application(
        ids["applied"],
        {"expected_version": applied["version"], "status": "closed", "outcome": "no_response"},
    )
    assert closed["outcome"] == "no_response" and closed["concluded_on"]


def test_a_failed_upgrade_leaves_the_schema_ten_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite"
    schema_ten_workspace(path)

    def broken(conn):
        raise sqlite3.IntegrityError("Synthetic failure after the rebuild.")

    monkeypatch.setattr("openings.outcomes.backfill_responses", broken)
    with pytest.raises(sqlite3.IntegrityError, match="Synthetic failure"):
        Workspace(path)
    monkeypatch.undo()
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 10
        assert "responses" not in table_names(conn)
        assert "applications_rebuilt" not in table_names(conn)
        assert conn.execute("SELECT count(*) FROM documents").fetchone()[0] == 1
    assert Workspace(path).list_applications()["total"] == 8


def test_restore_upgrades_a_schema_ten_backup(tmp_path):
    source = tmp_path / "backup.sqlite"
    ids = schema_ten_workspace(source)
    original = source.read_bytes()
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, source)
    assert source.read_bytes() == original
    restored = target.get_application(ids["interview"])
    assert [item["kind"] for item in restored["responses"]] == ["interview"]
    assert target.list_applications()["total"] == 8
    with target.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
