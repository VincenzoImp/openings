"""Worker lanes on a fake clock: leases, retries, cancellation, cooldowns and schedules.

Providers are synthetic and nothing sleeps: the lane's idle waits advance the clock.
"""

import json
import logging
import threading
from datetime import UTC, datetime, timedelta

import pytest

from discovery_fixtures import patch_discovery
from openings import retention
from openings.collectors import policy
from openings.collectors.policy import ProviderDeferred, ProviderPatch
from openings.discovery import CollectionWrite, DiscoveryService, SourceCreate, SourcePatch, network
from openings.errors import DomainError
from openings.worker import Worker
from openings.workspace import Workspace

START = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)
BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/example/jobs"


class Clock:
    def __init__(self):
        self.moment = START

    def advance(self, seconds):
        self.moment += timedelta(seconds=seconds)

    def stamp(self, offset=0):
        return (self.moment + timedelta(seconds=offset)).isoformat(timespec="microseconds")

    @property
    def elapsed(self):
        return (self.moment - START).total_seconds()


class Lane:
    """The stop event of a lane: an idle wait advances the clock instead of sleeping."""

    def __init__(self, clock, idle):
        self.clock, self.idle, self.waits, self.stopped = clock, idle, [], False

    def is_set(self):
        return self.stopped

    def wait(self, seconds):
        self.waits.append(seconds)
        self.clock.advance(seconds)
        self.stopped = len(self.waits) >= self.idle
        return self.stopped


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.moment.astimezone(tz) if tz else clock.moment.replace(tzinfo=None)

    patch_discovery(monkeypatch, "datetime", Frozen)
    patch_discovery(monkeypatch, "now", clock.stamp)
    monkeypatch.setattr(policy, "now", clock.stamp)
    monkeypatch.setattr(retention, "now", clock.stamp)
    monkeypatch.setattr(policy.time, "time", lambda: clock.moment.timestamp())
    monkeypatch.setattr(
        policy.time, "sleep", lambda seconds: pytest.fail("The collection lane slept.")
    )
    return clock


def open_workspace(path):
    workspace = Workspace(path)
    service = DiscoveryService(workspace)
    workspace.discovery = service
    return workspace, service, Worker(workspace)


@pytest.fixture
def lane(tmp_path, clock):
    return open_workspace(tmp_path / "worker.sqlite")


def make_source(service, kind="greenhouse", board="example", **changes):
    return service.create_source(
        SourceCreate(name=f"{kind} {board}", kind=kind, config={"board": board}, **changes)
    )


def posting(key, board="example"):
    return {
        "title": f"Engineer {key}",
        "company": "Example",
        "posting": "Build reliable APIs.",
        "url": f"https://boards.greenhouse.io/{board}/jobs/{key}",
        "source_key": f"greenhouse:{board}:{key}",
    }


def emit(source, *keys):
    source["streamed"] = True
    for key in keys:
        source["on_item"](posting(key))


def collect(worker, clock, idle=1, owner="worker-a"):
    stopping = Lane(clock, idle)
    worker._loop(owner, stopping, "collect")
    return stopping


def row(service, task_id):
    return service.db.one("SELECT * FROM tasks WHERE id=?", (task_id,))


def titles(workspace):
    return sorted(job["title"] for job in workspace.list_jobs()["items"])


def test_transient_failures_back_off_then_fail_without_sleeping(lane, clock, monkeypatch):
    _, service, worker = lane
    source = make_source(service)
    task = service.queue_collection(source["id"])
    attempts = []

    def feed(source):
        attempts.append(clock.elapsed)
        raise DomainError(502, "source_http", "The source returned HTTP 503.")

    patch_discovery(monkeypatch, "fetch_postings", feed)
    stopping = collect(worker, clock, idle=200)
    # The first retry waits 15 seconds, the second 60; the third failure is final.
    assert attempts == [0, 15, 75]
    assert set(stopping.waits) == {1}
    failed = service.get_task(task["id"])
    assert failed["state"] == "failed" and failed["attempts"] == 3
    assert failed["error"] == "The source returned HTTP 503."
    assert failed["result"]["failure_attempts"] == 3
    assert [entry["state"] for entry in failed["result"]["attempt_history"]] == [
        "queued",
        "queued",
        "failed",
    ]
    assert service.get_source(source["id"])["last_error"] == "The source returned HTTP 503."


