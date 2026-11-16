"""Seed the demo workspace: one fictional person's job search.

Alex Example, the backend engineer of examples/cv.tex and examples/career.json,
who lives in Amsterdam and looks for backend and data roles in Europe or remote,
with the example Preferences, three templates, four collection sources, an
agent token named "Claude Code" and fifteen jobs at fictional companies in
several countries, paid in EUR, GBP and CAD: new jobs (one a likely duplicate
of a job with an application, one that requires German), two dismissals (by the
owner and by the agent) and applications in every stage. The CVs and letters are
real PDFs built with Tectonic from the TeX files beside this module (the layout
of examples/cv.tex and letter.tex), stored with those exact sources.

Everything goes through the services, except the dates: each block's records
are dated back with raw SQL (``STAMPED``), so the screens always look current.
That stamping runs only on a file that carries the demo marker, which
``mark_demo`` writes on a new, empty workspace and nothing else writes.
"""

import asyncio
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..actors import OWNER, acting_as, batch, token_actor
from ..career import EntryCreate, HighlightCreate, ProfileUpdate, TemplateCreate
from ..common import encode, examples_dir, new_id, now
from ..discovery.models import RSSConfig, SourceCreate
from ..documents import DocumentCreate
from .postings import POSTINGS

FILES = Path(__file__).resolve().parent
# The settings key of the demo marker.
MARKER = "demo"
# A workspace with any of these is not new, so it never becomes a demo.
CONTENT = ("jobs", "sources", "applications", "knowledge", "templates")

# Columns stamped with the moment of the change that wrote them.
STAMPED = (
    ("jobs", "created_at"),
    ("jobs", "updated_at"),
    ("jobs", "dismissed_at"),
    ("postings", "first_seen_at"),
    ("postings", "last_seen_at"),
    ("applications", "created_at"),
    ("applications", "updated_at"),
    ("notes", "created_at"),
    ("notes", "updated_at"),
    ("replies", "created_at"),
    ("replies", "updated_at"),
    ("documents", "created_at"),
    ("files", "created_at"),
    ("knowledge", "created_at"),
    ("knowledge", "updated_at"),
    ("claims", "created_at"),
    ("claims", "updated_at"),
    ("templates", "created_at"),
    ("templates", "updated_at"),
    ("sources", "created_at"),
    ("sources", "updated_at"),
    ("sources", "last_scheduled_at"),
)


class NotADemo(RuntimeError):
    """The workspace is not one the demo created: its dates are never rewritten."""


def is_demo(db):
    """Whether this file carries the demo marker."""
    return db.one("SELECT 1 FROM settings WHERE key=?", (MARKER,)) is not None


def mark_demo(workspace):
    """Write the demo marker on a new, empty workspace; refuse any other."""
    if is_demo(workspace.db):
        return
    with workspace.db.transaction() as conn:
        for table in CONTENT:
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise NotADemo("Only a new, empty workspace becomes the demo workspace.")
        conn.execute(
            "INSERT INTO settings(key,data,updated_at) VALUES(?,?,?)",
            (MARKER, encode({"created_at": now()}), now()),
        )


def stamp(db, start, when):
    """Date every record written since ``start`` at ``when``, keeping the order of its events.

    Raw SQL on a demo file only: a workspace without the marker is refused.
    """
    if not is_demo(db):
        raise NotADemo("Dates are rewritten only in a workspace the demo created.")
    with db.transaction() as conn:
        for table, column in STAMPED:
            conn.execute(
                f"UPDATE {table} SET {column}=? WHERE {column}>=?",
                (when.isoformat(timespec="microseconds"), start),
            )
        rows = conn.execute(
            "SELECT id FROM events WHERE created_at>=? ORDER BY rowid", (start,)
        ).fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                "UPDATE events SET created_at=? WHERE id=?",
                ((when + timedelta(seconds=index)).isoformat(timespec="microseconds"), row["id"]),
            )


class _Upload:
    """The raw PUT of an upload grant, made in process: its headers and its bytes."""

    def __init__(self, grant, data):
        self.headers, self.data = grant["headers"], data

    async def stream(self):
        yield self.data


CV_GUIDANCE = (
    "Alex's main CV. Keep the four sections: Profile, Experience, Selected Project and "
    "Skills. Tailor the Profile and the order of bullets to the job; take every statement "
    "from approved highlights."
)
LETTER_GUIDANCE = (
    "Address the hiring team by name when the posting gives one. Open with the role and "
    "the company, connect one or two concrete results to the posting, and close briefly."
)
COMPACT_GUIDANCE = (
    "A shorter CV for forms with a strict length limit: Experience and Skills only, at "
    "most four bullets."
)


