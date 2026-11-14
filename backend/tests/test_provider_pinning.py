"""Public fetches and provider sessions (requests, curl) connect only to the checked address."""

import socket

import pytest
from curl_cffi import CurlOpt

from discovery_fixtures import open_gate, patch_discovery, synthetic_resolver
from openings._vendor.jobspy.util import RequestsRotating, TLSRotating
from openings.collectors.pinning import PinnedAdapter, curl_resolve_entry
from openings.discovery import DiscoveryService, network
from openings.errors import DomainError


@pytest.fixture
def gate(workspace):
    """The provider gate with its real URL checks; only DNS answers are scripted."""
    service = DiscoveryService(workspace)
    open_gate(service, "manual")
    return service


def session_for(gate, session_class):
    session = session_class()
    session.transport = gate.http_budget("manual")
    return session


def runtime(gate):
    return gate.providers.get("manual")["runtime"]


def test_a_public_fetch_connects_only_to_the_checked_address(gate, monkeypatch, local_server):
    """``fetch_bytes`` (httpx): each hop is checked, then dialed at the checked address."""
    port = local_server.server_address[1]
    budget = gate.http_budget("manual")
    with monkeypatch.context() as public:
        patch_discovery(public, "is_public_address", lambda address: address == "127.0.0.1")
        synthetic_resolver(public, {"pinned.test": ["127.0.0.1"] * 2})
        assert network.fetch_bytes(f"http://pinned.test:{port}/page", budget=budget) == b"internal"
        assert local_server.seen == [("pinned.test", "/page")]
        local_server.redirect = f"http://rebind.test:{port}/secret"
        synthetic_resolver(
            public,
            {"start.test": ["127.0.0.1", "127.0.0.1"], "rebind.test": ["127.0.0.1", "10.0.0.8"]},
        )
        with pytest.raises(DomainError) as refused:
            network.fetch_bytes(f"http://start.test:{port}/start", budget=budget)
        assert refused.value.code == "private_url"
        assert local_server.seen[1:] == [("start.test", "/start")]
    # A name that rebinds to a private address after the URL check is refused unconnected.
    calls = synthetic_resolver(monkeypatch, {"rebind.test": ["93.184.216.34", "127.0.0.1"]})
    with pytest.raises(DomainError) as refused:
        network.fetch_bytes(f"http://rebind.test:{port}/secret", budget=budget)
    assert refused.value.code == "private_url" and calls == ["rebind.test", "rebind.test"]
    assert len(local_server.seen) == 2


@pytest.mark.parametrize("session_class", [RequestsRotating, TLSRotating])
def test_a_provider_session_connects_only_to_the_checked_address(
    gate, monkeypatch, local_server, session_class
):
    """Each case uses a fresh session, so no connection is reused across them."""
    port = local_server.server_address[1]

    def get(url):
        session = session_for(gate, session_class)
        try:
            return session.get(url)
        finally:
            session.close()

    # A public name is dialed at the address that was checked, once per request.
    # The synthetic server counts as public; its name is unresolvable by the system.
    with monkeypatch.context() as public:
        patch_discovery(public, "is_public_address", lambda address: address == "127.0.0.1")
        calls = synthetic_resolver(public, {"pinned.test": ["127.0.0.1"] * 4})
        for path in ("/first", "/second"):
            assert get(f"http://pinned.test:{port}{path}").content == b"internal"
        assert local_server.seen == [("pinned.test", "/first"), ("pinned.test", "/second")]
        assert set(calls) == {"pinned.test"}
        assert runtime(gate)["total_requests"] == 2 and runtime(gate)["last_status"] == 200

        # Every redirect hop is checked and pinned again.
        local_server.redirect = f"http://rebind.test:{port}/secret"
        synthetic_resolver(
            public,
            {"start.test": ["127.0.0.1", "127.0.0.1"], "rebind.test": ["127.0.0.1", "10.0.0.8"]},
        )
        with pytest.raises(DomainError) as refused:
            get(f"http://start.test:{port}/start")
        assert refused.value.code == "private_url"
        assert local_server.seen[2:] == [("start.test", "/start")]
        assert runtime(gate)["total_requests"] == 4

    # A name that rebinds to a private address after the check is refused inside the gate:
    # the attempt is reserved and recorded, without a response.
    calls = synthetic_resolver(monkeypatch, {"rebind.test": ["93.184.216.34", "127.0.0.1"]})
    with pytest.raises(DomainError) as refused:
        get(f"http://rebind.test:{port}/secret")
    assert refused.value.code == "private_url" and calls == ["rebind.test", "rebind.test"]
    assert runtime(gate)["total_requests"] == 5
    assert runtime(gate)["last_status"] is None and runtime(gate)["last_error"] == "DomainError"

    # A private literal address is refused at connection time alone.
    session = session_for(gate, session_class)
    session.transport.validate_url = None
    try:
        with pytest.raises(DomainError) as refused:
            session.get(f"http://127.0.0.1:{port}/secret")
    finally:
        session.close()
    assert refused.value.code == "private_url"
    assert len(local_server.seen) == 3


