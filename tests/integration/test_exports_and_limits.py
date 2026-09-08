"""Edge cases of the export and upload surfaces."""

import csv
import io

import yaml


def test_csv_export_escapes_commas_and_newlines(client):
    client.post(
        "/api/jobs",
        json={
            "title": 'Engineer, "Platform"',
            "company": "Acme",
            "location": "Remote",
            "description": "Line one\nLine two, with comma",
        },
    )
    response = client.get("/api/export/jobs", params={"limit": 0})
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["title"] == 'Engineer, "Platform"'
    assert rows[0]["description"] == "Line one\nLine two, with comma"


def test_upload_above_the_limit_is_413(runtime, settings_dict):
    settings_dict["attachments"] = {"max_size_mb": 1}
    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    runtime.config(reload=True)
    from fastapi.testclient import TestClient

    from openings.web.app import create_app

    with TestClient(create_app()) as client:
        job_id = client.post(
            "/api/jobs", json={"title": "T", "company": "C", "location": "L"}
        ).json()["job_ids"][0]
        too_big = client.post(
            f"/api/jobs/{job_id}/attachments",
            files={"file": ("big.bin", b"x" * (1024 * 1024 + 1), "application/octet-stream")},
            data={"kind": "other"},
        )
        assert too_big.status_code == 413
        empty = client.post(
            f"/api/jobs/{job_id}/attachments",
            files={"file": ("empty.bin", b"", "application/octet-stream")},
            data={"kind": "other"},
        )
        assert empty.status_code == 422


def test_get_jobs_limit_zero_is_one_page_and_export_limit_zero_is_everything(client):
    for index in range(3):
        client.post(
            "/api/jobs",
            json={
                "title": f"J{index}",
                "company": "C",
                "location": "L",
                "job_url": f"https://linkedin.com/jobs/view/{index}",
            },
        )
    assert len(client.get("/api/jobs", params={"limit": 0}).json()["items"]) == 1
    assert len(client.get("/api/export/jobs", params={"limit": 0, "format": "json"}).json()) == 3
