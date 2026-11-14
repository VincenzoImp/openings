"""Synthetic work for Today and the histories in the browser-test workspace.

Ready applications with deadlines, a blocked one, applications sent at
different times, an agent's changes in a few batches (notes, a review that
shortlisted and dismissed jobs) and a few collection runs. Everything is
fictional.
"""

import json
from datetime import UTC, datetime, timedelta

from document_fixtures import source_revision
from openings.actors import OWNER, acting_as, batch, token_actor
from openings.common import new_id

POSTING = "Build reliable data services.\n\nResponsibilities\nDesign pipelines with a small team."


def dated(value):
    """A day as ISO text, also inside a reply."""
    if isinstance(value, dict):
        return {key: dated(item) for key, item in value.items()}
    return value.isoformat() if hasattr(value, "isoformat") else value


def ago(**delta):
    return (datetime.now(UTC) - timedelta(**delta)).isoformat(timespec="microseconds")


def seed_today(app, client, before_agent):
    """Seed the work; ``before_agent(agent)`` runs before the agent's last batch."""
    workspace, documents = app.state.workspace, app.state.documents
    with acting_as(OWNER):
        token = app.state.auth.create_token("career-agent", "agent")
    agent = token_actor(token["id"], "career-agent", "agent")

    def start(title, company, location, **fields):
        job = workspace.ingest_job(
            {"title": title, "company": company, "location": location, "posting": POSTING}
        )
        return workspace.create_application({"job_id": job["id"], **fields})

    def make_ready(application):
        """A CV and a letter, each with its source and PDF: the application is Ready."""
        for kind, title in (("cv", "CV"), ("letter", "Letter")):
            source_revision(
                documents,
                client.put,
                application["id"],
                kind,
                "Synthetic.",
                title=title,
            )

    def shift(batch_id, started, minutes=0):
        """Move the changes of one batch into the past."""
        begin = datetime.now(UTC) - started
        with workspace.db.transaction() as conn:
            rows = conn.execute(
                "SELECT id FROM events WHERE batch_id=? ORDER BY created_at", (batch_id,)
            ).fetchall()
            for index, row in enumerate(rows):
                moment = begin + timedelta(minutes=minutes) * (index + 1) / (len(rows) + 1)
                conn.execute(
                    "UPDATE events SET created_at=? WHERE id=?",
                    (moment.isoformat(timespec="microseconds"), row["id"]),
                )

    def last_batch():
        return workspace.db.one("SELECT batch_id FROM events ORDER BY created_at DESC LIMIT 1")[0]

    today = datetime.now().date()  # deadlines are the owner's calendar days
    day = lambda offset: (today + timedelta(days=offset)).isoformat()

    # Sent applications of different ages: three have waited longer than the
    # 45 days of the policy's "No reply" item.
    for title, company, days in (
        ("Data Engineer", "Kestrel Robotics", 62),
        ("Analytics Engineer", "Alpine Research", 51),
        ("Backend Developer", "Harbor Studio", 47),
        ("Platform Developer", "Sample Grid", 20),
        ("Data Engineer", "Orbit Works", 9),
    ):
        application = start(title, company, "Remote, Europe")
        workspace.update_application(
            application["id"],
            {
                "expected_version": application["version"],
                "status": "applied",
                "applied_at": ago(days=days),
            },
        )

    # What employers replied: an interview, a rejection, an application closed as
    # no reply and one closed without being sent (left out of Insights).
    with acting_as(OWNER):
        for title, company, location, sent, moves in (
            (
                "Research Software Engineer",
                "Alpine Research",
                "Lausanne, Switzerland",
                24,
                [{"reply": {"kind": "interview", "date": (today - timedelta(days=16))}}],
            ),
            (
                "Engineering Lead",
                "Northstar Labs",
                "Zurich, Switzerland",
                23,
                [
                    {
                        "reply": {
                            "kind": "rejection",
                            "date": (today - timedelta(days=11)),
                            "note": "Position filled internally.",
                        }
                    }
                ],
            ),
            (
                "Backend Engineer",
                "Cedar Systems",
                "Remote, Europe",
                57,
                [
                    {
                        "status": "closed",
                        "outcome": "no_response",
                        "concluded_on": (today - timedelta(days=12)),
                    }
                ],
            ),
            (
                "Data Analyst",
                "Orbit Works",
                "Remote, Europe",
                None,
                [{"status": "closed", "outcome": "not_pursued"}],
            ),
        ):
            application = start(title, company, location)
            if sent:
                application = workspace.update_application(
                    application["id"],
                    {
                        "expected_version": application["version"],
                        "status": "applied",
                        "applied_at": ago(days=sent),
                    },
                )
            for move in moves:
                application = workspace.update_application(
                    application["id"],
                    {
                        "expected_version": application["version"],
                        **{key: dated(value) for key, value in move.items()},
                    },
                )

    with acting_as(OWNER):
        cedar = start("Site Reliability Engineer", "Cedar Systems", "Bern, Switzerland")

    inbox = [
        workspace.ingest_job(
            {
                "title": title,
                "company": company,
                "location": "Zurich, Switzerland",
                "posting": POSTING,
            }
        )
        for title, company in (
            ("Staff Engineer, Data", "Alpine Research"),
            ("Cloud Engineer", "Kestrel Robotics"),
            ("Support Engineer", "Sample Grid"),
        )
    ]

    with acting_as(agent), batch():
        workspace.add_note(inbox[0]["id"], {"body": "Synthetic note about the Career record."})
        workspace.add_note(inbox[1]["id"], {"body": "Second synthetic note."})
        notes_batch = last_batch()
    with acting_as(agent), batch():
        # One review: two shortlisted, one dismissed with a reason.
        workspace.set_triage(
            inbox[0]["id"], "shortlisted", workspace.get_job(inbox[0]["id"])["version"]
        )
        workspace.set_triage(
            inbox[1]["id"], "shortlisted", workspace.get_job(inbox[1]["id"])["version"]
        )
        workspace.set_triage(
            inbox[2]["id"], "dismissed", inbox[2]["version"], reason="Support role, not data."
        )
        review_batch = last_batch()
    with acting_as(agent), batch():
        for title, company, location, fields in (
            (
                "Python Engineer",
                "Northstar Labs",
                "Zurich, Switzerland",
                {"deadline": day(1), "priority": 1},
            ),
            (
                "Data Platform Engineer",
                "Fjord Analytics",
                "Remote, Europe",
                {"deadline": day(5), "priority": 1},
            ),
            ("Backend Engineer", "Lumen Health", "Basel, Switzerland", {"priority": 2}),
            (
                "Senior Machine Learning Infrastructure and Reliability Engineer",
                "International Example Consortium for Measurement Data",
                "Geneva, Switzerland or remote within Europe",
                {"deadline": day(-2), "priority": 2},
            ),
            ("Data Engineer", "Orbit Analytics", "Remote, Europe", {"deadline": day(30)}),
            ("Machine Learning Engineer", "Quartz Systems", "Zurich, Switzerland", {}),
        ):
            make_ready(start(title, company, location, **fields))
        make_ready(cedar)
        harbor = start("Platform Engineer", "Harbor Bank", "Zurich, Switzerland")
        workspace.update_application(
            harbor["id"],
            {
                "expected_version": harbor["version"],
                "requirements": [
                    {
                        "kind": "authorship",
                        "text": "Harbor Bank accepts only applications written without AI tools.",
                        "blocking": True,
                    }
                ],
            },
        )
        prepare_batch = last_batch()

    before_agent(agent)
    with acting_as(agent), batch():
        workspace.add_note(inbox[1]["id"], {"body": "Synthetic note of the latest work."})
        latest_batch = last_batch()

    shift(notes_batch, timedelta(days=1, hours=7), 8)
    shift(review_batch, timedelta(days=1, hours=1), 12)
    shift(prepare_batch, timedelta(hours=20), 41)
    shift(latest_batch, timedelta(minutes=26))

    # Collection since yesterday: two sources found jobs and one failed.
    with workspace.db.transaction() as conn:
        for name, state, created, hours in (
            ("Data roles, Zurich", "succeeded", 12, 30),
            ("Northstar Labs careers", "succeeded", 7, 6),
            ("Fjord Analytics board", "failed", 0, 5),
        ):
            run_id, stamp = new_id(), ago(hours=hours)
            conn.execute(
                "INSERT INTO collection_runs(id,source_name,source_version,source_snapshot,created_at) "
                "VALUES(?,?,1,'{}',?)",
                (run_id, name, stamp),
            )
            conn.execute(
                "INSERT INTO tasks(id,kind,run_id,state,payload,result,attempts,next_run_at,error,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?,?)",
                (
                    new_id(),
                    "collect",
                    run_id,
                    state,
                    json.dumps({"provider": "synthetic"}),
                    json.dumps({"received": created * 3, "created": created, "started_at": stamp}),
                    stamp,
                    "The board did not answer." if state == "failed" else None,
                    stamp,
                    stamp,
                ),
            )
