"""The schema 15 to 16 upgrade, on the real fixture written by v0.27.3's own seed.

Each later change of the unreleased migration adds its own block of data
mapping assertions below ("Data mapping").
"""

import gzip
import hashlib
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from openings.db import SCHEMA_VERSION, Database
from openings.errors import DomainError
from openings.migrations import m16
from openings.operations import restore_database
from openings.workspace import Workspace

FIXTURE = Path(__file__).with_name("fixtures") / f"workspace-{SCHEMA_VERSION - 1}.sql.gz"


class Killed(BaseException):
    """A process stopped from outside: no cleanup code runs."""


def load_fixture(path, change=None):
    """The fixture as a database file, as a schema-15 installation keeps it."""
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
    """Rows per table, the search index aside."""
    with closing(sqlite3.connect(path)) as conn:
        return {
            name: conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            for name in tables(conn)
            if not name.startswith("jobs_fts")
        }


def rows(path, table):
    """Every row of a table in rowid (or key) order, with the columns of the original."""
    with closing(sqlite3.connect(path)) as conn:
        columns = [row[1] for row in conn.execute(f'PRAGMA table_xinfo("{table}")')]
        rowid = (
            ""
            if conn.execute(
                "SELECT 1 FROM pragma_table_list WHERE name=? AND wr", (table,)
            ).fetchone()
            else "rowid,"
        )
        order = "rowid" if rowid else ",".join(f'"{name}"' for name in columns)
        return columns, conn.execute(f'SELECT {rowid}* FROM "{table}" ORDER BY {order}').fetchall()


@pytest.fixture(scope="module")
def upgraded(tmp_path_factory):
    """The fixture upgraded at startup, once per module and only read by the tests:
    (database, pre-upgrade copy, input digest, input counts, files beside it)."""
    path = load_fixture(tmp_path_factory.mktemp("upgraded") / "openings.sqlite")
    before, original = digest(path), counts(path)
    Database(path)
    files = m16.files(path)
    beside = sorted(p.name for p in path.parent.iterdir())
    return path, files.pre_upgrade, before, original, beside


def test_an_upgraded_workspace_is_a_new_one_holding_every_row_of_the_original(tmp_path, upgraded):
    path, pre_upgrade, before, original, beside = upgraded
    Database(tmp_path / "fresh.sqlite")
    assert structure(path) == structure(tmp_path / "fresh.sqlite")
    assert query(path, "PRAGMA integrity_check") == [("ok",)]
    assert query(path, "PRAGMA foreign_key_check") == []
    # The original is kept byte for byte and every row is copied; nothing is archived.
    assert digest(pre_upgrade) == before
    assert query(pre_upgrade, "PRAGMA user_version") == [(15,)]
    assert counts(path) == original
    assert query(path, "SELECT count(*) FROM jobs_fts WHERE jobs_fts MATCH 'engineer'")[0][0] > 0
    assert beside == sorted([path.name, pre_upgrade.name])
    assert pre_upgrade.name == "openings.pre-0.28.sqlite"


# Data mapping: one block per change of the migration.


def test_every_value_is_copied_unchanged(upgraded):
    path, pre_upgrade = upgraded[:2]
    with closing(sqlite3.connect(pre_upgrade)) as conn:
        names = [name for name in tables(conn) if not name.startswith("jobs_fts")]
    for table in names:
        old_columns, old_rows = rows(pre_upgrade, table)
        new_columns, new_rows = rows(path, table)
        # Rows keep their rowid; a new column comes last, so the original's values lead.
        assert new_columns[: len(old_columns)] == old_columns, table
        width = len(old_rows[0]) if old_rows else 0
        assert [row[:width] for row in new_rows] == old_rows, table


def test_applications_have_a_salary_and_the_upgrade_sets_none(tmp_path, upgraded):
    # #348: salary is new on applications; the upgrade leaves every one without it.
    path, pre_upgrade = upgraded[:2]
    assert query(path, "SELECT count(*) FROM applications")[0][0] > 0
    assert query(path, "SELECT count(*) FROM applications WHERE salary IS NOT NULL") == [(0,)]
    assert query(
        pre_upgrade, "SELECT count(*) FROM pragma_table_info('applications') WHERE name='salary'"
    ) == [(0,)]
    # The upgraded workspace takes one (on a copy: the module's file is only read).
    copy = tmp_path / "openings.sqlite"
    copy.write_bytes(path.read_bytes())
    workspace = Workspace(copy)
    application = workspace.list_applications(limit=1)["items"][0]
    changed = workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "salary": "EUR 60-70k a year"},
    )
    assert changed["salary"] == "EUR 60-70k a year"


