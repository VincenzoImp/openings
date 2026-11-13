"""The schema 14 to 15 upgrade, on the real fixture written by v0.23.1's own seed.

Each later change of the unreleased migration adds its own block of data
mapping assertions below ("Data mapping").
"""

import gzip
import hashlib
import json
import re
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

import pytest

from openings.db import SCHEMA_VERSION, Database
from openings.errors import DomainError
from openings.migrations import m15
from openings.operations import restore_database
from openings.workspace import Workspace

FIXTURE = Path(__file__).with_name("fixtures") / f"workspace-{SCHEMA_VERSION - 1}.sql.gz"


class Killed(BaseException):
    """A process stopped from outside: no cleanup code runs."""


def load_fixture(path, change=None):
    """The fixture as a database file, as a schema-14 installation keeps it."""
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(gzip.decompress(FIXTURE.read_bytes()).decode())
        if change:
            conn.executescript(change)
        conn.commit()
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def query(path, sql, params=()):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql, params).fetchall()


def tables(conn):
    return [
        row[1]
        for row in conn.execute("PRAGMA table_list")
        if row[0] == "main"
        and row[2] in ("table", "virtual", "shadow")
        and not row[1].startswith("sqlite_")
    ]


def structure(path):
    """Every object's normalised SQL, columns, references and indexes."""
    with closing(sqlite3.connect(path)) as conn:
        objects = {
            (kind, name): re.sub(r"\s+", " ", sql or "").strip()
            for kind, name, sql in conn.execute("SELECT type,name,sql FROM sqlite_master")
        }
        details = {
            name: (
                conn.execute(f'PRAGMA table_xinfo("{name}")').fetchall(),
                conn.execute(f'PRAGMA foreign_key_list("{name}")').fetchall(),
                sorted(row[1:] for row in conn.execute(f'PRAGMA index_list("{name}")')),
            )
            for name in tables(conn)
        }
        return objects, details, conn.execute("PRAGMA user_version").fetchone()[0]


def counts(path):
    with closing(sqlite3.connect(path)) as conn:
        return {
            name: conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            for name in tables(conn)
            if not name.startswith("jobs_fts")
        }


# Tables the upgrade renames: schema-15 name -> schema-14 name.
RENAMED = {"replies": "responses"}  # #214


def created_by_upgrade(pre_upgrade):
    """Rows the upgrade's folds add, per schema-15 table, counted on the original."""
    created = {}
    # #214: an application (and its event) per shortlisted job without an open one,
    # and an event per stored Ready mark.
    started = query(
        pre_upgrade,
        "SELECT count(*) FROM jobs j WHERE triage='saved' AND NOT EXISTS(SELECT 1 FROM "
        "applications a WHERE a.job_id=j.id AND a.status<>'closed')",
    )[0][0]
    marks = query(pre_upgrade, "SELECT count(*) FROM applications WHERE ready_at IS NOT NULL")[0][0]
    created["applications"] = created.get("applications", 0) + started
    created["events"] = created.get("events", 0) + started + marks
    return created


def expected_counts(original, pre_upgrade):
    """The row counts of the upgraded file: the original's, renamed, plus folded rows."""
    renamed = {old: new for new, old in RENAMED.items()}
    expected = {renamed.get(name, name): number for name, number in original.items()}
    for name, number in created_by_upgrade(pre_upgrade).items():
        expected[name] += number
    return expected


@pytest.fixture
def upgraded(tmp_path):
    """The fixture upgraded at startup: (database, pre-upgrade copy, archive, input digest)."""
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)
    Database(path)
    files = m15.files(path)
    return path, files.pre_upgrade, files.archive, before, original


def test_an_upgraded_workspace_has_exactly_the_structure_of_a_new_one(tmp_path, upgraded):
    path = upgraded[0]
    Database(tmp_path / "fresh.sqlite")
    assert structure(path) == structure(tmp_path / "fresh.sqlite")
    assert query(path, "PRAGMA integrity_check") == [("ok",)]
    assert query(path, "PRAGMA foreign_key_check") == []


