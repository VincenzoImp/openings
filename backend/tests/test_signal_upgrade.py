"""The 11 -> 12 upgrade: dismissal records and listing observations filled, nothing else changed."""

import json
import sqlite3
from contextlib import closing

import pytest

from openings.actors import OWNER, acting_as, token_actor
from openings.common import new_id
from openings.db import SCHEMA_VERSION, Database
from openings.job_signals import signal_record
from openings.language_signals import text_signals
from openings.operations import restore_database
from openings.source_yield import YieldService
from openings.workspace import Workspace
from schema_fixtures import columns, index_names, table_names
from signal_fixtures import SCHEMA_TWELVE_COLUMNS, make_schema_eleven

AGENT = token_actor("agent-token", "Synthetic agent", "agent")
POSTING = (
    "Wir suchen eine Person für unser Team in Bern. Du entwickelst neue Funktionen in Python. "
    "Dein Profil: fließend Deutsch und gute Englischkenntnisse."
)
STARTED = "2026-10-01T08:00:00.000000+00:00"
FINISHED = "2026-10-01T08:05:00.000000+00:00"


def board_run(conn, source_id, snapshot, *, capped=False):
    """One succeeded collection task of a company board that started at STARTED."""
    run_id = new_id()
    conn.execute(
        "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,"
        "created_at) VALUES(?,?,?,?,?,?)",
        (run_id, source_id, snapshot["name"], 1, json.dumps(snapshot), STARTED),
    )
    result = {"started_at": STARTED, "received": 1, **({"result_capped": True} if capped else {})}
    conn.execute(
        "INSERT INTO tasks(id,kind,source_id,run_id,state,payload,result,next_run_at,created_at,"
        "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            new_id(),
            "collect",
            source_id,
            run_id,
            "succeeded",
            "{}",
            json.dumps(result),
            STARTED,
            STARTED,
            FINISHED,
        ),
    )


def schema_eleven_workspace(path):
    workspace = Workspace(path)
    ids = {}
    for name, board in (
        ("seen", "example"),
        ("missed", "example"),
        ("filtered", "example"),
        ("capped", "capped"),
        ("owner", None),
        ("agent", None),
        ("restored", None),
        ("inbox", None),
        ("silent", None),
    ):
        url = (
            f"https://boards.greenhouse.io/{board}/jobs/{name}"
            if board
            else f"https://example.test/jobs/{name}"
        )
        job = workspace.ingest_job(
            {
                "title": "Platform Engineer" if name != "filtered" else "Office Manager",
                "company": "Example",
                "url": url,
                "posting": POSTING,
                **({"source_key": f"greenhouse:{board}:{name}"} if board else {}),
            }
        )
        ids[name] = job["id"]
    with acting_as(OWNER):
        workspace.set_triage(ids["owner"], "dismissed", 1)
    with acting_as(AGENT):
        workspace.set_triage(ids["agent"], "dismissed", 1)
        workspace.set_triage(ids["restored"], "dismissed", 1)
    workspace.set_triage(ids["restored"], "inbox", 2)
    with workspace.db.transaction() as conn:
        # Dismissed without a change record, as before 0.17.
        conn.execute("UPDATE jobs SET triage='dismissed' WHERE id=?", (ids["silent"],))
    with workspace.db.transaction() as conn:
        for key, board, filters in (
            ("board", "example", {"titles": ["Engineer"]}),
            ("capped", "capped", {}),
        ):
            source_id = new_id()
            snapshot = {
                "id": source_id,
                "name": f"Board {board}",
                "kind": "greenhouse",
                "config": {"board": board, "filters": filters},
            }
            conn.execute(
                "INSERT INTO sources(id,name,kind,config,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (
                    source_id,
                    snapshot["name"],
                    "greenhouse",
                    json.dumps(snapshot["config"]),
                    STARTED,
                    STARTED,
                ),
            )
            board_run(conn, source_id, snapshot, capped=key == "capped")
        # "seen" was seen again by the run; the others were last seen before it.
        conn.execute("UPDATE postings SET last_seen_at='2026-09-30T10:00:00.000000+00:00'")
        conn.execute(
            "UPDATE postings SET last_seen_at='2026-10-01T08:01:00.000000+00:00' WHERE job_id=?",
            (ids["seen"],),
        )
    make_schema_eleven(path)
    return ids


def rows(conn, table):
    # Schema 14 dropped jobs.availability (kept in a note when it held a value).
    added = (*SCHEMA_TWELVE_COLUMNS.get(table, ()), *(("availability",) if table == "jobs" else ()))
    names = [f'"{row[0]}"' for row in columns(conn, table) if row[0] not in added]
    without_rowid = "WITHOUT ROWID" in (
        conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0] or ""
    )
    key = "" if without_rowid else "rowid,"
    return conn.execute(f"SELECT {key}{','.join(names)} FROM {table} ORDER BY 1,2").fetchall()


