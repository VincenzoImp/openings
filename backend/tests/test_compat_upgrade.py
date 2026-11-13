"""The 13 -> 14 upgrade: what 0.19 to 0.22 deprecated leaves, and every value it held stays.

A job's manual availability becomes a note on the job; the Profile's preferences
and roles must be held by the policy (0.19 copied them into decision items), and
one that is not is copied there before both fields leave the Profile.
"""

import json
import sqlite3
from contextlib import closing

import pytest

from compat_fixtures import make_schema_thirteen
from context_fixtures import make_schema_eight
from openings.activity import ActivityService
from openings.actors import OWNER, UNKNOWN_LABEL, acting_as, token_actor
from openings.career import CareerService, ProfileUpdate, TemplateCreate
from openings.db import SCHEMA_VERSION, Database
from openings.documents import ContextCreate, DocumentService
from openings.operations import restore_database
from openings.policy import PolicyService
from openings.snapshots import payload_text
from openings.workspace import Workspace
from openings.workspace.availability_upgrade import note_body
from outcome_fixtures import make_schema_ten
from policy_fixtures import make_schema_nine
from schema_fixtures import columns, index_names, make_schema_seven, table_names
from signal_fixtures import make_schema_eleven
from timeline_fixtures import make_schema_twelve

AGENT = token_actor("agent-token", "Synthetic agent", "agent")
# Availability values as 0.22 stored them: two set by hand, an awkward one set by an
# edit recorded before 0.17, and the two that carry nothing.
AVAILABILITY = {
    "closed": "closed",
    "open": "open",
    "awkward": "Ünïcode ✓ “closed”\r\n  ",
    "unknown": "unknown",
    "empty": "",
}
PREFERENCES = "Remote first.\nNo consultancies — “synthetic”."
ROLES = "Platform engineer, edited after 0.19 ✓"


def thirteen_workspace(path):
    """A schema 13 file: jobs with availability, a Profile with both texts, a frozen context.

    The policy holds the preferences (reflowed, as an owner may have edited the
    item) but not the roles, which changed after 0.19.
    """
    workspace = Workspace(path)
    ids = {
        name: workspace.ingest_job(
            {"title": f"Synthetic {name}", "company": "Example", "posting": "Build APIs."}
        )["id"]
        for name in AVAILABILITY
    }
    application = workspace.create_application({"job_id": ids["closed"]})
    career, policy = CareerService(workspace), PolicyService(workspace)
    with acting_as(OWNER):
        career.update_profile(
            ProfileUpdate(
                expected_version=career.get_profile()["version"],
                name="Alex Example",
                summary="Built Python APIs.",
                metadata={"notice_period_days": 30},
            )
        )
        policy.add_item(
            "decision",
            {
                "expected_version": 0,
                "label": "Where and with whom",
                "statement": "  Remote first. No consultancies —\n“synthetic”. ",
            },
        )
        policy.add_item("decision", {"expected_version": 1, "label": "No agencies"})
    with acting_as(AGENT):
        run = ActivityService(workspace).start_run({"workflow": "review-inbox"})
    template = career.create_template(TemplateCreate(name="Synthetic CV", tex="\\section{CV}"))
    context = DocumentService(workspace).prepare_context(
        ContextCreate(application_id=application["id"], template_ids=[template["id"]])
    )
    with workspace.db.transaction() as conn:
        # As 0.22 recorded an edit of the field: a job_edited event naming it.
        def edited(job_id, actor, run_id, stamp, fields=("availability",)):
            conn.execute(
                "INSERT INTO events(id,job_id,kind,payload,created_at,subject_type,subject_id,"
                "actor_kind,actor_id,actor_name,actor_token_kind,run_id) "
                "VALUES(?,?,'job_edited',?,?,'job',?,?,?,?,?,?)",
                (
                    f"e-{job_id}-{stamp}",
                    job_id,
                    json.dumps({"fields": list(fields)}),
                    stamp,
                    job_id,
                    *actor,
                    run_id,
                ),
            )

        edited(ids["closed"], ("owner", None, None, None), None, "2026-10-02T09:00:00+00:00")
        # A later edit of another field does not move the note's time or author.
        edited(ids["closed"], AGENT.columns(), None, "2026-10-05T09:00:00+00:00", ("title",))
        edited(ids["open"], AGENT.columns(), run["id"], "2026-10-03T09:00:00+00:00")
        edited(ids["awkward"], (None, None, None, None), None, "2026-01-05T09:00:00+00:00")
    make_schema_thirteen(
        path,
        availability={ids[name]: value for name, value in AVAILABILITY.items()},
        profile={"preferences": PREFERENCES, "roles": ROLES},
    )
    return ids, run["id"], context["id"]


