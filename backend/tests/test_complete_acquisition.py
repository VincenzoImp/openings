"""Real gate, parser and archive behavior across incomplete collection attempts."""

import json
from datetime import datetime, timezone

import pytest
import requests

from openings import discovery as module
from openings._vendor.jobspy import linkedin
from openings.collectors import policy
from openings.collectors.policy import ProviderDeferred, ProviderPatch
from openings.discovery import DiscoveryService, SourceCreate
from openings.workspace import Workspace


def response(url, status, body, headers=None):
    result = requests.Response()
    result.url, result.status_code = url, status
    result.headers.update(headers or {})
    result._content = body.encode()
    result._content_consumed = True
    return result


def cards(count):
    return "".join(
        f'<div class="base-search-card" data-entity-urn="urn:li:jobPosting:{index}">'
        '<h3 class="base-search-card__title">Engineer</h3>'
        '<h4 class="base-search-card__subtitle">Example</h4>'
        '<span class="job-search-card__location">Example City</span></div>'
        for index in range(1, count + 1)
    )


def transport(monkeypatch, send):
    class Session:
        def __init__(self, gate):
            self.gate = gate

        def get(self, url, **kwargs):
            return self.gate.request(send, "GET", url, **kwargs)

        def close(self):
            pass

    monkeypatch.setattr(
        linkedin, "create_session", lambda *args, transport=None, **kwargs: Session(transport)
    )


def run_next(service):
    task = service.claim_task("collector", "collect")
    assert task
    service.run_task(task, "collector")
    return service.get_task(task["id"])


def test_complete_jobs_only_across_batch_cooldown_and_restart(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "complete.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    workspace.set_settings("profile", {"summary": "Backend engineer"})
    workspace.set_settings("scoring", {"enabled": True, "auto_rescore_updates": False})
    service.update_provider("linkedin", ProviderPatch(expected_version=1, min_interval_seconds=0))
    monkeypatch.setattr(module, "public_url", lambda url: url)
    monkeypatch.setattr(policy, "REQUEST_BATCH_SIZE", 2)
    clock = [datetime.fromtimestamp(policy.time.time(), timezone.utc).timestamp()]
    monkeypatch.setattr(policy.time, "time", lambda: clock[0])
    monkeypatch.setattr(
        module, "now", lambda: datetime.fromtimestamp(clock[0], timezone.utc).isoformat()
    )
    calls = []

    def send(method, url, **kwargs):
        calls.append(url)
        if "seeMore" in url:
            return response(url, 200, cards(2))
        if url.endswith("/2") and calls.count(url) == 1:
            return response(url, 429, "", {"Retry-After": "120"})
        return response(
            url, 200, '<div class="show-more-less-html__markup">Build reliable APIs.</div>'
        )

    transport(monkeypatch, send)
    source = service.create_source(
        SourceCreate(
            name="Engineering",
            kind="jobspy",
            config={"query": "engineer", "providers": ["linkedin"], "results_wanted": 2},
        )
    )
    queued = service.queue_collection(source["id"])
    first = run_next(service)
    assert first["state"] == "queued" and first["result"]["created"] == 1
    assert first["result"]["pending_descriptions"] == 1
    assert first["result"]["attempt_history"][-1]["reason"] == "collection_batch"
    assert workspace.list_jobs(complete=False)["total"] == 0
    assert service.list_tasks(kind="score")["total"] == 1
    clock[0] += 2
    second = run_next(service)
    assert second["state"] == "queued" and second["result"]["created"] == 1
    assert second["result"]["attempt_history"][-1]["reason"] == "provider_cooldown"
    assert workspace.list_jobs()["total"] == 1

    restarted_workspace = Workspace(workspace.db.path)
    restarted = DiscoveryService(restarted_workspace)
    restarted_workspace.discovery = restarted
    with pytest.raises(ProviderDeferred):
        restarted.http_budget("linkedin").before("GET", "https://www.linkedin.com/jobs/view/2")
    assert len(calls) == 3
    clock[0] += 121
    final = run_next(restarted)
    assert final["state"] == "succeeded"
    assert final["result"]["received"] == final["result"]["created"] == 2
    assert final["result"]["existing"] == final["result"]["pending_descriptions"] == 0
    assert restarted_workspace.list_jobs(complete=True)["total"] == 2
    assert restarted_workspace.list_jobs(complete=False)["total"] == 0
    assert restarted.list_tasks(kind="score")["total"] == 2
    assert len(calls) == 4 and sum("seeMore" in url for url in calls) == 1
    assert calls.count("https://www.linkedin.com/jobs/view/1") == 1
    assert restarted.get_run(queued["run_id"])["counts"]["created"] == 2
    runtime = json.loads(
        restarted.db.one("SELECT runtime FROM providers WHERE id='linkedin'")["runtime"]
    )
    assert "runs" not in runtime


@pytest.mark.parametrize("status,path", [(403, "/jobs/view/1"), (200, "/authwall")])
def test_linkedin_provider_access_failure_stops_detail_loop(tmp_path, monkeypatch, status, path):
    workspace = Workspace(tmp_path / "access.sqlite")
    service = DiscoveryService(workspace)
    service.update_provider("linkedin", ProviderPatch(expected_version=1, min_interval_seconds=0))
    monkeypatch.setattr(module, "public_url", lambda url: url)
    calls = []

    def send(method, url, **kwargs):
        calls.append(url)
        return (
            response(url, 200, cards(3))
            if "seeMore" in url
            else response("https://www.linkedin.com" + path, status, "Sign in")
        )

    transport(monkeypatch, send)
    source = service.create_source(
        SourceCreate(
            name="Engineering",
            kind="jobspy",
            config={"query": "engineer", "providers": ["linkedin"], "results_wanted": 3},
        )
    )
    service.queue_collection(source["id"])
    result = run_next(service)
    assert result["state"] == "failed"
    assert result["result"]["attempt_history"][-1]["reason"] == "provider_access"
    assert len(calls) == 2 and workspace.list_jobs()["total"] == 0
    assert result["result"]["pending_descriptions"] == 3
