"""Ingest signals, the policy rules that act on them, and their precision.

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
from openings.job_signals import rule_matches
from openings.language_signals import language_requirements, posting_language, text_signals
from openings.policy import PolicyService
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


def rule(signal, operator, value, action="dismiss"):
    return {"signal": signal, "condition": {"operator": operator, "value": value}, "action": action}


def test_rule_conditions_follow_the_signals():
    german = {
        "language": "de",
        "required": [["de"], ["en", "fr"]],
        "duplicate": {"confidence": 0.9},
        "no_longer_listed": False,
    }
    # Values are codes or names, as the owner writes them.
    assert rule_matches(rule("language_required", "not_in", ["English", "Italian"]), german)
    assert not rule_matches(rule("language_required", "not_in", ["de", "en"]), german)
    assert rule_matches(rule("language_required", "in", ["German"]), german)
    # "English or French" is not a requirement of English alone.
    assert not rule_matches(rule("language_required", "in", ["en"]), german)
    assert rule_matches(rule("posting_language", "not_in", ["en"]), german)
    assert not rule_matches(
        rule("posting_language", "not_in", ["en"]), {**german, "language": None}
    )
    assert rule_matches(rule("likely_duplicate", "at_least", 0.85), german)
    assert not rule_matches(rule("likely_duplicate", "at_least", 0.95), german)
    assert not rule_matches(
        rule("likely_duplicate", "at_least", 0.5), {**german, "duplicate": None}
    )
    assert rule_matches(rule("no_longer_listed", "is", True), {**german, "no_longer_listed": True})


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
    workspace = Workspace(tmp_path / "signals.sqlite")
    return workspace, PolicyService(workspace)


def add_rule(policy, label, value, *, enabled=True, actor=OWNER):
    with acting_as(actor):
        version = policy.get_policy("decision")["version"]
        return policy.add_item(
            "decision",
            {
                "expected_version": version,
                "label": label,
                "statement": label,
                "rule": value,
                "enabled": enabled,
            },
        )["item"]


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
    workspace, _ = services
    first = job(workspace, "Softwareentwickler", GERMAN, 1)
    signals = first["signals"]
    assert signals["computed"] and signals["duplicate_checked"]
    assert signals["language"] == "de" and signals["language_confidence"] > 0.5
    assert signals["required"] == [["de"], ["en"]] and signals["duplicate"] is None
    assert not signals["no_longer_listed"] and signals["rules"] == []
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
    workspace, _ = services
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


def test_a_rule_dismisses_only_matching_new_jobs_names_the_rule_and_can_be_reverted(services):
    workspace, policy = services
    waiting = job(workspace, "Softwareentwickler", GERMAN, 1)
    languages = add_rule(
        policy,
        "Languages outside my list",
        rule("language_required", "not_in", ["English", "Italian"]),
    )
    # Rules act only on new jobs: the job already waiting stays in the Inbox.
    assert workspace.get_job(waiting["id"])["triage"] == "new"
    preview = policy.preview_rule({"rule": languages["rule"]})
    assert (preview["matches"], preview["inbox"], preview["pending"]) == (1, 1, 0)
    assert preview["examples"][0]["id"] == waiting["id"]
    assert workspace.get_job(waiting["id"])["triage"] == "new"

    dismissed = job(workspace, "Backend Entwickler", GERMAN, 2)
    kept = job(workspace, "Data Engineer", ENGLISH, 3)
    assert kept["triage"] == "new" and kept["dismissal"] is None
    assert dismissed["triage"] == "dismissed"
    assert dismissed["dismissal"]["rule"] == {
        "item_id": languages["id"],
        "label": languages["label"],
    }
    assert dismissed["dismissal"]["category"] == "rule"
    assert dismissed["dismissal"]["by"]["kind"] == "system"
    assert dismissed["signals"]["rules"] == [
        {"item_id": languages["id"], "label": languages["label"], "action": "dismiss"}
    ]
    event = workspace.db.one(
        "SELECT payload,actor_kind FROM events WHERE job_id=? AND kind='triage_changed'",
        (dismissed["id"],),
    )
    assert json.loads(event["payload"]) == {
        "from": "new",
        "to": "dismissed",
        "rule": {"item_id": languages["id"]},
    }
    assert event["actor_kind"] == "system"
    by_rule = workspace.list_jobs(triage="dismissed", dismissed_by="rule", include_counts=True)
    assert [item["id"] for item in by_rule["items"]] == [dismissed["id"]]
    assert by_rule["counts"]["dismissed_by"] == {"rule": 1, "agent": 0, "owner": 0, "other": 0}
    assert workspace.list_jobs(rule_id=languages["id"])["total"] == 1

    # Restoring is an ordinary triage change, and the job stays restored.
    restored = workspace.set_triage(dismissed["id"], "new", dismissed["version"])
    assert restored["triage"] == "new" and restored["dismissal"] is None
    again = workspace.ingest_job({"url": "https://example.test/jobs/2", "posting": GERMAN + " "})
    assert again["triage"] == "new" and not again["created"]


def test_rules_act_only_when_enabled_and_confirmed(services):
    workspace, policy = services
    proposal = add_rule(
        policy, "Agent proposal", rule("posting_language", "in", ["de"]), enabled=False, actor=AGENT
    )
    assert not proposal["confirmed"] and not proposal["enabled"]
    disabled = add_rule(
        policy, "Switched off", rule("posting_language", "in", ["de"]), enabled=False
    )
    assert disabled["confirmed"] and not disabled["enabled"]
    first = job(workspace, "Softwareentwickler", GERMAN, 1)
    assert first["triage"] == "new" and first["signals"]["rules"] == []
    # An agent edit switches an enabled rule off and makes it a proposal again.
    enabled = add_rule(policy, "German postings", rule("posting_language", "in", ["de"]))
    with acting_as(AGENT):
        policy.update_item(
            enabled["id"],
            {
                "expected_version": policy.get_policy("decision")["version"],
                "rule": rule("posting_language", "in", ["de", "fr"]),
            },
        )
    second = job(workspace, "Entwickler", GERMAN, 2)
    assert second["triage"] == "new"


def test_flag_rules_record_a_match_and_the_owner_adds_jobs_freely(services):
    workspace, policy = services
    flag = add_rule(
        policy, "Mention duplicates", rule("likely_duplicate", "at_least", 0.85, "flag")
    )
    dismiss = add_rule(policy, "German postings", rule("posting_language", "in", ["de"]))
    first = job(workspace, "Data Engineer", ENGLISH, 1, company="Northstar Labs")
    copy = job(workspace, "Data Engineer", ENGLISH, 2, company="Northstar Labs")
    assert copy["triage"] == "new"
    assert copy["signals"]["rules"] == [
        {"item_id": flag["id"], "label": flag["label"], "action": "flag"}
    ]
    assert workspace.list_jobs(signal="flagged")["total"] == 1
    assert first["signals"]["rules"] == []
    # A job the owner adds in the dashboard is never dismissed by a rule.
    with acting_as(OWNER):
        added = job(workspace, "Softwareentwickler", GERMAN, 3)
    assert added["triage"] == "new" and added["signals"]["language"] == "de"
    # An agent's ingest is collection like any other.
    with acting_as(AGENT):
        collected = job(workspace, "Entwickler", GERMAN, 4)
    assert collected["triage"] == "dismissed"
    assert collected["dismissal"]["rule"]["item_id"] == dismiss["id"]


def test_triage_reasons_and_who_dismissed(services):
    workspace, _ = services
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
    assert counts["dismissed_by"] == {"rule": 0, "agent": 1, "owner": 1, "other": 0}
    with pytest.raises(Exception, match="reason"):
        workspace.set_triage(third["id"], "shortlisted", third["version"], "Nice")


def test_a_board_that_stops_listing_a_posting_marks_it_and_its_rule_acts(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "collection.sqlite")
    service = DiscoveryService(workspace)
    workspace.discovery = service
    policy = PolicyService(workspace)
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
    add_rule(policy, "Postings no longer listed", rule("no_longer_listed", "is", True))
    listed["value"] = ["1"]
    second = run()
    assert second["state"] == "succeeded" and second["result"]["unlisted"] == 2
    after = {item["title"]: item for item in workspace.list_jobs()["items"]}
    assert after["Engineer 2"]["signals"]["no_longer_listed"]
    # Untouched jobs to review are dismissed by the rule; a shortlisted job is not.
    assert after["Engineer 2"]["triage"] == "dismissed"
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


def test_rest_and_mcp_expose_signals_rules_and_the_preview_alike(tmp_path):
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

    preview_rule = rule("likely_duplicate", "at_least", 0.85)
    with TestClient(app, base_url="http://localhost:8080") as client:
        over_rest = client.post(
            "/api/v1/policy/rules/preview", json={"rule": preview_rule}, headers=headers
        )
        assert over_rest.status_code == 200, over_rest.text
        assert over_rest.json() == tool(
            client, "policy_rule_preview", {"value": {"rule": preview_rule}}
        )
        assert over_rest.json()["matches"] == 1
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
        bad = client.post(
            "/api/v1/policy/rules/preview",
            json={"rule": rule("likely_duplicate", "in", ["en"])},
            headers=headers,
        )
        assert bad.status_code == 422
