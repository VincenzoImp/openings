"""Time budgets of the hot REST reads on a large synthetic workspace.

The workspace has 25,000 jobs with their ingest signals, 500 applications in
every stage, 20 company sources, Career evidence and 60 frozen contexts
(large_fixtures.py). Each route is read once to warm up, then the median of
five reads must stay under its budget.

The budgets were set from the median on an Apple M-series laptop, times three
for a shared CI runner, times two again for noise, rounded up; a route that
outgrows its budget has become several times slower, not a little noisier.
Measured on the laptop (2026-11): applications 24 ms, Today's reads 38 ms in
all, inbox 12 ms (29 ms with counts or facets), text search 106 ms, overview
19 ms, staleness 6 ms, insights 8 ms, source yield 90 ms.

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
from openings.documents import ContextCreate

pytestmark = pytest.mark.performance

JOBS, APPLICATIONS, SOURCES, CONTEXTS = 25_000, 500, 20, 60
# The reads of the Today screen, measured together as one budget.
TODAY = (
    "/api/v1/overview",
    "/api/v1/applications?limit=1",
    "/api/v1/applications?readiness=ready&sort=deadline&limit=5",
    "/api/v1/applications?readiness=blocked&status=draft&sort=deadline&limit=3",
    "/api/v1/applications?no_reply_due=true&limit=1",
    "/api/v1/questions?state=open&limit=3",
    "/api/v1/runs?limit=1",
    "/api/v1/collection/runs?limit=100",
)
BUDGETS_MS = {
    "applications": (("/api/v1/applications?limit=200",), 200),
    "today": (TODAY, 300),
    "jobs inbox": (("/api/v1/jobs?queue=inbox&limit=200",), 100),
    "jobs inbox counts": (("/api/v1/jobs?queue=inbox&limit=200&include_counts=true",), 200),
    "jobs inbox facets": (("/api/v1/jobs?queue=inbox&limit=200&include_facets=true",), 200),
    "jobs search": (("/api/v1/jobs?q=engineer&limit=200",), 700),
    "overview": (("/api/v1/overview",), 150),
    "staleness": (("/api/v1/staleness?status=all&stale_only=false",), 100),
    "insights": (("/api/v1/insights",), 100),
    "source yield": (("/api/v1/collection/yield",), 600),
    # Revisions are searched in the text derived from their sources.
    "document search": (("/api/v1/documents?q=Northstar&limit=100",), 50),
}


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
    drafts = workspace.db.all(
        "SELECT id FROM applications WHERE status='draft' ORDER BY id LIMIT ?", (CONTEXTS,)
    )
    for row in drafts:
        app.state.documents.prepare_context(ContextCreate(application_id=row["id"]))
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


def test_the_workspace_is_as_large_as_stated(client):
    jobs = client.get("/api/v1/jobs?limit=1&include_counts=true").json()
    applications = client.get("/api/v1/applications?limit=1").json()
    assert jobs["total"] == JOBS and applications["total"] == APPLICATIONS
    sources = client.get("/api/v1/collection/yield").json()
    assert len([item for item in sources["items"] if item.get("source_id")]) >= SOURCES // 2
