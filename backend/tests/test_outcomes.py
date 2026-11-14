"""Employer replies through the one update path, no reply and its period."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from openings.actors import OWNER, acting_as, token_actor
from openings.errors import DomainError
from openings.outcomes import no_reply_period, today
from openings.preferences import PreferencesService


def days_ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).date().isoformat()


def stamp_ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="microseconds")


def attempt(workspace, title="Synthetic data engineer", status=None, **fields):
    job = workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})
    application = workspace.create_application({"job_id": job["id"]})
    if status:
        application = workspace.update_application(
            application["id"],
            {"expected_version": application["version"], "status": status, **fields},
        )
    return application


def move(workspace, application, **fields):
    current = workspace.get_application(application["id"])
    return workspace.update_application(
        application["id"], {"expected_version": current["version"], **fields}
    )


def reply(workspace, application, **value):
    return move(workspace, application, reply=value)


def kinds(application):
    return [(item["kind"], item["date"]) for item in application["replies"]]


def events_of(workspace, application_id, since):
    return workspace.db.all(
        "SELECT kind,payload,subject_type FROM events WHERE application_id=? AND rowid>? "
        "ORDER BY rowid",
        (application_id, since),
    )


def last_rowid(workspace):
    return workspace.db.one("SELECT coalesce(max(rowid),0) AS n FROM events")["n"]


@pytest.mark.parametrize(
    ("kind", "status", "outcome"),
    [
        ("interview", "interview", None),
        ("offer", "offer", None),
        ("rejection", "closed", "rejected"),
        ("other", "applied", None),
    ],
)
def test_recording_a_reply_moves_the_stage_by_its_kind_in_one_event(
    workspace, kind, status, outcome
):
    sent = attempt(workspace, status="applied")
    before = last_rowid(workspace)
    recorded = reply(workspace, sent, kind=kind, note="Synthetic note.")
    assert (recorded["status"], recorded["outcome"]) == (status, outcome)
    assert kinds(recorded) == [(kind, today())]  # The date defaults to today.
    assert recorded["last_reply"]["kind"] == kind
    assert recorded["version"] == sent["version"] + 1
    events = events_of(workspace, sent["id"], before)
    assert [(event["kind"], event["subject_type"]) for event in events] == [
        ("reply_added", "reply")
    ]
    payload = json.loads(events[0]["payload"])
    assert payload["kind"] == kind and "Synthetic note" not in json.dumps(payload)
    if kind == "other":
        assert "to" not in payload
    else:
        assert (payload["from"], payload["to"]) == ("applied", status)


def test_replies_need_a_sent_application_and_move_only_forward(workspace):
    shortlisted = attempt(workspace)
    with pytest.raises(DomainError) as error:
        reply(workspace, shortlisted, kind="interview")
    assert (error.value.status, error.value.code) == (409, "application_not_sent")
    sent = attempt(workspace, "Synthetic backend engineer", status="applied")
    # A reply sets the stage itself.
    with pytest.raises(DomainError) as error:
        move(workspace, sent, status="interview", reply={"kind": "interview"})
    assert error.value.code == "reply_stage"
    with pytest.raises(ValidationError):
        reply(workspace, sent, date=today())
    with pytest.raises(ValidationError):
        reply(workspace, sent, kind="offer", date=days_ago(-3))
    offer = reply(workspace, sent, kind="offer", date=days_ago(3))
    # A later interview round does not move an Offer back.
    again = reply(workspace, offer, kind="interview", date=days_ago(1))
    assert again["status"] == "offer"
    # One reply of a kind per day; other may repeat.
    with pytest.raises(DomainError) as error:
        reply(workspace, sent, kind="offer", date=days_ago(3))
    assert error.value.code == "reply_exists"
    reply(workspace, sent, kind="other")
    reply(workspace, sent, kind="other")
    assert len(workspace.get_application(sent["id"])["replies"]) == 4
    # A rejection after an offer closes it.
    closed = reply(workspace, sent, kind="rejection")
    assert (closed["status"], closed["outcome"]) == ("closed", "rejected")
    # A late reply reopens an application closed as no reply.
    waited = attempt(workspace, "Synthetic analyst", status="applied")
    waited = move(workspace, waited, status="closed", outcome="no_response")
    reopened = reply(workspace, waited, kind="interview")
    assert (reopened["status"], reopened["outcome"], reopened["concluded_on"]) == (
        "interview",
        None,
        None,
    )


def test_replies_are_corrected_and_removed_through_the_same_update(workspace):
    sent = attempt(workspace, status="applied")
    agent = token_actor("token-1", "Synthetic agent", "agent")
    with acting_as(agent):
        recorded = reply(workspace, sent, kind="interview", date=days_ago(3), note="Call.")
    first = recorded["replies"][0]
    assert first["created_by"] == "agent:Synthetic agent" and first["version"] == 1
    before = last_rowid(workspace)
    corrected = reply(workspace, sent, id=first["id"], date=days_ago(4), note="Second round.")
    assert corrected["status"] == "interview"
    item = corrected["replies"][0]
    assert (item["date"], item["version"], item["note"]) == (days_ago(4), 2, "Second round.")
    # A correction of the kind never moves the stage.
    assert reply(workspace, sent, id=first["id"], kind="offer")["status"] == "interview"
    with pytest.raises(DomainError) as error:
        reply(workspace, sent, id="missing", note="x")
    assert error.value.status == 404
    with pytest.raises(ValidationError):
        reply(workspace, sent, id=first["id"], remove=True, note="x")
    removed = reply(workspace, sent, id=first["id"], remove=True)
    assert removed["replies"] == [] and removed["status"] == "interview"
    events = events_of(workspace, sent["id"], before)
    assert [event["kind"] for event in events] == ["reply_edited", "reply_edited", "reply_removed"]
    assert json.loads(events[0]["payload"]) == {"fields": ["date", "note"], "version": 2}
    assert "Second round" not in json.dumps([event["payload"] for event in events])


def test_mark_applied_and_its_undo_while_no_reply_exists(workspace):
    application = attempt(workspace)
    applied = move(workspace, application, status="applied")
    assert applied["applied_at"] and applied["ready"] is False
    edited = move(workspace, applied, applied_at="2026-01-05")
    assert edited["applied_at"].startswith("2026-01-05")
    undone = move(workspace, edited, status="shortlisted")
    assert (undone["status"], undone["applied_at"]) == ("shortlisted", None)
    applied = move(workspace, undone, status="applied")
    reply(workspace, applied, kind="other")
    with pytest.raises(DomainError) as error:
        move(workspace, applied, status="shortlisted")
    assert (error.value.status, error.value.code) == (409, "application_has_replies")


def test_no_reply_closes_only_sent_applications_by_hand(workspace):
    shortlisted = attempt(workspace)
    with pytest.raises(DomainError) as error:
        move(workspace, shortlisted, status="closed", outcome="no_response")
    assert (error.value.status, error.value.code) == (409, "application_not_sent")

    sent = attempt(workspace, "Synthetic backend engineer", status="applied")
    closed = move(workspace, sent, status="closed", outcome="no_response")
    assert (closed["outcome"], closed["concluded_on"]) == ("no_response", today())
    assert closed["replies"] == []
    corrected = move(workspace, sent, concluded_on=days_ago(2))
    assert corrected["concluded_on"] == days_ago(2)
    with pytest.raises(DomainError) as error:
        move(workspace, sent, outcome="not_pursued", concluded_on=days_ago(2))
    assert error.value.code == "application_concluded_on"
    reopened = move(workspace, sent, status="applied")
    assert (reopened["outcome"], reopened["concluded_on"]) == (None, None)

    bulk = attempt(workspace, "Synthetic analyst", status="applied")
    unsent = attempt(workspace, "Synthetic tester")
    result = workspace.bulk_applications(
        {
            "action": "close",
            "outcome": "no_response",
            "items": [
                {
                    "id": item["id"],
                    "expected_version": workspace.get_application(item["id"])["version"],
                }
                for item in (bulk, unsent)
            ],
        }
    )
    assert [item["ok"] for item in result["items"]] == [True, False]
    assert result["items"][1]["error"]["code"] == "application_not_sent"
    listed = workspace.list_applications(outcome="no_response")
    assert [item["id"] for item in listed["items"]] == [bulk["id"]]
    assert listed["items"][0]["concluded_on"] == today()
    funnel = workspace.overview()["funnel"]
    assert funnel[0]["outcomes"]["no_response"] == 1


def test_the_no_reply_period_lists_overdue_applications_and_closes_nothing(workspace):
    with workspace.db.connect() as conn:
        assert no_reply_period(conn) == {"days": 30, "source": "default"}
    old = attempt(workspace, "Synthetic old", status="applied", applied_at=stamp_ago(40))
    answered = attempt(workspace, "Synthetic answered", status="applied", applied_at=stamp_ago(50))
    reply(workspace, answered, kind="other")
    recent = attempt(workspace, "Synthetic recent", status="applied", applied_at=stamp_ago(10))
    attempt(workspace, "Synthetic interview", status="interview", applied_at=stamp_ago(60))
    overdue = workspace.list_applications(needs="reply_overdue")
    # Applied, without a reply, past the period.
    assert [item["id"] for item in overdue["items"]] == [old["id"]]
    assert overdue["no_reply"]["overdue"] == 1 and overdue["no_reply"]["days"] == 30
    # Nothing closes automatically: listing and reading leave the stage.
    assert workspace.get_application(old["id"])["status"] == "applied"

    preferences = PreferencesService(workspace)
    with acting_as(OWNER):
        settings = preferences.update_settings({"expected_version": 0, "no_reply_days": 7})
    assert {item["id"] for item in workspace.list_applications(needs="reply_overdue")["items"]} == {
        old["id"],
        recent["id"],
    }
    with acting_as(OWNER):
        preferences.update_settings({"expected_version": settings["version"], "no_reply_days": 45})
    listed = workspace.list_applications(needs="reply_overdue")
    assert listed["no_reply"]["days"] == 45 and listed["no_reply"]["source"] == "settings"
    assert listed["no_reply"]["overdue"] == 0 and listed["items"] == []
