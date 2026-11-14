"""Outcome insights on a synthetic workspace with known outcomes, and the title mapping."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.common import new_id, now
from openings.insights import (
    FAMILY_LABELS,
    SENIORITY_LABELS,
    InsightsService,
    location_group,
    role_family,
    seniority,
    source_kind,
    source_name,
)

MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.mark.parametrize(
    ("title", "family", "level"),
    [
        # English
        ("Senior Data Engineer", "data_engineering", "senior"),
        ("Analytics Engineer", "analytics", "unknown"),
        ("Python Engineer", "backend", "unknown"),
        ("Site Reliability Engineer (SRE)", "platform", "unknown"),
        ("Staff Machine Learning Engineer", "data_science", "lead"),
        ("Engineering Manager, Payments", "management", "head"),
        ("Junior Full-Stack Developer", "fullstack", "junior"),
        ("Research Software Engineer", "research", "unknown"),
        ("UI/UX Designer", "design", "unknown"),
        ("Product Owner", "product", "unknown"),
        ("QA Automation Engineer", "qa", "unknown"),
        ("iOS Developer", "mobile", "unknown"),
        ("Security Engineer", "security", "unknown"),
        ("Software Engineer Intern", "software", "intern"),
        ("Engineer", "unknown", "unknown"),
        # German
        ("Softwareentwickler (m/w/d)", "software", "unknown"),
        ("Werkstudent Datenanalyse", "analytics", "intern"),
        ("Teamleiter IT-Infrastruktur", "platform", "lead"),
        ("Junior Frontend-Entwickler", "frontend", "junior"),
        ("Leiter Softwareentwicklung", "management", "head"),
        ("Datenwissenschaftlerin", "data_science", "unknown"),
        # French
        ("Ingénieur de données confirmé", "data_engineering", "senior"),
        ("Stagiaire Développeur Web", "frontend", "intern"),
        ("Développeur Backend Java", "backend", "unknown"),
        ("Chercheur en apprentissage automatique", "data_science", "unknown"),
        # Italian
        ("Sviluppatore Backend Java", "backend", "unknown"),
        ("Ingegnere dei dati Senior", "data_engineering", "senior"),
        ("Stagista Analista dati", "analytics", "intern"),
        ("Direttore tecnico", "management", "head"),
        ("Ricercatore", "research", "unknown"),
    ],
)
def test_role_family_and_seniority_come_from_the_title(title, family, level):
    assert role_family(title) == family
    assert seniority(title) == level
    assert family in FAMILY_LABELS and level in SENIORITY_LABELS


def test_source_kind_and_name_come_from_the_source_or_the_job():
    assert source_kind("jobspy", {}) == "search"
    assert source_name("Data roles", "search", {}) == "Data roles"
    assert source_kind("greenhouse", {}) == "company"
    assert source_kind("rss", {}) == "feed"
    # Without a collection source, the job's metadata says where it was found.
    assert source_kind(None, {"source": "linkedin"}) == "search"
    assert source_name(None, "search", {"source": "linkedin"}) == "LinkedIn"
    assert source_kind(None, {"source": "greenhouse"}) == "company"
    assert source_name(None, "company", {"source": "greenhouse"}) == "Greenhouse"
    assert source_kind(None, {"ats": "lever"}) == "company"
    assert (source_kind(None, {}), source_name(None, "manual", {})) == ("manual", "Added by hand")


def test_location_groups_use_the_first_part():
    assert location_group("Zurich, Switzerland") == "Zurich"
    assert location_group("  Remote ,  Europe") == "Remote"
    assert location_group("") == ""


def days_ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0)


def record_reply(workspace, application_id, kind, day):
    """Record an employer reply through the application update, as the owner reports it."""
    current = workspace.get_application(application_id)
    workspace.update_application(
        application_id,
        {"expected_version": current["version"], "reply": {"kind": kind, "date": day}},
    )


def seeded(app):
    """Nine sent applications with known answers, and three never sent."""
    workspace = app.state.workspace
    applied = days_ago(40)
    day = applied.date()

    def sent(title, location, answers=(), status="applied", outcome=None, applied_at=applied):
        job = workspace.ingest_job(
            {"title": title, "company": "Example", "location": location, "posting": "Build."}
        )
        application = workspace.create_application({"job_id": job["id"]})
        application = workspace.update_application(
            application["id"],
            {
                "expected_version": application["version"],
                "status": "applied",
                "applied_at": applied_at.isoformat() if applied_at else None,
            },
        )
        for kind, offset in answers:
            record_reply(
                workspace, application["id"], kind, (day + timedelta(days=offset)).isoformat()
            )
        current = workspace.get_application(application["id"])
        if (current["status"], current["outcome"]) != (status, outcome):
            workspace.update_application(
                application["id"],
                {
                    "expected_version": current["version"],
                    "status": status,
                    **({"outcome": outcome} if outcome else {}),
                },
            )
        return job

    searched = [
        sent("Data Engineer", "Zurich, Switzerland", [("interview", 5)], status="interview"),
        sent("Data Engineer", "Zurich, Switzerland", [("rejection", 10)], "closed", "rejected"),
        sent(
            "Senior Data Engineer",
            "Remote, Europe",
            [("interview", 8), ("offer", 20)],
            status="offer",
        ),
    ]
    sent("Data Engineer", "Zurich, Switzerland")
    sent("Data Engineer", "Remote, Europe", status="closed", outcome="no_response")
    sent("Data Platform Engineer", "Zurich, Switzerland")
    sent("Senior Backend Engineer", "Zurich, Switzerland", [("rejection", 2)])
    sent("Senior Backend Engineer", "Basel, Switzerland")
    # Sent, answered, but without a sent date: counted, never timed.
    sent("Data Analyst", "Zurich, Switzerland", [("other", 3)], applied_at=None)
    for title, close in (
        ("Draft one", None),
        ("Draft two", "not_pursued"),
        ("Draft three", "rejected"),
    ):
        job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build."})
        application = workspace.create_application({"job_id": job["id"]})
        if close:
            workspace.update_application(
                application["id"],
                {"expected_version": application["version"], "status": "closed", "outcome": close},
            )
    # Three of the jobs came from a saved search.
    with workspace.db.transaction() as conn:
        source = new_id()
        conn.execute(
            "INSERT INTO sources(id,name,kind,created_at,updated_at) VALUES(?,?,?,?,?)",
            (source, "Synthetic search", "jobspy", now(), now()),
        )
        conn.executemany(
            "UPDATE postings SET source_id=? WHERE job_id=?",
            [(source, job["id"]) for job in searched],
        )
    return applied


def by_key(groups):
    return {group["key"]: group for group in groups}


def test_insights_count_only_employer_answers_and_withhold_small_samples(tmp_path):
    app = create_app(tmp_path / "insights.sqlite", start_worker=False)
    applied = seeded(app)
    service = InsightsService(app.state.workspace)
    result = service.insights()
    overall = result["overall"]
    assert result["min_sample"] == 5
    assert result["excluded"] == {"shortlisted": 1, "closed_unsent": 2}
    assert {key: overall[key] for key in ("sent", "responded", "interviews", "offers")} == {
        "sent": 9,
        "responded": 5,
        "interviews": 2,
        "offers": 1,
    }
    assert (overall["rejections"], overall["no_reply"], overall["waiting"]) == (2, 1, 3)
    assert (overall["response_rate"], overall["interview_rate"], overall["offer_rate"]) == (
        round(5 / 9, 4),
        round(2 / 9, 4),
        round(1 / 9, 4),
    )
    # First answers after 5, 10, 8 and 2 days; the undated one is counted apart.
    assert (overall["timed"], overall["undated"]) == (4, 1)
    assert overall["median_days_to_response"] is None
    assert overall["median_withheld"] == "too_few_dated_answers"
    assert [row["count"] for row in result["time_to_response"]] == [2, 2, 0, 0]
    assert all(row["share"] is None for row in result["time_to_response"])

    families = by_key(result["groups"]["role_family"])
    data = families["data_engineering"]
    assert (data["sent"], data["responded"], data["interviews"], data["offers"]) == (6, 3, 2, 1)
    assert (data["response_rate"], data["withheld"]) == (0.5, None)
    backend = families["backend"]
    assert (backend["sent"], backend["responded"]) == (2, 1)
    assert backend["response_rate"] is None and backend["withheld"] == "too_few_sent"
    assert families["analytics"]["sent"] == 1
    assert result["groups"]["role_family"][0]["key"] == "data_engineering"
    levels = by_key(result["groups"]["seniority"])
    assert (levels["senior"]["sent"], levels["unknown"]["sent"]) == (3, 6)
    places = by_key(result["groups"]["location"])
    assert places["zurich"]["label"] == "Zurich" and places["zurich"]["sent"] == 6
    kinds = by_key(result["groups"]["source_kind"])
    assert (kinds["search"]["sent"], kinds["manual"]["sent"]) == (3, 6)
    assert kinds["search"]["label"] == "Searches"
    named = by_key(result["groups"]["source"])
    assert named["Synthetic search"]["interviews"] == 2
    months = by_key(result["groups"]["month"])
    assert months[applied.strftime("%Y-%m")]["sent"] == 8 and months["unknown"]["sent"] == 1
    assert result["groups"]["month"][-1]["key"] == "unknown"

    smaller = service.insights({"min_sample": 3})
    assert smaller["overall"]["median_days_to_response"] == 6.5
    assert [row["share"] for row in smaller["time_to_response"]] == [0.5, 0.5, 0.0, 0.0]
    assert by_key(smaller["groups"]["role_family"])["backend"]["withheld"] == "too_few_sent"
    # A period counts only applications sent in it.
    since = (applied + timedelta(days=1)).date().isoformat()
    assert service.insights({"applied_since": since})["overall"]["sent"] == 0
    assert service.insights({"applied_until": since})["overall"]["sent"] == 8
    with pytest.raises(ValueError):
        service.insights({"min_sample": 0})


def test_rest_and_mcp_return_the_same_insights(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    seeded(app)
    agent = app.state.auth.create_token("Synthetic agent", "agent")
    headers = {"Authorization": "Bearer " + agent["token"]}
    with TestClient(app, base_url="http://localhost:8080") as client:
        over_rest = client.get("/api/v1/insights?min_sample=3", headers=headers)
        assert over_rest.status_code == 200
        response = client.post(
            "/mcp",
            headers={**MCP_HEADERS, **headers},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "insights_get", "arguments": {"value": {"min_sample": 3}}},
            },
        )
        result = response.json()["result"]
        over_mcp = result.get("structuredContent") or json.loads(result["content"][0]["text"])
        assert over_rest.json() == over_mcp
        assert over_mcp["overall"]["sent"] == 9
        bad = client.get("/api/v1/insights?min_sample=101", headers=headers)
        assert bad.status_code == 422


def test_month_and_time_buckets_follow_dates(tmp_path):
    app = create_app(tmp_path / "buckets.sqlite", start_worker=False)
    workspace = app.state.workspace
    start = date.today() - timedelta(days=90)
    for offset in (0, 6, 7, 8, 14, 15, 30, 31):
        job = workspace.ingest_job({"title": f"Data Engineer {offset}", "posting": "Build."})
        application = workspace.create_application({"job_id": job["id"]})
        workspace.update_application(
            application["id"],
            {
                "expected_version": application["version"],
                "status": "applied",
                "applied_at": start.isoformat(),
            },
        )
        record_reply(
            workspace, application["id"], "rejection", (start + timedelta(days=offset)).isoformat()
        )
    result = InsightsService(workspace).insights()
    assert [row["count"] for row in result["time_to_response"]] == [3, 2, 2, 1]
    assert result["overall"]["median_days_to_response"] == 11
