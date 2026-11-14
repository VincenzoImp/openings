"""Yield per source: the counts equal what the synthetic fixture says happened."""

import json
from collections import Counter

from fastapi.testclient import TestClient

from openings.actors import OWNER, acting_as, token_actor
from openings.app import create_app
from openings.common import new_id, now

AGENT = token_actor("agent-token", "Synthetic agent", "agent")
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
GERMAN = (
    "Wir suchen eine Person für unser Team in Bern. Deine Aufgaben: Du entwickelst neue "
    "Funktionen in Python. Dein Profil: fließend Deutsch und gute Englischkenntnisse."
)
ENGLISH = "You will build services in Python with a small team. Fluent English is required."
# (source, job board, posting, what happened). "applied" and later fates are sent.
FIXTURE = [
    ("search", "linkedin", ENGLISH, "new"),
    ("search", "linkedin", ENGLISH, "saved"),
    ("search", "linkedin", ENGLISH, "applied"),
    ("search", "linkedin", ENGLISH, "interview"),
    ("search", "indeed", ENGLISH, "rejected"),
    ("search", "indeed", ENGLISH, "dismissed_agent"),
    ("search", "indeed", GERMAN, "dismissed_system"),
    ("search", "indeed", GERMAN, "dismissed_system"),
    ("search", "linkedin", ENGLISH, "dismissed_owner"),
    ("search", "linkedin", ENGLISH, "shortlisted"),
    ("search", "linkedin", ENGLISH, "not_pursued"),
    ("board", "greenhouse", ENGLISH, "offer"),
    ("board", "greenhouse", ENGLISH, "new"),
    ("board", "greenhouse", GERMAN, "dismissed_system"),
    ("board", "greenhouse", ENGLISH, "dismissed_agent"),
    (None, "manual", ENGLISH, "saved"),
    (None, "manual", ENGLISH, "new"),
]
SENT = {"applied", "interview", "rejected", "offer"}
ANSWERED = {"interview": "interview", "rejected": "rejection", "offer": "offer"}
STARTED = SENT | {"shortlisted", "not_pursued"}


def expected(rows):
    """The counts computed straight from the fixture, without the service."""
    fates = [fate for *_, fate in rows]
    dismissed = Counter(
        {"dismissed_system": "system", "dismissed_agent": "agent", "dismissed_owner": "owner"}[fate]
        for fate in fates
        if fate in {"dismissed_system", "dismissed_agent", "dismissed_owner"}
    )
    return {
        "collected": len(fates),
        "to_review": fates.count("new"),
        "shortlisted": sum(fate == "saved" or fate in STARTED for fate in fates),
        "applied": sum(fate in SENT for fate in fates),
        "responded": sum(fate in ANSWERED for fate in fates),
        "interviews": sum(fate in {"interview", "offer"} for fate in fates),
        "offers": fates.count("offer"),
        "dismissed": sum(dismissed.values()),
        "dismissed_by": {key: dismissed.get(key, 0) for key in ("agent", "owner", "system")},
    }