def test_invalid_configuration_fails_once_without_retry(lane, clock, monkeypatch):
    _, service, worker = lane
    task = service.queue_collection(make_source(service)["id"])
    attempts = []

    def feed(source):
        attempts.append(clock.elapsed)
        raise DomainError(422, "invalid_board", "This board does not exist.")

    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock, idle=200)
    failed = service.get_task(task["id"])
    assert attempts == [0]
    assert failed["state"] == "failed" and failed["result"]["failure_attempts"] == 1


def test_counts_accumulate_across_a_provider_wait_and_a_retry(lane, clock, monkeypatch):
    workspace, service, worker = lane
    source = make_source(service)
    task = service.queue_collection(source["id"])
    attempts, seen = [], []

    def feed(source):
        attempts.append(clock.elapsed)
        seen.append(dict(row(service, task["id"])))
        if len(attempts) == 1:
            emit(source, "1")
            raise ProviderDeferred("greenhouse", "provider_cooldown", clock.stamp(300))
        if len(attempts) == 2:
            emit(source, "1", "2")
            raise DomainError(502, "source_http", "The source returned HTTP 502.")
        emit(source, "1", "2", "3")
        return []

    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock, idle=400)
    assert attempts == [0, 300, 315]
    done = service.get_task(task["id"])
    assert done["state"] == "succeeded" and done["attempts"] == 3 and done["error"] is None
    # Each posting counts once, although later attempts observed it again.
    assert done["result"]["received"] == done["result"]["created"] == 3
    assert done["result"]["existing"] == done["result"]["invalid"] == 0
    # The provider wait did not spend the transient-error allowance.
    assert done["result"]["failure_attempts"] == 1
    assert [entry["reason"] for entry in done["result"]["attempt_history"]] == [
        "provider_cooldown",
        "source_http",
        None,
    ]
    assert [entry["attempt"] for entry in done["result"]["attempt_history"]] == [1, 2, 3]
    assert json.loads(seen[1]["result"])["received"] == 1
    assert json.loads(seen[2]["result"])["received"] == 2
    assert service.get_run(task["run_id"])["counts"]["created"] == 3
    assert titles(workspace) == ["Engineer 1", "Engineer 2", "Engineer 3"]


def test_long_provider_wait_releases_the_lane_for_other_work(lane, clock, monkeypatch):
    _, service, worker = lane
    for provider in ("greenhouse", "lever"):
        service.update_provider(provider, ProviderPatch(expected_version=1, min_interval_seconds=0))
    # A real 503 with Retry-After leaves a durable ten-minute cooldown on one provider.
    probe = service.http_budget("greenhouse")
    probe.before("GET", BOARD_URL)
    probe.after(503, {"Retry-After": "600"})
    waiting = service.queue_collection(make_source(service)["id"])
    clock.advance(1)
    other = service.queue_collection(make_source(service, "lever", "other")["id"])
    attempts = []

    urls = {"greenhouse": BOARD_URL, "lever": "https://api.lever.co/v0/postings/other"}

    def feed(source):
        attempts.append((source["kind"], clock.elapsed))
        budget = network.HTTP_BUDGET.get()
        budget.before("GET", urls[source["kind"]])
        budget.after(200)
        return [posting("1", source["kind"])]

    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock, idle=5)
    # The blocked task yielded at once; the other provider ran without waiting for it.
    assert attempts == [("greenhouse", 1), ("lever", 1)]
    assert service.get_task(other["id"])["state"] == "succeeded"
    parked = row(service, waiting["id"])
    assert parked["state"] == "queued" and parked["lease_owner"] is None
    assert parked["lease_until"] is None
    assert parked["next_run_at"] == (START + timedelta(seconds=600)).isoformat(
        timespec="microseconds"
    )
    assert service.providers.get("greenhouse")["runtime"]["total_requests"] == 1

    collect(worker, clock, idle=600)
    assert attempts[2] == ("greenhouse", 600) and len(attempts) == 3
    resumed = service.get_task(waiting["id"])
    assert resumed["state"] == "succeeded" and resumed["result"]["failure_attempts"] == 0
    assert resumed["result"]["http_requests"] == 1


