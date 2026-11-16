"""A closed provider gate (the demo) refuses every provider request before any name lookup."""

import socket

import pytest
import requests

from openings.discovery.models import SourceCreate
from openings.errors import DomainError

SEARCH = {
    "query": "backend engineer python",
    "location": "Amsterdam",
    "providers": ["linkedin"],
    "results_wanted": 10,
    "hours_old": 72,
}


def code(response, status=409):
    assert response.status_code == status, response.text
    return response.json()["error"]["code"]


def test_a_closed_gate_contacts_no_job_site(app, client, monkeypatch):
    discovery = app.state.discovery
    discovery.providers.closed = True
    # A new enabled source queues no first check behind a closed gate.
    source = discovery.create_source(
        SourceCreate(
            name="Synthetic search",
            kind="jobspy",
            config=SEARCH,
            enabled=True,
            schedule={"kind": "interval", "minutes": 60},
        )
    )
    # Due long ago, so a scheduler tick would queue it.
    discovery.db.execute(
        "UPDATE sources SET created_at='2020-01-01T00:00:00+00:00',last_scheduled_at=NULL"
    )
    discovery.providers.closed = True
    touched = []

    def network(*args, **kwargs):
        touched.append(args)
        raise AssertionError("The network was used.")

    monkeypatch.setattr(socket, "getaddrinfo", network)
    monkeypatch.setattr(socket.socket, "connect", network)
    monkeypatch.setattr(socket.socket, "connect_ex", network)

    # Previews: a saved search, an unsaved feed and a company board.
    for body in (
        {"source_id": source["id"], "preview": True},
        {"preview": True, "kind": "rss", "url": "https://feed.example.org/jobs.rss"},
        {"preview": True, "kind": "greenhouse", "config": {"board": "example"}},
        {"preview": True, "kind": "hnhiring"},
    ):
        assert code(client.post("/api/v1/sources/run", json=body)) == "providers_closed"
    preview = {"kind": "jobspy", "config": SEARCH}
    assert code(client.post("/api/v1/sources/preview", json=preview)) == "providers_closed"
    # A job imported by its link.
    imported = client.post("/api/v1/jobs", json={"url": "https://jobs.example.org/1"})
    assert code(imported) == "providers_closed"
    # A manual run, over both routes.
    run = {"source_id": source["id"], "expected_version": source["version"]}
    assert code(client.post("/api/v1/sources/run", json=run)) == "providers_closed"
    one = client.post(
        f"/api/v1/sources/{source['id']}/run", json={"expected_version": source["version"]}
    )
    assert code(one) == "providers_closed"
    # Check all now: each source's result names the refusal.
    checked = client.post(
        "/api/v1/sources/bulk",
        json={
            "action": "run",
            "items": [{"id": source["id"], "expected_version": source["version"]}],
        },
    ).json()
    assert checked["failed"] == 1
    assert checked["items"][0]["error"]["code"] == "providers_closed"
    # A scheduler tick queues nothing, and no task is ever claimed.
    discovery.schedule_due()
    assert discovery.db.one("SELECT count(*) AS n FROM tasks")["n"] == 0
    assert discovery.claim_task("synthetic-worker") is None
    # Detail fetches and redirect hops of both clients go through the same refusal.
    with pytest.raises(DomainError) as refused:
        discovery.fetch_bytes("https://jobs.example.org/detail/1")
    assert refused.value.code == "providers_closed"
    with requests.Session() as session, pytest.raises(DomainError) as refused:
        discovery.http_budget("linkedin").request(session.request, "GET", "https://example.org/")
    assert refused.value.code == "providers_closed"
    assert touched == []
    # The source keeps its state, so the screens look real; nothing failed.
    kept = discovery.get_source(source["id"])
    assert kept["enabled"] and not kept["last_error"]
