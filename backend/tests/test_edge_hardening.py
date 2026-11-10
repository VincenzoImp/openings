"""Proxy-aware sign-in limits, pinned public fetches and single-use operational grants."""

import ipaddress
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from openings import __main__ as entrypoint
from openings import discovery as module
from openings.app import create_app
from openings.auth import COOKIE, LoginGuard
from openings.errors import DomainError

PASSWORD = "synthetic-password"


# --- SEC-3: trusted proxies and sign-in backoff -------------------------------------------


def test_trusted_proxies_default_to_none_and_normalize_entries():
    assert entrypoint.proxy_options("") == {"proxy_headers": False, "forwarded_allow_ips": ""}
    assert entrypoint.proxy_options(" , ") == {"proxy_headers": False, "forwarded_allow_ips": ""}
    assert entrypoint.proxy_options("172.18.0.5, 10.1.2.3/8 ,fd00::1") == {
        "proxy_headers": True,
        "forwarded_allow_ips": "172.18.0.5,10.0.0.0/8,fd00::1",
    }
    with pytest.raises(SystemExit, match="OPENINGS_TRUSTED_PROXIES"):
        entrypoint.proxy_options("proxy.example")
    with pytest.raises(SystemExit):
        entrypoint.proxy_options("*")


def test_entrypoint_passes_proxy_trust_to_uvicorn(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(entrypoint, "create_app", lambda database: "app")
    monkeypatch.setattr(entrypoint.uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))
    monkeypatch.setattr("sys.argv", ["openings", "--database", str(tmp_path / "x.sqlite")])
    monkeypatch.setenv("OPENINGS_TRUSTED_PROXIES", "192.0.2.10")
    entrypoint.main()
    monkeypatch.delenv("OPENINGS_TRUSTED_PROXIES")
    entrypoint.main()
    assert calls[0]["proxy_headers"] is True
    assert calls[0]["forwarded_allow_ips"] == "192.0.2.10"
    assert calls[1]["proxy_headers"] is False


def sign_in_client(tmp_path, peer, trusted):
    app = create_app(tmp_path / "proxy.sqlite", start_worker=False)
    app.state.auth.setup(PASSWORD)
    # Keep this test about per-client buckets; the global backoff is tested below.
    app.state.login_guard.free_failures = 1000
    return TestClient(ProxyHeadersMiddleware(app, trusted_hosts=trusted), client=(peer, 40000))


def login(client, password, forwarded=None):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return client.post("/api/v1/auth/login", json={"password": password}, headers=headers)


def test_trusted_proxy_gives_each_forwarded_client_its_own_bucket(tmp_path):
    with sign_in_client(tmp_path, "192.0.2.10", "192.0.2.10") as client:
        for _ in range(10):
            assert login(client, "wrong-password", "203.0.113.5").status_code == 401
        blocked = login(client, "wrong-password", "203.0.113.5")
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "login_rate"
        assert 1 <= int(blocked.headers["retry-after"]) <= 60
        # The owner behind the same proxy is not locked out by the attacker.
        assert login(client, PASSWORD, "203.0.113.6").status_code == 200


def test_untrusted_peer_cannot_spoof_forwarded_addresses(tmp_path):
    with sign_in_client(tmp_path, "198.51.100.7", "192.0.2.10") as client:
        for index in range(10):
            assert login(client, "wrong-password", f"203.0.113.{index}").status_code == 401
        assert login(client, "wrong-password", "203.0.113.99").status_code == 429


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


def test_global_backoff_spaces_attempts_and_clears_on_success():
    clock = Clock()
    guard = LoginGuard(free_failures=3, max_delay=4, max_wait=10, clock=clock)
    for index in range(3):
        assert guard.admit(f"198.51.100.{index}") == 0
        guard.failed()
    assert guard.delay() == 0
    guard.admit("198.51.100.10")
    guard.failed()
    assert guard.delay() == 1
    guard.failed()
    guard.failed()
    assert guard.delay() == 4
    guard.failed()
    assert guard.delay() == 4  # capped

    # Distributed attempts queue for global slots instead of running in parallel.
    assert [guard.admit(f"203.0.113.{index}") for index in range(3)] == [0, 4, 8]
    with pytest.raises(DomainError) as refused:
        guard.admit("203.0.113.50")
    assert refused.value.code == "login_backoff"
    assert refused.value.details["retry_after_seconds"] >= 1

    # The queue drains with time, so the owner gets a bounded turn.
    clock.value += 20
    assert guard.admit("192.0.2.1") <= 10
    guard.succeeded()
    assert guard.delay() == 0
    assert guard.admit("192.0.2.1") == 0