def test_server_cooldown_survives_a_restart_and_holds_every_task(lane, clock, monkeypatch):
    workspace, service, worker = lane
    service.update_provider("greenhouse", ProviderPatch(expected_version=1, min_interval_seconds=0))
    first = service.queue_collection(make_source(service)["id"])
    clock.advance(1)
    second = service.queue_collection(make_source(service, board="second")["id"])
    sent = []

    def feed(source):
        budget = network.HTTP_BUDGET.get()
        budget.before("GET", BOARD_URL)
        sent.append(clock.elapsed)
        if len(sent) == 1:
            budget.after(429, {"Retry-After": "120"})
            return []
        budget.after(200)
        return [posting(source["config"]["board"], source["config"]["board"])]

    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock, idle=3)
    until = (START + timedelta(seconds=121)).isoformat(timespec="microseconds")
    # One throttled response; the second task was held by the gate before any request.
    assert sent == [1]
    for task in (first, second):
        held = service.get_task(task["id"])
        assert held["state"] == "queued" and held["next_run_at"] == until
        assert held["result"]["attempt_history"][-1]["reason"] == "provider_cooldown"
        assert held["result"]["failure_attempts"] == 0

    restarted_workspace, restarted, restarted_worker = open_workspace(workspace.db.path)
    assert restarted.providers.get("greenhouse")["runtime"]["cooldown_until"] == until
    with pytest.raises(ProviderDeferred) as deferred:
        restarted.http_budget("greenhouse").before("GET", BOARD_URL)
    assert deferred.value.next_run_at == until
    collect(restarted_worker, clock, idle=100, owner="worker-b")
    assert sent == [1] and clock.elapsed < 121
    collect(restarted_worker, clock, idle=30, owner="worker-b")
    assert sent == [1, 121, 121]
    assert [restarted.get_task(task["id"])["state"] for task in (first, second)] == [
        "succeeded",
        "succeeded",
    ]
    assert restarted.providers.get("greenhouse")["runtime"]["total_requests"] == 3
    assert titles(restarted_workspace) == ["Engineer example", "Engineer second"]


def test_expired_lease_is_reclaimed_and_stale_work_cannot_overwrite_it(lane, clock, monkeypatch):
    workspace, service, worker = lane
    rival = Worker(workspace)
    source = make_source(service)
    task = service.queue_collection(source["id"])
    attempts = []

    def feed(source):
        attempts.append(clock.elapsed)
        if len(attempts) == 1:
            # The first owner stalls past its 90-second lease without a renewal;
            # a second lane takes the task over and finishes it meanwhile.
            clock.advance(91)
            collect(rival, clock, owner="worker-b")
            assert service.get_task(task["id"])["state"] == "succeeded"
            return [posting("stale")]
        return [posting("current")]

    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock)
    done = service.get_task(task["id"])
    assert attempts == [0, 91]
    assert done["state"] == "succeeded" and done["attempts"] == 2 and done["error"] is None
    assert done["result"]["created"] == 1 and done["result"]["received"] == 1
    # Only the current owner's attempt is recorded and archived.
    assert [entry["attempt"] for entry in done["result"]["attempt_history"]] == [2]
    assert titles(workspace) == ["Engineer current"]
    assert service.get_source(source["id"])["last_error"] is None


def test_heartbeat_keeps_a_long_task_leased(lane, clock, monkeypatch):
    workspace, service, worker = lane
    rival = Worker(workspace)
    worker.heartbeat_seconds = 0.001
    task = service.queue_collection(make_source(service)["id"])
    beat = threading.Event()
    heartbeat = service.heartbeat

    def observed(task_id, owner):
        kept = heartbeat(task_id, owner)
        beat.set()
        return kept

    def renewed(offset):
        expected = (START + timedelta(seconds=offset + 90)).isoformat(timespec="microseconds")
        for _ in range(2000):
            if row(service, task["id"])["lease_until"] == expected:
                return True
            beat.clear()
            if not beat.wait(5):
                break  # no renewal arrived at all
        return False

    def feed(source):
        clock.advance(60)
        assert renewed(60)
        clock.advance(60)
        assert renewed(120)
        # Two minutes in, the original lease would have expired; the renewed one holds.
        assert rival.discovery.claim_task("worker-b", "collect") is None
        return [posting("1")]

    monkeypatch.setattr(service, "heartbeat", observed)
    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock)
    done = service.get_task(task["id"])
    assert done["state"] == "succeeded" and done["attempts"] == 1
    assert row(service, task["id"])["lease_until"] is None
    assert not [thread for thread in threading.enumerate() if thread.name == "openings-lease"]


