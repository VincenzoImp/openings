"""Integration tests exercising the full pipeline with real databases.

No mocking of DB or scoring. External services (JobSpy, ChromaDB) are mocked
only where unavoidable. Tests verify end-to-end flows: scoring, partitioning,
reconciliation, API endpoints, and MCP tool functions.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from config import (
    Config,
    DatabaseConfig,
    RetentionConfig,
    ScoringConfig,
)
from database import JobDatabase, recalculate_all_scores
from models import Job
from scoring import Partitions, partition_by_thresholds, score_jobs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_jobs() -> list[Job]:
    """Diverse set of jobs for seeding a test database."""
    return [
        Job(
            title="Senior Python Backend Engineer",
            company="TechCo",
            location="Remote",
            description="Build scalable Python microservices with Docker and AWS.",
            relevance_score=50,
            job_url="https://example.com/1",
        ),
        Job(
            title="Frontend Developer",
            company="Widget Inc",
            location="New York, NY",
            description="React and TypeScript web applications.",
            relevance_score=20,
            job_url="https://example.com/2",
        ),
        Job(
            title="Junior Data Entry Clerk",
            company="OfficeCo",
            location="Chicago, IL",
            description="Enter data into spreadsheets.",
            relevance_score=0,
            job_url="https://example.com/3",
        ),
        Job(
            title="DevOps Engineer",
            company="CloudCorp",
            location="San Francisco, CA",
            description="Kubernetes, Docker, CI/CD pipelines on AWS.",
            relevance_score=35,
            job_url="https://example.com/4",
        ),
        Job(
            title="Machine Learning Researcher",
            company="AI Labs",
            location="Remote",
            description="Deep learning research with Python and PyTorch.",
            relevance_score=30,
            job_url="https://example.com/5",
        ),
    ]


def _make_config(
    save_threshold: int = 10,
    notify_threshold: int = 30,
    max_age_days: int = 30,
) -> Config:
    """Minimal config for integration tests."""
    return Config(
        scoring=ScoringConfig(
            save_threshold=save_threshold,
            notify_threshold=notify_threshold,
            weights={
                "backend": 20,
                "tech": 15,
                "remote": 5,
            },
            keywords={
                "backend": ["python", "backend", "engineer"],
                "tech": ["docker", "kubernetes", "aws"],
                "remote": ["remote"],
            },
        ),
        database=DatabaseConfig(
            retention=RetentionConfig(
                max_age_days=max_age_days,
                purge_blacklist_after_days=90,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def integration_env():
    """Set up a complete integration environment with real DB and config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = JobDatabase(db_path)
        config = _make_config()

        # Seed the database with diverse jobs
        for job in _seed_jobs():
            db.save_job(job, site="indeed")

        yield db, config, tmpdir

        db.close()


