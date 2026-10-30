"""Collection pages and scheduler work remain bounded with populated sources."""

import pytest

from openings import discovery as module
from openings.db import encode
from openings.discovery import CollectionWrite, DiscoveryService
from openings.errors import DomainError
from openings.workspace import Workspace


@pytest.fixture
def populated(tmp_path):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    service = DiscoveryService(workspace)
    stamp = "2026-01-01T00:00:00.000000+00:00"
    with workspace.db.transaction() as connection:
        for index in range(350):
            source_id = f"source-{index:04}"
            connection.execute(
                "INSERT INTO sources(id,name,kind,config,enabled,schedule,created_at,updated_at) VALUES(?,?,'greenhouse',?,1,?,?,?)",
                (
                    source_id,
                    f"Example {index:04}",
                    encode({"board": f"example-{index}"}),
                    encode({"kind": "interval", "minutes": 1440}),
                    stamp,
                    stamp,
                ),
            )
            connection.execute(
                "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,created_at) VALUES(?,?,?,1,'{}',?)",
                (f"run-{index:04}", source_id, f"Example {index:04}", stamp),
            )
            connection.execute(
                "INSERT INTO tasks(id,kind,source_id,run_id,payload,dedupe_key,next_run_at,created_at,updated_at) VALUES(?,'collect',?,?,?,?,?,?,?)",
                (
                    f"task-{index:04}",
                    source_id,
                    f"run-{index:04}",
                    encode({"manual": False, "source_version": 1, "provider": "greenhouse"}),
                    f"collect:{source_id}",
                    stamp,
                    stamp,
                    stamp,
                ),
            )
    return workspace, service, stamp


def test_source_page_batches_reads_and_preserves_provider_summaries(populated, monkeypatch):
    workspace, service, stamp = populated
    with workspace.db.transaction() as connection:
        connection.execute(
            "UPDATE sources SET kind='jobspy',config=? WHERE id='source-0000'",
            (encode({"providers": ["indeed", "linkedin"]}),),
        )
        connection.execute(
            "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,created_at) VALUES('new-run','source-0000','Example',1,'{}',?)",
            ("2026-01-03T00:00:00+00:00",),
        )
        for task_id, provider, state, result, error in [
            ("indeed-new", "indeed", "failed", {"created": 3}, "Blocked"),
            (
                "linkedin-new",
                "linkedin",
                "running",
                {"received": 2, "diagnostics": [{"provider": "linkedin"}]},
                None,
            ),
        ]:
            connection.execute(
                "INSERT INTO tasks(id,kind,source_id,run_id,state,payload,result,next_run_at,error,created_at,updated_at) VALUES(?,'collect','source-0000','new-run',?,?,?,?,?,?,?)",
                (
                    task_id,
                    state,
                    encode({"provider": provider}),
                    encode(result),
                    stamp,
                    error,
                    "2026-01-03T00:00:00+00:00",
                    stamp,
                ),
            )
    reads = []
    for name in ("one", "all"):
        original = getattr(workspace.db, name)

        def read(sql, params=(), original=original):
            reads.append(sql)
            return original(sql, params)

        monkeypatch.setattr(workspace.db, name, read)
    page = service.list_sources(limit=500)
    assert page["total"] == len(page["items"]) == 350
    assert len(reads) <= 5
    first = page["items"][0]
    assert first["last_outcome"] == "running"
    assert first["last_task_id"] in {"indeed-new", "linkedin-new"}
    assert first["last_counts"]["created"] == 3 and first["last_counts"]["received"] == 2
    assert first["last_error"] == "Blocked"
    assert first["last_diagnostics"] == [{"provider": "linkedin"}]
    assert first["next_run_at"] is None
    assert first["last_counts"] == service.get_source(first["id"])["last_counts"]
    assert page["items"][1]["last_outcome"] == "queued"
    assert [item["id"] for item in service.list_sources(limit=2, offset=348)["items"]] == [
        item["id"] for item in page["items"][348:]
    ]


def test_scheduler_does_not_rebuild_collection_or_source_summaries(populated, monkeypatch):
    workspace, service, _ = populated
    calls = []
    original = module.next_due

    def due(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    def summary(*args, **kwargs):
        pytest.fail("Scheduling must not build display summaries for each source")

    monkeypatch.setattr(module, "next_due", due)
    monkeypatch.setattr(service, "get_collection", summary)
    monkeypatch.setattr(service, "_source", summary)
    service.schedule_due()
    assert len(calls) == 350
    assert workspace.db.one("SELECT COUNT(*) AS n FROM tasks")["n"] == 350
    assert workspace.db.one("SELECT COUNT(*) AS n FROM tasks WHERE state='queued'")["n"] == 350


def test_collection_queue_preserves_pause_version_and_manual_controls(populated):
    workspace, service, _ = populated
    source_id = "source-0000"
    service.update_collection(CollectionWrite(enabled=False, expected_version=0))
    assert service.queue_collection(source_id, manual=False) is None
    assert service.queue_collection(source_id, expected_version=1)["payload"]["manual"]
    with pytest.raises(DomainError) as error:
        service.queue_collection(source_id, expected_version=0)
    assert error.value.status == 409
    workspace.db.execute("UPDATE sources SET enabled=0 WHERE id=?", (source_id,))
    service.update_collection(CollectionWrite(enabled=True, expected_version=1))
    assert service.queue_collection(source_id, manual=False) is None
    assert service.queue_collection(source_id, expected_version=1)["payload"]["manual"]