def test_requests_adapter_is_mounted_once_and_tries_the_checked_addresses_in_turn(
    gate, monkeypatch, local_server
):
    port = local_server.server_address[1]
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    refused_port = closed.getsockname()[1]
    closed.close()
    session = session_for(gate, RequestsRotating)
    budget = session.transport
    budget.validate_url = None
    dialed = []

    def resolve(host, port_):
        dialed.append((host, port_))
        return ["::1", "127.0.0.1"]  # nothing listens on the first address

    budget.resolve_host = resolve
    try:
        assert session.get(f"http://one.test:{port}/a").content == b"internal"
        adapter = session.adapters["https://"]
        assert isinstance(adapter, PinnedAdapter) and session.adapters["http://"] is adapter
        assert session.get(f"http://one.test:{port}/b").content == b"internal"
        assert session.adapters["https://"] is adapter
        # Every new connection is checked when it is dialed.
        assert dialed == [("one.test", port)] * 2
        with pytest.raises(Exception) as failed:
            session.get(f"http://two.test:{refused_port}/c")
        assert type(failed.value).__name__ == "ConnectionError"
        assert dialed[-1] == ("two.test", refused_port)
    finally:
        session.close()
    assert [path for _, path in local_server.seen] == ["/a", "/b"]
    assert gate.providers.get("manual")["runtime"]["last_error"] == "ConnectionError"


def test_curl_entries_cover_every_checked_address_and_replace_the_previous_pin(gate):
    answers = {"a.test": ["203.0.113.7", "2001:db8::7"], "203.0.113.9": ["203.0.113.9"]}

    def resolve(host, port):
        return answers[host]

    assert (
        curl_resolve_entry("https://a.test/jobs", resolve) == "a.test:443:203.0.113.7,[2001:db8::7]"
    )
    assert curl_resolve_entry("http://a.test:8080/", resolve).startswith("a.test:8080:")
    assert curl_resolve_entry("https://203.0.113.9/jobs", resolve) is None

    session = TLSRotating()
    budget = gate.http_budget("manual")
    budget.validate_url, budget.resolve_host = None, resolve
    sent = []

    def send(method, url, **kwargs):
        sent.append(dict(session.curl_options))
        raise RuntimeError("synthetic transport")

    send.__self__ = session
    try:
        for url in ("https://a.test/jobs", "https://203.0.113.9/jobs"):
            with pytest.raises(RuntimeError):
                budget.request(send, "GET", url)
    finally:
        session.close()
    assert sent[0][CurlOpt.RESOLVE] == ["a.test:443:203.0.113.7,[2001:db8::7]"]
    assert CurlOpt.RESOLVE not in sent[1]