def ago(**delta):
    return (datetime.now(UTC) - timedelta(**delta)).isoformat(timespec="microseconds")


def seed_demo(app):
    """Seed the demo workspace into the new, empty workspace of ``app``.

    Returns the agent token "Claude Code" with its secret.
    """
    workspace, career, documents = app.state.workspace, app.state.career, app.state.documents
    discovery, preferences = app.state.discovery, app.state.preferences
    today = datetime.now().date()

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    @contextmanager
    def moment(**delta):
        """Date what the block writes ``delta`` ago, keeping the order of its events."""
        start = datetime.now(UTC).isoformat(timespec="microseconds")
        yield
        stamp(workspace.db, start, datetime.now(UTC) - timedelta(**delta))

    mark_demo(workspace)
    with acting_as(OWNER):
        token = app.state.auth.create_token("Claude Code", "agent")
    agent = token_actor(token["id"], "Claude Code", "agent")
    examples = examples_dir()
    cv_tex = (examples / "cv.tex").read_text()
    letter_tex = (examples / "letter.tex").read_text()

    # The person, as in examples/career.json and examples/cv.tex.
    with moment(days=70):
        career.update_profile(
            ProfileUpdate(
                expected_version=career.get_profile()["version"],
                name="Alex Example",
                headline="Backend Engineer",
                location="Amsterdam, Netherlands",
                email="alex@example.test",
                phone="+31 20 000 0000",
                summary=(
                    "Backend engineer with five years of Python APIs and asynchronous "
                    "workers in production. Cares about reliable deployments, measured "
                    "performance work and services that colleagues can operate."
                ),
                links=[
                    {"label": "Website", "url": "https://example.test"},
                    {"label": "Code", "url": "https://code.example.test/alex"},
                ],
            )
        )
        career_json = json.loads((examples / "career.json").read_text())
        entries = {
            item["title"]: career.create_entry(EntryCreate.model_validate(item))
            for item in career_json["entries"]
        }
        career.create_entry(
            EntryCreate(
                kind="education",
                title="MSc Computer Science",
                organization="Example University",
                dates={"kind": "period", "start": "2018", "end": "2020"},
                narrative="Thesis on fault-tolerant job queues for web services.",
                skills=["Distributed systems", "Python"],
            )
        )
        for language, level in (
            ("Italian", "Native"),
            ("English", "Fluent (C1)"),
            ("Dutch", "Basic (A2)"),
        ):
            career.create_entry(EntryCreate(kind="language", title=language, narrative=level))
        for title, text, approved, always in (
            (
                "Backend engineer",
                "Built Python APIs and asynchronous workers for a developer platform.",
                True,
                True,
            ),
            (
                "Backend engineer",
                "Reduced API p95 latency by 20% through endpoint improvements and tracing.",
                True,
                True,
            ),
            (
                "Backend engineer",
                "Documented the rollout and helped four colleagues operate the services.",
                True,
                False,
            ),
            (
                "Backend engineer",
                "Added request tracing to the core endpoints of the platform.",
                False,
                False,
            ),
            (
                "Reliable deployment workflow",
                "Reduced manual deployment steps from nine to three.",
                True,
                True,
            ),
            (
                "Reliable deployment workflow",
                "Made release status visible to the whole team with health checks and rollback.",
                True,
                False,
            ),
        ):
            career.create_highlight(
                HighlightCreate(
                    career_id=entries[title]["id"],
                    text=text,
                    approved=approved,
                    always_include=always,
                )
            )
        for name, kind, tex, guidance, rules in (
            ("Main CV", "cv", cv_tex, CV_GUIDANCE, {"max_pages": 1, "engine": "tectonic"}),
            (
                "Cover letter",
                "letter",
                letter_tex,
                LETTER_GUIDANCE,
                {"max_pages": 1, "engine": "tectonic", "date_format": "D MMMM YYYY"},
            ),
            (
                "Compact CV",
                "cv",
                cv_tex.replace("margin=1.7cm", "margin=1.2cm"),
                COMPACT_GUIDANCE,
                {"max_pages": 1, "max_bullets": 4, "max_bullet_chars": 110, "engine": "tectonic"},
            ),
        ):
            career.create_template(
                TemplateCreate(name=name, kind=kind, tex=tex, guidance=guidance, rules=rules)
            )
        example = json.loads((examples / "preferences.json").read_text())
        with acting_as(OWNER):
            for section, items in example["sections"].items():
                preferences.update_preferences(section, {"expected_version": 0, "items": items})
            preferences.update_settings({"expected_version": 0, **example["settings"]})

    # Four sources, stored as the dashboard saves them.
    sources = {}
    with moment(days=45), acting_as(OWNER):
        for key, value in (
            (
                "search",
                SourceCreate(
                    name="Backend roles, Amsterdam",
                    kind="jobspy",
                    config={
                        "query": "backend engineer python",
                        "location": "Amsterdam",
                        "country": "netherlands",
                        "providers": ["linkedin", "indeed"],
                        "results_wanted": 30,
                        "hours_old": 72,
                    },
                    filters={"exclude_titles": ["intern", "working student"]},
                    enabled=True,
                    schedule={
                        "kind": "daily",
                        "times": ["07:00"],
                        "timezone": "Europe/Amsterdam",
                    },
                ),
            ),
            (
                "europe",
                SourceCreate(
                    name="Data and backend roles, Europe",
                    kind="jobspy",
                    config={
                        "query": "data platform engineer python",
                        "location": "Europe",
                        "providers": ["linkedin"],
                        "results_wanted": 40,
                        "hours_old": 72,
                    },
                    filters={"exclude_titles": ["intern", "working student"]},
                    enabled=True,
                    schedule={
                        "kind": "daily",
                        "times": ["07:30"],
                        "timezone": "Europe/Amsterdam",
                    },
                ),
            ),
            (
                "voltline",
                SourceCreate(
                    name="Voltline Grid Analytics careers",
                    kind="greenhouse",
                    url="https://boards.greenhouse.io/voltline",
                    config={"board": "voltline"},
                    enabled=True,
                ),
            ),
        ):
            sources[key] = discovery.create_source(value)["id"]
    # A feed's address is resolved when it is saved; stored directly, without the network.
    feed = "https://example.org/jobs/remote-python.rss"
    with moment(days=40), workspace.db.transaction() as conn:
        sources["feed"] = new_id()
        saved = ago()
        conn.execute(
            "INSERT INTO sources(id,name,kind,config,enabled,schedule,last_scheduled_at,"
            "created_at,updated_at) VALUES(?,?,?,?,1,?,?,?,?)",
            (
                sources["feed"],
                "Remote Python jobs feed",
                "rss",
                encode(
                    {
                        **RSSConfig(url=feed, max_results=50).model_dump(),
                        "url": feed,
                        "filters": {
                            "titles": ["python", "backend", "platform"],
                            "locations": [],
                            "exclude_titles": [],
                        },
                    }
                ),
                encode({"kind": "interval", "minutes": 720}),
                saved,
                saved,
                saved,
            ),
        )

    def collect(key, title, company, location, source, days, **extra):
        board = "greenhouse" if source == "voltline" else None
        # A search's jobs come from a job site, as real ones do.
        kind = "rss" if source == "feed" else "linkedin"
        url = (
            f"https://boards.greenhouse.io/voltline/jobs/{key}"
            if board
            else f"https://jobs.example.test/{source}/{key}"
        )
        if "salary" in extra:
            currency, low, high = extra["salary"]
            extra["salary"] = {
                "currency": currency,
                "min_amount": low,
                "max_amount": high,
                "interval": "yearly",
            }
        with moment(days=days):
            return workspace.ingest_job(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "posting": POSTINGS[extra.pop("posting", key)],
                    "source_id": sources[source],
                    "metadata": {"source": board or kind, **extra},
                    **({"source_key": f"greenhouse:voltline:{key}"} if board else {}),
                }
            )

    def revisions(application, company, days, letter=False):
        """The agent's CV (and the Voltline letter) for an application, with their sources."""
        kinds = [("cv", "demo-cv")]
        if letter:
            kinds.append(("letter", "demo-letter"))
        with moment(days=days), acting_as(agent), batch():
            for kind, name in kinds:
                tex = (FILES / f"{name}.tex").read_text()
                data = (FILES / f"{name}.pdf").read_bytes()
                document = documents.create_document(
                    DocumentCreate(
                        application_id=application["id"],
                        kind=kind,
                        title=f"{'CV' if kind == 'cv' else 'Letter'} for {company}",
                        source=tex,
                        pdf={"name": f"{kind}.pdf", "size": len(data)},
                    )
                )
                asyncio.run(documents.upload(_Upload(document["uploads"]["pdf"], data)))

    def change(application, **fields):
        current = workspace.get_application(application["id"])
        return workspace.update_application(
            application["id"], {"expected_version": current["version"], **fields}
        )

    # Applications, oldest first.
    quayside = collect(
        "quayside-payments-api",
        "Backend Engineer, Payments API",
        "Quayside Payments",
        "London, United Kingdom (hybrid)",
        "europe",
        44,
        salary=("GBP", 80000, 95000),
        posting="quayside",
    )
    larchmont = collect(
        "larchmont-data-platform",
        "Data Platform Engineer",
        "Larchmont Bank",
        "Lisbon, Portugal (hybrid)",
        "europe",
        58,
        salary=("EUR", 60000, 75000),
        posting="larchmont",
    )
    freightwise = collect(
        "freightwise-python",
        "Python Backend Engineer",
        "Freightwise",
        "Remote, Europe",
        "feed",
        30,
        salary=("EUR", 70000, 85000),
        posting="freightwise",
    )
    lumacare = collect(
        "lumacare-patient-platform",
        "Backend Engineer, Patient Platform",
        "Lumacare Health",
        "Dublin, Ireland",
        "europe",
        12,
        salary=("EUR", 75000, 90000),
        posting="lumacare",
    )
    for job, found, sent, reply in (
        (larchmont, 58, 52, None),
        (
            quayside,
            44,
            38,
            {
                "kind": "rejection",
                "date": day(-17),
                "note": "They chose a candidate with more payments experience.",
            },
        ),
        (
            freightwise,
            30,
            23,
            {
                "kind": "interview",
                "date": day(-9),
                "note": "Technical interview with two backend engineers, video call.",
            },
        ),
        (lumacare, 12, 6, None),
    ):
        with moment(days=found - 1), acting_as(OWNER):
            application = workspace.create_application({"job_id": job["id"]})
        revisions(application, job["company"], found - 2)
        with moment(days=sent), acting_as(OWNER):
            change(application, stage="applied", applied_at=ago(days=sent))
        if reply:
            waited = (today - datetime.fromisoformat(reply["date"]).date()).days
            with moment(days=waited), acting_as(OWNER):
                change(application, reply=reply)
        if job is freightwise:
            with moment(days=8), acting_as(OWNER):
                workspace.add_note(
                    job["id"],
                    {
                        "application_id": application["id"],
                        "body": (
                            "Interview on Thursday at 16:00 with Sam and Priya. Prepare the "
                            "deployment workflow story and questions about on-call."
                        ),
                    },
                )

    # Ready: the Voltline application, with the agent's CV and letter.
    voltline = collect(
        "senior-backend-grid-data",
        "Senior Backend Engineer, Grid Data",
        "Voltline Grid Analytics",
        "Amsterdam, Netherlands (hybrid)",
        "voltline",
        6,
        salary=("EUR", 80000, 95000),
        posting="voltline",
        ats="greenhouse",
    )
    with moment(days=5), acting_as(OWNER):
        ready = workspace.create_application(
            {"job_id": voltline["id"], "priority": 1, "deadline": day(12)}
        )
    revisions(ready, voltline["company"], 1, letter=True)
    with moment(hours=20), acting_as(agent):
        workspace.add_note(
            voltline["id"],
            {
                "application_id": ready["id"],
                "body": (
                    "CV leads with the latency work and the deployment workflow; the letter "
                    "connects them to the ingestion path in the posting. Ready to send."
                ),
            },
        )

    # Shortlisted, needing its letter: the Carbon Ledger Foundation, closing within a week.
    carbon = collect(
        "carbon-ledger-emissions",
        "Software Engineer, Emissions Data",
        "Carbon Ledger Foundation",
        "Remote, Europe",
        "feed",
        4,
        salary=("EUR", 65000, 75000),
        posting="carbon",
    )
    with moment(days=3), acting_as(agent), batch():
        workspace.set_triage(carbon["id"], "shortlisted", carbon["version"])
        application = workspace.db.one(
            "SELECT id FROM applications WHERE job_id=? AND status<>'closed'", (carbon["id"],)
        )
        carbon_app = change(
            application,
            priority=1,
            deadline=day(5),
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
    revisions(carbon_app, carbon["company"], 2)

    # Shortlisted by the owner, no documents yet: Tessellate Maps, which requires Italian.
    tessellate = collect(
        "tessellate-geospatial-api",
        "Backend Engineer, Geospatial APIs",
        "Tessellate Maps",
        "Barcelona, Spain (hybrid)",
        "europe",
        3,
        salary=("EUR", 55000, 65000),
        posting="tessellate",
    )
    with moment(days=2), acting_as(OWNER):
        workspace.create_application(
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

    # New jobs, a likely duplicate of the Voltline job among them.
    new = [
        collect(
            "voltline-grid-data",
            "Senior Backend Engineer - Grid Data",
            "Voltline Grid Analytics",
            "Amsterdam, Netherlands",
            "search",
            2,
            posting="voltline",
        ),
        collect(
            "kelpie-senior-python",
            "Senior Python Engineer, Developer Tools",
            "Kelpie Labs",
            "Toronto, Canada (remote)",
            "feed",
            2,
            salary=("CAD", 140000, 165000),
            posting="kelpie",
        ),
        collect(
            "meridian-data-apis",
            "Backend Engineer, Data APIs",
            "Meridian Insurance Group",
            "Berlin, Germany (hybrid)",
            "europe",
            1,
            salary=("EUR", 75000, 85000),
            posting="meridian",
        ),
        collect(
            "spreeland-backend",
            "Backend-Entwickler/in Python (m/w/d)",
            "Spreeland Energie GmbH",
            "Berlin, Germany",
            "europe",
            1,
            posting="spreeland",
        ),
        collect(
            "fernhill-platform",
            "Platform Engineer",
            "Fernhill Mobility",
            "Remote, Europe",
            "feed",
            0.4,
            posting="fernhill",
        ),
        collect(
            "cobalt-billing",
            "Software Engineer, Billing",
            "Cobalt Telecom",
            "Dublin, Ireland",
            "europe",
            0.1,
            salary=("EUR", 55000, 65000),
            posting="cobalt",
        ),
    ]
    with moment(hours=10), acting_as(agent):
        workspace.add_note(
            new[1]["id"],
            {
                "body": (
                    "Close match: the product is a deployment workflow like the one in your "
                    "Selected Project. Senior title; the posting asks for mentoring."
                )
            },
        )

    # Dismissals: one by the agent, one by the owner, each with its reason.
    agency = collect(
        "pixelwright-frontend",
        "Frontend Engineer (React)",
        "Pixelwright Studio",
        "Amsterdam, Netherlands",
        "search",
        3,
        posting="pixelwright",
    )
    london = collect(
        "northpeak-staff-backend",
        "Staff Backend Engineer",
        "Northpeak Trading",
        "London, United Kingdom",
        "europe",
        5,
        salary=("GBP", 120000, 140000),
        posting="northpeak",
    )
    with moment(days=2, hours=20), acting_as(agent), batch():
        workspace.set_triage(
            agency["id"],
            "dismissed",
            workspace.get_job(agency["id"])["version"],
            reason="Frontend role at an agency; both are ruled out in your Preferences.",
        )
    with moment(days=4), acting_as(OWNER):
        workspace.set_triage(
            london["id"],
            "dismissed",
            workspace.get_job(london["id"])["version"],
            reason="On site in London five days a week.",
        )

    # Collection history: each source ran this morning, the search also yesterday.
    with workspace.db.transaction() as conn:
        for source, name, received, created, hours in (
            ("search", "Backend roles, Amsterdam", 24, 3, 28),
            ("search", "Backend roles, Amsterdam", 27, 2, 4),
            ("europe", "Data and backend roles, Europe", 38, 4, 3),
            ("voltline", "Voltline Grid Analytics careers", 9, 0, 3),
            ("feed", "Remote Python jobs feed", 18, 2, 2),
        ):
            run_id, started = new_id(), ago(hours=hours)
            finished = ago(hours=hours, seconds=-40)
            conn.execute(
                "INSERT INTO collection_runs(id,source_id,source_name,source_version,"
                "source_snapshot,created_at) VALUES(?,?,?,1,'{}',?)",
                (run_id, sources[source], name, started),
            )
            conn.execute(
                "INSERT INTO tasks(id,kind,source_id,run_id,state,payload,result,attempts,"
                "next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,1,?,?,?)",
                (
                    new_id(),
                    "collect",
                    sources[source],
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
                (finished, started, sources[source]),
            )
    return token
