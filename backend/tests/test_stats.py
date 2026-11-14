"""Stats of sent applications and the counts of each source (#211)."""

from datetime import UTC, datetime, timedelta

import pytest

from openings.common import new_id, now
from openings.stats import StatsQuery, StatsService


def ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="microseconds")


def source(workspace, name):
    source_id = new_id()
    with workspace.db.transaction() as conn:
        conn.execute(
            "INSERT INTO sources(id,name,kind,created_at,updated_at) VALUES(?,?,'lever',?,?)",
            (source_id, name, now(), now()),
        )
    return source_id


def sent(workspace, source_id=None, days=10, replies=(), status="applied", applied=True):
    """A job found by ``source_id`` with an application sent ``days`` ago."""
    job = workspace.ingest_job(
        {"title": "Synthetic engineer", "company": "Example", "posting": "Build APIs."}
    )
    application = workspace.create_application({"job_id": job["id"]})
    with workspace.db.transaction() as conn:
        if source_id:
            for copy in range(2):  # a job seen twice by its source counts once
                conn.execute(
                    "INSERT INTO postings(id,job_id,source_id,identity,content_hash,first_seen_at,"
                    "last_seen_at) VALUES(?,?,?,?,'x',?,?)",
                    (new_id(), job["id"], source_id, new_id(), ago(days + copy), now()),
                )
        conn.execute(
            "UPDATE applications SET status=?,applied_at=? WHERE id=?",
            (status, ago(days) if applied else None, application["id"]),
        )
        for kind, after in replies:
            day = (datetime.now(UTC) - timedelta(days=days - after)).date().isoformat()
            conn.execute(
                "INSERT INTO responses(id,application_id,kind,date,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (new_id(), application["id"], kind, day, now(), now()),
            )
    return job, application


def test_stats_count_sent_applications_replies_and_the_funnel(workspace):
    stats = StatsService(workspace)
    empty = stats.stats()
    assert (empty["applied"], empty["reply_rate"], empty["median_days_to_reply"]) == (0, None, None)
    assert empty["by_source"] is None
    sent(workspace, replies=[("rejection", 4)])
    sent(workspace, replies=[("interview", 8), ("offer", 20)], status="offer")
    sent(workspace, status="interview")
    sent(workspace, days=200, replies=[("other", 2)])
    sent(workspace, status="interview", applied=False)  # sent without a date
    draft = workspace.ingest_job({"title": "Draft only", "posting": "Build."})
    workspace.create_application({"job_id": draft["id"]})  # never sent: not counted

    recent = stats.stats(StatsQuery(period="90d"))
    assert recent["since"] == (datetime.now(UTC) - timedelta(days=90)).date().isoformat()
    assert (recent["applied"], recent["replied"], recent["interviews"]) == (3, 2, 2)
    assert (recent["reply_rate"], recent["interview_rate"]) == (0.6667, 0.6667)
    assert recent["median_days_to_reply"] == 6
    assert [step["count"] for step in recent["funnel"]] == [3, 2, 2, 1]
    year = stats.stats(StatsQuery(period="12m"))
    assert (year["applied"], year["median_days_to_reply"]) == (4, 4)
    every = stats.stats(StatsQuery(period="all"))
    assert (every["since"], every["applied"], every["interviews"]) == (None, 5, 3)


def test_replies_by_source_need_two_sources_with_five_applications(workspace):
    stats = StatsService(workspace)
    first, second = source(workspace, "Data roles"), source(workspace, "Example board")
    for index in range(5):
        sent(workspace, first, replies=[("rejection", 3)] if index < 2 else ())
    for _ in range(4):
        sent(workspace, second)
    assert stats.stats()["by_source"] is None
    sent(workspace, second, replies=[("interview", 1)])
    sent(workspace)  # no source, a single application: left out
    assert stats.stats()["by_source"] == [
        {"source": "Data roles", "applied": 5, "replied": 2, "reply_rate": 0.4},
        {"source": "Example board", "applied": 5, "replied": 1, "reply_rate": 0.2},
    ]


def test_stats_on_rest_and_the_removed_routes(client):
    result = client.get("/api/v1/stats?period=12m").json()
    assert result["period"] == "12m" and result["applied"] == 0
    assert client.get("/api/v1/stats?period=week").status_code == 422
    for path in ("/api/v1/overview", "/api/v1/insights", "/api/v1/collection/yield"):
        assert client.get(path).status_code == 404, path


def test_stats_on_mcp_and_the_removed_tools(mcp):
    value, error = mcp.call("stats_get", {"value": {"period": "all"}})
    assert error is None and value["period"] == "all"
    for name, replacement in (
        ("insights_get", "stats_get"),
        ("overview_get", "stats_get"),
        ("sources_yield", "sources_list"),
    ):
        _, removed = mcp.call(name)
        assert removed["code"] == "tool_removed" and replacement in removed["message"]


def test_sources_list_counts_what_each_source_found(app, client):
    workspace = app.state.workspace
    first, second = source(workspace, "Data roles"), source(workspace, "Example board")
    sent(workspace, first, replies=[("rejection", 3)])
    sent(workspace, first, status="draft", applied=False)
    job, _ = sent(workspace, second)
    shortlisted = workspace.ingest_job({"title": "Kept", "posting": "Build."})
    with workspace.db.transaction() as conn:
        # Found by both sources: it counts for each.
        conn.execute(
            "INSERT INTO postings(id,job_id,source_id,identity,content_hash,first_seen_at,"
            "last_seen_at) VALUES(?,?,?,?,'x',?,?)",
            (new_id(), job["id"], first, new_id(), now(), now()),
        )
        conn.execute(
            "INSERT INTO postings(id,job_id,source_id,identity,content_hash,first_seen_at,"
            "last_seen_at) VALUES(?,?,?,?,'x',?,?)",
            (new_id(), shortlisted["id"], second, new_id(), now(), now()),
        )
    workspace.set_triage(shortlisted["id"], "saved", shortlisted["version"])
    source(workspace, "Quiet source")
    items = {item["name"]: item["counts"] for item in client.get("/api/v1/sources").json()["items"]}
    assert items == {
        "Data roles": {"found": 3, "shortlisted": 3, "applied": 2, "replied": 1},
        "Example board": {"found": 2, "shortlisted": 2, "applied": 1, "replied": 0},
        "Quiet source": {"found": 0, "shortlisted": 0, "applied": 0, "replied": 0},
    }
    single = client.get(f"/api/v1/sources/{second}").json()
    assert single["counts"] == items["Example board"]


@pytest.mark.parametrize("period", ["90d", "12m", "all"])
def test_every_period_is_accepted(workspace, period):
    assert StatsService(workspace).stats(StatsQuery(period=period))["period"] == period
