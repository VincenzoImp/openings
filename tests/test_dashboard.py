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
    """Create a dashboard AppTest wired to a temporary ``JOB_SEARCH_DATA_DIR``."""
    # In v6+ everything persistent lives under a single DATA_DIR root.
    # Lay out the subtree the application expects and let it discover it via env.
    (tmp_path / "config").mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    config_path = tmp_path / "config" / "settings.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            search:
              sites: [indeed]
              locations: [Remote]
            queries:
              test: ["software engineer"]
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

    db = JobDatabase(db_dir / "jobs.db")
    for job in jobs:
        db.save_job(job)
    db.close()

    vector_store_stub = types.ModuleType("vector_store")
    vector_store_stub.get_vector_store = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "vector_store", vector_store_stub)
    monkeypatch.setenv("JOB_SEARCH_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("JOB_SEARCH_CONFIG", raising=False)
    sys.modules.pop("config", None)
    st.cache_data.clear()
    st.cache_resource.clear()

    app = AppTest.from_file(
        str(Path(__file__).parent.parent / "scripts" / "dashboard.py"),
        default_timeout=10,
    )
    return app, db_dir


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


# ════════════════════════════════════════════════════════════════════════════
# Phase 5: Pure helper function tests
# ════════════════════════════════════════════════════════════════════════════


class TestEscapeHtmlText:
    """Tests for _escape_html_text."""

    def test_normal_string(self) -> None:
        from dashboard import _escape_html_text

        assert _escape_html_text("Hello World") == "Hello World"

    def test_html_entities(self) -> None:
        from dashboard import _escape_html_text

        result = _escape_html_text('<script>alert("xss")</script>')
        assert "<" not in result
        assert "&lt;" in result

    def test_ampersand(self) -> None:
        from dashboard import _escape_html_text

        assert "&amp;" in _escape_html_text("A & B")

    def test_quotes(self) -> None:
        from dashboard import _escape_html_text

        result = _escape_html_text('She said "hello"')
        assert "&quot;" in result

    def test_none_input(self) -> None:
        from dashboard import _escape_html_text

        assert _escape_html_text(None) == ""

    def test_empty_string(self) -> None:
        from dashboard import _escape_html_text

        assert _escape_html_text("") == ""

    def test_integer_input(self) -> None:
        from dashboard import _escape_html_text

        assert _escape_html_text(42) == "42"


class TestScoreBadgeHtml:
    """Tests for _score_badge_html."""

    def test_high_score(self) -> None:
        from dashboard import SCORE_HIGH, _score_badge_html

        result = _score_badge_html(SCORE_HIGH + 10)
        assert "score-high" in result
        assert str(SCORE_HIGH + 10) in result

    def test_exactly_high_threshold(self) -> None:
        from dashboard import SCORE_HIGH, _score_badge_html

        assert "score-high" in _score_badge_html(SCORE_HIGH)

    def test_medium_score(self) -> None:
        from dashboard import SCORE_MED, _score_badge_html

        assert "score-med" in _score_badge_html(SCORE_MED + 5)

    def test_exactly_medium_threshold(self) -> None:
        from dashboard import SCORE_MED, _score_badge_html

        assert "score-med" in _score_badge_html(SCORE_MED)

    def test_low_score(self) -> None:
        from dashboard import _score_badge_html

        assert "score-low" in _score_badge_html(5)

    def test_zero_score(self) -> None:
        from dashboard import _score_badge_html

        result = _score_badge_html(0)
        assert "score-low" in result
        assert "0" in result

    def test_negative_score(self) -> None:
        from dashboard import _score_badge_html

        assert "score-low" in _score_badge_html(-10)

    def test_just_below_medium(self) -> None:
        from dashboard import SCORE_MED, _score_badge_html

        assert "score-low" in _score_badge_html(SCORE_MED - 1)

    def test_just_below_high(self) -> None:
        from dashboard import SCORE_HIGH, _score_badge_html

        assert "score-med" in _score_badge_html(SCORE_HIGH - 1)


class TestFormatSalary:
    """Tests for _format_salary."""

    def test_range_usd(self) -> None:
        from dashboard import _format_salary

        job = {"min_amount": 100_000, "max_amount": 150_000, "currency": "USD"}
        result = _format_salary(job)
        assert "$100k" in result
        assert "$150k" in result
        assert "-" in result

    def test_min_only(self) -> None:
        from dashboard import _format_salary

        job = {"min_amount": 80_000, "max_amount": None, "currency": "USD"}
        assert "$80k+" in _format_salary(job)

    def test_max_only(self) -> None:
        from dashboard import _format_salary

        job = {"min_amount": None, "max_amount": 120_000, "currency": "USD"}
        result = _format_salary(job)
        assert "Up to" in result
        assert "$120k" in result

    def test_no_salary(self) -> None:
        from dashboard import _format_salary

        job = {"min_amount": None, "max_amount": None, "currency": None}
        assert _format_salary(job) == ""

    def test_non_usd_currency(self) -> None:
        from dashboard import _format_salary

        job = {"min_amount": 50_000, "max_amount": 70_000, "currency": "EUR"}
        result = _format_salary(job)
        assert "EUR" in result

    def test_missing_currency_defaults_to_dollar(self) -> None:
        from dashboard import _format_salary

        job = {"min_amount": 60_000, "max_amount": 80_000}
        assert "$" in _format_salary(job)

    def test_zero_amounts_treated_as_absent(self) -> None:
        from dashboard import _format_salary

        # 0 is falsy
        job = {"min_amount": 0, "max_amount": 0, "currency": "USD"}
        assert _format_salary(job) == ""


class TestShortNum:
    """Tests for _short_num."""

    def test_millions(self) -> None:
        from dashboard import _short_num

        assert _short_num(1_500_000) == "1.5M"

    def test_exact_million(self) -> None:
        from dashboard import _short_num

        assert _short_num(1_000_000) == "1.0M"

    def test_thousands(self) -> None:
        from dashboard import _short_num

        assert _short_num(120_000) == "120k"

    def test_exact_thousand(self) -> None:
        from dashboard import _short_num

        assert _short_num(1_000) == "1k"

    def test_small_number(self) -> None:
        from dashboard import _short_num

        assert _short_num(500) == "500"

    def test_zero(self) -> None:
        from dashboard import _short_num

        assert _short_num(0) == "0"


class TestDaysAgo:
    """Tests for _days_ago."""

    def test_today(self) -> None:
        from dashboard import _days_ago

        from datetime import date

        assert _days_ago(date.today().isoformat()) == "Today"

    def test_yesterday(self) -> None:
        from dashboard import _days_ago

        from datetime import date, timedelta

        assert _days_ago((date.today() - timedelta(days=1)).isoformat()) == "Yesterday"

    def test_multiple_days_ago(self) -> None:
        from dashboard import _days_ago

        from datetime import date, timedelta

        assert _days_ago((date.today() - timedelta(days=5)).isoformat()) == "5d ago"

    def test_none_input(self) -> None:
        from dashboard import _days_ago

        assert _days_ago(None) == ""

    def test_empty_string(self) -> None:
        from dashboard import _days_ago

        assert _days_ago("") == ""

    def test_invalid_date(self) -> None:
        from dashboard import _days_ago

        assert _days_ago("not-a-date") == ""


class TestFilteredJobsCsvBytes:
    """Tests for _filtered_jobs_csv_bytes."""

    def test_normal_list(self) -> None:
        from dashboard import _filtered_jobs_csv_bytes

        jobs = [
            {"title": "Dev", "company": "Acme", "relevance_score": 30},
            {"title": "PM", "company": "Beta", "relevance_score": 20},
        ]
        result = _filtered_jobs_csv_bytes(jobs)
        assert isinstance(result, bytes)
        assert b"Dev" in result
        assert b"PM" in result

    def test_empty_list(self) -> None:
        from dashboard import _filtered_jobs_csv_bytes

        assert _filtered_jobs_csv_bytes([]) == b""
