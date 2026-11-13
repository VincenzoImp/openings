"""Regenerate the documentation screenshots from a synthetic workspace.

Starts an isolated server on a temporary database (no collection workers),
fills it with fictional people, companies and documents through REST, then runs
`scripts/docs_screenshots.mjs` with the frontend's Playwright to capture
`docs/images/*.png`. The temporary database is deleted afterwards.

Requirements: `uv sync`, `npm --prefix frontend ci`, `npm --prefix frontend run build`
and `npx playwright install chromium` in `frontend`.

    uv run python scripts/docs_screenshots.py [--port 18640] [--keep-running]
"""

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

import httpx
import uvicorn

from openings.app import create_app

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "synthetic-screenshot-password"
TODAY = date.today()


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def synthetic_pdf(title, lines=()):
    """A one-page PDF with a title and a few lines of text, built without dependencies."""
    escape = lambda text: text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = "".join(
        f" 0 -22 Td ({escape(line)}) Tj" for line in lines if line.isascii()
    )
    stream = (
        f"BT /F1 16 Tf 40 450 Td ({escape(title)}) Tj /F1 9 Tf 0 -12 Td{body} ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 500] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    data, offsets = "%PDF-1.4\n", []
    for index, item in enumerate(objects, 1):
        offsets.append(len(data.encode()))
        data += f"{index} 0 obj\n{item}\nendobj\n"
    xref = len(data.encode())
    data += "xref\n0 6\n0000000000 65535 f \n"
    data += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return data.encode()


POSTING = """{company} is hiring a {title} to join a small product engineering team.

Responsibilities
- Design and operate reliable Python services and APIs.
- Improve observability, deployment safety and data quality.
- Work closely with product, design and research colleagues.

Requirements
- Several years of backend or data engineering experience.
- Practical knowledge of Python, SQL and cloud infrastructure.
- Clear written English.

This is a fictional posting created for the Openings documentation."""


class Seeder:
    """Seeds as the agent (API token); `owner` is the dashboard session for the owner's part."""

    def __init__(self, base, token):
        self.http = httpx.Client(
            base_url=base + "/api/v1", headers={"Authorization": f"Bearer {token}"}, timeout=30
        )
        self.session = httpx.Client(base_url=base + "/api/v1", timeout=30)
        login = self.session.post("/auth/login", json={"password": PASSWORD})
        self.session.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        self.base = base

    def call(self, method, path, **kwargs):
        return self._request(self.http, method, path, **kwargs)

    def owner(self, method, path, **kwargs):
        return self._request(self.session, method, path, **kwargs)

    @staticmethod
    def _request(client, method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
        return response.json() if response.content else None

    def job(self, title, company, location, source="manual", key=None, posting=None, url=None):
        slug = f"{company}-{title}".lower().replace(" ", "-").replace("&", "and")
        return self.call(
            "POST",
            "/jobs",
            json={
                "title": title,
                "company": company,
                "location": location,
                "url": url or f"https://jobs.example.test/{slug}",
                "posting": posting or POSTING.format(company=company, title=title),
                "source_key": key,
                "metadata": {"source": source},
            },
        )

    def triage(self, job, triage):
        return self.call(
            "POST",
            f"/jobs/{job['id']}/triage",
            json={"triage": triage, "expected_version": job["version"]},
        )

    def application(self, job, stage="draft", outcome=None, via="draft", **fields):
        """Create an attempt and record each stage up to `stage` (Closed after `via`)."""
        app = self.call("POST", "/applications", json={"job_id": job["id"], **fields})
        path = ["draft", "applied", "interview", "offer"]
        last = via if stage == "closed" else stage
        for status in path[1 : path.index(last) + 1]:
            app = self.patch_application(app, status=status)
        if stage == "closed":
            app = self.patch_application(app, status="closed", outcome=outcome)
        return app

    def patch_application(self, app, **fields):
        # The owner applies and records each stage.
        return self.owner(
            "PATCH",
            f"/applications/{app['id']}",
            json={"expected_version": app["version"], **fields},
        )

    def upload(self, document, name, media_type, data):
        grant = self.call(
            "POST",
            "/files/uploads",
            json={
                "owner_type": "document",
                "owner_id": document["id"],
                "name": name,
                "media_type": media_type,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
        )
        upload = grant.get("upload", grant)
        response = httpx.request(
            upload["method"],
            httpx.URL(self.base).join(upload["url"]),
            headers=upload.get("headers", {}),
            content=data,
            timeout=30,
        )
        response.raise_for_status()

    def document(self, app, context, kind, title, lines, pdf=True, approve=False, previous=None):
        content = {"paragraphs": lines}
        document = self.call(
            "POST",
            "/documents",
            json={
                "application_id": app["id"],
                "context_id": context["id"],
                "kind": kind,
                "title": title,
                "content": content,
                **({"previous_id": previous["id"]} if previous else {}),
            },
        )
        if pdf:
            tex = "\\begin{document}\n" + "\n".join(line.replace("%", "\\%") for line in lines)
            tex += "\n\\end{document}\n"
            self.upload(document, "source.tex", "application/x-tex", tex.encode())
            self.upload(
                document, f"{kind}.pdf", "application/pdf", synthetic_pdf(title, lines)
            )
        if approve:
            current = self.call("GET", f"/documents/{document['id']}")
            self.call(
                "POST",
                f"/documents/{document['id']}/review",
                json={"review_state": "approved", "expected_version": current["version"]},
            )
        return document


def seed(s: Seeder):
    profile = s.call("GET", "/career/profile")
    s.call(
        "PATCH",
        "/career/profile",
        json={
            "expected_version": profile["version"],
            "name": "Alex Morgan",
            "headline": "Backend and data engineer",
            "location": "Zurich, Switzerland",
            "email": "alex.morgan@example.test",
            "roles": "Backend engineer, data platform engineer, research software engineer",
            "preferences": "Zurich, Basel or remote within Europe. Product teams; no on-call-only roles.",
            "summary": "Backend engineer who builds reliable Python services and data pipelines.",
        },
    )
    instructions = s.call("GET", "/instructions")
    s.call(
        "PATCH",
        "/instructions",
        json={
            "expected_version": instructions["version"],
            "general": "Use clear international English. Cite stored evidence; never invent metrics.",
        },
    )

    career = [
        (
            "experience",
            "Backend engineer",
            "Example Cloud",
            {"kind": "period", "start": "2021-01", "current": True},
            ["Python", "SQL", "APIs"],
            "Built Python APIs and asynchronous workers for a developer platform.",
            [
                "Reduced API p95 latency by 20% with request tracing and endpoint revisions.",
                "Helped four colleagues operate the services with runbooks.",
            ],
        ),
        (
            "experience",
            "Software engineer",
            "Example Analytics",
            {"kind": "period", "start": "2018-09", "end": "2020-12"},
            ["Python", "Airflow", "PostgreSQL"],
            "Maintained batch pipelines that fed internal reporting.",
            ["Moved nightly reports from manual scripts to scheduled, monitored pipelines."],
        ),
        (
            "project",
            "Reliable deployment workflow",
            "",
            {"kind": "single", "start": "2023"},
            ["TypeScript", "Docker", "Linux"],
            "Designed a typed deployment workflow with health checks and rollback.",
            ["Reduced the manual deployment procedure from nine steps to three."],
        ),
        (
            "education",
            "MSc in Computer Science",
            "Example University",
            {"kind": "period", "start": "2016-09", "end": "2018-07"},
            ["Distributed systems"],
            "Thesis on reliable stream processing.",
            ["Evaluated exactly-once delivery in three stream processors."],
        ),
        (
            "publication",
            "A fictional note on API reliability",
            "Example Developer Conference",
            {"kind": "single", "start": "2024-05"},
            [],
            "",
            [],
        ),
        (
            "skill",
            "Languages",
            "",
            None,
            ["English", "German", "Italian"],
            "",
            ["English (fluent), German (B2), Italian (native)"],
        ),
    ]
    entries = []
    for kind, title, organization, dates, skills, narrative, claims in career:
        entry = s.call(
            "POST",
            "/career/knowledge",
            json={
                "kind": kind,
                "title": title,
                "organization": organization,
                "dates": dates,
                "skills": skills,
                "narrative": narrative,
            },
        )
        entries.append(entry)
        for index, text in enumerate(claims):
            s.call(
                "POST",
                "/career/claims",
                json={
                    "knowledge_id": entry["id"],
                    "text": text,
                    "approved": True,
                    # Typed selection: the first claim of an entry carries the account.
                    "default_in_cv": index == 0,
                    "role": "core" if index == 0 else "supporting",
                    "group": "Impact" if index == 0 else "Teamwork",
                },
            )

    resume = s.call(
        "POST",
        "/templates",
        json={
            "name": "Engineering CV",
            "kind": "resume",
            "tex": (ROOT / "examples/resume.tex").read_text(),
            "guidance": "One page. Lead with backend and data work.",
            "rules": {
                "max_pages": 1,
                "max_bullets": 4,
                "max_bullet_chars": 160,
                "engine": "pdflatex",
                "statements": [
                    {
                        "label": "Order of sections",
                        "statement": "Experience, projects, education, skills.",
                    },
                    {
                        "label": "Bullets start with a result",
                        "statement": "Each bullet opens with what changed, then how.",
                    },
                    {"label": "Links", "statement": "Website in the header only."},
                ],
            },
            "is_default": True,
        },
    )
    research = s.call(
        "POST",
        "/templates",
        json={
            "name": "Research CV",
            "kind": "resume",
            "tex": (ROOT / "examples/resume.tex").read_text(),
            "guidance": "Two pages. Include publications.",
        },
    )
    letter = s.call(
        "POST",
        "/templates",
        json={
            "name": "Cover letter",
            "kind": "cover_letter",
            "tex": (ROOT / "examples/cover-letter.tex").read_text(),
            "guidance": "Under 300 words.",
            "is_default": True,
        },
    )
    del resume

    # The synthetic policy: the owner's items through the dashboard session, the
    # agent's proposals with its token.
    policy = json.loads((ROOT / "examples/policy.json").read_text())
    for section in ("decision", "eligibility", "writing", "facts"):
        for item in policy[section]:
            item = dict(item)
            request = s.call if item.pop("proposed", False) else s.owner
            current = s.call("GET", f"/policy/{section}")["version"]
            request("POST", f"/policy/{section}/items", json={"expected_version": current, **item})

    sources = [
        {
            "name": "Engineering roles in Zurich",
            "kind": "jobspy",
            "config": {
                "query": "backend engineer",
                "location": "Zurich, Switzerland",
                "country": "switzerland",
                "providers": ["linkedin", "indeed"],
                "results_wanted": 30,
                "hours_old": 72,
            },
            "filters": {"titles": ["engineer", "developer"], "exclude_titles": ["intern", "sales"]},
            "enabled": True,
            "schedule": {"kind": "daily", "times": ["08:00", "17:00"], "timezone": "Europe/Zurich"},
        },
        {
            "name": "Remote data engineering",
            "kind": "jobspy",
            "config": {
                "query": "data engineer",
                "location": "Europe",
                "country": "germany",
                "providers": ["linkedin"],
                "is_remote": True,
            },
            "filters": {"exclude_titles": ["principal", "manager"]},
        },
    ]
    for source in sources:
        s.call("POST", "/sources", json=source)
    for name, board in [
        ("Northstar Labs", "northstar-labs-example"),
        ("Brightline AI", "brightline-example"),
    ]:
        s.call(
            "POST",
            "/sources",
            json={"name": name, "kind": "greenhouse", "config": {"board": board}},
        )

    # Inbox: unreviewed jobs.
    for title, company, location, source in [
        ("Senior Backend Engineer", "Quarry Logistics", "Basel, Switzerland", "linkedin"),
        ("Data Engineer", "Meridian Energy", "Remote, Europe", "indeed"),
        ("Python Developer", "Tessellate", "Zurich, Switzerland", "linkedin"),
        ("Platform Engineer", "Larch Mobility", "Bern, Switzerland", "greenhouse"),
        ("Analytics Engineer", "Helio Retail", "Remote, Europe", "linkedin"),
    ]:
        s.job(title, company, location, source, key=f"{source}:{company}:{title}".lower())

    # Possible duplicates: one vacancy from three places, one from two.
    ml_posting = POSTING.format(company="Brightline AI", title="Machine Learning Engineer")
    for source, url in [
        ("linkedin", "https://www.linkedin.example.test/jobs/view/4100001"),
        ("indeed", "https://indeed.example.test/viewjob?jk=ab12cd34"),
        ("greenhouse", "https://boards.example.test/brightline/jobs/7700012"),
    ]:
        s.job(
            "Machine Learning Engineer",
            "Brightline AI",
            "Zurich, Switzerland",
            source,
            key=f"{source}:brightline-ml",
            posting=ml_posting,
            url=url,
        )
    for source in ["linkedin", "greenhouse"]:
        job = s.job(
            "Frontend Engineer",
            "Pine & Co",
            "Lausanne, Switzerland",
            source,
            key=f"{source}:pine-frontend",
            url=f"https://{source}.example.test/pine-and-co/frontend-engineer",
        )
        s.triage(job, "saved")

    # Shortlist and dismissed.
    for title, company, location in [
        ("Backend Engineer, Payments", "Saffron Pay", "Zurich, Switzerland"),
        ("Research Engineer", "Glacier Climate Lab", "Geneva, Switzerland"),
    ]:
        s.triage(s.job(title, company, location, "linkedin"), "saved")
    for title, company in [("Sales Engineer", "Quartz CRM"), ("Junior QA Intern", "Bolt Games")]:
        s.triage(s.job(title, company, "Remote", "indeed"), "dismissed")

    # Applications across stages, with planning fields.
    cv_lines = [
        "Built Python APIs and asynchronous workers for a developer platform.",
        "Reduced API p95 latency by 20% with request tracing and endpoint revisions.",
    ]
    letter_lines = [
        "Dear Hiring Team,",
        "I build reliable Python services and would like to bring that work to your team.",
    ]
    northstar = s.application(
        s.job("Python Engineer", "Northstar Labs", "Zurich, Switzerland", "greenhouse"),
        priority=1,
        deadline=day(6),
        questions=[{"id": "notice", "label": "What is your notice period?", "required": True}],
        requirements=[
            {
                "kind": "attachment",
                "text": "Attach a CV and a cover letter as PDF.",
                "resolved": True,
                "note": "Both documents prepared.",
            },
            {"kind": "reference", "text": "Name two professional references.", "blocking": False},
            {"kind": "language", "text": "Write the letter in English.", "resolved": True},
        ],
    )
    context = s.call(
        "POST",
        "/contexts",
        json={"application_id": northstar["id"], "template_ids": []},
    )
    first = s.document(northstar, context, "resume", "Engineering CV", cv_lines, approve=True)
    s.document(
        northstar,
        context,
        "resume",
        "Engineering CV — updated experience",
        cv_lines + ["Helped four colleagues operate the services with runbooks."],
        previous=first,
    )
    s.document(northstar, context, "cover_letter", "Cover letter", letter_lines)

    lumen = s.application(
        s.job("Backend Engineer", "Lumen Health", "Basel, Switzerland", "linkedin"),
        priority=2,
        deadline=day(3),
        requirements=[
            {
                "kind": "authorship",
                "text": "Applications must be written without AI writing tools.",
                "blocking": True,
                "note": "Ask the owner whether to apply and write the letter personally.",
            },
            {"kind": "eligibility", "text": "Swiss or EU work permit required.", "resolved": True},
            {"kind": "deadline", "text": "Applications close on the stated date."},
        ],
    )
    s.application(
        s.job("Data Platform Engineer", "Fjord Analytics", "Remote, Europe", "linkedin"),
        priority=3,
        deadline=day(-1),
    )

    orbit = s.application(
        s.job("Data Engineer", "Orbit Works", "Remote, Europe", "lever"),
        priority=2,
        deadline=day(12),
    )
    orbit_context = s.call(
        "POST",
        "/contexts",
        json={"application_id": orbit["id"], "template_ids": [research["id"], letter["id"]]},
    )
    s.document(orbit, orbit_context, "resume", "Research CV", cv_lines, approve=True)
    s.document(orbit, orbit_context, "cover_letter", "Cover letter", letter_lines, approve=True)
    # A later template edit marks Orbit Works as built on older inputs.
    current = s.call("GET", f"/templates/{research['id']}")
    s.call(
        "PATCH",
        f"/templates/{research['id']}",
        json={"expected_version": current["version"], "guidance": "Two pages. Publications first."},
    )

    # Two more Drafts the agent hands over complete: Today lists them closest deadline first.
    for title, company, location, source, fields in (
        (
            "Python Engineer",
            "Fjord Analytics",
            "Remote, Europe",
            "ashby",
            {"deadline": day(1), "priority": 1},
        ),
        (
            "Data Platform Engineer",
            "Quartz Systems",
            "Basel, Switzerland",
            "lever",
            {"deadline": day(5), "priority": 1},
        ),
    ):
        ready = s.application(s.job(title, company, location, source), **fields)
        context = s.call("POST", "/contexts", json={"application_id": ready["id"]})
        s.document(ready, context, "resume", "Engineering CV", cv_lines, approve=True)
        s.document(ready, context, "cover_letter", "Cover letter", letter_lines, approve=True)
        current = s.call("GET", f"/applications/{ready['id']}")
        s.call(
            "POST",
            f"/applications/{ready['id']}/ready",
            json={"expected_version": current["version"]},
        )

    cedar = s.application(
        s.job("Site Reliability Engineer", "Cedar Systems", "Zurich, Switzerland", "indeed"),
        priority=4,
    )
    cedar_context = s.call("POST", "/contexts", json={"application_id": cedar["id"]})
    s.document(cedar, cedar_context, "resume", "Engineering CV", cv_lines, pdf=False)

    s.application(
        s.job("Product Engineer", "Harbor Studio", "Geneva, Switzerland", "linkedin"), "applied"
    )
    # Sent long ago without a reply: Today asks the owner to record what happened.
    for title, company, location, source, days in (
        ("Data Engineer", "Tidewater Energy", "Bern, Switzerland", "greenhouse", 63),
        ("Analytics Engineer", "Sample Grid", "Remote, Europe", "lever", 51),
    ):
        sent = s.application(s.job(title, company, location, source), "applied")
        s.patch_application(sent, applied_at=f"{day(-days)}T09:00:00+00:00")
    s.application(
        s.job("Research Software Engineer", "Alpine Research", "Lausanne, Switzerland", "rss"),
        "interview",
    )
    s.application(
        s.job("Platform Engineer", "Kestrel Robotics", "Zurich, Switzerland", "greenhouse"),
        "offer",
    )
    s.application(
        s.job("Engineering Lead", "Northstar Labs", "Zurich, Switzerland", "greenhouse"),
        "closed",
        outcome="rejected",
        via="interview",
    )
    s.application(
        s.job("Backend Developer", "Willow Finance", "Lugano, Switzerland", "indeed"),
        "closed",
        outcome="not_pursued",
    )

    answers(s)
    activity(s, lumen, cedar, orbit)
    skill_notes(s)


def answers(s: Seeder):
    """Applications sent weeks ago with the employers' answers, for Insights."""
    history = [
        # title, company, location, source, days ago sent, answer, days to answer
        ("Data Engineer", "Basalt Analytics", "Zurich, Switzerland", "greenhouse", 70, "interview", 6),
        ("Senior Data Engineer", "Fjordline Data", "Zurich, Switzerland", "lever", 64, "rejection", 12),
        ("Data Engineer", "Granite Metrics", "Remote, Europe", "linkedin", 58, None, None),
        ("Data Platform Engineer", "Larch Systems", "Basel, Switzerland", "greenhouse", 55, "interview", 9),
        ("Analytics Engineer", "Meadow Health", "Zurich, Switzerland", "linkedin", 52, "rejection", 21),
        ("Data Engineer", "Pine Logistics", "Remote, Europe", "indeed", 49, None, None),
        ("Backend Engineer", "Quarry Bank", "Zurich, Switzerland", "linkedin", 46, "rejection", 4),
        ("Backend Developer", "Rowan Retail", "Geneva, Switzerland", "indeed", 44, None, None),
        ("Senior Backend Engineer", "Sable Insurance", "Zurich, Switzerland", "greenhouse", 41, "interview", 7),
        ("Backend Engineer", "Thistle Payments", "Remote, Europe", "linkedin", 38, None, None),
        ("Python Developer", "Umber Labs", "Basel, Switzerland", "lever", 35, "rejection", 10),
        ("Platform Engineer", "Vale Energy", "Zurich, Switzerland", "greenhouse", 33, "offer", 25),
        ("Site Reliability Engineer", "Willow Grid", "Remote, Europe", "linkedin", 30, None, None),
        ("Data Engineer", "Yew Robotics", "Zurich, Switzerland", "ashby", 28, "rejection", 8),
    ]
    for title, company, location, source, sent, answer, after in history:
        app = s.application(s.job(title, company, location, source), "applied")
        app = s.patch_application(app, applied_at=f"{day(-sent)}T09:00:00+00:00")
        if answer is None:
            if sent > 45:
                s.patch_application(app, status="closed", outcome="no_response")
            continue
        move = {
            "interview": {"status": "interview"},
            "offer": {"status": "offer"},
            "rejection": {"status": "closed", "outcome": "rejected"},
        }[answer]
        if company != "Sable Insurance":
            s.patch_application(app, **move, response_date=day(after - sent))
            continue
        # One application with a note on the answer and on the attempt, for its timeline.
        s.patch_application(
            app,
            **move,
            response_date=day(after - sent),
            response_note="Phone screen with the hiring manager, then a technical round.",
        )
        s.owner(
            "POST",
            f"/jobs/{app['job_id']}/notes",
            json={
                "body": "Ask about the on-call rotation in the technical round.",
                "application_id": app["id"],
            },
        )


def skill_notes(s: Seeder):
    """Local notes of a skill: the owner's first version, then the agent's addition."""
    first = s.owner(
        "PUT",
        "/skills/review-inbox/notes",
        json={
            "expected_version": 0,
            "text": "Leave every job at Northstar Labs for me, even when it looks like "
            "a duplicate.",
        },
    )
    s.call(
        "PUT",
        "/skills/review-inbox/notes",
        json={
            "expected_version": first["version"],
            "text": first["text"] + "\n\nWhen a posting mentions on-call work, quote the "
            "sentence in your reason.",
        },
    )


def activity(s: Seeder, lumen, cedar, orbit):
    """Two agent runs with their changes, a stored report and questions for the owner."""
    review = s.call(
        "POST",
        "/runs",
        json={
            "workflow": "review-inbox",
            "scope": "Routine Inbox review: every unreviewed job collected this week.",
        },
    )
    kept = s.job("Senior Backend Engineer", "Tidewater Energy", "Bern, Switzerland", "greenhouse")
    s.triage(kept, "saved")
    dropped = s.job("Sales Engineer", "Harbor Studio", "Geneva, Switzerland", "linkedin")
    s.triage(dropped, "dismissed")
    unclear = s.job("Staff Engineer", "Kestrel Robotics", "Zurich, Switzerland", "greenhouse")
    s.call(
        "POST",
        f"/jobs/{kept['id']}/notes",
        json={"body": "Matches the backend and data platform roles in the Profile."},
    )
    s.call(
        "POST",
        "/questions",
        json={
            "question": "Is working from Bern three days a week acceptable?",
            "why": "Tidewater Energy asks for three office days. The Profile names Zurich, "
            "Basel or remote, so the job stays on the Shortlist without a Draft until you decide.",
            "subject_type": "job",
            "subject_id": kept["id"],
            "choices": ["Yes", "No", "Only for the first six months"],
        },
    )
    letter = s.call(
        "POST",
        "/questions",
        json={
            "question": "Do you want to write the Lumen Health letter yourself?",
            "why": "The employer accepts only applications written without AI writing tools.",
            "subject_type": "application",
            "subject_id": lumen["id"],
            "choices": ["Yes, I will write it", "No, close this application"],
        },
    )
    s.call(
        "POST",
        f"/runs/{review['id']}/finish",
        json={
            "expected_version": review["version"],
            "summary": "Reviewed three new jobs: one shortlisted, one dismissed, one left "
            "in the Inbox. Two questions need your answer.",
            "changes": "Shortlisted Senior Backend Engineer at Tidewater Energy and dismissed "
            "Sales Engineer at Harbor Studio (a sales role, outside the Profile).",
            "not_done": [
                {
                    "item": "Staff Engineer at Kestrel Robotics",
                    "reason": "The posting does not say whether the role includes on-call "
                    "duty; it stays in the Inbox.",
                    "subject_type": "job",
                    "subject_id": unclear["id"],
                }
            ],
            "checks": [
                {"check": "Final Inbox query re-read after the last decision."},
                {"check": "Each decision compared with the full posting text."},
                {"check": "Salary range for Tidewater Energy", "verified": False},
            ],
            "limits": "No application was submitted, no employer was contacted and no "
            "application was marked Applied.",
            "method": "The posting text has no structured on-call field, so that criterion "
            "needs a manual read of every posting.",
        },
    )
    s.owner(
        "POST",
        f"/questions/{letter['id']}/answer",
        json={
            "expected_version": letter["version"],
            "choice": "Yes, I will write it",
            "answer": "I will send it before the deadline.",
        },
    )
    drafts = s.call(
        "POST",
        "/runs",
        json={
            "workflow": "prepare-shortlist",
            "scope": "Drafts for the two Shortlist jobs without an application.",
        },
    )
    s.call(
        "POST",
        f"/jobs/{cedar['job_id']}/notes",
        json={
            "body": "The CV still needs its PDF; the letter follows once the CV is approved.",
            "application_id": cedar["id"],
        },
    )
    s.call(
        "POST",
        "/questions",
        json={
            "question": "Which notice period should applications state?",
            "why": "Two application forms ask for the earliest start date.",
        },
    )
    # The owner's requests: the agent handles one in this run, one still waits.
    asked = s.owner(
        "POST",
        "/requests",
        json={
            "text": "Check whether the Orbit Works documents still fit after the template change.",
            "subject_type": "application",
            "subject_id": orbit["id"],
        },
    )
    s.owner("POST", "/requests", json={"text": "Do not prepare roles at consultancies."})
    taken = s.call(
        "POST", f"/requests/{asked['id']}/take", json={"expected_version": asked["version"]}
    )
    s.call(
        "POST",
        f"/requests/{taken['id']}/complete",
        json={
            "expected_version": taken["version"],
            "result": "The CV and letter still match the role; only the page limit changed in "
            "the template. Marked the Draft ready to apply.",
        },
    )
    # The agent hands a complete Draft to the owner: both documents approved, no blocker.
    current = s.call("GET", f"/applications/{orbit['id']}")
    s.call(
        "POST",
        f"/applications/{orbit['id']}/ready",
        json={"expected_version": current["version"]},
    )
    s.call(
        "PATCH",
        f"/runs/{drafts['id']}",
        json={
            "expected_version": drafts["version"],
            "note": "First Draft prepared; the second waits for the notice period.",
        },
    )


def free_port(preferred):
    for port in [preferred, *range(18600, 18700)]:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("No free port in 18600-18699.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=18640)
    parser.add_argument("--out", type=Path, default=ROOT / "docs/images")
    parser.add_argument("--keep-running", action="store_true", help="serve until interrupted")
    args = parser.parse_args()
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the dashboard first: npm --prefix frontend run build")
    directory = Path(tempfile.mkdtemp(prefix="openings-screenshots-"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # still remove the database
    try:
        app = create_app(directory / "workspace.sqlite", start_worker=False)
        app.state.auth.setup(PASSWORD)
        app.state.auth.create_token("Backup script")  # an owner token, for the token list
        token = app.state.auth.create_token("Agent on laptop", "agent")["token"]
        port = free_port(args.port)
        base = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            try:
                if httpx.get(base + "/health").status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        seeder = Seeder(base, token)
        seed(seeder)
        print(f"Synthetic workspace at {base} (password: {PASSWORD})")
        if args.keep_running:
            thread.join()
        else:
            subprocess.run(
                ["node", str(ROOT / "scripts/docs_screenshots.mjs"), base, PASSWORD, str(args.out)],
                check=True,
            )
        server.should_exit = True
        thread.join(timeout=10)
    except KeyboardInterrupt:
        pass
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
