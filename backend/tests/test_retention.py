"""Refresh events, trimmed observations, pruning of finished collection work, restore room."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from openings import operations, retention
from openings._vendor.jobspy.model import JobPost
from openings.collectors.catalog import COMPANY_KINDS
from openings.common import encode
from openings.discovery import DiscoveryService, SourceCreate
from openings.events import EventLog
from openings.operations import (
    RESTORE_MARGIN,
    replace_room,
    restore_database,
    restore_limit,
    restore_room,
)
from openings.retention import KEPT_RUNS_PER_SOURCE, observation_payload, prune
from openings.worker import Worker
from openings.workspace import Workspace
from provider_fixtures import JOBSPY_ROW, provider_postings, released_payload

MIB = 1024**2


def stamp(days_ago):
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(timespec="microseconds")


def open_workspace(path):
    workspace = Workspace(path)
    workspace.discovery = DiscoveryService(workspace)
    return workspace


def kinds(workspace, **where):
    clause = " AND ".join(f"{key}=?" for key in where) or "1"
    return [
        row["kind"]
        for row in workspace.db.all(
            f"SELECT kind FROM events WHERE {clause} ORDER BY created_at", tuple(where.values())
        )
    ]


# Refresh events


def test_a_refresh_is_an_event_only_when_a_visible_field_changes_and_never_undoes_the_owner(
    tmp_path,
):
    workspace = open_workspace(tmp_path / "refresh.sqlite")
    posting = {
        "url": "https://example.org/jobs/1",
        "title": "Engineer",
        "company": "Example",
        "location": "Rome",
        "posting": "Build synthetic services.",
        "metadata": {"date_posted": "2026-01-01"},
        "source_key": "custom:1",
    }
    job = workspace.ingest_job(posting)
    seen = workspace.db.one("SELECT * FROM postings")
    # The same posting again, then one with new provider metadata: sightings only.
    workspace.ingest_job(posting)
    again = workspace.ingest_job({**posting, "metadata": {"date_posted": "2026-01-02"}})
    assert kinds(workspace, job_id=job["id"]) == ["job_added"]
    assert again["metadata"]["date_posted"] == "2026-01-02" and again["version"] > job["version"]
    later = workspace.db.one("SELECT * FROM postings")
    assert later["id"] == seen["id"] and later["last_seen_at"] > seen["last_seen_at"]
    assert later["first_seen_at"] == seen["first_seen_at"]
    # A new title and location for the owner to read: one attributed event naming them.
    workspace.ingest_job(
        {**posting, "title": "Senior Engineer", "location": "Milan", "metadata": {"x": 1}}
    )
    assert kinds(workspace, job_id=job["id"]) == ["job_added", "job_refreshed"]
    activity = EventLog(workspace)
    event = activity.list_events({"kind": "job_refreshed", "include_system": True})["items"][0]
    assert event["payload"] == {"fields": ["title", "location"]}
    assert event["subject"]["id"] == job["id"] and event["actor"] == "system"
    assert activity.list_events({"kind": "posting_updated"})["total"] == 0
    # An owner correction is not refreshed away or reported.
    current = workspace.get_job(job["id"])
    workspace.update_job(job["id"], {"expected_version": current["version"], "title": "Corrected"})
    workspace.ingest_job({**posting, "title": "Source title", "location": "Milan"})
    assert workspace.get_job(job["id"])["title"] == "Corrected"
    assert kinds(workspace, job_id=job["id"]) == ["job_added", "job_refreshed", "job_edited"]


# Observations


def test_an_observation_stores_only_the_provider_values_in_use(tmp_path):
    # The fixture covers every shape the collectors emit.
    assert set(JOBSPY_ROW) == set(JobPost.model_fields)
    seen = {
        (item.get("metadata") or {}).get("ats") or (item.get("metadata") or {}).get("source")
        for item in provider_postings()
    }
    assert {*COMPANY_KINDS, "lever", "ashby", "linkedin", "indeed", "glassdoor"} <= seen
    assert any(str(item.get("source_key", "")).startswith("rss:") for item in provider_postings())
    workspace = open_workspace(tmp_path / "observations.sqlite")
    for item in provider_postings():
        job = workspace.ingest_job(item)
        row = workspace.db.one("SELECT payload FROM postings WHERE job_id=?", (job["id"],))
        stored = json.loads(row["payload"])
        assert row["payload"] == encode(observation_payload(released_payload(item)))
        assert set(stored) <= {"source_key", "raw"}
        assert stored.get("source_key") == item.get("source_key")
        assert stored.get("raw", {}) == (
            {"job_url_direct": item["raw"]["job_url_direct"]}
            if (item.get("raw") or {}).get("job_url_direct") is not None
            else {}
        )
        assert len(row["payload"]) < 400
    board = next(i for i in provider_postings() if i["source_key"] == "indeed:in-2001")
    # The trimmed observation is found again by its source key under another URL.
    moved = workspace.ingest_job({**board, "url": board["url"] + "&from=synthetic"})
    assert not moved["created"] and len(moved["postings"]) == 1


# Retention


def add_run(workspace, source_id, days, state="succeeded", name="Synthetic"):
    run_id, task_id, created = uuid4().hex, uuid4().hex, stamp(days)
    with workspace.db.transaction() as conn:
        conn.execute(
            "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,"
            "created_at) VALUES(?,?,?,?,?,?)",
            (run_id, source_id, name, 1, "{}", created),
        )
        conn.execute(
            "INSERT INTO tasks(id,kind,source_id,run_id,state,payload,result,next_run_at,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                task_id,
                "collect",
                source_id,
                run_id,
                state,
                encode({"provider": "greenhouse", "checkpoint": {"pending_details": ["a"]}}),
                encode({"received": 3, "created": 1, "existing": 2}),
                created,
                created,
                created,
            ),
        )
        for kind, subject in (("collection_queued", run_id), ("task_cancelled", task_id)):
            conn.execute(
                "INSERT INTO events(id,kind,created_at,subject_type,subject_id,actor) "
                "VALUES(?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    kind,
                    created,
                    "task" if kind.startswith("task") else "collection_run",
                    subject,
                    "owner",
                ),
            )
    return run_id


@pytest.fixture
def collected(tmp_path):
    workspace = open_workspace(tmp_path / "retention.sqlite")
    source = workspace.discovery.create_source(
        SourceCreate(name="Board", kind="greenhouse", config={"board": "example"})
    )
    return workspace, source["id"]


def test_old_finished_runs_go_and_the_recent_ones_of_each_source_stay(collected):
    workspace, source = collected
    job = workspace.ingest_job({"title": "Engineer", "company": "Example", "posting": "Build."})
    application = workspace.create_application({"job_id": job["id"]})
    workspace.db.execute("UPDATE events SET created_at=?", (stamp(400),))
    timeline = workspace.db.one("SELECT count(*) n FROM events WHERE job_id IS NOT NULL")["n"]
    history = workspace.application_events(application["id"])["total"]
    old = [add_run(workspace, source, 200 + number) for number in range(KEPT_RUNS_PER_SOURCE + 4)]
    queued = add_run(workspace, source, 500, state="queued")
    running = add_run(workspace, source, 499, state="running")
    fresh = add_run(workspace, source, 5, state="failed")
    gone = [add_run(workspace, None, 300), add_run(workspace, None, 120)]
    orphan_recent = add_run(workspace, None, 30)
    workspace.db.execute(
        "INSERT INTO tasks(id,kind,state,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        ("loose-old", "collect", "cancelled", stamp(200), stamp(200), stamp(200)),
    )
    workspace.db.execute(
        "INSERT INTO tasks(id,kind,state,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        ("loose-queued", "collect", "queued", stamp(200), stamp(200), stamp(200)),
    )
    summary = workspace.discovery.get_source(source)["last_run"]

    removed = prune(workspace.db, days=90)
    assert removed == {"runs": 7, "tasks": 8, "events": 14, "keys": 0, "more": False}
    left = {row["id"] for row in workspace.db.all("SELECT id FROM collection_runs")}
    # The newest finished run and the next 19 stay; the five oldest finished ones go.
    assert left == {fresh, *old[: KEPT_RUNS_PER_SOURCE - 1], queued, running, orphan_recent}
    assert not left.intersection(gone)
    tasks = {row["id"] for row in workspace.db.all("SELECT id FROM tasks WHERE run_id IS NULL")}
    assert tasks == {"loose-queued"}
    checkpoint = workspace.db.one("SELECT payload FROM tasks WHERE run_id=?", (queued,))
    assert json.loads(checkpoint["payload"])["checkpoint"] == {"pending_details": ["a"]}
    # Job and application history is untouched, whatever its age.
    assert (
        workspace.db.one("SELECT count(*) n FROM events WHERE job_id IS NOT NULL")["n"] == timeline
    )
    assert workspace.application_events(application["id"])["total"] == history
    orphans = workspace.db.one(
        "SELECT count(*) n FROM events e WHERE subject_type='collection_run' AND NOT EXISTS("
        "SELECT 1 FROM collection_runs r WHERE r.id=e.subject_id)"
    )
    assert orphans["n"] == 0
    assert workspace.discovery.get_source(source)["last_run"] == summary
    assert workspace.discovery.list_runs(source_id=source)["total"] == KEPT_RUNS_PER_SOURCE + 2
    assert prune(workspace.db, days=90) == {
        "runs": 0,
        "tasks": 0,
        "events": 0,
        "keys": 0,
        "more": False,
    }


def test_pruning_is_bounded_and_keeps_records_of_agent_changes(collected, monkeypatch):
    workspace, source = collected
    for number in range(KEPT_RUNS_PER_SOURCE):
        add_run(workspace, source, 1 + number)
    old = [add_run(workspace, source, 100 + number) for number in range(5)]
    # A change an agent token made stays when its collection run goes.
    workspace.db.execute(
        "UPDATE events SET actor='agent:Agent',batch_id='b_agent' WHERE subject_id=? "
        "AND kind='collection_queued'",
        (old[0],),
    )
    first = prune(workspace.db, days=90, batch=2)
    assert first["runs"] == 2 and first["more"]
    passes = 1
    while prune(workspace.db, days=90, batch=2)["more"]:
        passes += 1
    assert passes >= 2
    assert workspace.db.one("SELECT count(*) n FROM collection_runs")["n"] == KEPT_RUNS_PER_SOURCE
    kept = workspace.db.all("SELECT subject_id FROM events WHERE batch_id='b_agent'")
    assert kept == [{"subject_id": old[0]}]
    # The setting: a number of days, 0 keeps everything.
    add_run(workspace, None, 400)
    monkeypatch.setenv("OPENINGS_RETENTION_DAYS", "0")
    assert retention.retention_days() == 0 and prune(workspace.db)["runs"] == 0
    monkeypatch.setenv("OPENINGS_RETENTION_DAYS", "many")
    assert retention.retention_days() == 90
    monkeypatch.setenv("OPENINGS_RETENTION_DAYS", "30")
    assert prune(workspace.db)["runs"] == 1


class Lane:
    def __init__(self, cycles):
        self.cycles = cycles

    def is_set(self):
        return self.cycles <= 0

    def wait(self, seconds):
        self.cycles -= 1


def test_the_worker_prunes_at_start_and_then_at_a_slow_pace(collected, monkeypatch):
    workspace, _ = collected
    add_run(workspace, None, 400)
    calls = []

    def counted(db, *args):
        calls.append(retention.prune(db, *args))
        return calls[-1]

    monkeypatch.setattr("openings.worker.prune", counted)
    worker = Worker(workspace)
    worker._schedule_loop(Lane(3))
    assert [call["runs"] for call in calls] == [1]
    # While a bounded pass leaves old records behind, the next pass comes soon.
    monkeypatch.setattr("openings.worker.prune", lambda db: calls.append("again") or {"more": True})
    worker.prune_backlog_seconds = 0
    worker._schedule_loop(Lane(3))
    assert calls[1:] == ["again"] * 3


def test_idempotency_keys_older_than_thirty_days_are_pruned(tmp_path, monkeypatch):
    workspace = open_workspace(tmp_path / "keys.sqlite")
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build APIs."})
    for key, age in (("old", 31), ("recent", 29)):
        workspace.db.execute(
            "INSERT INTO idempotency_keys(scope,key,fingerprint,record_id,created_at) "
            "VALUES(?,?,?,?,?)",
            ("jobs", key, "digest", job["id"], stamp(age)),
        )
    # Collection retention switched off does not keep the keys.
    monkeypatch.setenv("OPENINGS_RETENTION_DAYS", "0")
    assert prune(workspace.db)["keys"] == 1
    left = workspace.db.all("SELECT key FROM idempotency_keys ORDER BY key")
    assert left == [{"key": "recent"}]
    assert workspace.get_job(job["id"])["id"] == job["id"]
    assert prune(workspace.db)["keys"] == 0


# Restore room


def test_the_restore_limit_is_the_largest_backup_that_fits():
    for database in (0, 5 * MIB, 600 * MIB, 3000 * MIB):
        for free in (0, 10 * MIB, RESTORE_MARGIN + 1, 900 * MIB, 4000 * MIB, 50_000 * MIB):
            limit = restore_limit(free, database)
            assert limit >= 0
            assert limit == 0 or restore_room(limit, database) <= free
            assert restore_room(limit + 4, database) > free or limit == 0
    # Upload, upgraded copy, rollback copy, write-ahead log and growth of the file.
    assert restore_room(100, 40) == 100 + 100 + 40 + 100 + 60 + RESTORE_MARGIN
    assert replace_room(100, 400) == 400 + 100 + RESTORE_MARGIN


def disk(monkeypatch, free):
    class Usage:
        pass

    usage = Usage()
    usage.free = free
    monkeypatch.setattr(operations.shutil, "disk_usage", lambda path: usage)


def test_restore_is_refused_early_with_the_sizes_when_the_disk_is_too_small(
    tmp_path, monkeypatch, app, client
):
    monkeypatch.delenv("OPENINGS_MAX_RESTORE_MB", raising=False)
    app.state.workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    folder = app.state.workspace.db.path.parent
    backup = client.get("/api/v1/backup").content
    disk(monkeypatch, RESTORE_MARGIN + 1000)
    headers = {"Content-Type": "application/vnd.sqlite3"}
    refused = client.post("/api/v1/backup/restore", content=backup, headers=headers)
    assert refused.status_code == 413
    error = refused.json()["error"]
    size = app.state.workspace.db.path.stat().st_size
    assert error["code"] == "backup_size" and "free" in error["message"]
    assert error["details"] == {
        "size_bytes": len(backup),
        "limit_bytes": 0,
        "free_bytes": RESTORE_MARGIN + 1000,
        "needed_bytes": restore_room(len(backup), error["details"]["database_bytes"]),
        "database_bytes": error["details"]["database_bytes"],
        "configured_limit_bytes": None,
    }
    assert error["details"]["database_bytes"] >= size
    assert not list(folder.glob(".openings-temp-*"))
    # A stream without a declared length is stopped when it passes the limit.
    disk(monkeypatch, restore_room(2000, error["details"]["database_bytes"]))

    def chunks():
        yield backup[:1000]
        yield backup[1000:]

    streamed = client.post("/api/v1/backup/restore", content=chunks(), headers=headers)
    assert streamed.status_code == 413 and streamed.json()["error"]["code"] == "backup_size"
    assert not list(folder.glob(".openings-temp-*"))
    # The service itself checks the room before it replaces the database.
    upload = tmp_path / "upload.sqlite"
    upload.write_bytes(backup)
    disk(monkeypatch, 1000)
    with pytest.raises(operations.DomainError) as raised:
        restore_database(app.state.workspace, upload)
    assert raised.value.code == "backup_size" and raised.value.details["free_bytes"] == 1000
    assert app.state.workspace.list_jobs()["total"] == 1


def test_free_space_not_a_fixed_number_decides_and_the_variable_only_lowers_it(
    monkeypatch, client, agent_token
):
    monkeypatch.delenv("OPENINGS_MAX_RESTORE_MB", raising=False)
    backup = client.get("/api/v1/backup").content
    headers = {"Content-Type": "application/vnd.sqlite3"}
    # Far more than the former fixed 2048 MiB fits when the volume has the room.
    disk(monkeypatch, 40_000 * MIB)
    storage = client.get("/api/v1/workspace").json()["storage"]
    assert storage["restore_limit_bytes"] > 2048 * MIB
    assert storage["restore_limit_bytes"] == restore_limit(40_000 * MIB, storage["database_bytes"])
    assert storage["restore_limit_configured_bytes"] is None
    assert storage["free_bytes"] == 40_000 * MIB
    assert storage["retention_days"] == 90
    assert storage["kept_runs_per_source"] == KEPT_RUNS_PER_SOURCE
    # An agent reads the same storage report, with the retention setting.
    monkeypatch.setenv("OPENINGS_RETENTION_DAYS", "45")
    agent = client.get("/api/v1/workspace", headers=agent_token["headers"]).json()["storage"]
    assert agent["retention_days"] == 45 and agent["free_bytes"] == 40_000 * MIB
    monkeypatch.setenv("OPENINGS_MAX_RESTORE_MB", "3000")
    assert client.get("/api/v1/workspace").json()["storage"]["restore_limit_bytes"] == 3000 * MIB
    monkeypatch.setenv("OPENINGS_MAX_RESTORE_MB", "0")
    refused = client.post("/api/v1/backup/restore", content=backup, headers=headers)
    assert refused.status_code == 413
    assert "OPENINGS_MAX_RESTORE_MB" in refused.json()["error"]["message"]
    assert refused.json()["error"]["details"]["configured_limit_bytes"] == 0
    monkeypatch.setenv("OPENINGS_MAX_RESTORE_MB", "")
    restored = client.post("/api/v1/backup/restore", content=backup, headers=headers)
    assert restored.status_code == 200, restored.text
