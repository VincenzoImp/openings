"""Career categories survive import, filtering and citation."""

import json

from fastapi.testclient import TestClient

from openings.app import create_app


def test_awards_and_publications_survive_import_filtering_and_citation(tmp_path):
    """The one-record career routes the dashboard uses, and the owner's import (REST only)."""
    app = create_app(tmp_path / "categories.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic category client", "owner")["token"]
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:

        def call(tool, method, path, arguments):
            # REST names the identifiers in the path and the rest in the body or query.
            body = {
                k: v for k, v in arguments.items() if not (k.endswith("_id") and f"/{v}" in path)
            }
            response = client.request(
                method,
                "/api/v1" + path,
                params=body if method == "GET" else None,
                json=body if method != "GET" else None,
            )
            response.raise_for_status()
            return response.json()

        entries = [
            {
                "kind": kind,
                "title": f"Example {kind}",
                "narrative": f"Synthetic supporting evidence for an example {kind}.",
                "metadata": {"year": 2024, "url": "https://example.org/evidence"},
            }
            for kind in ("award", "publication")
        ]
        created = [
            call("knowledge_create", "POST", "/career/knowledge", entry) for entry in entries
        ]
        preview = call(
            "career_preview_import",
            "POST",
            "/career/import/preview",
            {"text": json.dumps(entries)},
        )
        assert [row["kind"] for row in preview["entries"]] == ["award", "publication"]
        before_import = call("knowledge_list", "GET", "/career/knowledge", {})
        assert before_import["total"] == 2
        imported = call(
            "career_import",
            "POST",
            "/career/import",
            {"entries": preview["entries"]},
        )
        assert imported["total"] == 2
        for entry, record in zip(entries, created):
            listed = call(
                "knowledge_list",
                "GET",
                "/career/knowledge",
                {"kind": entry["kind"], "summary": True},
            )
            assert listed["total"] == 2
            assert {row["kind"] for row in listed["items"]} == {entry["kind"]}
            read = call(
                "knowledge_get",
                "GET",
                f"/career/knowledge/{record['id']}",
                {"career_id": record["id"]},
            )
            assert all(read[key] == value for key, value in entry.items())

        job = call(
            "jobs_create",
            "POST",
            "/jobs",
            {"title": "Engineer", "company": "Example", "posting": "Build APIs."},
        )
        application = call("applications_create", "POST", "/applications", {"job_id": job["id"]})
        cited = [record["id"] for record in created + imported["items"]]
        document = call(
            "documents_create",
            "POST",
            "/documents",
            {
                "application_id": application["id"],
                "kind": "other",
                "content": {"text": "Synthetic notes."},
                "career_ids": cited,
            },
        )
        assert document["career_ids"] == cited

        award = created[0]
        changed = call(
            "knowledge_update",
            "PATCH",
            f"/career/knowledge/{award['id']}",
            {
                "career_id": award["id"],
                "expected_version": award["version"],
                "kind": "publication",
                "narrative": "Revised live evidence.",
            },
        )
        assert changed["kind"] == "publication"
        # The revision keeps citing the entry by id.
        saved = call(
            "documents_get",
            "GET",
            f"/documents/{document['id']}",
            {"document_id": document["id"]},
        )
        assert saved["career_ids"] == cited

        invalid = {"kind": "unsupported", "title": "Invalid category"}
        assert client.post("/api/v1/career/knowledge", json=invalid).status_code == 422
