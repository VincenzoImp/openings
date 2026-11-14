"""A curated demo workspace: one fictional person's job search, for screenshots.

Alex Example, the backend engineer of examples/cv.tex and examples/career.json,
with the example Preferences, three templates, three collection sources, an
agent token named "Claude Code" and fifteen jobs at fictional companies: new
jobs (one a likely duplicate of a job with an application, one that requires
German), two dismissals (by the owner and by the agent) and applications in
every stage. The Ready application's CV and letter are the real PDFs built from
examples/cv.tex and examples/letter.tex (tests/fixtures/demo-*.pdf), with those
exact sources. All dates are relative to now, so the screens always look current.
Everything is fictional and uses example domains.
"""

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from openings.actors import OWNER, acting_as, batch, token_actor
from openings.career import EntryCreate, HighlightCreate, ProfileUpdate, TemplateCreate
from openings.common import encode, new_id
from openings.discovery.models import RSSConfig, SourceCreate
from openings.documents import DocumentCreate

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

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

POSTINGS = {
    "voltline": (
        "Voltline Grid Analytics turns measurements from electricity networks into forecasts "
        "that grid operators use to plan their day. Our grid data team of seven engineers runs "
        "the services that receive meter and substation readings, check them and serve them "
        "to forecasting models and to our customers' control rooms. We work from Zurich, with "
        "two office days a week.\n\n"
        "As a senior backend engineer you will design and run Python services and APIs for "
        "measurement data, improve the reliability and latency of our ingestion path, and "
        "help the team operate what it builds, including a shared on-call rotation. You have "
        "five or more years of backend development with Python and SQL, experience running "
        "services in containers on Linux, and a habit of measuring before you optimize. "
        "Experience with time-series data or the energy sector is welcome but not required. "
        "Fluent English is required."
    ),
    "carbon": (
        "The Carbon Ledger Foundation is a nonprofit that publishes open emissions data for "
        "more than 4,000 companies. Researchers, journalists and regulators rely on our "
        "datasets and our public API. We are a remote team of 25 across Europe, with a small "
        "engineering group of five.\n\n"
        "You will build the services behind our public API, keep our data pipelines correct "
        "and reproducible, and work with our research team on new datasets. You will review "
        "code, write clear documentation and share on-call duty for the API. We look for "
        "three or more years of backend experience with Python, good SQL, experience with "
        "public APIs and an interest in climate data. Please include a link to a public code "
        "sample with your application. Fluent English is required. Applications close at "
        "the end of next week."
    ),
    "tessellate": (
        "Tessellate Maps builds geospatial software for public transport companies and city "
        "planners in Switzerland and Italy. Our backend team in Lugano maintains the APIs "
        "that serve routes, stops and timetables to web and mobile applications used by "
        "around two million travelers each month.\n\n"
        "As a backend engineer you will develop new endpoints for our geospatial APIs, "
        "improve query performance on PostgreSQL and take part in design reviews. You will "
        "work closely with our customers' technical teams. We look for solid experience with "
        "Python and SQL, practical knowledge of Docker and Linux, and care for API design. "
        "Experience with PostGIS is a plus. Fluent Italian and English are required, as "
        "many of our customers work in Italian. We offer a hybrid model with three office "
        "days a week in Lugano."
    ),
    "lumacare": (
        "Lumacare Health makes software that helps hospitals in Switzerland and Germany plan "
        "patient care across wards. Our patient platform team owns the services that store "
        "care plans and synchronize them with hospital systems. The team has six engineers "
        "and a product manager and works from Basel, with flexible office days.\n\n"
        "You will build and operate backend services in Python, design APIs used by our "
        "web application and by hospital integrations, and help us improve observability "
        "across the platform. You have at least four years of backend experience, are "
        "comfortable with SQL and asynchronous workers, and you write tests and "
        "documentation as part of your work. Experience with healthcare data standards is a "
        "plus. Fluent English is required; German is an advantage."
    ),
    "larchmont": (
        "The data platform team of Larchmont Bank builds the shared services that our "
        "analysts and risk teams use to load, check and query data. We are twelve engineers "
        "in Zurich and work closely with the bank's security and compliance teams.\n\n"
        "As a data platform engineer you will develop Python services that move data "
        "between our core systems and the analytics platform, build self-service APIs for "
        "data access, and automate deployments. You will also help analysts write efficient "
        "SQL. We look for experience with Python, SQL and APIs, familiarity with Docker and "
        "Linux, and a careful approach to change in a regulated environment. Experience in "
        "financial services is welcome. Fluent English is required. We offer a hybrid model, "
        "a yearly training budget and a pension plan above the legal minimum."
    ),
    "freightwise": (
        "Freightwise is a logistics scale-up that matches freight with available trucks "
        "across Europe. Our routing and pricing services handle about 30,000 shipments a "
        "day. The backend team works remotely within Europe and meets in person twice a "
        "year.\n\n"
        "As a Python backend engineer you will design and build APIs for carriers and "
        "shippers, move slow synchronous work to asynchronous workers, and improve how we "
        "deploy and roll back services. You have three or more years of experience with "
        "Python in production, good knowledge of SQL, and experience with Docker and "
        "continuous delivery. You like to make operations simpler for the whole team. "
        "Fluent English is required. We offer a remote contract within Europe, a home "
        "office budget and four weeks of paid holiday plus public holidays."
    ),
    "quayside": (
        "Quayside Payments provides payment processing for online shops in Switzerland and "
        "Austria. Our payments API team builds the endpoints that merchants integrate "
        "with and keeps them fast and available around the clock.\n\n"
        "You will develop new API features, improve error handling and idempotency, and "
        "take part in incident reviews. We look for four or more years of backend "
        "experience, strong SQL, experience with REST APIs and an interest in payments. "
        "Experience with Kotlin or Java is a plus. Fluent English is required. The role is "
        "based in Zurich with two days of remote work a week."
    ),
    "kelpie": (
        "Kelpie Labs builds developer tools for teams that run Python services: a deployment "
        "dashboard, health checks and release notes generated from commits. We are a fully "
        "remote company of 40 people across Europe.\n\n"
        "As a senior Python engineer you will work on our deployment workflow product, from "
        "the API to the background workers that run checks and rollbacks. You will help "
        "shape our technical direction and mentor colleagues. We look for strong Python "
        "experience, a good understanding of Linux and containers, and experience designing "
        "reliable deployment or release processes. Experience with TypeScript is a plus. "
        "Fluent English is required. We offer a remote contract, flexible hours and a "
        "learning budget."
    ),
    "meridian": (
        "Meridian Insurance Group is modernizing how its brokers and customers access policy "
        "data. Our new data APIs team in Basel replaces nightly file exports with APIs that "
        "partners can call directly.\n\n"
        "You will design and build those APIs in Python, model data in SQL and work with "
        "architects on security and access control. You will also help colleagues from "
        "other teams adopt the new APIs. We look for experience with Python, SQL and REST "
        "APIs and an interest in clear documentation. Experience in insurance is not needed. "
        "Fluent English is required. The role is hybrid, with two office days a week in Basel."
    ),
    "fernhill": (
        "Fernhill Mobility runs a booking platform for shared electric vans in eight European "
        "cities. Our platform team provides the infrastructure and tooling that our product "
        "teams use to ship every day.\n\n"
        "As a platform engineer you will improve our deployment pipelines, run our container "
        "platform on Linux and build internal APIs for service health. You will also take "
        "part in an on-call rotation. We look for experience with Docker, Linux and Python, "
        "and an interest in making developers' work simpler. Experience with Terraform is a "
        "plus. Fluent English is required. The role is remote within Europe."
    ),
    "cobalt": (
        "Cobalt Telecom provides mobile and internet plans to small businesses in "
        "Switzerland. The billing team builds the services that rate usage and produce "
        "monthly invoices for 60,000 customers.\n\n"
        "As a software engineer you will develop billing services in Python, improve the "
        "accuracy of our rating rules and work with finance on reports. We look for two or "
        "more years of experience with Python and SQL, care for correctness, and good "
        "communication. Fluent English is required. The role is based in Zurich, with "
        "flexible hours and one remote day a week."
    ),
    "rheintal": (
        "Die Rheintal Energie AG versorgt über 200'000 Haushalte mit Strom und Wärme. Für "
        "unser Team Digitale Dienste in Zürich suchen wir eine Backend-Entwicklerin oder "
        "einen Backend-Entwickler.\n\n"
        "Deine Aufgaben: Du entwickelst Dienste in Python für unser Kundenportal, du "
        "betreust Schnittstellen zu unseren Abrechnungssystemen und du arbeitest eng mit "
        "dem Betrieb zusammen. Dein Profil: mehrjährige Erfahrung mit Python und SQL, "
        "Erfahrung mit Docker und Linux, fließend Deutsch (C1) und gute Englischkenntnisse. "
        "Wir bieten flexible Arbeitszeiten, zwei Tage Homeoffice pro Woche und ein "
        "Generalabonnement."
    ),
    "pixelwright": (
        "Pixelwright Studio is a digital agency that builds websites and web applications "
        "for clients in retail and tourism. We are looking for a frontend engineer to join "
        "our client delivery team in Zurich.\n\n"
        "You will build user interfaces in React and TypeScript for client projects, work "
        "with our designers on component libraries and present your work to clients. We "
        "look for three years of experience with React, strong CSS skills and experience "
        "with design systems. Fluent English is required. We offer a hybrid model and a "
        "yearly team trip."
    ),
    "northpeak": (
        "Northpeak Trading builds low-latency trading systems for energy markets. Our "
        "backend group in London is growing and we are looking for a staff backend "
        "engineer.\n\n"
        "You will lead the design of our order and position services, set engineering "
        "standards and mentor engineers across three teams. We look for eight or more years "
        "of backend experience, deep knowledge of Python or Java, and experience with "
        "trading systems. Fluent English is required. The role is on site in London, five "
        "days a week."
    ),
}

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