class Stub:
    """A discovery double for lane mechanics that need no database."""

    def __init__(self, claims=(), failures=0):
        self.claims, self.failures = list(claims), failures
        self.beats, self.ran, self.cycles = [], [], 0
        self.lost = threading.Event()

    def heartbeat(self, task_id, owner):
        self.beats.append((task_id, owner))
        if len(self.beats) == 1:
            raise RuntimeError("database is locked")
        self.lost.set()
        return False

    def run_task(self, task, owner):
        self.ran.append((task["id"], owner))

    def claim_task(self, owner, kind):
        self.cycles += 1
        if self.cycles <= self.failures:
            raise RuntimeError("database is locked")
        return self.claims.pop(0) if self.claims else None

    def schedule_due(self, stopping):
        self.cycles += 1
        if self.cycles <= self.failures:
            raise RuntimeError("database is locked")


def test_heartbeat_survives_an_error_and_ends_once_the_lease_is_lost(caplog):
    stub = Stub()
    stub.run_task = lambda task, owner: stub.ran.append(stub.lost.wait(5))
    worker = Worker(None, stub)
    worker.heartbeat_seconds = 0.001
    with caplog.at_level(logging.WARNING, logger="openings.worker"):
        worker._run({"id": "task"}, "owner", threading.Event())
    # One failed renewal is tolerated; a lost lease ends the renewals.
    assert stub.ran == [True]
    assert stub.beats == [("task", "owner")] * 2
    assert "Task heartbeat failed" in caplog.text


def test_a_stopping_lane_does_not_start_claimed_work():
    stub = Stub()
    stopping = threading.Event()
    stopping.set()
    Worker(None, stub)._run({"id": "task"}, "owner", stopping)
    assert stub.ran == [] and stub.beats == []


def test_lanes_survive_a_failed_cycle(clock, caplog):
    stub = Stub(claims=[{"id": "first"}, {"id": "second"}], failures=1)
    worker = Worker(None, stub)
    with caplog.at_level(logging.ERROR, logger="openings.worker"):
        stopping = collect(worker, clock, idle=2)
    # The failed cycle and the empty queue each idle one second; ready work runs back to back.
    assert stub.ran == [("first", "worker-a"), ("second", "worker-a")]
    assert stopping.waits == [1, 1]
    assert "background worker could not complete this cycle" in caplog.text

    scheduler = Stub(failures=1)
    stopping = Lane(clock, 3)
    with caplog.at_level(logging.ERROR, logger="openings.worker"):
        Worker(None, scheduler)._schedule_loop(stopping)
    assert scheduler.cycles == 3 and stopping.waits == [15, 15, 15]
    assert "scheduler could not complete this cycle" in caplog.text


def test_cancelling_the_run_stops_active_work_for_good(lane, clock, monkeypatch):
    workspace, service, worker = lane
    source = make_source(service)
    task = service.queue_collection(source["id"])
    attempts = []

    def feed(source):
        attempts.append(clock.elapsed)
        emit(source, "1")
        service.cancel_run(task["run_id"])
        with pytest.raises(DomainError) as refused:
            network.HTTP_BUDGET.get().before("GET", BOARD_URL)
        assert refused.value.code == "task_cancelled"
        emit(source, "2")
        pytest.fail("A cancelled run kept collecting.")

    patch_discovery(monkeypatch, "fetch_postings", feed)
    collect(worker, clock, idle=200)
    cancelled = service.get_task(task["id"])
    # The interrupted attempt is neither recorded as a failure nor retried.
    assert attempts == [0]
    assert cancelled["state"] == "cancelled" and cancelled["error"] is None
    assert cancelled["result"]["received"] == 1
    assert "failure_attempts" not in cancelled["result"]
    assert service.get_run(task["run_id"])["state"] == "cancelled"
    assert titles(workspace) == ["Engineer 1"]
    assert service.providers.get("greenhouse")["runtime"]["total_requests"] == 0
    assert service.get_source(source["id"])["last_error"] is None


