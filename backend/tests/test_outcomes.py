"""Employer responses, the automatic responses of stage moves, no reply and its period."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from openings.actors import OWNER, acting_as, token_actor
from openings.errors import DomainError
from openings.outcomes import ResponseService, no_reply_period, reply_days, today
from openings.policy import PolicyService
from openings.workspace import Workspace


def days_ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).date().isoformat()


def stamp_ago(days):
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="microseconds")


@pytest.fixture
def workspace(tmp_path):
    return Workspace(tmp_path / "outcomes.sqlite")


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


def kinds(application):
    return [(item["kind"], item["date"], item["origin"]) for item in application["responses"]]


def test_responses_are_recorded_corrected_and_removed_for_a_sent_application(workspace):
    responses = ResponseService(workspace)
    draft = attempt(workspace)
    with pytest.raises(DomainError) as error:
        responses.add_response(draft["id"], {"kind": "other", "date": today()})
    assert (error.value.status, error.value.code) == (409, "application_not_sent")

    sent = attempt(workspace, "Synthetic backend engineer", status="applied")
    agent = token_actor("token-1", "Synthetic agent", "agent")
    with acting_as(agent):
        first = responses.add_response(
            sent["id"],
            {
                "kind": "other",
                "date": days_ago(3),
                "note": "Asked for references.",
                "idempotency_key": "k1",
            },
        )
    assert first["created_by"]["token_kind"] == "agent" and first["origin"] == "manual"
    assert first["estimated"] is False and first["version"] == 1
    # A retry with the same key returns the same response; another use of the key is refused.
    assert (
        responses.add_response(
            sent["id"], {"kind": "other", "date": days_ago(3), "idempotency_key": "k1"}
        )["id"]
        == first["id"]
    )
    with pytest.raises(DomainError) as error:
        responses.add_response(
            sent["id"], {"kind": "rejection", "date": days_ago(3), "idempotency_key": "k1"}
        )
    assert error.value.code == "conflict"
    # Other answers may repeat on a day; one response of another kind per day.
    responses.add_response(sent["id"], {"kind": "other", "date": days_ago(3)})
    interview = responses.add_response(sent["id"], {"kind": "interview", "date": days_ago(2)})
    with pytest.raises(DomainError) as error:
        responses.add_response(sent["id"], {"kind": "interview", "date": days_ago(2)})
    assert error.value.code == "response_exists"
    assert error.value.details == {"response_id": interview["id"]}
    # Adding a response never moves the stage.
    assert workspace.get_application(sent["id"])["status"] == "applied"
    with pytest.raises(ValidationError):
        responses.add_response(sent["id"], {"kind": "offer", "date": days_ago(-3)})
    with pytest.raises(ValidationError):
        responses.add_response(sent["id"], {"kind": "offer", "date": "2026-02-30"})

    corrected = responses.update_response(
        interview["id"], {"expected_version": 1, "date": days_ago(4), "note": "Second round."}
    )
    assert (corrected["date"], corrected["version"], corrected["note"]) == (
        days_ago(4),
        2,
        "Second round.",
    )
    with pytest.raises(DomainError) as error:
        responses.update_response(interview["id"], {"expected_version": 1, "note": "Stale"})
    assert error.value.details == {"current_version": 2}
    listed = responses.list_responses(sent["id"])
    assert listed["total"] == 3 and listed["items"][0]["date"] == days_ago(3)
    read = workspace.get_application(sent["id"])
    assert len(read["responses"]) == 3 and read["last_response"]["date"] == days_ago(3)
    assert responses.remove_response(interview["id"], 2) == {"deleted": True, "id": interview["id"]}
    assert responses.list_responses(sent["id"])["total"] == 2

    # Events name the response, never its note.
    events = workspace.db.all(
        "SELECT kind,payload,subject_type,actor_token_kind FROM events WHERE subject_type='response' ORDER BY created_at"
    )
    assert [event["kind"] for event in events] == [
        "response_added",
        "response_added",
        "response_added",
        "response_edited",
        "response_removed",
    ]
    assert events[0]["actor_token_kind"] == "agent"
    assert json.loads(events[3]["payload"]) == {"fields": ["date", "note"], "version": 2}
    assert "references" not in json.dumps([event["payload"] for event in events]).lower()
    assert "Second round" not in json.dumps([event["payload"] for event in events])


def test_stage_moves_record_the_matching_response_once(workspace):
    sent = attempt(workspace, status="applied")
    interview = move(
        workspace, sent, status="interview", response_date=days_ago(5), response_note="Call."
    )
    assert kinds(interview) == [("interview", days_ago(5), "stage")]
    assert interview["responses"][0]["note"] == "Call."
    # Back and forth on the same day records nothing twice.
    move(workspace, sent, status="applied")
    again = move(workspace, sent, status="interview", response_date=days_ago(5))
    assert kinds(again) == [("interview", days_ago(5), "stage")]
    offer = move(workspace, sent, status="offer")
    assert kinds(offer)[0] == ("offer", today(), "stage")
    accepted = move(workspace, sent, status="closed", outcome="accepted")
    # An offer is on record: accepting adds none.
    assert [kind for kind, _, _ in kinds(accepted)] == ["offer", "interview"]

    rejected = attempt(workspace, "Synthetic platform engineer", status="applied")
    closed = move(
        workspace, rejected, status="closed", outcome="rejected", response_date=days_ago(1)
    )
    assert kinds(closed) == [("rejection", days_ago(1), "stage")]
    # Correcting the outcome of a closed application to rejected again records nothing new.
    assert kinds(move(workspace, rejected, note="Synthetic")) == kinds(closed)

    accepted_directly = attempt(workspace, "Synthetic analyst", status="interview")
    assert kinds(accepted_directly) == [("interview", today(), "stage")]
    done = move(workspace, accepted_directly, status="closed", outcome="accepted")
    assert [kind for kind, _, _ in kinds(done)] == ["offer", "interview"]

    # A Draft closed as rejected was never sent: no employer answered it.
    draft = attempt(workspace, "Synthetic tester")
    unsent = move(workspace, draft, status="closed", outcome="rejected")
    assert unsent["responses"] == [] and unsent["applied_at"] is None
    other = attempt(workspace, "Synthetic designer")
    with pytest.raises(DomainError) as error:
        move(workspace, other, status="closed", outcome="rejected", response_date=days_ago(1))
    assert error.value.code == "application_not_sent"
    # A response date belongs to a change that records a response.
    with pytest.raises(DomainError) as error:
        move(workspace, other, priority=2, response_date=days_ago(1))
    assert (error.value.status, error.value.code) == (422, "application_response")
    with pytest.raises(ValidationError):
        move(workspace, other, status="applied", response_date=days_ago(-2))

    # Bulk closing as rejected records rejections dated today.
    bulk = attempt(workspace, "Synthetic mobile developer", status="applied")
    current = workspace.get_application(bulk["id"])
    result = workspace.bulk_applications(
        {
            "action": "close",
            "outcome": "rejected",
            "items": [{"id": bulk["id"], "expected_version": current["version"]}],
        }
    )
    assert result["succeeded"] == 1
    assert kinds(workspace.get_application(bulk["id"])) == [("rejection", today(), "stage")]


def test_no_reply_closes_only_sent_applications_with_the_day_it_was_concluded(workspace):
    draft = attempt(workspace)
    with pytest.raises(DomainError) as error:
        move(workspace, draft, status="closed", outcome="no_response")
    assert (error.value.status, error.value.code) == (409, "application_not_sent")

    sent = attempt(workspace, "Synthetic backend engineer", status="applied")
    closed = move(workspace, sent, status="closed", outcome="no_response")
    assert (closed["outcome"], closed["concluded_on"]) == ("no_response", today())
    assert closed["responses"] == []
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
    # The funnel counts the new outcome.
    funnel = workspace.overview()["funnel"]
    assert funnel[0]["outcomes"]["no_response"] == 1


def test_the_no_reply_period_comes_from_the_policy_and_lists_the_applications_past_it(workspace):
    assert reply_days(45) == reply_days("45") == reply_days(" 45 days ") == 45
    assert reply_days("six weeks") is reply_days(0) is reply_days(True) is reply_days(4000) is None
    with workspace.db.connect() as conn:
        assert no_reply_period(conn) == {
            "days": 30,
            "source": "default",
            "item_id": None,
            "confirmed": False,
        }
    old = attempt(workspace, "Synthetic old", status="applied", applied_at=stamp_ago(40))
    recent = attempt(workspace, "Synthetic recent", status="applied", applied_at=stamp_ago(10))
    attempt(workspace, "Synthetic interview", status="interview", applied_at=stamp_ago(60))
    due = workspace.list_applications(no_reply_due=True)
    assert [item["id"] for item in due["items"]] == [old["id"]]
    assert due["no_reply"]["due"] == 1 and due["no_reply"]["days"] == 30
    assert old["id"] not in {
        item["id"] for item in workspace.list_applications(no_reply_due=False)["items"]
    }

    policy = PolicyService(workspace)
    with acting_as(token_actor("token-1", "Synthetic agent", "agent")):
        proposal = policy.add_item(
            "decision",
            {
                "expected_version": 0,
                "label": "No response after",
                "value": 7,
                "value_type": "number",
            },
        )
    with workspace.db.connect() as conn:
        period = no_reply_period(conn)
    assert period == {
        "days": 7,
        "source": "policy",
        "item_id": proposal["item"]["id"],
        "confirmed": False,
    }
    assert {item["id"] for item in workspace.list_applications(no_reply_due=True)["items"]} == {
        old["id"],
        recent["id"],
    }
    # A confirmed item comes before a proposal.
    with acting_as(OWNER):
        confirmed = policy.add_item(
            "decision",
            {"expected_version": 1, "label": "No reply", "value": "45 days", "value_type": "text"},
        )
    listed = workspace.list_applications(no_reply_due=True)
    assert listed["no_reply"] == {
        "days": 45,
        "source": "policy",
        "item_id": confirmed["item"]["id"],
        "confirmed": True,
        "due": 0,
    }
    assert listed["items"] == []


def test_ready_filter_separates_preparing_from_ready(workspace):
    plain = attempt(workspace)
    marked = attempt(workspace, "Synthetic ready")
    with workspace.db.transaction() as conn:
        conn.execute("UPDATE applications SET ready_at=? WHERE id=?", (stamp_ago(0), marked["id"]))
    assert [item["id"] for item in workspace.list_applications(ready=True)["items"]] == [
        marked["id"]
    ]
    assert [
        item["id"] for item in workspace.list_applications(ready=False, status="draft")["items"]
    ] == [plain["id"]]
