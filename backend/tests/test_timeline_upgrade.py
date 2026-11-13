"""The 12 -> 13 timeline upgrade: each application note becomes a pinned note, byte for byte."""

import sqlite3
from contextlib import closing

import pytest

from context_fixtures import make_schema_eight
from openings.activity import ActivityService
from openings.actors import OWNER, UNKNOWN_LABEL, acting_as, token_actor
from openings.db import SCHEMA_VERSION, Database
from openings.operations import restore_database
from openings.workspace import Workspace
from outcome_fixtures import make_schema_ten
from policy_fixtures import make_schema_nine
from schema_fixtures import columns, index_names, make_schema_seven, table_names
from signal_fixtures import make_schema_eleven
from timeline_fixtures import guided_application, make_schema_twelve, older_rows

AGENT = token_actor("agent-token", "Synthetic agent", "agent")
# Awkward but valid texts: they must come back exactly.
TEXTS = {
    "owner": "Lead with the platform work.",
    "agent": "Ünïcode ✓ “quotes” — 日本語 🙂\r\nCRLF line\n\ttab  trailing  \n\n",
    "created": " leading space and a long tail " + "x" * 29_000,
    "unknown": "Set before attribution.",
}


def schema_twelve_workspace(path):
    """Applications whose note was last set by the owner, an agent in a run, at creation, before 0.17."""
    workspace = Workspace(path)
    ids = {}
    for name in (*TEXTS, "empty"):
        job = workspace.ingest_job(
            {"title": f"Synthetic {name}", "company": "Example", "posting": "Build APIs."}
        )
        ids[name] = workspace.create_application({"job_id": job["id"]})["id"]
    with acting_as(OWNER):
        application = workspace.get_application(ids["owner"])
        workspace.update_application(
            ids["owner"], {"expected_version": application["version"], "priority": 2}
        )
    with acting_as(AGENT):
        run = ActivityService(workspace).start_run({"workflow": "prepare-shortlist"})
    note = workspace.add_note(
        workspace.get_application(ids["owner"])["job_id"],
        {"body": "A job note stays a job note."},
    )
    with workspace.db.transaction() as conn:
        # As schema 12 recorded writes of the note field: an update naming it, or the creation.
        def updated(application_id, actor, run_id, stamp):
            conn.execute(
                "INSERT INTO events(id,job_id,application_id,kind,payload,created_at,subject_type,"
                "subject_id,actor_kind,actor_id,actor_name,actor_token_kind,run_id) "
                "SELECT ?,job_id,id,'application_updated',?,?,'application',id,?,?,?,?,? "
                "FROM applications WHERE id=?",
                (
                    "e-" + application_id,
                    '{"fields":["note"],"from":"draft","to":"draft"}',
                    stamp,
                    *actor,
                    run_id,
                    application_id,
                ),
            )

        updated(ids["owner"], ("owner", None, None, None), None, "2026-10-02T09:00:00.000000+00:00")
        updated(ids["agent"], AGENT.columns(), run["id"], "2026-10-03T09:00:00.000000+00:00")
        updated(ids["unknown"], (None, None, None, None), None, "2026-01-05T09:00:00.000000+00:00")
        conn.execute(
            "UPDATE events SET created_at='2026-09-01T08:00:00.000000+00:00' "
            "WHERE application_id=? AND kind='application_created'",
            (ids["created"],),
        )
    make_schema_twelve(path)
    with closing(sqlite3.connect(path)) as conn:
        for name, text in TEXTS.items():
            conn.execute("UPDATE applications SET note=? WHERE id=?", (text, ids[name]))
        conn.commit()
    return ids, run["id"], note["id"]


def pinned_notes(conn):
    return {
        row[0]: row[1:]
        for row in conn.execute(
            "SELECT application_id,CAST(body AS BLOB),author_kind,author_name,author_token_kind,"
            "run_id,created_at,updated_at,pinned_at,version,origin FROM notes "
            "WHERE pinned_at IS NOT NULL"
        )
    }


