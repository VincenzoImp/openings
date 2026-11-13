"""The browser tests' reset route exists only in their synthetic server, and it restores everything."""

import shutil

from fastapi.testclient import TestClient

from dashboard_server import RESET_PATH, resettable
from openings.app import create_app

PASSWORD = "synthetic-password"  # the owner of the `owned_database` fixture


def test_the_product_application_has_no_test_routes(app):
    paths = [getattr(route, "path", "") for route in app.routes]
    assert paths and not [path for path in paths if path.startswith("/__e2e__")]
    with TestClient(app) as client:
        assert client.post(RESET_PATH).status_code != 204


def test_reset_restores_the_snapshot_and_keeps_its_sessions(tmp_path, owned_database):
    snapshot = tmp_path / "snapshot.sqlite"
    shutil.copyfile(owned_database, snapshot)
    live = tmp_path / "live" / "workspace.sqlite"
    live.parent.mkdir()
    shutil.copyfile(snapshot, live)
    app = create_app(live, start_worker=False)
    with TestClient(resettable(app, snapshot), base_url="http://localhost:8080") as client:
        assert client.post("/api/v1/auth/login", json={"password": PASSWORD}).status_code == 200
        csrf = {"X-CSRF-Token": client.get("/api/v1/auth/session").json()["csrf_token"]}
        job = client.post(
            "/api/v1/jobs",
            headers=csrf,
            json={"title": "Synthetic engineer", "company": "Example Labs", "posting": "Build."},
        )
        assert job.status_code == 200, job.text
        assert client.get("/api/v1/jobs").json()["total"] == 1

        assert client.get(RESET_PATH).status_code == 405
        assert client.post(RESET_PATH).status_code == 204
        # The session was signed with the snapshot's secret, so it survives the reset.
        assert client.get("/api/v1/jobs").json()["total"] == 0
        assert client.get(f"/api/v1/jobs/{job.json()['id']}").status_code == 404
        # The snapshot itself never changes.
        assert snapshot.read_bytes() == owned_database.read_bytes()