def test_global_backoff_forgets_old_failures_and_skips_setup():
    clock = Clock()
    guard = LoginGuard(free_failures=1, failure_window=60, clock=clock)
    guard.failed()
    guard.failed()
    assert guard.delay() == 1
    assert guard.admit("192.0.2.1", login=False) == 0
    clock.value += 61
    assert guard.delay() == 0


def test_client_buckets_stay_bounded():
    clock = Clock()
    guard = LoginGuard(max_clients=3, clock=clock)
    for index in range(10):
        guard.admit(f"203.0.113.{index}", login=False)
    assert len(guard.clients) <= 3


def test_failed_logins_feed_the_global_backoff(tmp_path):
    app = create_app(tmp_path / "backoff.sqlite", start_worker=False)
    app.state.auth.setup(PASSWORD)
    guard = app.state.login_guard
    guard.free_failures = 2
    with TestClient(app) as client:
        for _ in range(3):
            assert login(client, "wrong-password").status_code == 401
        assert guard.delay() == 1
        assert login(client, PASSWORD).status_code == 200
        assert guard.delay() == 0


# --- SEC-5: single-use operational grants ------------------------------------------------


def test_operational_grants_are_single_use_and_separate_from_sessions(tmp_path):
    app = create_app(tmp_path / "grants.sqlite", start_worker=False)
    auth = app.state.auth
    auth.setup(PASSWORD)
    grant = auth.operation_ticket("export")
    with TestClient(app) as client:
        assert client.get("/api/v1/export", headers={"X-Operational-Token": grant}).status_code == (
            200
        )
        reused = client.get("/api/v1/export", headers={"X-Operational-Token": grant})
        assert reused.status_code == 401
        assert reused.json()["error"]["code"] == "transfer_used"

        # Grants are not sessions, and session cookies are not grants.
        client.cookies.set(COOKIE, auth.operation_ticket("backup"))
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False
        cookie, _ = auth.login(PASSWORD)
        client.cookies.clear()
        forged = client.get("/api/v1/backup", headers={"X-Operational-Token": cookie})
        assert forged.status_code == 401
        assert forged.json()["error"]["code"] == "transfer_expired"


def test_used_grant_nonces_are_forgotten_after_expiry(tmp_path):
    app = create_app(tmp_path / "nonces.sqlite", start_worker=False)
    auth = app.state.auth
    auth.setup(PASSWORD)
    clock = Clock()
    auth.used_operations.clock = clock
    auth.authorize_operation(auth.operation_ticket("backup"), "backup")
    assert len(auth.used_operations.expiries) == 1
    clock.value += 200
    auth.authorize_operation(auth.operation_ticket("backup"), "backup")
    assert len(auth.used_operations.expiries) == 1


# --- SEC-4: DNS rebinding ----------------------------------------------------------------


@pytest.fixture
def local_server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", self.server.redirect)
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def synthetic_resolver(monkeypatch, answers):
    """Return the next scripted address for each lookup of a host."""
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


def test_rebinding_after_the_url_check_is_refused_before_connecting(monkeypatch, local_server):
    port = local_server.server_address[1]
    calls = synthetic_resolver(monkeypatch, {"rebind.test": ["93.184.216.34", "127.0.0.1"]})
    with pytest.raises(DomainError) as refused:
        module.fetch_bytes(f"http://rebind.test:{port}/secret")
    assert refused.value.code == "private_url"
    assert calls == ["rebind.test", "rebind.test"]
    assert local_server.seen == []


def test_connections_use_the_checked_address(monkeypatch, local_server):
    port = local_server.server_address[1]
    # Treat the synthetic server as public; the name itself is unresolvable by the system.
    monkeypatch.setattr(module, "is_public_address", lambda address: address == "127.0.0.1")
    synthetic_resolver(monkeypatch, {"pinned.test": ["127.0.0.1", "127.0.0.1"]})
    assert module.fetch_bytes(f"http://pinned.test:{port}/page") == b"internal"
    assert local_server.seen == ["/page"]


def test_every_redirect_hop_is_pinned(monkeypatch, local_server):
    port = local_server.server_address[1]
    local_server.redirect = f"http://rebind.test:{port}/secret"
    monkeypatch.setattr(module, "is_public_address", lambda address: address == "127.0.0.1")
    synthetic_resolver(
        monkeypatch,
        {"start.test": ["127.0.0.1", "127.0.0.1"], "rebind.test": ["127.0.0.1", "10.0.0.8"]},
    )
    with pytest.raises(DomainError) as refused:
        module.fetch_bytes(f"http://start.test:{port}/start")
    assert refused.value.code == "private_url"
    assert local_server.seen == ["/start"]