def seed(app):
    workspace = app.state.workspace
    sources = {"search": new_id(), "board": new_id()}
    with workspace.db.transaction() as conn:
        for key, name, kind, config in (
            ("search", "Python engineer Zurich", "jobspy", {"providers": ["linkedin", "indeed"]}),
            ("board", "Example board", "greenhouse", {"board": "example"}),
        ):
            conn.execute(
                "INSERT INTO sources(id,name,kind,config,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (sources[key], name, kind, json.dumps(config), now(), now()),
            )
    for number, (source, board, posting, fate) in enumerate(FIXTURE):
        job = workspace.ingest_job(
            {
                "title": f"Engineer {number}",
                "company": f"Company {number}",
                "url": f"https://example.test/jobs/{number}",
                "posting": posting,
                "metadata": {"source": board} if board != "manual" else {},
                "source_id": sources.get(source),
            }
        )
        # Nothing is dismissed automatically.
        assert job["triage"] == "new", (number, fate)
        if fate == "dismissed_system":
            workspace.set_triage(job["id"], "dismissed", job["version"])
        elif fate in {"saved", "dismissed_owner"}:
            with acting_as(OWNER):
                triage = "shortlisted" if fate == "saved" else "dismissed"
                workspace.set_triage(job["id"], triage, job["version"])
        elif fate == "dismissed_agent":
            with acting_as(AGENT):
                workspace.set_triage(job["id"], "dismissed", job["version"], "Not a match.")
        elif fate in STARTED:
            application = workspace.create_application({"job_id": job["id"]})
            if fate in SENT:
                application = workspace.update_application(
                    application["id"],
                    {"expected_version": application["version"], "status": "applied"},
                )
            if fate == "not_pursued":
                workspace.update_application(
                    application["id"],
                    {
                        "expected_version": application["version"],
                        "status": "closed",
                        "outcome": "not_pursued",
                    },
                )
            if fate in ANSWERED:
                workspace.update_application(
                    application["id"],
                    {
                        "expected_version": application["version"],
                        "reply": {"kind": ANSWERED[fate], "date": now()[:10]},
                    },
                )
    return sources


def test_yield_equals_the_counts_of_the_fixture(tmp_path):
    app = create_app(tmp_path / "yield.sqlite", start_worker=False)
    sources = seed(app)
    result = app.state.source_yield.source_yield({"min_sample": 5})
    rows = {item["source_id"]: item for item in result["items"]}
    assert set(rows) == {sources["search"], sources["board"], None}
    for key, source_id in (
        ("search", sources["search"]),
        ("board", sources["board"]),
        (None, None),
    ):
        want = expected([row for row in FIXTURE if row[0] == key])
        got = rows[source_id]
        assert {name: got[name] for name in want} == want, key
    search = rows[sources["search"]]
    assert search["kind"] == "search" and search["name"] == "Python engineer Zurich"
    assert search["kept_rate"] == round(6 / 11, 4) and search["withheld"] is None
    assert rows[None]["kept_rate"] is None and rows[None]["withheld"] == "too_few_collected"
    # A search is split by job board, and the boards add up to the search.
    boards = {item["provider"]: item for item in search["providers"]}
    assert {item["label"] for item in boards.values()} == {"LinkedIn", "Indeed"}
    for board in ("linkedin", "indeed"):
        want = expected([row for row in FIXTURE if row[0] == "search" and row[1] == board])
        assert {name: boards[board][name] for name in want if name != "dismissed_by"} == {
            name: value for name, value in want.items() if name != "dismissed_by"
        }
    total = result["total"]
    assert {name: total[name] for name in expected(FIXTURE)} == expected(FIXTURE)
    assert "dismissed_by_rule" not in total and "rule" not in total["dismissed_by"]
    assert total["sources"] == 2
    # A period that ends before anything was collected counts nothing.
    empty = app.state.source_yield.source_yield({"until": "2000-01-01"})
    assert empty["total"]["collected"] == 0 and len(empty["items"]) == 2


def test_rest_and_mcp_return_the_same_yield(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    seed(app)
    agent = app.state.auth.create_token("Synthetic agent", "agent")
    headers = {"Authorization": "Bearer " + agent["token"]}
    with TestClient(app, base_url="http://localhost:8080") as client:
        over_rest = client.get("/api/v1/collection/yield?min_sample=3", headers=headers)
        assert over_rest.status_code == 200
        response = client.post(
            "/mcp",
            headers={**MCP_HEADERS, **headers},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "sources_yield", "arguments": {"value": {"min_sample": 3}}},
            },
        )
        result = response.json()["result"]
        over_mcp = result.get("structuredContent") or json.loads(result["content"][0]["text"])
        assert over_rest.json() == over_mcp
        assert over_mcp["total"]["collected"] == len(FIXTURE)
        assert (
            client.get("/api/v1/collection/yield?min_sample=0", headers=headers).status_code == 422
        )
