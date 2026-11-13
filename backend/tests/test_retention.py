"""Refresh events, trimmed observations, pruning of finished collection work, restore room."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from context_fixtures import make_schema_eight
from openings import operations, retention
from openings._vendor.jobspy.model import JobPost
from openings.activity import ActivityService
from openings.app import create_app
from openings.collectors.catalog import COMPANY_KINDS
from openings.common import encode
from openings.db import SCHEMA_VERSION
from openings.discovery import DiscoveryService, SourceCreate
from openings.duplicate_signals import Features, job_features
from openings.identities import job_identities, normalize_url
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
from schema_fixtures import make_schema_seven

MIB = 1024**2
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
# The statement that finds the observation a refresh updates, unchanged since 0.17.
# The observation fields of a job read that schema 11 had.
OBSERVATION_FIELDS = ("id", "source_id", "identity", "url", "first_seen_at", "last_seen_at")
OBSERVATION = (
    "SELECT id FROM postings WHERE job_id=? AND (identity=? OR (?<>'' AND url=?) OR "
    "(? IS NOT NULL AND json_extract(payload,'$.source_key')=?)) ORDER BY first_seen_at,id LIMIT 1"
)


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


def test_a_refresh_is_an_event_only_when_a_visible_field_changes(tmp_path):
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
    activity = ActivityService(workspace)
    event = activity.list_events({"kind": "job_refreshed"})["items"][0]
    assert event["payload"] == {"fields": ["title", "location"]}
    assert event["subject"]["id"] == job["id"] and event["actor"]["kind"] == "system"
    assert activity.list_events({"kind": "posting_updated"})["total"] == 0
    assert [item["kind"] for item in workspace.overview()["activity"]] == [
        "job_refreshed",
        "job_added",
    ]


def test_an_owner_correction_is_not_refreshed_away_or_reported(tmp_path):
    workspace = open_workspace(tmp_path / "override.sqlite")
    posting = {"url": "https://example.org/jobs/2", "title": "Engineer", "posting": "Build."}
    job = workspace.ingest_job(posting)
    workspace.update_job(job["id"], {"expected_version": job["version"], "title": "Corrected"})
    workspace.ingest_job({**posting, "title": "Source title"})
    assert workspace.get_job(job["id"])["title"] == "Corrected"
    assert "job_refreshed" not in kinds(workspace, job_id=job["id"])


# Observations


def test_the_fixture_covers_every_shape_the_collectors_emit():
    assert set(JOBSPY_ROW) == set(JobPost.model_fields)
    seen = {
        (item.get("metadata") or {}).get("ats") or (item.get("metadata") or {}).get("source")
        for item in provider_postings()
    }
    assert {*COMPANY_KINDS, "lever", "ashby", "linkedin", "indeed", "glassdoor"} <= seen
    assert any(str(item.get("source_key", "")).startswith("rss:") for item in provider_postings())


def test_an_observation_stores_only_the_provider_values_in_use(tmp_path):
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


# The upgrade


def released_workspace(path):
    """A schema 8 file with full provider payloads and refresh events, as 0.17 wrote them."""
    workspace = open_workspace(path)
    sources = [
        workspace.discovery.create_source(
            SourceCreate(name=f"Board {name}", kind="greenhouse", config={"board": name})
        )
        for name in ("one", "two")
    ]
    items, jobs = provider_postings(), {}
    for number, item in enumerate(items):
        item["source_id"] = sources[number % 2]["id"] if number % 3 else None
        jobs[item["title"]] = workspace.ingest_job(item)["id"]
    # The owner merged a job board copy into the employer's posting: two observations.
    copy, target = jobs.pop("Platform Engineer (m/f/d)"), jobs["Platform Engineer"]
    workspace.merge_jobs(
        copy,
        target,
        workspace.get_job(copy)["version"],
        workspace.get_job(target)["version"],
    )
    application = workspace.create_application({"job_id": jobs["Backend Engineer"]})
    for source in sources:
        for _ in range(3):
            queued = workspace.discovery.queue_collection(source["id"])
            workspace.db.execute(
                "UPDATE tasks SET state='succeeded',result=? WHERE run_id=?",
                (encode({"received": 4, "created": 1, "existing": 3}), queued["run_id"]),
            )
    workspace.discovery.queue_collection(sources[0]["id"])  # stays queued
    # Sources, runs and tasks are the same tables in schema 8: read them as they are.
    collection = source_reads(workspace)
    history = workspace.application_events(application["id"])["total"]
    del workspace
    make_schema_eight(path)
    run_id, token = uuid4().hex, uuid4().hex
    refreshes = [
        (jobs["Platform Engineer"], ["metadata"], None),
        (jobs["Platform Engineer"], ["url", "metadata"], None),
        (jobs["Platform Engineer"], ["title", "metadata"], None),
        (jobs["Backend Engineer"], ["title", "company", "location", "url", "posting"], run_id),
        (jobs["Backend Engineer"], ["metadata"], run_id),
        (jobs["Data Engineer"], ["posting"], None),
        (jobs["Data Engineer"], None, None),
    ]
    with closing(sqlite3.connect(path)) as conn:
        for item in items:
            url = normalize_url(item.get("url", ""))
            identities = job_identities(url, item.get("source_key"))
            changed = conn.execute(
                "UPDATE postings SET payload=? WHERE identity=? OR (?='' AND job_id="
                "(SELECT id FROM jobs WHERE title=?))",
                (
                    encode(released_payload(item)),
                    identities[0] if identities else "",
                    identities[0] if identities else "",
                    item["title"],
                ),
            ).rowcount
            assert changed == 1, item["title"]
        conn.execute(
            "INSERT INTO runs(id,token_id,token_name,workflow,status,change_counts,started_at,"
            "last_activity_at,ended_at,updated_at,token_kind) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                token,
                "Synthetic agent",
                "review-inbox",
                "finished",
                encode({"job_added": 1, "posting_updated": 2}),
                *[stamp(2)] * 4,
                "agent",
            ),
        )
        for number, (job_id, fields, run) in enumerate(refreshes):
            conn.execute(
                "INSERT INTO events(id,job_id,kind,payload,created_at,subject_type,subject_id,"
                "actor_kind,actor_id,actor_token_kind,run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"refresh-{number}",
                    job_id,
                    "posting_updated",
                    encode({} if fields is None else {"fields": fields}),
                    stamp(1 + number),
                    "job",
                    job_id,
                    "token" if run else "system",
                    token if run else None,
                    "agent" if run else None,
                    run,
                ),
            )
        conn.commit()
    return jobs, (application["id"], history), run_id, collection


def lookups(conn):
    wanted = set()
    for job_id, url in conn.execute("SELECT id,url FROM jobs WHERE url<>''"):
        wanted.add((job_id, "url", url))
    for job_id, url, payload in conn.execute("SELECT job_id,url,payload FROM postings"):
        if url:
            wanted.add((job_id, "url", url))
        if json.loads(payload).get("source_key"):
            wanted.add((job_id, "source_key", json.loads(payload)["source_key"]))
    return sorted(wanted)


def feature_values(features):
    return [getattr(features, name, None) for name in Features.__slots__]


def released_reads(path):
    """What 0.17 read from the schema 8 file, with plain SQL and its statements."""
    record = {"resolve": {}, "observation": {}, "sources": {}, "features": {}, "links": {}}
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        record["lookups"] = lookups(conn)
        for job_id, kind, value in record["lookups"]:
            url = normalize_url(value) if kind == "url" else ""
            aliases = job_identities(url, None if kind == "url" else value)
            matched = {}
            for row in conn.execute(
                "SELECT job_id,identity FROM job_identities WHERE identity IN ("
                + ",".join("?" for _ in aliases)
                + ")",
                aliases,
            ):
                matched.setdefault(row[0], set()).add(row[1])
            if url:
                for row in conn.execute("SELECT id FROM jobs WHERE url=?", (url,)):
                    matched.setdefault(row[0], set()).add("job_url")
                for row in conn.execute("SELECT job_id FROM postings WHERE url=?", (url,)):
                    matched.setdefault(row[0], set()).add("posting_url")
            record["resolve"][(job_id, kind, value)] = (
                url,
                aliases,
                {key: sorted(found) for key, found in matched.items()},
            )
        for row in conn.execute(
            "SELECT id,job_id,identity,url,json_extract(payload,'$.source_key') FROM postings"
        ).fetchall():
            key = row[4]
            record["observation"][row[0]] = conn.execute(
                OBSERVATION, (row[1], row[2], row[3], row[3], key, key)
            ).fetchone()[0]
        for job in conn.execute(
            "SELECT id,title,company,location,url,posting,metadata,created_at FROM jobs"
        ).fetchall():
            job = dict(job)
            record["sources"][job["id"]] = [
                dict(row)
                for row in conn.execute(
                    "SELECT id,source_id,identity,url,first_seen_at,last_seen_at FROM postings "
                    "WHERE job_id=? ORDER BY first_seen_at",
                    (job["id"],),
                )
            ]
            record["links"][job["id"]] = sorted(
                row[0]
                for row in conn.execute(
                    "SELECT json_extract(payload,'$.raw.job_url_direct') FROM postings "
                    "WHERE job_id=? AND instr(payload,'job_url_direct')",
                    (job["id"],),
                )
                if isinstance(row[0], str)
            )
            job["metadata"] = json.loads(job["metadata"])
            job["identities"] = [
                row[0]
                for row in conn.execute(
                    "SELECT identity FROM job_identities WHERE job_id=?", (job["id"],)
                )
            ]
            job["urls"] = record["links"][job["id"]]
            record["features"][job["id"]] = feature_values(job_features(job))
        record["payload_bytes"] = conn.execute(
            "SELECT sum(length(payload)) FROM postings"
        ).fetchone()[0]
        record["hashes"] = dict(conn.execute("SELECT id,content_hash FROM postings"))
    return record


def assert_same_reads(workspace, before):
    for item in before["lookups"]:
        result = workspace.resolve_jobs({item[1]: item[2]})
        assert (
            result["url"],
            result["identities"],
            {entry["id"]: entry["matched_by"] for entry in result["items"]},
        ) == before["resolve"][item], item
    with workspace.db.connect() as conn:
        index = workspace._duplicate_index(conn)
        for row in conn.execute(
            "SELECT id,job_id,identity,url,json_extract(payload,'$.source_key') FROM postings"
        ).fetchall():
            found = conn.execute(OBSERVATION, (row[1], row[2], row[3], row[3], row[4], row[4]))
            assert found.fetchone()[0] == before["observation"][row[0]]
        assert dict(conn.execute("SELECT id,content_hash FROM postings")) == before["hashes"]
    assert set(index.jobs) == set(before["features"])
    for job_id, expected in before["features"].items():
        assert feature_values(index.jobs[job_id]) == expected, job_id
        assert [
            {key: posting[key] for key in OBSERVATION_FIELDS}
            for posting in workspace.get_job(job_id)["postings"]
        ] == before["sources"][job_id]


def source_reads(workspace):
    sources = workspace.discovery.list_sources()["items"]
    runs = workspace.discovery.list_runs(limit=200)
    for record in [*runs["items"], *(s["last_run"] for s in sources if s["last_run"])]:
        if record["finished_at"] is None:
            record.pop("total_seconds"), record.pop("waiting_seconds")
    return sources, runs


def test_the_upgrade_keeps_every_read_and_removes_only_resightings(tmp_path):
    current = tmp_path / "current.sqlite"
    jobs, (application, history), run_id, collection = released_workspace(current)
    before = released_reads(current)
    assert before["payload_bytes"] > 40_000
    assert any(before["links"].values()) and len(before["sources"][jobs["Platform Engineer"]]) == 2
    workspace = open_workspace(current)
    assert workspace.db.one("PRAGMA user_version")["user_version"] == SCHEMA_VERSION
    assert_same_reads(workspace, before)
    # Every source's last-run summary and the run list read as before.
    assert source_reads(workspace) == collection
    assert collection[1]["total"] == 7 and all(s["last_run"] for s in collection[0])

    with workspace.db.connect() as conn:
        stored = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM postings")]
        assert conn.execute("SELECT sum(length(payload)) FROM postings").fetchone()[0] < 3000
        refreshed = {
            row["id"]: (row["kind"], json.loads(row["payload"]), row["run_id"])
            for row in conn.execute("SELECT * FROM events WHERE id LIKE 'refresh-%'")
        }
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert all(set(item) <= {"source_key", "raw"} for item in stored)
    assert {"href": "https://example.org/apply/odd"} in [
        item.get("raw", {}).get("job_url_direct") for item in stored
    ]
    assert refreshed == {
        "refresh-2": ("job_refreshed", {"fields": ["title"]}, None),
        "refresh-3": (
            "job_refreshed",
            {"fields": ["title", "company", "location", "posting"]},
            run_id,
        ),
        "refresh-5": ("job_refreshed", {"fields": ["posting"]}, None),
    }
    assert "posting_updated" not in kinds(workspace)
    assert sorted(kinds(workspace, job_id=jobs["Data Engineer"])) == ["job_added", "job_refreshed"]
    # The agent run's stored counts name what its events now are.
    run = workspace.db.one("SELECT change_counts FROM runs WHERE id=?", (run_id,))
    assert json.loads(run["change_counts"]) == {"job_added": 1, "job_refreshed": 1}
    assert workspace.application_events(application)["total"] == history
    # A refresh after the upgrade updates the migrated observation in place.
    board = next(i for i in provider_postings() if i["source_key"] == "linkedin:li-1002")
    again = workspace.ingest_job(board)
    assert not again["created"] and len(again["postings"]) == 1


@pytest.mark.parametrize("version", [7, 6, 5])
def test_older_schemas_chain_through_the_same_step(tmp_path, version):
    path = tmp_path / "chain.sqlite"
    jobs, _, _, collection = released_workspace(path)
    before = released_reads(path)
    Workspace(path)  # make_schema_seven starts from a current file
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")
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
        # Put back what the upgrade above removed: these releases stored it too.
        for item in provider_postings():
            url = normalize_url(item.get("url", ""))
            identities = job_identities(url, item.get("source_key"))
            conn.execute(
                "UPDATE postings SET payload=? WHERE identity=? OR (?='' AND job_id="
                "(SELECT id FROM jobs WHERE title=?))",
                (
                    encode(released_payload(item)),
                    identities[0] if identities else "",
                    identities[0] if identities else "",
                    item["title"],
                ),
            )
        conn.executemany(
            "INSERT INTO events(id,job_id,kind,payload,created_at) VALUES(?,?,?,?,?)",
            [
                ("old-1", jobs["Data Engineer"], "posting_updated", '{"fields":["metadata"]}', "1"),
                ("old-2", jobs["Data Engineer"], "posting_updated", '{"fields":["company"]}', "2"),
            ],
        )
        conn.execute(f"PRAGMA user_version={version}")
        conn.commit()
        assert conn.execute("SELECT sum(length(payload)) FROM postings").fetchone()[0] > 40_000
    workspace = open_workspace(path)
    assert_same_reads(workspace, before)
    assert source_reads(workspace) == collection
    rows = workspace.db.all("SELECT id,kind,payload FROM events WHERE id LIKE 'old-%'")
    assert rows == [{"id": "old-2", "kind": "job_refreshed", "payload": '{"fields":["company"]}'}]
    assert "posting_updated" not in kinds(workspace)
    with workspace.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT sum(length(payload)) FROM postings").fetchone()[0] < 3000
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_restore_of_a_released_backup_goes_through_the_same_step(tmp_path):
    backup = tmp_path / "backup.sqlite"
    released_workspace(backup)
    before = released_reads(backup)
    workspace = open_workspace(tmp_path / "live" / "live.sqlite")
    restore_database(workspace, backup)
    assert_same_reads(workspace, before)
    assert "posting_updated" not in kinds(workspace)
    # The uploaded file is not changed.
    assert released_reads(backup)["payload_bytes"] == before["payload_bytes"]


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
                "INSERT INTO events(id,kind,created_at,subject_type,subject_id,actor_kind) "
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


def test_pruning_is_bounded_and_keeps_records_of_agent_runs(collected, monkeypatch):
    workspace, source = collected
    for number in range(KEPT_RUNS_PER_SOURCE):
        add_run(workspace, source, 1 + number)
    old = [add_run(workspace, source, 100 + number) for number in range(5)]
    token = uuid4().hex
    workspace.db.execute(
        "INSERT INTO runs(id,token_id,token_name,workflow,status,started_at,last_activity_at,"
        "updated_at) VALUES('agent-run',?,?,?,?,?,?,?)",
        (token, "Agent", "manage-sources", "finished", *[stamp(100)] * 3),
    )
    workspace.db.execute(
        "UPDATE events SET run_id='agent-run' WHERE subject_id=? AND kind='collection_queued'",
        (old[0],),
    )
    first = prune(workspace.db, days=90, batch=2)
    assert first["runs"] == 2 and first["more"]
    passes = 1
    while prune(workspace.db, days=90, batch=2)["more"]:
        passes += 1
    assert passes >= 2
    assert workspace.db.one("SELECT count(*) n FROM collection_runs")["n"] == KEPT_RUNS_PER_SOURCE
    kept = workspace.db.all("SELECT subject_id FROM events WHERE run_id='agent-run'")
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


def signed_in(tmp_path):
    app = create_app(tmp_path / "data" / "live.sqlite", start_worker=False)
    app.state.workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    client = TestClient(app, base_url="http://localhost:8080")
    session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
    client.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    return app, client


def test_restore_is_refused_early_with_the_sizes_when_the_disk_is_too_small(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENINGS_MAX_RESTORE_MB", raising=False)
    app, client = signed_in(tmp_path)
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
    assert not list((tmp_path / "data").glob(".openings-temp-*"))
    # A stream without a declared length is stopped when it passes the limit.
    disk(monkeypatch, restore_room(2000, error["details"]["database_bytes"]))

    def chunks():
        yield backup[:1000]
        yield backup[1000:]

    streamed = client.post("/api/v1/backup/restore", content=chunks(), headers=headers)
    assert streamed.status_code == 413 and streamed.json()["error"]["code"] == "backup_size"
    assert not list((tmp_path / "data").glob(".openings-temp-*"))
    # The service itself checks the room before it replaces the database.
    upload = tmp_path / "upload.sqlite"
    upload.write_bytes(backup)
    disk(monkeypatch, 1000)
    with pytest.raises(operations.DomainError) as raised:
        restore_database(app.state.workspace, upload)
    assert raised.value.code == "backup_size" and raised.value.details["free_bytes"] == 1000
    assert app.state.workspace.list_jobs()["total"] == 1


def test_free_space_not_a_fixed_number_decides_and_the_variable_only_lowers_it(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("OPENINGS_MAX_RESTORE_MB", raising=False)
    _, client = signed_in(tmp_path)
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


def test_storage_reads_the_same_over_rest_and_mcp(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENINGS_RETENTION_DAYS", "45")
    app, client = signed_in(tmp_path)
    disk(monkeypatch, 9000 * MIB)
    token = app.state.auth.create_token("Agent", "agent")["token"]
    headers = {"Authorization": "Bearer " + token}
    with client:
        rest = client.get("/api/v1/workspace", headers=headers).json()["storage"]
        response = client.post(
            "/mcp",
            headers={**MCP_HEADERS, **headers},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "workspace_info", "arguments": {}},
            },
        )
    result = response.json()["result"]
    info = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    assert info["storage"] == rest
    assert rest["retention_days"] == 45 and rest["database_bytes"] > 0
    assert rest["restore_limit_bytes"] == restore_limit(9000 * MIB, rest["database_bytes"])
