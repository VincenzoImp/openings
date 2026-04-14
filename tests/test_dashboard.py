"""Smoke tests for the Streamlit dashboard."""

from __future__ import annotations

from io import BytesIO
import sys
import textwrap
import types
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from database import JobDatabase
from models import Job


def _prepare_dashboard_app(
    tmp_path: Path,
    monkeypatch,
    jobs: list[Job],
) -> tuple[AppTest, Path]:
    """Create a dashboard AppTest wired to a temporary config and database."""
    data_dir = tmp_path / "data"
    results_dir = tmp_path / "results"
    data_dir.mkdir()
    results_dir.mkdir()

    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            search:
              sites: [indeed]
              locations: [Remote]
            queries:
              test: ["software engineer"]
            output:
              data_dir: "{data_dir}"
              results_dir: "{results_dir}"
              database_file: jobs.db
            notifications:
              enabled: false
            scheduler:
              enabled: false
            vector_search:
              enabled: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    db = JobDatabase(data_dir / "jobs.db")
    for job in jobs:
        db.save_job(job)
    db.close()

    vector_store_stub = types.ModuleType("vector_store")
    vector_store_stub.get_vector_store = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "vector_store", vector_store_stub)
    monkeypatch.setenv("JOB_SEARCH_CONFIG", str(config_path))
    sys.modules.pop("config", None)
    st.cache_data.clear()
    st.cache_resource.clear()

    app = AppTest.from_file(
        str(Path(__file__).parent.parent / "scripts" / "dashboard.py"),
        default_timeout=10,
    )
    return app, data_dir


def test_dashboard_smoke_renders_and_escapes_html(monkeypatch, tmp_path: Path) -> None:
    """The dashboard should render and escape scraped HTML in job titles."""
    app, _data_dir = _prepare_dashboard_app(
        tmp_path,
        monkeypatch,
        jobs=[Job(title="<b>Evil</b>", company="Acme", location="Remote")],
    )

    app.run(timeout=10)

    assert len(app.exception) == 0
    title_markup = next(
        markdown.value for markdown in app.markdown if "Evil" in markdown.value
    )
    assert "<b>Evil</b>" not in title_markup
    assert "&lt;b&gt;Evil&lt;/b&gt;" in title_markup


def test_dashboard_bulk_delete_blacklists_selected_jobs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Selecting and deleting a page of jobs should blacklist them persistently."""
    app, data_dir = _prepare_dashboard_app(
        tmp_path,
        monkeypatch,
        jobs=[
            Job(title="Role 1", company="Acme", location="Remote"),
            Job(title="Role 2", company="Acme", location="Remote"),
        ],
    )

    app.run(timeout=10)
    app.button(key="jobs_select_page").click()
    app.run(timeout=10)
    app.button(key="jobs_delete_selected").click()
    app.run(timeout=10)

    db = JobDatabase(data_dir / "jobs.db")
    stats = db.get_statistics()
    db.close()

    assert stats["total_jobs"] == 0
    assert stats["blacklisted"] == 2


def test_filtered_jobs_csv_bytes_sanitizes_formula_payloads(monkeypatch) -> None:
    """Filtered dashboard CSV exports should use the sanitized exporter path."""
    vector_store_stub = types.ModuleType("vector_store")
    vector_store_stub.get_vector_store = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "vector_store", vector_store_stub)
    sys.modules.pop("dashboard", None)

    from dashboard import _filtered_jobs_csv_bytes

    csv_bytes = _filtered_jobs_csv_bytes(
        [
            {
                "title": '=HYPERLINK("http://evil","click")',
                "company": "Corp",
                "location": "Remote",
            }
        ]
    )

    loaded = pd.read_csv(BytesIO(csv_bytes))
    assert loaded.iloc[0]["title"].startswith("'=")
