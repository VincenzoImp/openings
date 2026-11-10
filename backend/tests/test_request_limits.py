"""Request bodies are bounded by bytes received, not by the declared length."""

from fastapi.testclient import TestClient

from openings.app import create_app
from openings.limits import AUTH_LIMIT, REQUEST_LIMIT


def chunks(total, size=64 * 1024):
    sent = 0
    while sent < total:
        part = min(size, total - sent)
        sent += part
        yield b" " * part


def test_chunked_bodies_without_length_are_cut_off(tmp_path):
    app = create_app(tmp_path / "limits.sqlite", start_worker=False)
    json_headers = {"Content-Type": "application/json"}
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login", content=chunks(AUTH_LIMIT + 1), headers=json_headers
        )
        assert login.status_code == 413
        assert login.json()["error"]["code"] == "request_size"

        setup = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        assert setup.status_code == 200
        client.headers["X-CSRF-Token"] = setup.json()["csrf_token"]

        large = client.post("/api/v1/jobs", content=chunks(REQUEST_LIMIT + 1), headers=json_headers)
        assert large.status_code == 413
        assert large.json()["error"]["code"] == "request_size"

        normal = client.post(
            "/api/v1/jobs", json={"title": "Synthetic engineer", "posting": "Build."}
        )
        assert normal.status_code in (200, 201)
