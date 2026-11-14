"""Preferences: whole-section writes with versions, two settings, and what reads them."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from openings.actors import OWNER, acting_as, token_actor
from openings.errors import DomainError
from openings.outcomes import no_reply_period
from openings.preferences import SECTIONS, PreferencesService

AGENT = token_actor("token-agent", "Synthetic agent", "agent")


@pytest.fixture
def services(workspace):
    return workspace, PreferencesService(workspace)


def section(preferences, name):
    return next(s for s in preferences.get_preferences()["sections"] if s["section"] == name)


def write(preferences, name, items, actor=OWNER):
    with acting_as(actor):
        return preferences.update_preferences(
            name, {"expected_version": section(preferences, name)["version"], "items": items}
        )


def stamp_ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="microseconds")


def test_a_new_workspace_has_five_sections_and_the_default_settings(services):
    _, preferences = services
    read = preferences.get_preferences()
    assert [item["section"] for item in read["sections"]] == list(SECTIONS)
    assert [item["title"] for item in read["sections"]] == [
        "What I'm looking for",
        "What I rule out",
        "Facts about me",
        "Writing rules",
        "Working with me",
    ]
    writing = read["sections"][3]
    assert writing["version"] == 0 and writing["items"][0]["scope"] == "all"
    assert writing["items"][0]["text"].startswith("Use only the supplied career evidence.")
    assert all(not s["items"] for s in read["sections"] if s["section"] != "writing")
    assert read["settings"] == {
        "no_reply_days": 30,
        "spoken_languages": [],
        "version": 0,
        "updated_at": None,
    }


def test_a_write_replaces_the_section_records_who_wrote_it_and_checks_its_version(services):
    workspace, preferences = services
    first = write(preferences, "looking_for", [{"text": "  Backend roles.  "}, {"text": "Zurich."}])
    assert first["items"] == [{"text": "Backend roles."}, {"text": "Zurich."}]
    assert (first["version"], first["updated_by"]) == (1, "owner")
    # The same list again is no change: no version, no record.
    assert write(preferences, "looking_for", first["items"])["version"] == 1
    second = write(preferences, "looking_for", [{"text": "Zurich."}], actor=AGENT)
    assert second["items"] == [{"text": "Zurich."}]
    assert (second["version"], second["updated_by"]) == (2, "agent:Synthetic agent")
    events = workspace.db.all(
        "SELECT kind,payload,subject_type,subject_id,actor FROM events "
        "WHERE kind='preferences_updated' ORDER BY created_at"
    )
    assert [(e["subject_type"], e["subject_id"], e["actor"]) for e in events] == [
        ("preferences", "looking_for", "owner"),
        ("preferences", "looking_for", "agent:Synthetic agent"),
    ]
    # The change record names the section and its size, never the text.
    assert json.loads(events[1]["payload"]) == {"section": "looking_for", "version": 2, "items": 1}
    # Other sections are untouched.
    assert section(preferences, "ruled_out")["version"] == 0

    # A stale version is a conflict that names the current one.
    write(preferences, "facts", [{"text": "Notice period: one month."}])
    with pytest.raises(DomainError) as stale:
        preferences.update_preferences("facts", {"expected_version": 0, "items": []})
    assert (stale.value.status, stale.value.code) == (409, "conflict")
    assert stale.value.details == {"current_version": 1, "id": "facts", "section": "facts"}
    with pytest.raises(DomainError) as unknown:
        preferences.update_preferences("decision", {"expected_version": 0, "items": []})
    assert unknown.value.status == 404


def test_only_writing_rules_have_a_scope_and_statements_have_limits(services):
    _, preferences = services
    written = write(
        preferences,
        "writing",
        [{"text": "One page.", "scope": "cv"}, {"text": "British spelling."}],
    )
    assert written["items"] == [
        {"text": "One page.", "scope": "cv"},
        {"text": "British spelling.", "scope": "all"},
    ]
    with pytest.raises(DomainError) as scoped:
        write(preferences, "facts", [{"text": "Notice period.", "scope": "cv"}])
    assert scoped.value.code == "preferences_scope"
    with pytest.raises(ValidationError):
        write(preferences, "writing", [{"text": "Short.", "scope": "body"}])

    for items in (
        [{"text": "x" * 2001}],
        [{"text": "   "}],
        [{"text": f"Item {n}"} for n in range(201)],
        [{"text": "Fine.", "label": "Not a field"}],
    ):
        with pytest.raises(ValidationError):
            write(preferences, "ruled_out", items)
    assert section(preferences, "ruled_out")["version"] == 0
    # The limits themselves are allowed.
    write(preferences, "ruled_out", [{"text": "x" * 2000}] + [{"text": "y"}] * 199)
    assert len(section(preferences, "ruled_out")["items"]) == 200


def test_settings_change_with_their_version(services):
    workspace, preferences = services
    with acting_as(OWNER):
        changed = preferences.update_settings(
            {"expected_version": 0, "no_reply_days": 45, "spoken_languages": ["English", "it"]}
        )
    assert (changed["no_reply_days"], changed["spoken_languages"]) == (45, ["en", "it"])
    assert changed["version"] == 1
    # Omitted settings stay; an unchanged write is no new version.
    kept = preferences.update_settings({"expected_version": 1, "no_reply_days": 45})
    assert kept["version"] == 1 and kept["spoken_languages"] == ["en", "it"]
    with pytest.raises(DomainError) as stale:
        preferences.update_settings({"expected_version": 0, "no_reply_days": 10})
    assert stale.value.status == 409
    assert stale.value.details == {"current_version": 1, "id": "settings"}
    for wrong in (
        {"no_reply_days": 0},
        {"no_reply_days": 366},
        {"no_reply_days": "45"},
        {"no_reply_days": None},
        {"spoken_languages": ["Klingon"]},
        {"spoken_languages": None},
    ):
        with pytest.raises(ValidationError):
            preferences.update_settings({"expected_version": 1, **wrong})
    event = workspace.db.one("SELECT payload FROM events WHERE kind='settings_updated'")
    assert json.loads(event["payload"]) == {
        "fields": ["no_reply_days", "spoken_languages"],
        "version": 1,
    }


def test_the_no_reply_period_comes_from_the_settings(services):
    workspace, preferences = services

    def attempt(title, status, days):
        job = workspace.ingest_job({"title": title, "company": "Example", "posting": "APIs."})
        application = workspace.create_application({"job_id": job["id"]})
        return workspace.update_application(
            application["id"],
            {
                "expected_version": application["version"],
                "stage": status,
                "applied_at": stamp_ago(days),
            },
        )

    with workspace.db.connect() as conn:
        assert no_reply_period(conn) == {"days": 30, "source": "default"}
    old = attempt("Synthetic old", "applied", 40)
    recent = attempt("Synthetic recent", "applied", 10)
    attempt("Synthetic interview", "interview", 60)
    due = workspace.list_applications(needs="reply_overdue")
    assert [item["id"] for item in due["items"]] == [old["id"]]
    assert due["no_reply"] == {"days": 30, "source": "default", "overdue": 1}
    preferences.update_settings({"expected_version": 0, "no_reply_days": 7})
    listed = workspace.list_applications(needs="reply_overdue")
    assert {item["id"] for item in listed["items"]} == {old["id"], recent["id"]}
    assert listed["no_reply"] == {"days": 7, "source": "settings", "overdue": 2}
    # A text that names a period does nothing: only the setting counts.
    write(preferences, "facts", [{"text": "No reply: 45 days."}])
    with workspace.db.connect() as conn:
        assert no_reply_period(conn)["days"] == 7


GERMAN = (
    "Wir suchen eine Person für unser Team in Bern. Deine Aufgaben: Du entwickelst neue "
    "Funktionen in Python. Dein Profil: fließend Deutsch und gute Englischkenntnisse."
)
FRENCH_OR_GERMAN = "Fluent French or German is required. You will build APIs in Python."
ENGLISH = "You will build services in Python with a small team. Fluent English is required."


def test_the_languages_filter_hides_jobs_and_never_dismisses_them(services):
    workspace, preferences = services
    jobs = {
        name: workspace.ingest_job(
            {"title": f"Engineer {name}", "company": name, "posting": posting}
        )
        for name, posting in (
            ("german", GERMAN),
            ("either", FRENCH_OR_GERMAN),
            ("english", ENGLISH),
            ("none", "Build APIs in Python with a friendly team."),
        )
    }
    assert jobs["german"]["signals"]["required"] == [["de"], ["en"]]
    # Without spoken languages the filter hides nothing.
    listed = workspace.list_jobs(hide_unspoken_required=True)
    assert listed["total"] == 4
    assert listed["unspoken_required"] == {"spoken_languages": [], "count": 0, "hidden": False}
    preferences.update_settings({"expected_version": 0, "spoken_languages": ["en", "fr"]})
    shown = workspace.list_jobs(hide_unspoken_required=True, include_counts=True)
    # German is required by one posting; French or German is satisfied by French.
    assert {item["company"] for item in shown["items"]} == {"either", "english", "none"}
    assert shown["unspoken_required"] == {
        "spoken_languages": ["en", "fr"],
        "count": 1,
        "hidden": True,
    }
    assert shown["counts"]["new"] == 3
    # Off: every job is listed, with how many the filter would hide.
    everything = workspace.list_jobs(hide_unspoken_required=False)
    assert everything["total"] == 4 and everything["unspoken_required"]["count"] == 1
    assert everything["unspoken_required"]["hidden"] is False
    assert "unspoken_required" not in workspace.list_jobs()
    # The count follows the other filters.
    assert (
        workspace.list_jobs(q="Engineer german", hide_unspoken_required=False)["unspoken_required"][
            "count"
        ]
        == 1
    )
    assert (
        workspace.list_jobs(company="english", hide_unspoken_required=True)["unspoken_required"][
            "count"
        ]
        == 0
    )
    # Nothing was dismissed.
    assert {job["triage"] for job in workspace.list_jobs()["items"]} == {"new"}