@pytest.fixture()
def seeded_db():
    """A seeded database with bookmark/applied flags for protection tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = JobDatabase(db_path)

        jobs = _seed_jobs()
        for job in jobs:
            db.save_job(job, site="indeed")

        # Bookmark the low-score data entry clerk
        all_jobs = db.get_all_jobs()
        clerk_job = next(j for j in all_jobs if "Data Entry" in j.title)
        db.toggle_bookmark(clerk_job.job_id)

        # Mark frontend dev as applied
        frontend_job = next(j for j in all_jobs if "Frontend" in j.title)
        db.toggle_applied(frontend_job.job_id)

        yield db
        db.close()


# ---------------------------------------------------------------------------
# Score -> Partition -> Save cycle
# ---------------------------------------------------------------------------


def test_score_and_partition_pipeline():
    """Create a DataFrame, score it, partition it, verify thresholds."""
    config = _make_config(save_threshold=10, notify_threshold=30)

    # Build a DataFrame with varied content
    rows = [
        {
            "title": "Python Backend Engineer",
            "company": "A",
            "location": "Remote",
            "description": "Python Docker AWS",
            "site": "indeed",
        },
        {
            "title": "Frontend Dev",
            "company": "B",
            "location": "NYC",
            "description": "React TypeScript",
            "site": "indeed",
        },
        {
            "title": "Senior DevOps",
            "company": "C",
            "location": "SF",
            "description": "Kubernetes Docker AWS remote",
            "site": "indeed",
        },
        {
            "title": "Data Entry",
            "company": "D",
            "location": "Chicago",
            "description": "Spreadsheets",
            "site": "indeed",
        },
        {
            "title": "ML Engineer",
            "company": "E",
            "location": "Remote",
            "description": "Python AWS",
            "site": "indeed",
        },
        {
            "title": "Junior QA",
            "company": "F",
            "location": "Boston",
            "description": "Manual testing",
            "site": "indeed",
        },
        {
            "title": "Backend Python Developer",
            "company": "G",
            "location": "Remote",
            "description": "Python backend Docker Kubernetes",
            "site": "indeed",
        },
        {
            "title": "Sales Manager",
            "company": "H",
            "location": "Miami",
            "description": "Sales leadership",
            "site": "indeed",
        },
        {
            "title": "Python Engineer",
            "company": "I",
            "location": "Remote",
            "description": "Python AWS Docker remote",
            "site": "indeed",
        },
        {
            "title": "Office Admin",
            "company": "J",
            "location": "Dallas",
            "description": "Office admin tasks",
            "site": "indeed",
        },
    ]
    df = pd.DataFrame(rows)

    scored = score_jobs(df, config)
    assert "relevance_score" in scored.columns
    assert len(scored) == 10

    parts = partition_by_thresholds(scored, config)
    assert isinstance(parts, Partitions)
    assert len(parts.scored) == 10

    # to_save: all with score >= 10
    for _, row in parts.to_save.iterrows():
        assert row["relevance_score"] >= 10

    # to_notify: all with score >= 30
    for _, row in parts.to_notify.iterrows():
        assert row["relevance_score"] >= 30

    # to_notify is a subset of to_save
    assert len(parts.to_notify) <= len(parts.to_save)


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def test_reconcile_removes_below_threshold(integration_env):
    db, _, _ = integration_env
    config = _make_config(save_threshold=25)

    # Recalculate with current config so scores match
    recalculate_all_scores(db, config)

    db.reconcile_with_config(config)

    remaining = db.get_all_jobs()
    for job in remaining:
        assert job.relevance_score >= 25 or job.bookmarked or job.applied


def test_reconcile_protects_bookmarked(seeded_db):
    config = _make_config(save_threshold=50)

    # Recalculate scores
    recalculate_all_scores(seeded_db, config)

    seeded_db.reconcile_with_config(config)

    remaining = seeded_db.get_all_jobs()
    bookmarked = [j for j in remaining if j.bookmarked]
    assert len(bookmarked) >= 1, "Bookmarked job should survive reconciliation"


def test_reconcile_protects_applied(seeded_db):
    config = _make_config(save_threshold=50)

    recalculate_all_scores(seeded_db, config)
    seeded_db.reconcile_with_config(config)

    remaining = seeded_db.get_all_jobs()
    applied = [j for j in remaining if j.applied]
    assert len(applied) >= 1, "Applied job should survive reconciliation"


def test_reconcile_removes_stale():
    """Seed a job with old last_seen, verify reconcile removes it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = JobDatabase(Path(tmpdir) / "test.db")
        job = Job(
            title="Old Job",
            company="OldCo",
            location="Nowhere",
            relevance_score=50,
        )
        db.save_job(job, site="indeed")

        # Manually set last_seen to 60 days ago
        import sqlite3

        conn = sqlite3.connect(db.db_path)
        old_date = (date.today() - timedelta(days=60)).isoformat()
        conn.execute("UPDATE jobs SET last_seen = ?", (old_date,))
        conn.commit()
        conn.close()

        config = _make_config(max_age_days=30)
        report = db.reconcile_with_config(config)
        assert report.deleted_stale >= 1
        assert db.get_job_count() == 0
        db.close()


def test_reconcile_idempotent(integration_env):
    db, config, _ = integration_env

    recalculate_all_scores(db, config)
    db.reconcile_with_config(config)
    report2 = db.reconcile_with_config(config)

    assert report2.deleted_below_score == 0
    assert report2.deleted_stale == 0
    assert report2.purged_blacklist == 0


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