def rows(conn, table):
    """A table's rows, without the column schema 14 dropped, in storage order."""
    names = [
        f'"{row[0]}"' for row in columns(conn, table) if (table, row[0]) != ("jobs", "availability")
    ]
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]
    key = "" if "WITHOUT ROWID" in (sql or "") else "rowid,"
    return conn.execute(f"SELECT {key}{','.join(names)} FROM {table} ORDER BY 1,2").fetchall()


def test_upgrade_keeps_availability_and_the_profile_texts_and_changes_nothing_else(tmp_path):
    path = tmp_path / "thirteen.sqlite"
    ids, run_id, context_id = thirteen_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 13
        tables = sorted(
            table for table in table_names(conn) if not table.startswith(("jobs_fts", "sqlite"))
        )
        before = {table: rows(conn, table) for table in tables}
        profile_before = json.loads(
            conn.execute("SELECT data FROM settings WHERE key='profile'").fetchone()[0]
        )
        payload = payload_text(conn, context_id)
        updated = dict(conn.execute("SELECT id,updated_at FROM jobs"))
    workspace = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with closing(sqlite3.connect(path)) as conn, closing(sqlite3.connect(fresh.path)) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 14
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert table_names(conn) == table_names(reference)
        assert index_names(conn) == index_names(reference)
        for table in table_names(reference):
            if not table.startswith("jobs_fts"):
                assert columns(conn, table) == columns(reference, table), table
        changed = {"notes", "policy_items", "policy_sections", "settings"}
        for table in sorted(set(tables) - changed):
            assert rows(conn, table) == before[table], table
        # Notes: the earlier ones as they were, plus one per job whose value says something.
        assert rows(conn, "notes")[: len(before["notes"])] == before["notes"]
        added = conn.execute(
            "SELECT job_id,application_id,CAST(body AS BLOB),author_kind,author_name,"
            "author_token_kind,run_id,created_at,updated_at,pinned_at,version,origin "
            "FROM notes WHERE origin='upgrade'"
        ).fetchall()
        assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == len(before["events"])
        assert payload_text(conn, context_id) == payload
        # Settings: only the Profile lost its two texts; its version and time stay.
        settings = {row[1]: row[2:] for row in rows(conn, "settings") if row[1] != "profile"}
        assert settings == {row[1]: row[2:] for row in before["settings"] if row[1] != "profile"}
        data, version, stamp = conn.execute(
            "SELECT data,version,updated_at FROM settings WHERE key='profile'"
        ).fetchone()
        old = next(row for row in before["settings"] if row[1] == "profile")
        assert (version, stamp) == old[3:5]
        assert json.loads(data) == {
            key: value
            for key, value in profile_before.items()
            if key not in ("preferences", "roles")
        }
        # Policy: the items as they were, and one new item for the roles.
        assert rows(conn, "policy_items")[: len(before["policy_items"])] == before["policy_items"]
    notes = {row[0]: row[1:] for row in added}
    assert set(notes) == {ids[name] for name in ("closed", "open", "awkward")}
    for name in ("closed", "open", "awkward"):
        note = notes[ids[name]]
        assert note[0] is None and note[1] == note_body(AVAILABILITY[name]).encode()
        assert AVAILABILITY[name].encode() in note[1]
        assert (note[8], note[9], note[10]) == (None, 1, "upgrade")
    assert notes[ids["closed"]][2:7] == ("owner", None, None, None, "2026-10-02T09:00:00+00:00")
    assert notes[ids["open"]][2:7] == (
        "token",
        "Synthetic agent",
        "agent",
        run_id,
        "2026-10-03T09:00:00+00:00",
    )
    assert notes[ids["awkward"]][2:7] == (None, None, None, None, "2026-01-05T09:00:00+00:00")
    # Read back through the services: the job's timeline shows the note.
    timeline = workspace.timeline(job_id=ids["awkward"], value={"kinds": ["note"]})["items"]
    assert [item["note"]["body"] for item in timeline] == [note_body(AVAILABILITY["awkward"])]
    assert timeline[0]["actor"]["label"] == UNKNOWN_LABEL
    assert "availability" not in workspace.get_job(ids["closed"])
    assert workspace.get_job(ids["unknown"])["updated_at"] == updated[ids["unknown"]]
    profile = CareerService(workspace).get_profile()
    assert "preferences" not in profile and "roles" not in profile
    assert profile["metadata"] == {"notice_period_days": 30}
    decision = next(
        section
        for section in PolicyService(workspace).get_policy()["sections"]
        if section["section"] == "decision"
    )
    assert decision["version"] == 3
    assert [item["label"] for item in decision["items"]] == [
        "Where and with whom",
        "No agencies",
        "Target roles",
    ]
    copied = decision["items"][-1]
    assert copied["statement"] == ROLES and copied["position"] == 2
    assert copied["confirmed"] is False and copied["created_by"]["kind"] == "system"
    assert copied["origin"] == {
        "source": "profile_roles_removed",
        "key": "roles",
        "note": "Copied from Profile roles when 0.23 removed the field",
    }
    # Opening again changes nothing.
    again = Workspace(path)
    with again.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM notes WHERE origin='upgrade'").fetchone()[0] == 3
        assert conn.execute("SELECT count(*) FROM policy_items").fetchone()[0] == 3


