"""Ingest signals, their precision, and the filters they give: never a dismissal.

The labelled fixture (language_fixture.json) is synthetic: postings in English,
German, French and Italian (and a few in Spanish, Dutch and Portuguese) with the
language they are written in and the languages they require or welcome.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from discovery_fixtures import patch_discovery
from openings.actors import OWNER, acting_as, token_actor
from openings.app import create_app
from openings.discovery import DiscoveryService, SourceCreate
from openings.language_signals import language_requirements, posting_language, text_signals
from openings.workspace import Workspace

FIXTURE = json.loads((Path(__file__).with_name("language_fixture.json")).read_text())["items"]
AGENT = token_actor("agent-token", "Synthetic agent", "agent")
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}

# What the detectors must reach on the labelled fixture. Measured when written:
# language 89/89 correct where a language was given (89 of 90 labelled postings),
# required 83/83 correct with 83/83 found, welcome 28/28 with 28/28 found. A held-out
# round of 26 postings written before the detectors saw them scored language 25/25,
# required 19/20 (recall 19/25) and welcome 5/5 on the first run.
LANGUAGE_PRECISION = 0.95
LANGUAGE_COVERAGE = 0.9
REQUIRED_PRECISION = 0.9
REQUIRED_RECALL = 0.8
WELCOME_PRECISION = 0.85


def test_language_detection_reaches_the_stated_precision():
    predicted = correct = labelled = 0
    for item in FIXTURE:
        language = text_signals(item["title"], item["posting"])["language"]
        labelled += item["language"] is not None
        if language is not None:
            predicted += 1
            correct += language == item["language"]
    assert labelled >= 80 and {item["language"] for item in FIXTURE} >= {"en", "de", "fr", "it"}
    assert correct / predicted >= LANGUAGE_PRECISION, (correct, predicted)
    assert predicted / labelled >= LANGUAGE_COVERAGE, (predicted, labelled)
    # Too little text says nothing.
    assert posting_language("Python developer wanted.") == (None, None)


def test_language_requirement_detection_reaches_the_stated_precision():
    found = {"required": [0, 0, 0], "welcome": [0, 0, 0]}  # correct, predicted, labelled
    for item in FIXTURE:
        signals = text_signals(item["title"], item["posting"])
        for key, gold, got in (
            (
                "required",
                {tuple(g) for g in item["required"]},
                {tuple(g) for g in signals["required"]},
            ),
            ("welcome", set(item["welcome"]), set(signals["welcome"])),
        ):
            found[key][0] += len(gold & got)
            found[key][1] += len(got)
            found[key][2] += len(gold)
    correct, predicted, labelled = found["required"]
    assert labelled >= 60
    assert correct / predicted >= REQUIRED_PRECISION, found
    assert correct / labelled >= REQUIRED_RECALL, found
    correct, predicted, labelled = found["welcome"]
    assert correct / predicted >= WELCOME_PRECISION, found


@pytest.mark.parametrize(
    ("text", "required", "welcome"),
    [
        ("Fluent German required, English is a plus.", [["de"]], ["en"]),
        ("Deutsch C1 und Englisch B2.", [["de"], ["en"]], []),
        ("La langue française est exigée.", [["fr"]], []),
        ("Richiesta la conoscenza fluente del francese o del tedesco.", [["de", "fr"]], []),
        ("Knowledge of the German market is important.", [], []),
        ("Keine Deutschkenntnisse erforderlich.", [], []),
        ("Le français n'est pas requis.", [], []),
        ("Wir betreuen deutsche Kunden.", [], []),
    ],
)
def test_requirement_phrases(text, required, welcome):
    assert language_requirements(text) == {"required": required, "welcome": welcome}


GERMAN = (
    "Wir suchen eine Person für unser Team in Bern. Deine Aufgaben: Du entwickelst neue "
    "Funktionen in Python und arbeitest mit unseren Kunden. Dein Profil: fließend Deutsch "
    "und sehr gute Englischkenntnisse. Wir bieten flexible Arbeitszeiten."
)
ENGLISH = (
    "You will build data pipelines in Python and work with a small team of analysts. "
    "We are looking for three years of experience and fluent English. We offer a yearly "
    "learning budget and flexible hours in our Zurich office. Your days start with a short "
    "planning meeting, then you design, test and run the jobs that load measurement data "
    "into our warehouse, review the changes of your colleagues and help the analysts who "
    "depend on clean, documented tables every week."
)


@pytest.fixture
def services(tmp_path):
    return Workspace(tmp_path / "signals.sqlite")


def job(workspace, title, posting, number, **extra):
    return workspace.ingest_job(
        {
            "title": title,
            "company": extra.pop("company", f"Example {number}"),
            "location": "Zurich, Switzerland",
            "url": f"https://example.test/jobs/{number}",
            "posting": posting,
            **extra,
        }
    )


def test_signals_are_computed_at_ingest_and_follow_the_text(services):
    workspace = services
    first = job(workspace, "Softwareentwickler", GERMAN, 1)
    signals = first["signals"]
    assert signals["computed"] and signals["duplicate_checked"]
    assert signals["language"] == "de" and signals["language_confidence"] > 0.5
    assert signals["required"] == [["de"], ["en"]] and signals["duplicate"] is None
    assert not signals["no_longer_listed"] and "rules" not in signals
    # A refresh that changes the text changes the text signals.
    refreshed = workspace.ingest_job({"url": "https://example.test/jobs/1", "posting": ENGLISH})
    assert refreshed["signals"]["language"] == "en" and refreshed["signals"]["required"] == [["en"]]
    edited = workspace.update_job(
        first["id"], {"expected_version": refreshed["version"], "posting": GERMAN}
    )
    assert edited["signals"]["language"] == "de"
    # The list and the compact summary carry the same signals.
    listed = workspace.list_jobs(posting_language="German")["items"]
    assert [item["id"] for item in listed] == [first["id"]]
    assert workspace.list_jobs(requires="en")["total"] == 1
    assert workspace.list_jobs(posting_language_not="de")["total"] == 0
    assert workspace.list_jobs(signal="language_required")["total"] == 1


def test_a_likely_duplicate_is_flagged_against_the_earlier_job_and_never_merged(services):
    workspace = services
    first = job(workspace, "Data Engineer", ENGLISH, 1, company="Northstar Labs")
    copy = job(workspace, "Data Engineer", ENGLISH, 2, company="Northstar Labs AG")
    other = job(workspace, "Gardener", "Plant trees in the park every morning.", 3)
    assert first["signals"]["duplicate"] is None
    duplicate = copy["signals"]["duplicate"]
    assert duplicate["job_id"] == first["id"] and duplicate["confidence"] >= 0.85
    assert duplicate["tier"] == "high" and other["signals"]["duplicate"] is None
    assert workspace.db.one("SELECT count(*) n FROM jobs")["n"] == 3
    assert [item["id"] for item in workspace.list_jobs(signal="likely_duplicate")["items"]] == [
        copy["id"]
    ]
    # "Different": the flag goes and stays gone when signals are computed again.
    cleared = workspace.mark_distinct(copy["id"], first["id"])
    assert cleared["signals"]["duplicate"] is None
    workspace.db.execute("UPDATE job_signals SET format=0,duplicate_checked=0")
    assert workspace.signals.backfill() == {"text": 3, "duplicates": 3}
    assert workspace.get_job(copy["id"])["signals"]["duplicate"] is None
    assert (
        workspace.db.one("SELECT count(*) n FROM events WHERE kind='duplicate_cleared'")["n"] == 1
    )
    # Merging the earlier job into another keeps flags pointing at the kept record.
    third = job(workspace, "Data Engineer", ENGLISH, 4, company="Northstar Labs")
    assert third["signals"]["duplicate"]["job_id"] == first["id"]
    merged_into = workspace.merge_jobs(
        first["id"], other["id"], workspace.get_job(first["id"])["version"], other["version"]
    )
    assert workspace.get_job(third["id"])["signals"]["duplicate"]["job_id"] == merged_into["id"]


def test_triage_reasons_and_who_dismissed(services):
    workspace = services
    first, second, third = (job(workspace, "Engineer", ENGLISH + str(n), n) for n in (1, 2, 3))
    with acting_as(AGENT):
        result = workspace.bulk_jobs(
            {
                "action": "dismissed",
                "reason": "Junior role; the policy targets senior roles.",
                "items": [{"id": first["id"], "expected_version": first["version"]}],
            }
        )
    assert result["succeeded"] == 1
    dismissal = workspace.get_job(first["id"])["dismissal"]
    assert dismissal["category"] == "agent" and dismissal["reason"].startswith("Junior")
    with acting_as(OWNER):
        owner = workspace.set_triage(second["id"], "dismissed", second["version"], "Too far.")
    assert owner["dismissal"]["category"] == "owner" and owner["dismissal"]["reason"] == "Too far."
    counts = workspace.list_jobs(include_counts=True)["counts"]
    assert counts["dismissed"] == 2 and counts["new"] == 1
    assert counts["dismissed_by"] == {"agent": 1, "owner": 1, "system": 0}
    with pytest.raises(Exception, match="reason"):
        workspace.set_triage(third["id"], "shortlisted", third["version"], "Nice")


def test_a_board_that_stops_listing_a_posting_marks_it_and_dismisses_nothing(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "collection.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    source = service.create_source(
        SourceCreate(name="Example board", kind="greenhouse", config={"board": "example"})
    )
    listed = {"value": ["1", "2", "3"]}

    def collect(snapshot):
        for number in listed["value"]:
            snapshot["on_item"](
                {
                    "title": f"Engineer {number}",
                    "company": "Example",
                    "url": f"https://boards.greenhouse.io/example/jobs/{number}",
                    "source_key": f"greenhouse:example:{number}",
                    "posting": ENGLISH,
                    "metadata": {"ats": "greenhouse", "board": "example", "external_id": number},
                }
            )
        snapshot["streamed"] = True
        snapshot["on_checkpoint"]({"complete": True, "pending_details": 0})
        return []

    patch_discovery(monkeypatch, "fetch_postings", collect)

    def run():
        service.queue_collection(source["id"])
        task = service.claim_task("worker", "collect")
        service.run_task(task, "worker")
        return service.get_task(task["id"])

    assert run()["state"] == "succeeded"
    jobs = {item["title"]: item for item in workspace.list_jobs()["items"]}
    assert not any(item["signals"]["no_longer_listed"] for item in jobs.values())
    workspace.set_triage(jobs["Engineer 3"]["id"], "shortlisted", jobs["Engineer 3"]["version"])
    listed["value"] = ["1"]
    second = run()
    assert second["state"] == "succeeded" and second["result"]["unlisted"] == 2
    after = {item["title"]: item for item in workspace.list_jobs()["items"]}
    assert after["Engineer 2"]["signals"]["no_longer_listed"]
    # A label only: the job waits in the Inbox.
    assert after["Engineer 2"]["triage"] == "new"
    assert (
        after["Engineer 3"]["triage"] == "shortlisted"
        and after["Engineer 3"]["signals"]["no_longer_listed"]
    )
    assert not after["Engineer 1"]["signals"]["no_longer_listed"]
    # Listed again: the observation is listed again.
    listed["value"] = ["1", "3"]
    run()
    assert not workspace.get_job(after["Engineer 3"]["id"])["signals"]["no_longer_listed"]
    assert workspace.list_jobs(signal="no_longer_listed")["total"] == 1


def test_rest_and_mcp_expose_signals_alike(tmp_path):
    app = create_app(tmp_path / "interfaces.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    workspace = app.state.workspace
    first = job(workspace, "Data Engineer", ENGLISH, 1, company="Northstar Labs")
    copy = job(workspace, "Data Engineer", ENGLISH, 2, company="Northstar Labs")
    agent = app.state.auth.create_token("Synthetic agent", "agent")
    headers = {"Authorization": "Bearer " + agent["token"]}

    def tool(client, name, arguments):
        response = client.post(
            "/mcp",
            headers={**MCP_HEADERS, **headers},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        result = response.json()["result"]
        assert not result.get("isError"), result
        return result.get("structuredContent") or json.loads(result["content"][0]["text"])

    with TestClient(app, base_url="http://localhost:8080") as client:
        listed = client.get(
            "/api/v1/jobs?signal=likely_duplicate&include_counts=true", headers=headers
        ).json()
        assert listed == tool(
            client,
            "jobs_list",
            {"value": {"signal": "likely_duplicate", "include_counts": True}},
        )
        assert [item["id"] for item in listed["items"]] == [copy["id"]]
        dismissed = client.post(
            f"/api/v1/jobs/{first['id']}/triage",
            json={"triage": "dismissed", "expected_version": first["version"], "reason": "Seen."},
            headers=headers,
        ).json()
        assert (
            dismissed["dismissal"]["reason"] == "Seen."
            and dismissed["dismissal"]["category"] == "agent"
        )
        distinct = tool(
            client, "jobs_distinct", {"job_id": copy["id"], "value": {"other_id": first["id"]}}
        )
        assert distinct["signals"]["duplicate"] is None
        over_rest = client.post(
            f"/api/v1/jobs/{copy['id']}/distinct", json={"other_id": first["id"]}, headers=headers
        )
        assert over_rest.status_code == 200 and over_rest.json()["signals"]["duplicate"] is None
