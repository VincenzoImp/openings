"""The demo's jobs and applications, in every stage, by the owner and by the agent.

47 jobs at fictional companies in 20 countries: 33 New (one a likely duplicate of
the Voltline job), three dismissals (two by the agent "Claude Code" with its
reasons, one by the owner) and eleven applications: three Ready with the agent's
CV and letter, priorities 1 to 3, deadlines and a salary range with its basis;
two Shortlisted that still need work; and Applied (one past its no-reply
period), Interview with the agent's interview brief, Offer and a rejection.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from ..actors import OWNER, acting_as, batch
from ..common import new_id
from ..documents import DocumentCreate
from ..models import ApplicationPatch
from .marker import ago, moment
from .postings import NEW_JOBS, POSTINGS

FILES = Path(__file__).resolve().parent
# An application keeps its salary range in its own field where it has one;
# otherwise the agent's salary note carries the range too.
SALARY_FIELD = "salary" in ApplicationPatch.model_fields

# Sent applications, oldest first: key, title, company, location, source, days since
# found, salary, days since sent, and the replies (kind, days ago, note).
SENT = (
    (
        "larchmont",
        "Data Platform Engineer",
        "Larchmont Bank",
        "Lisbon, Portugal (hybrid)",
        "europe",
        58,
        ("EUR", 60000, 75000),
        52,
        (),
    ),
    (
        "quayside",
        "Backend Engineer, Payments API",
        "Quayside Payments",
        "London, United Kingdom (hybrid)",
        "europe",
        44,
        ("GBP", 80000, 95000),
        38,
        (("rejection", 17, "They chose a candidate with more payments experience."),),
    ),
    (
        "saltmarsh",
        "Backend Engineer, Forecasting Platform",
        "Saltmarsh Analytics",
        "Copenhagen, Denmark (hybrid)",
        "europe",
        40,
        ("DKK", 620000, 700000),
        34,
        (
            ("interview", 24, "Two video interviews: system design, then the team."),
            ("offer", 3, "Written offer: DKK 680,000 a year. Answer by the end of next week."),
        ),
    ),
    (
        "freightwise",
        "Python Backend Engineer",
        "Freightwise",
        "Remote, Europe",
        "feed",
        30,
        ("EUR", 70000, 85000),
        23,
        (("interview", 9, "Technical interview with two backend engineers, video call."),),
    ),
    (
        "lindgren",
        "Backend Engineer, Supplier APIs",
        "Lindgren Climate Tech",
        "Stockholm, Sweden (hybrid)",
        "feed",
        16,
        ("SEK", 650000, 720000),
        12,
        (),
    ),
    (
        "lumacare",
        "Backend Engineer, Patient Platform",
        "Lumacare Health",
        "Dublin, Ireland",
        "europe",
        12,
        ("EUR", 75000, 90000),
        6,
        (),
    ),
)

# Ready applications: the job, who shortlisted it, priority, deadline (days ahead), the
# letter, the salary range and its basis, and the agent's note.
READY = (
    (
        (
            "senior-backend-grid-data",
            "Senior Backend Engineer, Grid Data",
            "Voltline Grid Analytics",
            "Amsterdam, Netherlands (hybrid)",
            "voltline",
            6,
            ("EUR", 80000, 95000),
            POSTINGS["voltline"],
        ),
        "agent",
        1,
        12,
        "demo-letter",
        "EUR 85,000–95,000",
        (
            "The posting's range is EUR 80,000–95,000; your expected EUR 80,000 is its floor "
            "and the role is senior, so aim for the upper half."
        ),
        (
            "CV leads with the latency work and the deployment workflow; the letter connects "
            "them to the ingestion path in the posting. Ready to send."
        ),
    ),
    (
        (
            "meridian-data-apis",
            "Backend Engineer, Data APIs",
            "Meridian Insurance Group",
            "Berlin, Germany (hybrid)",
            "europe",
            4,
            ("EUR", 75000, 85000),
            POSTINGS["meridian"],
        ),
        "agent",
        2,
        9,
        "demo-letter-meridian",
        "EUR 80,000–85,000",
        (
            "The posting's range is EUR 75,000–85,000; your expectation in Preferences is "
            "EUR 80,000."
        ),
        (
            "The letter answers the posting's ask for help with adoption by other teams with "
            "your documentation work. Ready to send."
        ),
    ),
    (
        (
            "fernhill-platform",
            "Platform Engineer",
            "Fernhill Mobility",
            "Remote, Europe",
            "feed",
            5,
            None,
            POSTINGS["fernhill"],
        ),
        "agent",
        3,
        20,
        "demo-letter-fernhill",
        "EUR 80,000–85,000",
        (
            "The posting gives no range; your expectation in Preferences is EUR 80,000, so ask "
            "for EUR 80,000–85,000."
        ),
        (
            "Remote within Europe, as your Preferences ask. The letter leads with the "
            "deployment workflow; Terraform, a plus in the posting, is not in your record and "
            "stays out, as your writing rules ask. Ready to send."
        ),
    ),
)


# The agent's brief for the Freightwise technical interview, in the sections of the
# prepare-interview skill; saved as a note, unpinned.
INTERVIEW_BRIEF = """Interview brief: Freightwise, technical interview with two backend engineers.