def test_the_original_is_kept_byte_for_byte_and_every_row_is_copied(upgraded):
    path, pre_upgrade, archive, before, original = upgraded
    assert digest(pre_upgrade) == before
    assert query(pre_upgrade, "PRAGMA user_version") == [(14,)]
    assert counts(path) == expected_counts(original, pre_upgrade)
    assert query(path, "SELECT count(*) FROM jobs_fts WHERE jobs_fts MATCH 'engineer'")[0][0] > 0
    assert sorted(p.name for p in path.parent.iterdir()) == sorted(
        [path.name, pre_upgrade.name, archive.name]
    )


# Data mapping: one block per change of the migration.


def test_generic_changes_keep_every_value(upgraded):
    path, pre_upgrade = upgraded[:2]
    # Ids, versions and every kept value are copied unchanged.
    # Rows an upgrade fold adds (#214) are not in the original.
    for table, columns in (
        ("jobs", "id,title,company,posting,version,created_at,dismissed_reason"),
        ("applications", "id,job_id,outcome,version,questions,answers,requirements"),
        ("events", "id,job_id,application_id,kind,payload,actor_kind,actor_name,run_id"),
        ("documents", "id,previous_id,text,legacy_content,claim_ids"),
        ("blobs", "sha256,content,size"),
    ):
        sql = f"SELECT rowid,{columns} FROM {table} ORDER BY rowid"
        if table == "blobs":
            sql = f"SELECT {columns} FROM {table} ORDER BY sha256"
        assert query(path, sql)[: len(old := query(pre_upgrade, sql))] == old
    # An estimated response day becomes text on the response.
    old = query(pre_upgrade, "SELECT id,note FROM responses WHERE estimated=1")
    assert old
    for response_id, note in old:
        expected = (note + " " if note else "") + "(day estimated during the 0.20 upgrade)"
        assert query(path, "SELECT note FROM replies WHERE id=?", (response_id,)) == [(expected,)]
    assert query(path, "SELECT count(*) FROM pragma_table_info('notes') WHERE name='origin'") == [
        (0,)
    ]
    # job_identities keeps its rows without a rowid.
    assert query(path, "SELECT identity,job_id FROM job_identities ORDER BY 1,2") == query(
        pre_upgrade, "SELECT identity,job_id FROM job_identities ORDER BY 1,2"
    )


def test_text_that_is_not_json_is_repaired_and_archived(tmp_path):
    path = load_fixture(
        tmp_path / "openings.sqlite",
        "UPDATE jobs SET overrides='not json' WHERE rowid=(SELECT min(rowid) FROM jobs);",
    )
    job_id = query(path, "SELECT id FROM jobs WHERE overrides='not json'")[0][0]
    Database(path)
    assert query(path, "SELECT overrides FROM jobs WHERE id=?", (job_id,)) == [("{}",)]
    archive = json.loads(m15.files(path).archive.read_text())
    assert archive["repaired_json"]["jobs.overrides"] == [{"id": job_id, "value": "not json"}]
    assert archive["counts"]["repaired_json.jobs.overrides"] == 1


# Archive.


def test_the_archive_holds_every_dropped_value_with_the_counts_of_its_source(upgraded):
    pre_upgrade, archive_path = upgraded[1:3]
    assert stat.S_IMODE(archive_path.stat().st_mode) == 0o600
    archive = json.loads(archive_path.read_text())
    assert (archive["format"], archive["from_schema"], archive["to_schema"]) == (
        "openings-archive",
        14,
        15,
    )
    dropped = archive["dropped_columns"]
    for table, column, condition in (
        ("applications", "idempotency_key", "idempotency_key IS NOT NULL"),
        ("contexts", "idempotency_key", "idempotency_key IS NOT NULL"),
        ("responses", "estimated", "estimated<>0"),
        ("responses", "origin", "origin<>'manual'"),
        ("notes", "origin", "origin<>'manual'"),
    ):
        rows = query(pre_upgrade, f"SELECT id,{column} FROM {table} WHERE {condition}")
        assert rows, (table, column)
        key = f"{table}.{column}"
        assert sorted((item["id"], item["value"]) for item in dropped[key]) == sorted(rows)
        assert archive["counts"]["dropped_columns." + key] == len(rows)
    assert set(archive["counts"]) == {
        f"{top}.{sub}" for top in ("dropped_columns",) for sub in dropped
    } | {section.name for section in m15.SECTIONS}