def test_a_backup_of_the_previous_schema_is_restored_upgraded(tmp_path):
    backup = load_fixture(tmp_path / "upload.sqlite")
    before = digest(backup)
    workspace = Workspace(tmp_path / "data" / "openings.sqlite")
    assert restore_database(workspace, backup)["restored"]
    assert digest(backup) == before
    # Restore keeps the destination's tokens and drops transfer grants.
    restored, uploaded = counts(workspace.db.path), counts(backup)
    for name in ("api_tokens", "transfer_grants"):
        restored.pop(name), uploaded.pop(name)
    assert restored == uploaded
    assert sorted(p.name for p in (tmp_path / "data").iterdir() if "pre-" in p.name) == []


# Interruptions and refusals.


def test_a_stop_between_the_two_renames_is_finished_at_the_next_start(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)
    calls = []

    def replace(source, target):
        calls.append(target)
        if len(calls) == 2:
            raise Killed
        m16.os.replace(source, target)

    monkeypatch.setattr(m16, "_replace", replace)
    with pytest.raises(Killed):
        Database(path)
    files = m16.files(path)
    assert not path.exists() and files.next.exists() and files.pre_upgrade.exists()
    monkeypatch.undo()
    Database(path)
    assert counts(path) == original
    assert digest(files.pre_upgrade) == before
    assert not files.next.exists()


def test_a_stop_before_the_swap_leaves_the_original_and_runs_again(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before, original = digest(path), counts(path)

    def stop(*args):
        raise Killed

    monkeypatch.setattr(m16, "_verify", stop)
    with pytest.raises(Killed):
        Database(path)
    files = m16.files(path)
    assert digest(path) == before and files.next.exists()
    monkeypatch.undo()
    Database(path)
    assert counts(path) == original
    assert digest(files.pre_upgrade) == before
    assert not files.next.exists()


def unchanged_after_refusal(path, before):
    files = m16.files(path)
    assert digest(path) == before
    assert not files.next.exists() and not files.pre_upgrade.exists()


def test_a_refused_start_writes_nothing(tmp_path, monkeypatch):
    path = load_fixture(tmp_path / "openings.sqlite")
    before = digest(path)
    # A failed check removes the new file and keeps the original.
    with monkeypatch.context() as patch:
        patch.setattr(m16, "INVARIANTS", (("an impossible value", "SELECT 1", "SELECT 2"),))
        with pytest.raises(DomainError) as refused:
            Database(path)
    assert refused.value.code == "upgrade_failed"
    assert "an impossible value: 1 instead of 2" in refused.value.message
    unchanged_after_refusal(path, before)

    # A value the new schema has no place for is refused, not lost.
    extra = load_fixture(
        tmp_path / "extra.sqlite", "ALTER TABLE notes ADD COLUMN mood TEXT; CREATE TABLE odd(x);"
    )
    digest_before = digest(extra)
    with pytest.raises(DomainError) as refused:
        Database(extra)
    assert refused.value.code == "upgrade_failed"
    assert "odd" in refused.value.message and "notes.mood" in refused.value.message
    unchanged_after_refusal(extra, digest_before)

    # Without room the start is refused.
    usage = m16.shutil.disk_usage(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(m16.shutil, "disk_usage", lambda _: usage._replace(free=1024))
        with pytest.raises(DomainError) as refused:
            Database(path)
    assert (refused.value.status, refused.value.code) == (507, "upgrade_room")
    assert refused.value.details["needed_bytes"] > 2.2 * path.stat().st_size
    unchanged_after_refusal(path, before)

    # Other schemas are refused unchanged.
    for version, words in (
        (14, "older than 0.24. Open it once with the 0.27 image"),
        (17, "newer Openings"),
    ):
        other = load_fixture(
            tmp_path / f"schema-{version}.sqlite", f"PRAGMA user_version={version};"
        )
        digest_before = digest(other)
        with pytest.raises(DomainError) as refused:
            Database(other)
        assert refused.value.code == "schema_version" and words in refused.value.message
        unchanged_after_refusal(other, digest_before)

    # So is the database of another program: no schema version, tables of its own.
    unrelated = tmp_path / "unrelated.sqlite"
    with closing(sqlite3.connect(unrelated)) as conn:
        conn.execute("CREATE TABLE jobs (old_field TEXT)")
        conn.execute("INSERT INTO jobs VALUES ('retained')")
        conn.commit()
    digest_before = digest(unrelated)
    with pytest.raises(DomainError):
        Workspace(unrelated)
    unchanged_after_refusal(unrelated, digest_before)
