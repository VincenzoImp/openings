"""Seed the demo workspace: one fictional person's job search.

Alex Example, the backend engineer of examples/cv.tex and examples/career.json,
who lives in Amsterdam and looks for backend and data roles in Europe or remote,
with the example Preferences, three templates, four collection sources and an
agent token named "Claude Code"; the jobs and applications are in jobs.py. The
CVs and letters are real PDFs built with Tectonic from the TeX files beside this
module (the layout of examples/cv.tex and letter.tex), stored with those sources;
the templates carry the same PDFs as their samples.

Everything goes through the services, except the dates: each block's records
are dated back with raw SQL (marker.py), so the screens always look current.
That runs only on a file that carries the demo marker, which ``mark_demo``
writes on a new, empty workspace and nothing else writes.
"""

import asyncio
import json

from ..actors import OWNER, acting_as, token_actor
from ..career import EntryCreate, HighlightCreate, ProfileUpdate, TemplateCreate
from ..common import encode, examples_dir, new_id
from ..discovery.models import RSSConfig, SourceCreate
from ..documents import UploadReservation
from . import marker
from .jobs import FILES, DemoJobs, Upload
from .marker import mark_demo

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


def seed_demo(app):
    """Seed the demo workspace into the new, empty workspace of ``app``.

    Returns the agent token "Claude Code" with its secret.
    """
    workspace, career = app.state.workspace, app.state.career
    discovery, preferences = app.state.discovery, app.state.preferences
    documents = app.state.documents

    def moment(**delta):
        return marker.moment(workspace.db, **delta)

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
                "Ran the team's first load tests before a customer launch.",
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
        # Each template with a sample PDF for its Preview: one of the demo's own documents.
        for name, kind, tex, guidance, rules, sample in (
            (
                "Main CV",
                "cv",
                cv_tex,
                CV_GUIDANCE,
                {"max_pages": 1, "engine": "tectonic"},
                "demo-cv",
            ),
            (
                "Cover letter",
                "letter",
                letter_tex,
                LETTER_GUIDANCE,
                {"max_pages": 1, "engine": "tectonic", "date_format": "D MMMM YYYY"},
                "demo-letter",
            ),
            (
                "Compact CV",
                "cv",
                cv_tex.replace("margin=1.7cm", "margin=1.2cm"),
                COMPACT_GUIDANCE,
                {"max_pages": 1, "max_bullets": 4, "max_bullet_chars": 110, "engine": "tectonic"},
                "demo-cv",
            ),
        ):
            template = career.create_template(
                TemplateCreate(name=name, kind=kind, tex=tex, guidance=guidance, rules=rules)
            )
            data = (FILES / f"{sample}.pdf").read_bytes()
            with acting_as(OWNER):
                grant = documents.reserve_upload(
                    UploadReservation(
                        owner_type="template",
                        owner_id=template["id"],
                        name="sample.pdf",
                        media_type="application/pdf",
                        size=len(data),
                    )
                )
                asyncio.run(documents.upload(Upload(grant, data)))
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
                    url="https://careers.voltline.example/jobs",
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
        saved = marker.ago()
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

    DemoJobs(app, agent, sources).seed()
    return token