def test_a_backup_of_the_previous_schema_is_restored_upgraded(tmp_path):
    backup = load_fixture(tmp_path / "upload.sqlite")
    before = digest(backup)
    workspace = Workspace(tmp_path / "data" / "openings.sqlite")
    assert restore_database(workspace, backup)["restored"]
    assert digest(backup) == before
    # Restore keeps the destination's tokens and drops transfer grants.
    restored, uploaded = counts(workspace.db.path), expected_counts(counts(backup), backup)
    for name in ("api_tokens", "transfer_grants"):
        restored.pop(name), uploaded.pop(name)
    assert restored == uploaded
    archives = list((tmp_path / "data").glob("openings.pre-0.24-archive-restored-*.json"))
    assert len(archives) == 1 and json.loads(archives[0].read_text())["counts"]


# Interruptions and refusals.


def test_a_stop_between_the_two_renames_is_finished_at_the_next_start(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)
    calls = []

    def replace(source, target):
        calls.append(target)
        if len(calls) == 2:
            raise Killed
        m15.os.replace(source, target)

    monkeypatch.setattr(m15, "_replace", replace)
    with pytest.raises(Killed):
        Database(path)
    files = m15.files(path)
    assert not path.exists() and files.next.exists() and files.pre_upgrade.exists()
    monkeypatch.undo()
    Database(path)
    assert counts(path) == expected_counts(original, files.pre_upgrade)
    assert digest(files.pre_upgrade) == before
    assert not files.next.exists()


def test_a_stop_before_the_swap_leaves_the_original_and_runs_again(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)

    def stop(*args):
        raise Killed

    monkeypatch.setattr(m15, "_verify", stop)
    with pytest.raises(Killed):
        Database(path)
    files = m15.files(path)
    assert digest(path) == before and files.next.exists()
    monkeypatch.undo()
    Database(path)
    assert counts(path) == expected_counts(original, files.pre_upgrade)
    assert digest(files.pre_upgrade) == before
    assert not files.next.exists()


def unchanged_after_refusal(path, before):
    files = m15.files(path)
    assert digest(path) == before
    assert not files.next.exists() and not files.archive.exists()
    assert not files.pre_upgrade.exists()


def test_a_failed_check_removes_the_new_file_and_keeps_the_original(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before = digest(path)
    monkeypatch.setattr(m15, "INVARIANTS", (("an impossible value", "SELECT 1", "SELECT 2"),))
    with pytest.raises(DomainError) as refused:
        Database(path)
    assert refused.value.code == "upgrade_failed"
    assert "an impossible value: 1 instead of 2" in refused.value.message
    unchanged_after_refusal(path, before)


def test_without_room_the_start_is_refused_and_nothing_is_written(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before = digest(path)
    usage = m15.shutil.disk_usage(tmp_path)
    monkeypatch.setattr(m15.shutil, "disk_usage", lambda _: usage._replace(free=1024))
    with pytest.raises(DomainError) as refused:
        Database(path)
    assert (refused.value.status, refused.value.code) == (507, "upgrade_room")
    assert refused.value.details["needed_bytes"] > 2.2 * path.stat().st_size
    unchanged_after_refusal(path, before)


@pytest.mark.parametrize(
    ("version", "words"),
    [(13, "older than 0.23. Open it once with the 0.23 image"), (16, "newer Openings")],
)
def test_other_schemas_are_refused_unchanged(tmp_path, version, words):
    path = load_fixture(tmp_path / "openings.sqlite", f"PRAGMA user_version={version};")
    before = digest(path)
    with pytest.raises(DomainError) as refused:
        Database(path)
    assert refused.value.code == "schema_version" and words in refused.value.message
    unchanged_after_refusal(path, before)