def test_a_failed_upgrade_leaves_the_schema_thirteen_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite"
    ids, _, _ = thirteen_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        original = {table: rows(conn, table) for table in ("jobs", "notes", "settings")}
    # A value the policy never holds: the check before the fields go fails.
    monkeypatch.setattr("openings.policy.profile_upgrade.found", lambda conn, value: False)
    with pytest.raises(sqlite3.IntegrityError):
        Workspace(path)
    monkeypatch.undo()
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 13
        assert "availability" in {row[0] for row in columns(conn, "jobs")}
        assert {table: rows(conn, table) for table in original} == original
        assert conn.execute("SELECT count(*) FROM policy_items").fetchone() == (2,)
        assert conn.execute(
            "SELECT availability FROM jobs WHERE id=?", (ids["awkward"],)
        ).fetchone() == (AVAILABILITY["awkward"],)
    assert "roles" not in CareerService(Workspace(path)).get_profile()


def test_a_value_no_policy_item_holds_is_copied_whole(tmp_path):
    """A workspace that never ran the 0.19 step: both texts become decision items."""
    path = tmp_path / "plain.sqlite"
    Workspace(path)
    structured = {"remote": True, "cities": ["Zurich"]}
    make_schema_thirteen(path, profile={"preferences": structured, "roles": "   "})
    workspace = Workspace(path)
    profile = CareerService(workspace).get_profile()
    assert "preferences" not in profile and "roles" not in profile
    sections = {s["section"]: s for s in PolicyService(workspace).get_policy()["sections"]}
    # A value that is not text is kept as it was stored; blank text says nothing.
    [item] = sections["decision"]["items"]
    assert (item["label"], item["value"], item["value_type"]) == (
        "Preferences",
        structured,
        "structured",
    )
    assert sections["decision"]["version"] == 1


def downgrade(path, version):
    """Turn a current workspace file into the released layout of an older schema."""
    if version == 13:
        make_schema_thirteen(path)
        return
    {
        12: make_schema_twelve,
        11: make_schema_eleven,
        10: make_schema_ten,
        9: make_schema_nine,
        8: make_schema_eight,
    }.get(version, make_schema_seven)(path)
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


@pytest.mark.parametrize("version", [13, 12, 11, 10, 9, 8, 7, 6, 5])
def test_every_supported_schema_upgrades_and_restores_keeping_every_value(tmp_path, version):
    path = tmp_path / f"schema{version}.sqlite"
    workspace = Workspace(path)
    job = workspace.ingest_job({"title": "Synthetic", "company": "Example", "posting": "Build."})
    career = CareerService(workspace)
    career.update_profile(
        ProfileUpdate(expected_version=career.get_profile()["version"], name="Alex Example")
    )
    downgrade(path, version)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("UPDATE jobs SET availability='closed' WHERE id=?", (job["id"],))
        conn.execute(
            "UPDATE settings SET data=json_set(data,'$.preferences',?,'$.roles',?) "
            "WHERE key='profile'",
            (PREFERENCES, ROLES),
        )
        conn.commit()
        assert conn.execute("PRAGMA user_version").fetchone()[0] == version
    original = path.read_bytes()
    # A restore upgrades a copy and leaves the backup as it was.
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, path)
    assert path.read_bytes() == original
    for opened in (Workspace(path), target):
        with opened.db.connect() as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
            assert [
                tuple(row)
                for row in conn.execute(
                    "SELECT body FROM notes WHERE origin='upgrade' AND job_id=? "
                    "AND application_id IS NULL",
                    (job["id"],),
                )
            ] == [(note_body("closed"),)]
            statements = {row[0] for row in conn.execute("SELECT statement FROM policy_items")}
        assert {PREFERENCES, ROLES} <= statements
        profile = CareerService(opened).get_profile()
        assert profile["name"] == "Alex Example" and "roles" not in profile
