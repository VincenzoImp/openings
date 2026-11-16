"""The demo workspace: seeded from the package, dated back only in a file the demo created."""

from datetime import UTC, datetime, timedelta

import pytest

from openings.demo import NotADemo, is_demo, mark_demo, seed_demo, stamp


def test_dates_are_rewritten_only_in_a_file_with_the_demo_marker(workspace):
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build."})
    before = workspace.get_job(job["id"])["created_at"]
    with pytest.raises(NotADemo):
        stamp(workspace.db, "", datetime.now(UTC) - timedelta(days=30))
    assert workspace.get_job(job["id"])["created_at"] == before
    # A workspace with records never becomes a demo, so it can never be stamped.
    with pytest.raises(NotADemo):
        mark_demo(workspace)
    assert not is_demo(workspace.db)


def test_the_demo_seeds_a_new_workspace_with_dates_relative_to_now(app):
    token = seed_demo(app)
    workspace = app.state.workspace
    assert is_demo(workspace.db) and token["name"] == "Claude Code" and token["token"]
    oldest = workspace.db.one("SELECT min(created_at) AS at FROM jobs")["at"]
    age = datetime.now(UTC) - datetime.fromisoformat(oldest)
    assert timedelta(days=30) < age < timedelta(days=90)
    # Every CV and letter is a complete revision built from its stored TeX source.
    pdfs = workspace.db.all("SELECT source_sha256 FROM files WHERE media_type='application/pdf'")
    assert pdfs and all(row["source_sha256"] for row in pdfs)
