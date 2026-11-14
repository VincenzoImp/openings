"""Proxy-aware sign-in limits and single-use operational grants."""

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from conftest import BASE_URL, PASSWORD
from doubles import Clock
from openings import __main__ as entrypoint
from openings.auth import COOKIE, LoginGuard
from openings.errors import DomainError

# --- SEC-3: trusted proxies and sign-in backoff -------------------------------------------


def test_trusted_proxies_default_to_none_normalize_and_reach_uvicorn(monkeypatch, tmp_path):
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


def login(client, password, forwarded=None):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return client.post("/api/v1/auth/login", json={"password": password}, headers=headers)


def test_forwarded_clients_get_their_own_bucket_only_behind_a_trusted_proxy(app):
    # Keep this test about per-client buckets; the global backoff is tested below.
    app.state.login_guard.free_failures = 1000
    proxied = ProxyHeadersMiddleware(app, trusted_hosts="192.0.2.10")
    trusted = TestClient(proxied, base_url=BASE_URL, client=("192.0.2.10", 40000))
    for _ in range(10):
        assert login(trusted, "wrong-password", "203.0.113.5").status_code == 401
    blocked = login(trusted, "wrong-password", "203.0.113.5")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "login_rate"
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    # The owner behind the same proxy is not locked out by the attacker.
    assert login(trusted, PASSWORD, "203.0.113.6").status_code == 200

    # An untrusted peer cannot spread its attempts over spoofed addresses.
    untrusted = TestClient(proxied, base_url=BASE_URL, client=("198.51.100.7", 40000))
    for index in range(10):
        assert login(untrusted, "wrong-password", f"203.0.113.{index}").status_code == 401
    assert login(untrusted, "wrong-password", "203.0.113.99").status_code == 429


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
    clock.advance(20)
    assert guard.admit("192.0.2.1") <= 10
    guard.succeeded()
    assert guard.delay() == 0
    assert guard.admit("192.0.2.1") == 0


def test_global_backoff_forgets_old_failures_skips_setup_and_bounds_clients():
    clock = Clock()
    guard = LoginGuard(free_failures=1, failure_window=60, max_clients=3, clock=clock)
    guard.failed()
    guard.failed()
    assert guard.delay() == 1
    assert guard.admit("192.0.2.1", login=False) == 0
    clock.advance(61)
    assert guard.delay() == 0
    for index in range(10):
        guard.admit(f"203.0.113.{index}", login=False)
    assert len(guard.clients) <= 3


def test_failed_logins_feed_the_global_backoff(app):
    guard = app.state.login_guard
    guard.free_failures = 2
    client = TestClient(app, base_url=BASE_URL)
    for _ in range(3):
        assert login(client, "wrong-password").status_code == 401
    assert guard.delay() == 1
    assert login(client, PASSWORD).status_code == 200
    assert guard.delay() == 0


# --- SEC-5: single-use operational grants ------------------------------------------------


def test_operational_grants_are_single_use_and_separate_from_sessions(app):
    auth = app.state.auth
    grant = auth.operation_ticket("export")
    client = TestClient(app, base_url=BASE_URL)
    assert client.get("/api/v1/export", headers={"X-Operational-Token": grant}).status_code == 200
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

    # Used nonces are forgotten once their grant could no longer be used.
    clock = Clock()
    auth.used_operations.clock = clock
    auth.used_operations.expiries.clear()
    auth.authorize_operation(auth.operation_ticket("backup"), "backup")
    assert len(auth.used_operations.expiries) == 1
    clock.advance(200)
    auth.authorize_operation(auth.operation_ticket("backup"), "backup")
    assert len(auth.used_operations.expiries) == 1
