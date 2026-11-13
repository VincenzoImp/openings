"""Synthetic work for Today and Activity in the browser-test workspace.

Ready applications with deadlines, a blocked one, applications sent at
different times, an agent's runs (finished with reports, interrupted, in
progress), questions with and without choices, requests in every state and a
few collection runs. Everything is fictional.
"""

import json
from datetime import UTC, datetime, timedelta

from openings.actors import OWNER, acting_as, token_actor
from openings.common import new_id
from openings.documents import DocumentCreate, ReviewUpdate, UploadReservation

PDF = b"%PDF-1.4\nSynthetic test PDF"
POSTING = "Build reliable data services.\n\nResponsibilities\nDesign pipelines with a small team."


def ago(**delta):
    return (datetime.now(UTC) - timedelta(**delta)).isoformat(timespec="microseconds")


def seed_today(app, client, before_open_run):
    """Seed the work; ``before_open_run(agent)`` runs before the run left in progress starts."""
    workspace, documents = app.state.workspace, app.state.documents
    activity, requests = app.state.activity, app.state.requests
    with acting_as(OWNER):
        token = app.state.auth.create_token("career-agent", "agent")
    agent = token_actor(token["id"], "career-agent", "agent")

    def start(title, company, location, **fields):
        job = workspace.ingest_job(
            {"title": title, "company": company, "location": location, "posting": POSTING}
        )
        return workspace.create_application({"job_id": job["id"], **fields})

    def make_ready(application):
        for kind, title in (("resume", "CV"), ("cover_letter", "Letter")):
            document = documents.create_document(
                DocumentCreate(
                    application_id=application["id"],
                    kind=kind,
                    title=title,
                    content={"text": "Synthetic."},
                )
            )
            grant = documents.reserve_upload(
                UploadReservation(
                    owner_type="document",
                    owner_id=document["id"],
                    name=f"{kind}.pdf",
                    size=len(PDF),
                    media_type="application/pdf",
                )
            )
            assert (
                client.put(grant["url"], headers=grant["headers"], content=PDF).status_code == 200
            )
            current = documents.get_document(document["id"])
            documents.review_document(
                document["id"], ReviewUpdate(expected_version=current["version"])
            )
        current = workspace.get_application(application["id"])
        workspace.set_ready(application["id"], {"expected_version": current["version"]})

    def shift(run, started, minutes=None):
        """Move a run and what it recorded into the past."""
        begin = datetime.now(UTC) - started
        end = begin + timedelta(minutes=minutes) if minutes else None
        stamp = lambda moment: moment.isoformat(timespec="microseconds")
        with workspace.db.transaction() as conn:
            conn.execute(
                "UPDATE runs SET started_at=?,last_activity_at=?,ended_at=CASE WHEN ended_at IS NULL "
                "THEN NULL ELSE ? END WHERE id=?",
                (stamp(begin), stamp(end or begin), stamp(end or begin), run["id"]),
            )
            rows = conn.execute(
                "SELECT id FROM events WHERE run_id=? ORDER BY created_at", (run["id"],)
            ).fetchall()
            for index, row in enumerate(rows):
                moment = begin + (end - begin) * (index + 1) / (len(rows) + 1) if end else begin
                conn.execute(
                    "UPDATE events SET created_at=? WHERE id=?", (stamp(moment), row["id"])
                )
            conn.execute(
                "UPDATE questions SET created_at=? WHERE run_id=?", (stamp(end or begin), run["id"])
            )

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

    # What employers answered: an interview, a rejection, an application closed as
    # no reply and a Draft closed without being sent (left out of Insights).
    with acting_as(OWNER):
        for title, company, location, sent, moves in (
            (
                "Research Software Engineer",
                "Alpine Research",
                "Lausanne, Switzerland",
                24,
                [{"status": "interview", "response_date": (today - timedelta(days=16))}],
            ),
            (
                "Engineering Lead",
                "Northstar Labs",
                "Zurich, Switzerland",
                23,
                [
                    {
                        "status": "closed",
                        "outcome": "rejected",
                        "response_date": (today - timedelta(days=11)),
                        "response_note": "Position filled internally.",
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
                        **{
                            key: value.isoformat() if hasattr(value, "isoformat") else value
                            for key, value in move.items()
                        },
                    },
                )

    with acting_as(OWNER):
        cedar = start("Site Reliability Engineer", "Cedar Systems", "Bern, Switzerland")
        asked = requests.create_request(
            {
                "text": "Prepare the Cedar Systems application too.",
                "subject_type": "application",
                "subject_id": cedar["id"],
            }
        )
        declined = requests.create_request({"text": "Send the Northstar Labs application for me."})
        requests.create_request({"text": "Look for roles at energy companies next week."})
        withdrawn = requests.create_request({"text": "Shorten every letter to 150 words."})
        requests.withdraw_request(withdrawn["id"], {"expected_version": withdrawn["version"]})

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

    with acting_as(agent):
        # A run the agent never closed: the next start marks it interrupted.
        career_run = activity.start_run(
            {"workflow": "maintain-career", "scope": "The Career record"}
        )
        workspace.add_note(inbox[0]["id"], {"body": "Synthetic note about the Career record."})
        workspace.add_note(inbox[1]["id"], {"body": "Second synthetic note."})

        review = activity.start_run(
            {"workflow": "review-inbox", "scope": "3 jobs to review", "supersede": True}
        )
        workspace.set_triage(inbox[0]["id"], "saved", workspace.get_job(inbox[0]["id"])["version"])
        workspace.set_triage(inbox[1]["id"], "saved", workspace.get_job(inbox[1]["id"])["version"])
        workspace.set_triage(inbox[2]["id"], "dismissed", inbox[2]["version"])
        activity.ask_question(
            {
                "question": "Do you want roles that require on-call work at night?",
                "why": "2 new jobs mention it and your policy does not. I left them in Jobs to review.",
            }
        )
        relocation = activity.ask_question({"question": "Would you relocate outside Switzerland?"})
        activity.finish_run(
            review["id"],
            {
                "expected_version": review["version"],
                "summary": "3 jobs reviewed: 2 shortlisted, 1 dismissed.",
                "changes": "Shortlisted two data roles and dismissed a support role.",
                "checks": [{"check": "The review queue was read again and is empty."}],
                "limits": "I did not open the employers' own pages.",
            },
        )

        prepare = activity.start_run(
            {"workflow": "prepare-shortlist", "scope": "7 shortlisted jobs"}
        )
        taken = requests.take_request(asked["id"], {"expected_version": asked["version"]})
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
        activity.ask_question(
            {
                "question": "Can you start before 1 February?",
                "why": "Cedar Systems asks for a start date in January. Your policy says "
                '"available from February". I prepared the documents and left the date open.',
                "subject_type": "application",
                "subject_id": cedar["id"],
                "choices": ["Yes, from 15 January", "No, February only"],
            }
        )
        contract = activity.ask_question(
            {"question": "Is a 60% contract acceptable for Harbor Studio?"}
        )
        requests.complete_request(
            taken["id"],
            {
                "expected_version": taken["version"],
                "result": "Prepared and marked ready. The start date waits for your answer.",
            },
        )
        requests.decline_request(
            declined["id"],
            {
                "expected_version": declined["version"],
                "reason": "I never submit an application. It is ready for you to send.",
            },
        )
        activity.finish_run(
            prepare["id"],
            {
                "expected_version": activity.get_run(prepare["id"])["version"],
                "summary": "7 applications are ready for you. One was not written: the employer "
                "accepts only applications written without AI tools.",
                "changes": "Wrote a CV and a letter for seven applications and marked them ready.",
                "not_done": [
                    {
                        "item": "Platform Engineer · Harbor Bank",
                        "reason": "No documents. The posting says applications written with AI "
                        "tools are rejected. Recorded as a blocking requirement for you to decide.",
                        "subject_type": "application",
                        "subject_id": harbor["id"],
                    }
                ],
                "checks": [
                    {"check": "Every PDF was built from the uploaded source (14 of 14)."},
                    {"check": "Every sentence cites an approved claim."},
                    {"check": "Letter length under 200 words", "verified": False},
                ],
                "limits": "I did not check whether the postings were still open.",
                "method": "The skill does not say what to do when a posting forbids AI-written "
                "applications. I stopped and recorded a requirement.",
            },
        )
        activity.withdraw_question(contract["id"], {"expected_version": contract["version"]})

    with acting_as(OWNER):
        activity.answer_question(
            relocation["id"],
            {
                "expected_version": relocation["version"],
                "answer": "No. Remote for a company abroad is fine.",
            },
        )
        later = requests.create_request({"text": "Check the Lumen Health posting again."})

    before_open_run(agent)
    with acting_as(agent):
        current = activity.start_run(
            {"workflow": "prepare-shortlist", "scope": "2 shortlisted jobs"}
        )
        requests.take_request(later["id"], {"expected_version": later["version"]})
        workspace.add_note(inbox[1]["id"], {"body": "Synthetic note of the run in progress."})

    shift(career_run, timedelta(days=1, hours=7), 8)
    shift(review, timedelta(days=1, hours=1), 12)
    shift(prepare, timedelta(hours=20), 41)
    shift(current, timedelta(minutes=26))

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