def test_upgrade_keeps_every_row_and_fills_only_the_new_columns(tmp_path):
    path = tmp_path / "eleven.sqlite"
    ids = schema_eleven_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 11
        assert "job_signals" not in table_names(conn)
        tables = sorted(table_names(conn) - {"jobs_fts"})
        before = {table: rows(conn, table) for table in tables if not table.startswith("jobs_fts")}
    workspace = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with closing(sqlite3.connect(path)) as conn, closing(sqlite3.connect(fresh.path)) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 14
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert table_names(conn) == table_names(reference)
        assert index_names(conn) == index_names(reference)
        for table in ("jobs", "postings", "job_signals"):
            assert sorted(columns(conn, table)) == sorted(columns(reference, table)), table
        for table, kept in before.items():
            assert rows(conn, table) == kept, table
        # Signals are computed after the upgrade, not in it.
        assert conn.execute("SELECT count(*) FROM job_signals").fetchone()[0] == 0
        dismissals = {
            row[0]: row[1:]
            for row in conn.execute(
                "SELECT id,dismissed_by_kind,dismissed_by_token_kind,dismissed_by_name,"
                "dismissed_at IS NOT NULL,dismissed_rule_id,dismissed_reason FROM jobs"
            )
        }
        unlisted = {
            row[0]: row[1] for row in conn.execute("SELECT job_id,unlisted_at FROM postings")
        }
    assert dismissals[ids["owner"]] == ("owner", None, None, 1, None, "")
    assert dismissals[ids["agent"]] == ("token", "agent", "Synthetic agent", 1, None, "")
    assert dismissals[ids["restored"]] == (None, None, None, 0, None, "")
    assert dismissals[ids["inbox"]] == (None, None, None, 0, None, "")
    assert dismissals[ids["silent"]] == (None, None, None, 0, None, "")
    # Only the board posting the last complete run missed is no longer listed: not the
    # one it saw, not one its filters exclude, not one of a capped run, not a URL job.
    assert {job_id for job_id, stamp in unlisted.items() if stamp} == {ids["missed"]}
    assert unlisted[ids["missed"]] == FINISHED
    listed = workspace.get_job(ids["missed"])
    assert listed["signals"]["no_longer_listed"] and not listed["signals"]["computed"]
    assert workspace.get_job(ids["owner"])["dismissal"]["category"] == "owner"
    assert workspace.get_job(ids["silent"])["dismissal"]["category"] == "other"
    by = {"rule": 0, "agent": 1, "owner": 1, "other": 1}
    assert (
        workspace.list_jobs(queue="dismissed", include_counts=True)["counts"]["dismissed_by"] == by
    )
    assert [item["id"] for item in workspace.list_jobs(dismissed_by="other")["items"]] == [
        ids["silent"]
    ]
    assert YieldService(workspace).source_yield()["total"]["dismissed_by"] == by
    # The backfill computes every job's signals and applies no rule.
    assert workspace.signals.backfill() == {"text": 9, "duplicates": 9}
    assert workspace.signals.backfill() == {"text": 0, "duplicates": 0}
    signals = workspace.get_job(ids["inbox"])["signals"]
    expected = text_signals("Platform Engineer", POSTING)
    assert {key: signals[key] for key in expected} == expected
    assert signals["computed"] and signals["duplicate_checked"]
    # A short posting under one title and company is no evidence of one vacancy.
    read = [workspace.get_job(job_id)["signals"] for job_id in ids.values()]
    assert all(item["duplicate_checked"] and item["duplicate"] is None for item in read)
    assert [item["triage"] for item in workspace.list_jobs(sort="oldest")["items"]].count(
        "dismissed"
    ) == 3


def test_a_failed_upgrade_leaves_the_schema_eleven_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite"
    schema_eleven_workspace(path)

    def broken(conn):
        raise sqlite3.IntegrityError("Synthetic failure after the new columns.")

    monkeypatch.setattr("openings.job_signals.backfill_unlisted", broken)
    with pytest.raises(sqlite3.IntegrityError, match="Synthetic failure"):
        Workspace(path)
    monkeypatch.undo()
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 11
        assert "job_signals" not in table_names(conn)
        assert "dismissed_at" not in {row[0] for row in columns(conn, "jobs")}
    assert Workspace(path).list_jobs()["total"] == 9


def test_restore_upgrades_a_schema_eleven_backup(tmp_path):
    source = tmp_path / "backup.sqlite"
    ids = schema_eleven_workspace(source)
    original = source.read_bytes()
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, source)
    assert source.read_bytes() == original
    assert target.get_job(ids["agent"])["dismissal"]["category"] == "agent"
    assert target.get_job(ids["missed"])["signals"]["no_longer_listed"]
    with target.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_signal_record_without_a_row_reads_as_not_computed():
    record = signal_record(None)
    assert record["computed"] is False and record["required"] == [] and record["duplicate"] is None