def seed_demo(app, client):
    """Seed the demo workspace with the services of ``app`` and its test ``client``."""
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
        when = datetime.now(UTC) - timedelta(**delta)
        with workspace.db.transaction() as conn:
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
                    (
                        (when + timedelta(seconds=index)).isoformat(timespec="microseconds"),
                        row["id"],
                    ),
                )

    with acting_as(OWNER):
        token = app.state.auth.create_token("Claude Code", "agent")
    agent = token_actor(token["id"], "Claude Code", "agent")
    cv_tex = (ROOT / "examples/cv.tex").read_text()
    letter_tex = (ROOT / "examples/letter.tex").read_text()

    # The person, as in examples/career.json and examples/cv.tex.
    with moment(days=70):
        career.update_profile(
            ProfileUpdate(
                expected_version=career.get_profile()["version"],
                name="Alex Example",
                headline="Backend Engineer",
                location="Zurich, Switzerland",
                email="alex@example.test",
                phone="+41 44 000 00 00",
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
        career_json = json.loads((ROOT / "examples/career.json").read_text())
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
        for language, level in (("Italian", "Native"), ("English", "Fluent (C1)")):
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
        example = json.loads((ROOT / "examples/preferences.json").read_text())
        with acting_as(OWNER):
            for section, items in example["sections"].items():
                preferences.update_preferences(section, {"expected_version": 0, "items": items})
            preferences.update_settings({"expected_version": 0, **example["settings"]})

    # Three sources, stored as the dashboard saves them.
    sources = {}
    with moment(days=45), acting_as(OWNER):
        for key, value in (
            (
                "search",
                SourceCreate(
                    name="Backend roles, Zurich",
                    kind="jobspy",
                    config={
                        "query": "backend engineer python",
                        "location": "Zurich",
                        "country": "switzerland",
                        "providers": ["linkedin", "indeed"],
                        "results_wanted": 30,
                        "hours_old": 72,
                    },
                    filters={"exclude_titles": ["intern", "working student"]},
                    enabled=True,
                    schedule={"kind": "daily", "times": ["07:00"], "timezone": "Europe/Zurich"},
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
        stamp = ago()
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
                stamp,
                stamp,
                stamp,
            ),
        )

    def collect(key, title, company, location, source, days, **extra):
        board = "greenhouse" if source == "voltline" else None
        url = (
            f"https://boards.greenhouse.io/voltline/jobs/{key}"
            if board
            else f"https://jobs.example.test/{source}/{key}"
        )
        with moment(days=days):
            return workspace.ingest_job(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "posting": POSTINGS[extra.pop("posting", key)],
                    "source_id": sources[source],
                    "metadata": {"source": board or source, **extra},
                    **({"source_key": f"greenhouse:voltline:{key}"} if board else {}),
                }
            )

    def revisions(application, company, days, letter=True):
        """The agent's CV (and letter) for an application: the demo PDFs with their sources."""
        kinds = [("cv", cv_tex, "demo-cv.pdf")]
        if letter:
            kinds.append(("letter", letter_tex, "demo-letter.pdf"))
        with moment(days=days), acting_as(agent), batch():
            for kind, tex, pdf in kinds:
                data = (FIXTURES / pdf).read_bytes()
                document = documents.create_document(
                    DocumentCreate(
                        application_id=application["id"],
                        kind=kind,
                        title=f"{'CV' if kind == 'cv' else 'Letter'} for {company}",
                        source=tex,
                        pdf={"name": f"{kind}.pdf", "size": len(data)},
                    )
                )
                grant = document["uploads"]["pdf"]
                response = client.put(grant["url"], headers=grant["headers"], content=data)
                assert response.status_code == 200, response.text

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
        "Zurich, Switzerland (hybrid)",
        "search",
        44,
        posting="quayside",
    )
    larchmont = collect(
        "larchmont-data-platform",
        "Data Platform Engineer",
        "Larchmont Bank",
        "Zurich, Switzerland (hybrid)",
        "search",
        58,
        posting="larchmont",
    )
    freightwise = collect(
        "freightwise-python",
        "Python Backend Engineer",
        "Freightwise",
        "Remote, Europe",
        "feed",
        30,
        posting="freightwise",
    )
    lumacare = collect(
        "lumacare-patient-platform",
        "Backend Engineer, Patient Platform",
        "Lumacare Health",
        "Basel, Switzerland",
        "search",
        12,
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
        "Zurich, Switzerland (hybrid)",
        "voltline",
        6,
        posting="voltline",
        ats="greenhouse",
    )
    with moment(days=5), acting_as(OWNER):
        ready = workspace.create_application(
            {"job_id": voltline["id"], "priority": 1, "deadline": day(12)}
        )
    revisions(ready, voltline["company"], 1)
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
    revisions(carbon_app, carbon["company"], 2, letter=False)

    # Shortlisted by the owner, no documents yet: Tessellate Maps, which requires Italian.
    tessellate = collect(
        "tessellate-geospatial-api",
        "Backend Engineer, Geospatial APIs",
        "Tessellate Maps",
        "Lugano, Switzerland (hybrid)",
        "search",
        3,
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
            "Zurich, Switzerland",
            "search",
            2,
            posting="voltline",
        ),
        collect(
            "kelpie-senior-python",
            "Senior Python Engineer, Developer Tools",
            "Kelpie Labs",
            "Remote, Europe",
            "feed",
            2,
            posting="kelpie",
        ),
        collect(
            "meridian-data-apis",
            "Backend Engineer, Data APIs",
            "Meridian Insurance Group",
            "Basel, Switzerland (hybrid)",
            "search",
            1,
            posting="meridian",
        ),
        collect(
            "rheintal-backend",
            "Backend-Entwickler/in Python (m/w/d)",
            "Rheintal Energie AG",
            "Zurich, Switzerland",
            "search",
            1,
            posting="rheintal",
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
            "Zurich, Switzerland",
            "search",
            0.1,
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
        "Zurich, Switzerland",
        "search",
        3,
        posting="pixelwright",
    )
    london = collect(
        "northpeak-staff-backend",
        "Staff Backend Engineer",
        "Northpeak Trading",
        "London, United Kingdom",
        "feed",
        5,
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
            ("search", "Backend roles, Zurich", 24, 3, 28),
            ("search", "Backend roles, Zurich", 27, 2, 4),
            ("voltline", "Voltline Grid Analytics careers", 9, 0, 3),
            ("feed", "Remote Python jobs feed", 18, 2, 2),
        ):
            run_id, stamp = new_id(), ago(hours=hours)
            finished = ago(hours=hours, seconds=-40)
            conn.execute(
                "INSERT INTO collection_runs(id,source_id,source_name,source_version,"
                "source_snapshot,created_at) VALUES(?,?,?,1,'{}',?)",
                (run_id, sources[source], name, stamp),
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
                    json.dumps({"provider": "linkedin" if source == "search" else source}),
                    json.dumps(
                        {
                            "received": received,
                            "created": created,
                            "existing": received - created,
                            "started_at": stamp,
                            "processing_seconds": 31.5,
                            "http_requests": 4,
                        }
                    ),
                    stamp,
                    stamp,
                    finished,
                ),
            )
            conn.execute(
                "UPDATE sources SET last_run_at=?,last_scheduled_at=? WHERE id=?",
                (finished, stamp, sources[source]),
            )