def test_api_full_workflow():
    """Seed real DB, exercise API endpoints through TestClient."""
    from fastapi.testclient import TestClient

    import api_server
    import job_service

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = JobDatabase(db_path)

        for job in _seed_jobs():
            db.save_job(job, site="indeed")

        # Patch service singletons
        job_service._db = db
        job_service._vs = None
        job_service._vs_attempted = True

        api_server.app.router.lifespan_context = _noop_lifespan
        with TestClient(api_server.app, raise_server_exceptions=True) as client:
            # Health
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["jobs_count"] == 5

            # List all jobs
            resp = client.get("/jobs", params={"limit": 100})
            assert resp.status_code == 200
            all_jobs = resp.json()
            assert len(all_jobs) == 5

            # Sorted by score descending
            scores = [j["relevance_score"] for j in all_jobs]
            assert scores == sorted(scores, reverse=True)

            # Filter by min_score
            resp = client.get("/jobs", params={"min_score": 30})
            assert resp.status_code == 200
            filtered = resp.json()
            assert all(j["relevance_score"] >= 30 for j in filtered)

            # Bookmark a job
            job_id = all_jobs[0]["job_id"]
            resp = client.post(f"/jobs/{job_id}/bookmark")
            assert resp.status_code == 200
            assert resp.json()["bookmarked"] is True

            # Delete below score -- should protect bookmarked
            resp = client.delete("/jobs/below-score/15")
            assert resp.status_code == 200
            deleted_count = resp.json()["deleted_count"]
            assert deleted_count >= 1

            # Verify bookmarked job survived
            resp = client.get(f"/jobs/{job_id}")
            assert resp.status_code == 200
            assert resp.json()["bookmarked"] is True

            # Stats should be consistent
            resp = client.get("/stats")
            assert resp.status_code == 200
            stats = resp.json()
            assert stats["total_jobs"] == 5 - deleted_count

        db.close()
        job_service.reset_singletons()


# ---------------------------------------------------------------------------
# MCP integration
# ---------------------------------------------------------------------------


def test_mcp_full_workflow():
    """Seed real DB, call MCP tool functions directly."""
    import job_service

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = JobDatabase(db_path)

        for job in _seed_jobs():
            db.save_job(job, site="indeed")

        job_service._db = db
        job_service._vs = None
        job_service._vs_attempted = True

        from mcp_server import (
            bookmark_job,
            delete_jobs_below_score,
            get_job,
            get_statistics,
            list_jobs,
        )

        # list_jobs
        result = json.loads(list_jobs())
        assert len(result) == 5
        # Should be sorted by score descending
        scores = [j["relevance_score"] for j in result]
        assert scores == sorted(scores, reverse=True)
        # No description in summaries
        assert all("description" not in j for j in result)

        # get_job with full detail
        job_id = result[0]["job_id"]
        detail = json.loads(get_job(job_id))
        assert "description" in detail
        assert detail["job_id"] == job_id

        # bookmark toggle
        bm_result = json.loads(bookmark_job(job_id))
        assert bm_result["bookmarked"] is True

        # get_statistics
        stats = json.loads(get_statistics())
        assert stats["total_jobs"] == 5

        # delete below score -- protects bookmarked
        del_result = json.loads(delete_jobs_below_score(15))
        assert del_result["deleted_count"] >= 1

        # Verify bookmarked survived
        detail_after = json.loads(get_job(job_id))
        assert "error" not in detail_after

        # Stats consistent
        stats_after = json.loads(get_statistics())
        assert stats_after["total_jobs"] == 5 - del_result["deleted_count"]

        db.close()
        job_service.reset_singletons()


# ---------------------------------------------------------------------------
# Rescore + Reconcile (config change simulation)
# ---------------------------------------------------------------------------


def test_config_change_reconcile():
    """Simulate a config change: new keywords/weights, re-score, reconcile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = JobDatabase(Path(tmpdir) / "test.db")

        for job in _seed_jobs():
            db.save_job(job, site="indeed")

        # Old config: generous, everything scores high
        old_config = Config(
            scoring=ScoringConfig(
                save_threshold=0,
                notify_threshold=0,
                weights={"catch_all": 50},
                keywords={
                    "catch_all": [
                        "engineer",
                        "developer",
                        "data",
                        "devops",
                        "researcher",
                        "clerk",
                    ]
                },
            ),
        )
        recalculate_all_scores(db, old_config)
        all_before = db.get_all_jobs()
        assert all(j.relevance_score >= 50 for j in all_before)

        # New config: strict, only Python backend engineers score high
        new_config = Config(
            scoring=ScoringConfig(
                save_threshold=15,
                notify_threshold=30,
                weights={"python": 20, "backend": 15},
                keywords={
                    "python": ["python"],
                    "backend": ["backend"],
                },
            ),
            database=DatabaseConfig(
                retention=RetentionConfig(max_age_days=365),
            ),
        )
        recalculate_all_scores(db, new_config)
        report = db.reconcile_with_config(new_config)

        remaining = db.get_all_jobs()
        # Jobs below save_threshold=15 should be gone (unless bookmarked/applied)
        for job in remaining:
            assert job.relevance_score >= 15

        # At least some jobs should have been deleted
        assert report.deleted_below_score > 0
        # Some jobs should survive
        assert len(remaining) > 0

        db.close()