def test_missed_daily_slots_coalesce_into_one_run(lane, clock, monkeypatch):
    _, service, worker = lane
    schedule = {"kind": "daily", "times": ["06:00", "12:00", "18:00"], "timezone": "UTC"}
    source = make_source(service, enabled=True, schedule=schedule)
    patch_discovery(monkeypatch, "fetch_postings", lambda source: [posting("1")])

    def runs():
        return service.list_runs(source_id=source["id"])["items"]

    worker._schedule_loop(Lane(clock, 2))
    assert runs() == []

    # Two days without a scheduler leave seven elapsed slots.
    clock.advance(2 * 86400 + 5 * 3600 - 30)
    stopping = Lane(clock, 3)
    worker._schedule_loop(stopping)
    assert stopping.waits == [15, 15, 15]
    assert len(runs()) == 1
    planned = service.get_run(runs()[0]["id"])
    assert planned["planned_at"] == "2026-03-04T12:00:00.000000+00:00"
    assert len(planned["task_ids"]) == 1 and planned["state"] == "queued"

    # A slot that elapses while the run is still active is absorbed by it.
    clock.advance(6 * 3600)
    worker._schedule_loop(Lane(clock, 1))
    assert len(runs()) == 1
    collect(worker, clock)
    assert service.get_run(planned["id"])["state"] == "succeeded"
    worker._schedule_loop(Lane(clock, 1))
    assert len(runs()) == 1

    clock.advance(12 * 3600)
    worker._schedule_loop(Lane(clock, 1))
    assert sorted(service.get_run(run["id"])["planned_at"] for run in runs()) == [
        "2026-03-04T12:00:00.000000+00:00",
        "2026-03-05T06:00:00.000000+00:00",
    ]


def test_paused_automation_schedules_nothing_until_resumed(lane, clock):
    _, service, worker = lane
    source = make_source(service, enabled=True)  # default schedule: one run a day
    paused = make_source(service, board="paused")
    service.update_collection(CollectionWrite(enabled=False, expected_version=0))
    clock.advance(3 * 86400)
    worker._schedule_loop(Lane(clock, 2))
    assert service.list_runs()["total"] == 0

    service.update_collection(CollectionWrite(enabled=True, expected_version=1))
    worker._schedule_loop(Lane(clock, 2))
    # One run for the enabled source, however many intervals passed; none for the paused one.
    assert [run["source_id"] for run in service.list_runs()["items"]] == [source["id"]]
    assert service.list_runs(source_id=paused["id"])["total"] == 0

    current = service.get_source(source["id"])
    service.update_source(
        source["id"], SourcePatch(expected_version=current["version"], enabled=False)
    )
    service.cancel_run(service.list_runs()["items"][0]["id"])
    clock.advance(3 * 86400)
    worker._schedule_loop(Lane(clock, 2))
    assert service.list_runs()["total"] == 1


def test_stop_releases_the_lease_and_a_restart_uses_a_new_owner(tmp_path, monkeypatch):
    workspace, service, worker = open_workspace(tmp_path / "threads.sqlite")
    worker.stop()  # stopping a worker that never started is harmless
    task = service.queue_collection(make_source(service)["id"])
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    attempts = []

    def feed(source):
        attempts.append(threading.current_thread().name)
        if len(attempts) == 1:
            entered.set()
            assert release.wait(10)
            return [posting("stale")]
        return [posting("current")]

    run_task = service.run_task

    def observed(claimed, owner):
        run_task(claimed, owner)
        if service.get_task(task["id"])["state"] == "succeeded":
            finished.set()

    patch_discovery(monkeypatch, "fetch_postings", feed)
    monkeypatch.setattr(service, "run_task", observed)
    try:
        worker.start()
        first_owner, first_threads = worker.owner, list(worker.threads)
        worker.start()  # already running: the same lanes continue
        assert worker.owner == first_owner and worker.threads == first_threads
        assert [thread.name for thread in first_threads] == [
            "openings-scheduler",
            "openings-collect",
        ]
        assert entered.wait(10)
        assert row(service, task["id"])["lease_owner"] == first_owner

        worker.stop(timeout=0)
        released = row(service, task["id"])
        assert released["state"] == "queued" and released["lease_owner"] is None

        worker.start()
        assert worker.owner != first_owner
        assert finished.wait(10)
        # The interrupted attempt now finishes late; it must not replace the result.
        release.set()
        for thread in first_threads:
            thread.join(timeout=10)
    finally:
        release.set()
        worker.stop()
    assert not any(thread.is_alive() for thread in first_threads + worker.threads)
    done = service.get_task(task["id"])
    assert done["state"] == "succeeded" and done["attempts"] == 2
    assert done["result"]["created"] == 1
    assert [entry["attempt"] for entry in done["result"]["attempt_history"]] == [2]
    assert titles(workspace) == ["Engineer current"]
