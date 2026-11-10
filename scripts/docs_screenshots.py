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


def synthetic_pdf(title):
    """A one-page PDF with a single line of text, built without dependencies."""
    stream = f"BT /F1 16 Tf 40 440 Td ({title}) Tj ET"
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
    def __init__(self, base, token):
        self.http = httpx.Client(
            base_url=base + "/api/v1", headers={"Authorization": f"Bearer {token}"}, timeout=30
        )
        self.base = base

    def call(self, method, path, **kwargs):
        response = self.http.request(method, path, **kwargs)
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
        return self.call(
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
            self.upload(document, f"{kind}.pdf", "application/pdf", synthetic_pdf(title))
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
        for text in claims:
            s.call(
                "POST",
                "/career/claims",
                json={"knowledge_id": entry["id"], "text": text, "approved": True},
            )

    resume = s.call(
        "POST",
        "/templates",
        json={
            "name": "Engineering CV",
            "kind": "resume",
            "tex": (ROOT / "examples/resume.tex").read_text(),
            "guidance": "One page. Lead with backend and data work.",
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
    del lumen

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

    cedar = s.application(
        s.job("Site Reliability Engineer", "Cedar Systems", "Zurich, Switzerland", "indeed"),
        priority=4,
    )
    cedar_context = s.call("POST", "/contexts", json={"application_id": cedar["id"]})
    s.document(cedar, cedar_context, "resume", "Engineering CV", cv_lines, pdf=False)

    s.application(
        s.job("Product Engineer", "Harbor Studio", "Geneva, Switzerland", "linkedin"), "applied"
    )
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

    s.call("POST", "/tokens", json={"name": "Agent on laptop"})


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
        token = app.state.auth.create_token("Screenshot seeding")["token"]
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
        current = seeder.call("GET", "/tokens")
        for item in current.get("items", []):
            if item["name"] == "Screenshot seeding":
                seeder.call("DELETE", f"/tokens/{item['id']}")
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
