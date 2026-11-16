"""The first owner claims a new workspace with a one-time code from the server's log."""

import logging

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app

PASSWORD = "synthetic-password"


def start(path, caplog, demo=False):
    """One start of the server on ``path``: the app and the code it logged, if any."""
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="openings.auth"):
        app = create_app(path, start_worker=False, demo=demo)
    logged = [record.getMessage() for record in caplog.records if "Setup code" in record.message]
    return app, logged


def setup(client, code=None):
    body = {"password": PASSWORD} | ({"setup_code": code} if code is not None else {})
    return client.post("/api/v1/auth/setup", json=body)


def test_the_right_code_claims_the_workspace_once(tmp_path, caplog, monkeypatch):
    monkeypatch.delenv("OPENINGS_PASSWORD", raising=False)
    app, logged = start(tmp_path / "claim.sqlite", caplog)
    code = app.state.auth.setup_code
    assert logged == [
        f"Setup code: {code} · find it again with `docker compose logs openings` (or `docker logs openings`)"
    ]
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/session").json()["setup_code"] is True
        for wrong in (None, "", "AAAA-AAAA"):
            refused = setup(client, wrong)
            assert refused.status_code == 403
            assert refused.json()["error"]["code"] == "setup_code"
        assert not app.state.auth.configured()
        # Typed in lower case and without the dash, it is the same code.
        claimed = setup(client, code.replace("-", " ").lower())
        assert claimed.status_code == 200 and claimed.json()["authenticated"]
        assert client.get("/api/v1/auth/session").json()["setup_code"] is False
        # The code has done its work: the workspace has an owner.
        assert setup(client, code).status_code == 409
        assert app.state.auth.setup_code is None


def test_repeated_wrong_codes_are_throttled_like_sign_in(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENINGS_PASSWORD", raising=False)
    app = create_app(tmp_path / "guess.sqlite", start_worker=False)
    with TestClient(app) as client:
        codes = [setup(client, f"WRNG-{index:04d}").status_code for index in range(11)]
    assert codes[:10] == [403] * 10 and codes[10] == 429
    assert len(app.state.login_guard.failures) == 10


def test_a_restart_before_the_claim_replaces_the_code(tmp_path, caplog, monkeypatch):
    monkeypatch.delenv("OPENINGS_PASSWORD", raising=False)
    path = tmp_path / "restart.sqlite"
    first, _ = start(path, caplog)
    old = first.state.auth.setup_code
    second, logged = start(path, caplog)
    new = second.state.auth.setup_code
    assert new != old and logged and new in logged[0]
    with TestClient(second) as client:
        assert setup(client, old).status_code == 403
        assert setup(client, new).status_code == 200
    # Once claimed, a start prints no code.
    third, logged = start(path, caplog)
    assert third.state.auth.setup_code is None and logged == []


@pytest.mark.parametrize("preset", ["password", "demo"])
def test_a_preset_password_or_the_demo_needs_no_code(tmp_path, caplog, monkeypatch, preset):
    monkeypatch.delenv("OPENINGS_PASSWORD", raising=False)
    if preset == "password":
        monkeypatch.setenv("OPENINGS_PASSWORD", PASSWORD)
    app, logged = start(tmp_path / "preset.sqlite", caplog, demo=preset == "demo")
    assert app.state.auth.setup_code is None and logged == []
    with TestClient(app) as client:
        session = client.get("/api/v1/auth/session").json()
        assert session["setup_code"] is False and session["demo"] is (preset == "demo")
