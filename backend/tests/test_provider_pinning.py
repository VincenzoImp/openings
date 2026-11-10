"""Provider sessions (requests and curl) connect only to the checked public address."""

import ipaddress
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from curl_cffi import CurlOpt

from openings import discovery as module
from openings._vendor.jobspy.util import RequestsRotating, TLSRotating
from openings.collectors.pinning import PinnedAdapter, curl_resolve_entry
from openings.collectors.policy import ProviderPatch
from openings.discovery import DiscoveryService
from openings.errors import DomainError
from openings.workspace import Workspace

SESSIONS = pytest.mark.parametrize("session_class", [RequestsRotating, TLSRotating])


@pytest.fixture
def local_server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.headers["Host"].split(":")[0], self.path))
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", self.server.redirect)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b"internal"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.seen = seen
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def gate(tmp_path, monkeypatch):
    service = DiscoveryService(Workspace(tmp_path / "pinning.sqlite"))
    service.update_provider("manual", ProviderPatch(expected_version=1, min_interval_seconds=0))
    return service


def synthetic_resolver(monkeypatch, answers):
    """Return the next scripted address for each lookup of a host; names never reach DNS."""
    calls = []

    def resolve(host, port, *args, **kwargs):
        if host in answers:
            calls.append(host)
            address = answers[host].pop(0)
        else:
            address = str(ipaddress.ip_address(host))  # the pinned dial itself
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(module.socket, "getaddrinfo", resolve)
    return calls


def session_for(gate, session_class):
    session = session_class()
    session.transport = gate.http_budget("manual")
    return session


def runtime(gate):
    return gate.providers.get("manual")["runtime"]


@SESSIONS
def test_provider_sessions_connect_to_the_checked_address(
    gate, monkeypatch, local_server, session_class
):
    port = local_server.server_address[1]
    # Treat the synthetic server as public; the name itself is unresolvable by the system.
    monkeypatch.setattr(module, "is_public_address", lambda address: address == "127.0.0.1")
    calls = synthetic_resolver(monkeypatch, {"pinned.test": ["127.0.0.1"] * 4})
    session = session_for(gate, session_class)
    try:
        for path in ("/first", "/second"):
            assert session.get(f"http://pinned.test:{port}{path}").content == b"internal"
    finally:
        session.close()
    assert local_server.seen == [("pinned.test", "/first"), ("pinned.test", "/second")]
    assert set(calls) == {"pinned.test"}
    assert runtime(gate)["total_requests"] == 2 and runtime(gate)["last_status"] == 200


@SESSIONS
def test_rebinding_after_the_url_check_is_refused_inside_the_gate(
    gate, monkeypatch, local_server, session_class
):
    port = local_server.server_address[1]
    calls = synthetic_resolver(monkeypatch, {"rebind.test": ["93.184.216.34", "127.0.0.1"]})
    session = session_for(gate, session_class)
    try:
        with pytest.raises(DomainError) as refused:
            session.get(f"http://rebind.test:{port}/secret")
    finally:
        session.close()
    assert refused.value.code == "private_url"
    assert calls == ["rebind.test", "rebind.test"]
    assert local_server.seen == []
    # The refused attempt was reserved and recorded by the provider gate, without a response.
    assert runtime(gate)["total_requests"] == 1
    assert runtime(gate)["last_status"] is None and runtime(gate)["last_error"] == "DomainError"


@SESSIONS
def test_every_redirect_hop_of_a_provider_session_is_pinned(
    gate, monkeypatch, local_server, session_class
):
    port = local_server.server_address[1]
    local_server.redirect = f"http://rebind.test:{port}/secret"
    monkeypatch.setattr(module, "is_public_address", lambda address: address == "127.0.0.1")
    synthetic_resolver(
        monkeypatch,
        {"start.test": ["127.0.0.1", "127.0.0.1"], "rebind.test": ["127.0.0.1", "10.0.0.8"]},
    )
    session = session_for(gate, session_class)
    try:
        with pytest.raises(DomainError) as refused:
            session.get(f"http://start.test:{port}/start")
    finally:
        session.close()
    assert refused.value.code == "private_url"
    assert local_server.seen == [("start.test", "/start")]
    assert runtime(gate)["total_requests"] == 2


@SESSIONS
def test_private_literal_addresses_are_refused(gate, local_server, session_class):
    port = local_server.server_address[1]
    session = session_for(gate, session_class)
    session.transport.validate_url = None  # only the connection-time check remains
    try:
        with pytest.raises(DomainError) as refused:
            session.get(f"http://127.0.0.1:{port}/secret")
    finally:
        session.close()
    assert refused.value.code == "private_url" and local_server.seen == []


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
    resolve = lambda host, port: answers[host]  # noqa: E731
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