def test_upgrade_copies_each_application_note_exactly_and_changes_nothing_else(tmp_path):
    path = tmp_path / "twelve.sqlite"
    ids, run_id, job_note = schema_twelve_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 12
        tables = sorted(table_names(conn) - {"applications"})
        before = {
            table: older_rows(conn, table) for table in tables if not table.startswith("jobs_fts")
        }
        applications = older_rows(conn, "applications")
        texts = dict(conn.execute("SELECT id,CAST(note AS BLOB) FROM applications"))
        updated = dict(conn.execute("SELECT id,updated_at FROM applications"))
    workspace = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with closing(sqlite3.connect(path)) as conn, closing(sqlite3.connect(fresh.path)) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 14
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert table_names(conn) == table_names(reference)
        assert index_names(conn) == index_names(reference)
        for table in ("applications", "notes"):
            assert columns(conn, table) == columns(reference, table), table
        for table, rows in before.items():
            assert older_rows(conn, table) == rows, table
        assert older_rows(conn, "applications") == applications
        pinned = pinned_notes(conn)
        # One pinned note per non-empty note, and nothing for the empty one.
        assert set(pinned) == {ids[name] for name in TEXTS}
        for name, text in TEXTS.items():
            assert pinned[ids[name]][0] == text.encode() == texts[ids[name]]
        assert conn.execute("SELECT count(*) FROM notes WHERE origin='upgrade'").fetchone()[0] == 4
        # The upgrade writes no event (the events rows are compared above): the only
        # note event is the job note's.
        assert conn.execute("SELECT count(*) FROM events WHERE subject_type='note'").fetchone() == (
            1,
        )
    owner, agent, created, unknown = (pinned[ids[name]][1:] for name in TEXTS)
    assert owner == (
        "owner",
        None,
        None,
        None,
        *("2026-10-02T09:00:00.000000+00:00",) * 3,
        1,
        "upgrade",
    )
    assert agent[:4] == ("token", "Synthetic agent", "agent", run_id)
    assert agent[4] == "2026-10-03T09:00:00.000000+00:00"
    # Never changed after creation: the creation's actor (the system) and time.
    assert created[:5] == ("system", None, None, None, "2026-09-01T08:00:00.000000+00:00")
    assert unknown[:5] == (None, None, None, None, "2026-01-05T09:00:00.000000+00:00")
    # Reads: the pinned note and the timeline.
    for name, text in TEXTS.items():
        application = workspace.get_application(ids[name])
        assert application["pinned_note"]["body"] == text and "note" not in application
        assert application["pinned_note"]["origin"] == "upgrade"
        first = workspace.timeline(application_id=ids[name])["items"][0]
        assert first["note"]["pinned"] and first["note"]["body"] == text
    assert workspace.get_application(ids["unknown"])["pinned_note"]["author"]["label"] == (
        UNKNOWN_LABEL
    )
    assert workspace.get_application(ids["empty"])["pinned_note"] is None
    assert not workspace.get_note(job_note)["pinned"]
    assert updated[ids["empty"]] == workspace.get_application(ids["empty"])["updated_at"]


def test_a_failed_upgrade_leaves_the_schema_twelve_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite"
    schema_twelve_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        original = {table: older_rows(conn, table) for table in ("applications", "notes", "events")}
    monkeypatch.setattr("openings.workspace.timeline_upgrade.INDEXES", "SELECT no_such_function();")
    with pytest.raises(sqlite3.OperationalError):
        Workspace(path)
    monkeypatch.undo()
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 12
        assert "pinned_at" not in {row[0] for row in columns(conn, "notes")}
        assert "note" in {row[0] for row in columns(conn, "applications")}
        assert {table: older_rows(conn, table) for table in original} == original
        assert conn.execute("SELECT count(*) FROM applications WHERE note<>''").fetchone() == (4,)
    assert Workspace(path).list_applications()["total"] == 5


def downgrade(path, version):
    """Turn a current workspace file into the released layout of an older schema."""
    if version == 12:
        make_schema_twelve(path)
        return
    {11: make_schema_eleven, 10: make_schema_ten, 9: make_schema_nine, 8: make_schema_eight}.get(
        version, make_schema_seven
    )(path)
    if version <= 6:
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("DROP INDEX applications_deadline")
            for column in ("requirements", "deadline", "priority"):
                conn.execute(f"ALTER TABLE applications DROP COLUMN {column}")
            if version == 5:
                conn.execute(
                    "ALTER TABLE jobs ADD COLUMN initial_score_pending INTEGER NOT NULL DEFAULT 0"
                )
            conn.execute(f"PRAGMA user_version={version}")
            conn.commit()


@pytest.mark.parametrize("version", [12, 11, 10, 9, 8, 7, 6, 5])
def test_every_supported_schema_upgrades_and_restores_with_the_notes_pinned(tmp_path, version):
    path = tmp_path / f"schema{version}.sqlite"
    workspace = Workspace(path)
    ids = {}
    for name, text in TEXTS.items():
        job = workspace.ingest_job({"title": name, "company": "Example", "posting": "Build."})
        ids[name] = guided_application(workspace, job["id"], text)["id"]
    downgrade(path, version)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == version
        texts = dict(conn.execute("SELECT id,CAST(note AS BLOB) FROM applications"))
    original = path.read_bytes()
    # A restore upgrades a copy and leaves the backup as it was.
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, path)
    assert path.read_bytes() == original
    for opened in (Workspace(path), target):
        with opened.db.connect() as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
            assert {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT application_id,CAST(body AS BLOB) FROM notes WHERE pinned_at IS NOT NULL"
                )
            } == texts
        for name, text in TEXTS.items():
            assert opened.get_application(ids[name])["pinned_note"]["body"] == text
