"""Time budgets of the hot REST reads on a large synthetic workspace.

The workspace has 25,000 jobs with their ingest signals, 500 applications in
every stage, 20 company sources and Career evidence (large_fixtures.py). Each route is read once to warm up, then the median of
five reads must stay under its budget.

The budgets were set from the median on an Apple M-series laptop, times three
for a shared CI runner, times two again for noise, rounded up; a route that
outgrows its budget has become several times slower, not a little noisier.
Measured on the laptop (2026-11): applications 24 ms, Today's reads 38 ms in
all, new 12 ms (29 ms with counts or facets), text search 106 ms, overview
19 ms, insights 8 ms, source yield 90 ms; the three reads of a busy
timeline (1,500 entries) 13 ms.

Run them alone with ``uv run pytest -m performance``; skip them with
``-m "not performance"``.
"""

import statistics
import time

import pytest
from fastapi.testclient import TestClient

from large_fixtures import seed_large, seed_signals
from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate, TemplateCreate
from timeline_fixtures import guided_application

pytestmark = pytest.mark.performance

JOBS, APPLICATIONS, SOURCES = 25_000, 500, 20
# The reads of the Today screen, measured together as one budget.
TODAY = (
    "/api/v1/overview",
    "/api/v1/applications?limit=1",
    "/api/v1/applications?stage=ready&sort=deadline&limit=5",
    "/api/v1/applications?needs=documents&sort=deadline&limit=3",
    "/api/v1/applications?needs=reply_overdue&limit=1",
    "/api/v1/questions?state=open&limit=3",
    "/api/v1/runs?limit=1",
    "/api/v1/collection/runs?limit=100",
)
BUDGETS_MS = {
    "applications": (("/api/v1/applications?limit=200",), 200),
    "today": (TODAY, 300),
    "jobs new": (("/api/v1/jobs?triage=new&limit=200",), 100),
    "jobs new counts": (("/api/v1/jobs?triage=new&limit=200&include_counts=true",), 200),
    "jobs new facets": (("/api/v1/jobs?triage=new&limit=200&include_facets=true",), 200),
    "jobs search": (("/api/v1/jobs?q=engineer&limit=200",), 700),
    "overview": (("/api/v1/overview",), 150),
    "insights": (("/api/v1/insights",), 100),
    "source yield": (("/api/v1/collection/yield",), 600),
    # Revisions are searched in the text derived from their sources.
    "document search": (("/api/v1/documents?q=Northstar&limit=100",), 50),
}
# The three timeline reads of test_a_busy_timeline_stays_within_its_budget together.
TIMELINE_BUDGET_MS = 100


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    app = create_app(tmp_path_factory.mktemp("budgets") / "large.sqlite", start_worker=False)
    workspace, career = app.state.workspace, app.state.career
    seed_large(workspace, JOBS, APPLICATIONS, sources=SOURCES)
    seed_signals(workspace)
    for index in range(20):
        entry = career.create_knowledge(
            KnowledgeCreate(
                kind="project",
                title=f"Synthetic project {index:02d}",
                narrative="Built reliable services.",
                skills=["Python"],
            )
        )
        career.create_claim(
            ClaimCreate(
                knowledge_id=entry["id"], text=f"Synthetic claim {index:02d}", approved=True
            )
        )
    career.create_template(
        TemplateCreate(name="Synthetic CV", tex="Synthetic TeX", is_default=True)
    )
    with TestClient(app) as client:
        client.post("/api/v1/auth/setup", json={"password": "synthetic-password"})
        yield client


def median_ms(client, routes, reads=5):
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, (route, response.text)
    times = []
    for _ in range(reads):
        started = time.perf_counter()
        for route in routes:
            client.get(route)
        times.append(time.perf_counter() - started)
    return statistics.median(times) * 1000


@pytest.mark.parametrize("name", list(BUDGETS_MS))
def test_hot_reads_stay_within_their_budget(client, name):
    routes, budget = BUDGETS_MS[name]
    elapsed = median_ms(client, routes)
    assert elapsed < budget, f"{name}: {elapsed:.0f} ms, budget {budget} ms"


def test_a_busy_timeline_stays_within_its_budget(client):
    """The first page of the timelines of a job with 1,200 events and 300 notes, with counts."""
    workspace = client.app.state.workspace
    job = workspace.ingest_job({"title": "Busy", "company": "Synthetic", "posting": "Busy."})
    application = guided_application(workspace, job["id"], "Pinned.")
    with workspace.db.transaction() as conn:
        for index in range(1_200):
            stamp = f"2026-{1 + index % 12:02d}-{1 + index % 28:02d}T10:{index % 60:02d}:00+00:00"
            on_application = application["id"] if index % 2 else None
            conn.execute(
                "INSERT INTO events(id,job_id,application_id,kind,payload,created_at,actor_kind) "
                "VALUES(?,?,?,?,?,?,?)",
                (f"busy-{index}", job["id"], on_application, "job_edited", "{}", stamp, "owner"),
            )
            if index % 4 == 0:
                conn.execute(
                    "INSERT INTO notes(id,job_id,application_id,body,created_at,updated_at,"
                    "author_kind) VALUES(?,?,?,?,?,?,?)",
                    (
                        f"busy-{index}",
                        job["id"],
                        on_application,
                        "Note " * 40,
                        stamp,
                        stamp,
                        "owner",
                    ),
                )
    routes = (
        f"/api/v1/applications/{application['id']}/timeline?limit=50",
        f"/api/v1/jobs/{job['id']}/timeline?limit=50",
        f"/api/v1/applications/{application['id']}/timeline?limit=50&kinds=note&who=owner",
    )
    assert client.get(routes[1]).json()["total"] >= 1_500
    elapsed = median_ms(client, routes)
    # The other budgets count the workspace as stated: remove the busy job again.
    workspace.forget_job(job["id"], workspace.get_job(job["id"])["version"])
    assert elapsed < TIMELINE_BUDGET_MS, f"timeline: {elapsed:.0f} ms"


def test_the_workspace_is_as_large_as_stated(client):
    jobs = client.get("/api/v1/jobs?limit=1&include_counts=true").json()
    applications = client.get("/api/v1/applications?limit=1").json()
    assert jobs["total"] == JOBS and applications["total"] == APPLICATIONS
    sources = client.get("/api/v1/collection/yield").json()
    assert len([item for item in sources["items"] if item.get("source_id")]) >= SOURCES // 2