What they need
- APIs for carriers and shippers, in Python with SQL.
- Slow synchronous work moved to asynchronous workers.
- Safer deployment and rollback with Docker and continuous delivery.
- Operations the whole team finds simpler.

Stories
- Workers: at Example Cloud you moved long-running jobs from request handlers to a queue \
of workers with retries and idempotent steps.
- Deployment: your workflow with health checks and automatic rollback cut the manual \
steps from nine to three; you designed it, the team uses it.
- Latency: tracing first, then the slowest endpoints; API p95 latency down by 20%.
- Operations: you documented the services until four colleagues could run them on call.

Likely questions
- Design an API that accepts a shipment and returns a price quickly. (Workers story.)
- How do you make a retried job safe to run twice? (Idempotent steps.)
- Tell us about a deployment that went wrong. (Health checks and rollback.)
- Why Freightwise? (Simpler operations for a remote team, as in the posting.)

Weak spots
- No logistics or routing work in your record. Bridge: the APIs and workers you built \
serve other teams every day, and the domain can be learned on the job.

Logistics
- Available from February 2027; notice of one month to the end of a month.
- EU citizen; the role is remote within Europe.
- Their range is EUR 70,000–85,000; your expectation is EUR 80,000.

Questions to ask
- Which synchronous work would you move to workers first?
- How does a release reach production today, and how often do you roll back?
- How is on-call shared in a team that meets in person twice a year?"""


class Upload:
    """The raw PUT of an upload grant, made in process: its headers and its bytes."""

    def __init__(self, grant, data):
        self.headers, self.data = grant["headers"], data

    async def stream(self):
        yield self.data


class DemoJobs:
    """Write the demo's jobs, applications and collection history through the services."""

    def __init__(self, app, agent, sources):
        self.workspace, self.documents = app.state.workspace, app.state.documents
        self.agent, self.sources = agent, sources
        self.today = datetime.now().date()

    def moment(self, **delta):
        return moment(self.workspace.db, **delta)

    def day(self, offset):
        return (self.today + timedelta(days=offset)).isoformat()

    def collect(self, key, title, company, location, source, days, salary=None, posting=None):
        board = source == "voltline"
        metadata = {"source": "greenhouse" if board else "rss" if source == "feed" else "linkedin"}
        if board:
            metadata["ats"] = "greenhouse"
        if salary:
            currency, low, high = salary
            metadata["salary"] = {
                "currency": currency,
                "min_amount": low,
                "max_amount": high,
                "interval": "yearly",
            }
        with self.moment(days=days):
            return self.workspace.ingest_job(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": f"https://careers.voltline.example/jobs/{key}"
                    if board
                    else f"https://jobs.example.test/{source}/{key}",
                    "posting": posting or POSTINGS[key],
                    "source_id": self.sources[source],
                    "metadata": metadata,
                    **({"source_key": f"greenhouse:voltline:{key}"} if board else {}),
                }
            )

    def revisions(self, application, company, days, letter=None):
        """The agent's CV (and letter) for an application, each with its TeX source."""
        kinds = [("cv", "demo-cv")] + ([("letter", letter)] if letter else [])
        with self.moment(days=days), acting_as(self.agent), batch():
            for kind, name in kinds:
                data = (FILES / f"{name}.pdf").read_bytes()
                document = self.documents.create_document(
                    DocumentCreate(
                        application_id=application["id"],
                        kind=kind,
                        title=f"{'CV' if kind == 'cv' else 'Letter'} for {company}",
                        source=(FILES / f"{name}.tex").read_text(),
                        pdf={"name": f"{kind}.pdf", "size": len(data)},
                    )
                )
                grant = document["uploads"]["pdf"]
                asyncio.run(self.documents.upload(Upload(grant, data)))

    def change(self, application, **fields):
        current = self.workspace.get_application(application["id"])
        return self.workspace.update_application(
            application["id"], {"expected_version": current["version"], **fields}
        )

    def note(self, job, body, application=None):
        value = {"body": body, **({"application_id": application["id"]} if application else {})}
        return self.workspace.add_note(job["id"], value)

    def shortlist(self, job, by):
        """Start the job's application, by the owner or as the agent's triage."""
        if by is OWNER:
            with acting_as(OWNER):
                return self.workspace.create_application({"job_id": job["id"]})
        with acting_as(self.agent), batch():
            self.workspace.set_triage(job["id"], "shortlisted", job["version"])
        return self.workspace.db.one(
            "SELECT id FROM applications WHERE job_id=? AND status<>'closed'", (job["id"],)
        )

    def dismiss(self, job, by, reason):
        with acting_as(by), batch():
            current = self.workspace.get_job(job["id"])["version"]
            self.workspace.set_triage(job["id"], "dismissed", current, reason=reason)

    def seed(self):
        self.sent()
        self.ready()
        self.shortlisted()
        self.new()
        self.dismissed()
        self.history()

    def sent(self):
        for key, title, company, location, source, found, salary, sent, replies in SENT:
            job = self.collect(
                f"{key}-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}",
                title,
                company,
                location,
                source,
                found,
                salary,
                POSTINGS[key],
            )
            with self.moment(days=found - 1):
                application = self.shortlist(job, OWNER)
            self.revisions(application, company, found - 2)
            with self.moment(days=sent), acting_as(OWNER):
                self.change(application, stage="applied", applied_at=ago(days=sent))
            for kind, days, note in replies:
                with self.moment(days=days), acting_as(OWNER):
                    self.change(
                        application, reply={"kind": kind, "date": self.day(-days), "note": note}
                    )
            if key == "freightwise":
                with self.moment(days=8), acting_as(OWNER):
                    self.note(
                        job,
                        "Interview on Thursday at 16:00 with Sam and Priya. Prepare the "
                        "deployment workflow story and questions about on-call.",
                        application,
                    )
                with self.moment(days=7), acting_as(self.agent):
                    self.note(job, INTERVIEW_BRIEF, application)

    def ready(self):
        for job_spec, by, priority, deadline, letter, salary, basis, summary in READY:
            job = self.collect(*job_spec)
            days = job_spec[5]
            with self.moment(days=days - 1):
                application = self.shortlist(job, by)
                actor = OWNER if by is OWNER else self.agent
                with acting_as(actor):
                    self.change(application, priority=priority, deadline=self.day(deadline))
            self.revisions(application, job["company"], 1, letter=letter)
            with self.moment(hours=20), acting_as(self.agent), batch():
                if SALARY_FIELD:
                    self.change(application, salary=salary)
                    self.note(job, f"Salary basis: {basis}", application)
                else:
                    self.note(job, f"Salary range: {salary}. Salary basis: {basis}", application)
                self.note(job, summary, application)

    def shortlisted(self):
        # By the agent, needing its letter and a code sample: closing within a week.
        carbon = self.collect(
            "carbon-ledger-emissions",
            "Software Engineer, Emissions Data",
            "Carbon Ledger Foundation",
            "Remote, Europe",
            "feed",
            4,
            ("EUR", 65000, 75000),
            POSTINGS["carbon"],
        )
        with self.moment(days=3):
            application = self.shortlist(carbon, "agent")
            with acting_as(self.agent), batch():
                application = self.change(
                    application,
                    priority=1,
                    deadline=self.day(5),
                    questions=[
                        {
                            "id": "motivation",
                            "label": "Why do you want to work on open climate data?",
                            "type": "text",
                            "required": True,
                            "max_length": 1500,
                        }
                    ],
                    requirements=[
                        {
                            "kind": "attachment",
                            "text": "Include a link to a public code sample.",
                            "blocking": True,
                            "note": "Which repository should be linked?",
                        }
                    ],
                )
        self.revisions(application, carbon["company"], 2)
        # By the owner, no documents yet: a role that requires Italian, which Alex speaks.
        tessellate = self.collect(
            "tessellate-geospatial-api",
            "Backend Engineer, Geospatial APIs",
            "Tessellate Maps",
            "Barcelona, Spain (hybrid)",
            "europe",
            3,
            ("EUR", 55000, 65000),
            POSTINGS["tessellate"],
        )
        with self.moment(days=2), acting_as(OWNER):
            self.workspace.create_application(
                {
                    "job_id": tessellate["id"],
                    "priority": 2,
                    "requirements": [
                        {
                            "kind": "language",
                            "text": "Fluent Italian and English.",
                            "resolved": True,
                            "note": "Italian is my native language.",
                        }
                    ],
                }
            )

    def new(self):
        # A likely duplicate of the Ready Voltline job, found again by the search.
        self.collect(
            "voltline-grid-data",
            "Senior Backend Engineer - Grid Data",
            "Voltline Grid Analytics",
            "Amsterdam, Netherlands",
            "search",
            2,
            posting=POSTINGS["voltline"],
        )
        kelpie = self.collect(
            "kelpie-senior-python",
            "Senior Python Engineer, Developer Tools",
            "Kelpie Labs",
            "Toronto, Canada (remote)",
            "feed",
            2,
            ("CAD", 140000, 165000),
            POSTINGS["kelpie"],
        )
        self.collect(
            "cobalt-billing",
            "Software Engineer, Billing",
            "Cobalt Telecom",
            "Dublin, Ireland",
            "europe",
            0.1,
            ("EUR", 55000, 65000),
            POSTINGS["cobalt"],
        )
        found = {}
        for key, title, company, location, source, days, salary, about, role in NEW_JOBS:
            found[key] = self.collect(
                key, title, company, location, source, days, salary, f"{about}\n\n{role}"
            )
        with self.moment(hours=10), acting_as(self.agent), batch():
            self.note(
                kelpie,
                "Close match: the product is a deployment workflow like the one in your "
                "Selected Project. Senior title; the posting asks for mentoring.",
            )
            self.note(
                found["tallgrass-senior-backend"],
                "Requires US work authorization; your Preferences say you are an EU citizen "
                "in the Netherlands. Left in New for you to decide.",
            )

    def dismissed(self):
        german = self.collect(
            "spreeland-backend",
            "Backend-Entwickler/in Python (m/w/d)",
            "Spreeland Energie GmbH",
            "Berlin, Germany",
            "europe",
            1,
            posting=POSTINGS["spreeland"],
        )
        agency = self.collect(
            "pixelwright-frontend",
            "Frontend Engineer (React)",
            "Pixelwright Studio",
            "Amsterdam, Netherlands",
            "search",
            3,
            posting=POSTINGS["pixelwright"],
        )
        london = self.collect(
            "northpeak-staff-backend",
            "Staff Backend Engineer",
            "Northpeak Trading",
            "London, United Kingdom",
            "europe",
            5,
            ("GBP", 120000, 140000),
            POSTINGS["northpeak"],
        )
        with self.moment(hours=18):
            self.dismiss(
                german, self.agent, "Requires fluent German; you speak English and Italian."
            )
        with self.moment(days=2, hours=20):
            self.dismiss(
                agency,
                self.agent,
                "Frontend role at an agency; you rule out pure frontend roles and agencies.",
            )
        with self.moment(days=4):
            self.dismiss(london, OWNER, "On site in London five days a week.")

    def history(self):
        """Collection history: each source ran this morning, the search also yesterday."""
        with self.workspace.db.transaction() as conn:
            # It replaces the first checks the new sources queued when they were added.
            conn.execute("DELETE FROM tasks WHERE kind='collect'")
            conn.execute("DELETE FROM collection_runs")
            for source, name, received, created, hours in (
                ("search", "Backend roles, Amsterdam", 24, 3, 28),
                ("search", "Backend roles, Amsterdam", 27, 5, 4),
                ("europe", "Data and backend roles, Europe", 38, 9, 3),
                ("voltline", "Voltline Grid Analytics careers", 9, 1, 3),
                ("feed", "Remote Python jobs feed", 18, 6, 2),
            ):
                run_id, started = new_id(), ago(hours=hours)
                finished = ago(hours=hours, seconds=-40)
                conn.execute(
                    "INSERT INTO collection_runs(id,source_id,source_name,source_version,"
                    "source_snapshot,created_at) VALUES(?,?,?,1,'{}',?)",
                    (run_id, self.sources[source], name, started),
                )
                conn.execute(
                    "INSERT INTO tasks(id,kind,source_id,run_id,state,payload,result,attempts,"
                    "next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,1,?,?,?)",
                    (
                        new_id(),
                        "collect",
                        self.sources[source],
                        run_id,
                        "succeeded",
                        json.dumps(
                            {"provider": "linkedin" if source in ("search", "europe") else source}
                        ),
                        json.dumps(
                            {
                                "received": received,
                                "created": created,
                                "existing": received - created,
                                "started_at": started,
                                "processing_seconds": 31.5,
                                "http_requests": 4,
                            }
                        ),
                        started,
                        started,
                        finished,
                    ),
                )
                conn.execute(
                    "UPDATE sources SET last_run_at=?,last_scheduled_at=? WHERE id=?",
                    (finished, started, self.sources[source]),
                )
