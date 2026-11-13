"""Synthetic, isolated server for browser workflows; no acquisition workers.

Listens on 127.0.0.1:$OPENINGS_E2E_PORT (a free port when unset) and answers
`/__e2e__/run` with $OPENINGS_E2E_TOKEN, so a Playwright run can verify that it
reached the server it started. The route exists only in this test server.

$OPENINGS_E2E_JOBS and $OPENINGS_E2E_APPLICATIONS set the size of the workspace
(60 jobs and 53 applications by default). Above 500 jobs they are written in
bulk (large_fixtures.py), so 5,000 jobs and 500 applications take seconds.
"""

import json
import os
import socket
import tempfile
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

from openings.actors import OWNER, acting_as
from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate, ProfileUpdate, TemplateCreate
from openings.common import new_id, now
from openings.documents import ContextCreate
from openings.policy import SECTIONS
from large_fixtures import seed_large
from today_fixtures import seed_today

RUN_PATH = "/__e2e__/run"
# Above this many jobs the workspace is seeded in bulk (large_fixtures.py).
LARGE = 500
ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def identified(app, token):
    """Wrap the application so that only this process answers RUN_PATH with its run token."""
    body = token.encode()

    async def serve(scope, receive, send):
        if scope["type"] != "http" or scope["path"] != RUN_PATH:
            return await app(scope, receive, send)
        headers = [(b"content-type", b"text/plain"), (b"cache-control", b"no-store")]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    return serve


def seed_library(app, agent):
    """A Profile, typed claims, template rules and the example policy, with one copied value."""
    career, policy = app.state.career, app.state.policy
    career.update_profile(
        ProfileUpdate(
            expected_version=career.get_profile()["version"],
            name="Alex Morgan",
            headline="Senior data engineer",
            location="Zurich, Switzerland",
            email="alex@example.test",
            summary="Data engineer with seven years of Python in production.",
            links=[{"label": "Website", "url": "https://example.test/alex"}],
            metadata={
                "pronouns": "they/them",
                "newsletter": False,
                "interview_availability": {
                    "days": ["Tue", "Thu"],
                    "from": "16:00",
                    "timezone": "Europe/Zurich",
                },
            },
        )
    )
    for kind, title, organization, dates, skills in (
        (
            "experience",
            "Senior data engineer",
            "Example Labs",
            {"kind": "period", "start": "2022-02", "current": True},
            ["Python", "PostgreSQL", "Kafka", "Airflow", "Terraform"],
        ),
        (
            "experience",
            "Software engineer",
            "Sample Grid",
            {"kind": "period", "start": "2019-09", "end": "2022-01"},
            ["Python", "REST APIs", "Docker"],
        ),
        (
            "education",
            "MSc Computer Science",
            "Example University",
            {"kind": "period", "start": "2017", "end": "2019"},
            [],
        ),
    ):
        entry = career.create_knowledge(
            KnowledgeCreate(
                kind=kind,
                title=title,
                organization=organization,
                dates=dates,
                skills=skills,
                narrative="Platform team for grid measurement data. Six engineers.",
                metadata={
                    "team_size": 6,
                    "employment": "Permanent, full time",
                    "may_name_customers": False,
                    "customers": ["Operator A", "Operator B"],
                    "references": {"manager": {"name": "Sam Example"}, "years": [2022, 2023]},
                }
                if title == "Senior data engineer"
                else {},
            )
        )
        if kind == "experience":
            for text, approved, in_cv, role, group in (
                ("Built Python pipelines that process 40 million measurements a day.", 1, 1, 0, 0),
                ("Moved reporting queries to PostgreSQL and cut their time by 70%.", 1, 1, 1, 1),
                ("Introduced on-call handbooks used by all three platform teams.", 1, 0, 1, 2),
                ("Led the migration of 14 pipelines to a new scheduler.", 0, 0, 2, 2),
            ):
                career.create_claim(
                    ClaimCreate(
                        knowledge_id=entry["id"],
                        text=text,
                        approved=bool(approved),
                        default_in_cv=bool(in_cv),
                        role=("core", "supporting", "bench")[role],
                        group=("Scale", "Impact", "Leadership")[group],
                    )
                )
    career.create_template(
        TemplateCreate(
            name="Synthetic letter",
            kind="cover_letter",
            tex="Synthetic letter TeX",
            guidance="Three short paragraphs.",
            rules={
                "max_pages": 1,
                "engine": "lualatex",
                "date_format": "MMM YYYY",
                "statements": [
                    {"label": "Opening", "statement": "Name the role and one result that fits it."},
                    {"label": "Links", "statement": "No links in the body.", "scope": "body"},
                ],
            },
        )
    )
    example = json.loads((ROOT / "examples/policy.json").read_text())
    for section in SECTIONS:
        for item in example[section]:
            item = dict(item)
            with acting_as(agent if item.pop("proposed", False) else OWNER):
                current = policy.get_policy(section)["version"]
                policy.add_item(section, {"expected_version": current, **item})
    # One value as the 0.19 upgrade copies it from Profile metadata: unconfirmed, structured.
    with app.state.workspace.db.transaction() as conn:
        stamp = now()
        conn.execute(
            "INSERT INTO policy_items(id,section,position,label,value,value_type,origin,origin_key,"
            "created_by_kind,updated_by_kind,created_at,updated_at) "
            "SELECT ?, 'facts', count(*), 'Interview availability', ?, 'structured', "
            "'profile_metadata', 'interview_availability', 'system', 'system', ?, ? "
            "FROM policy_items WHERE section='facts'",
            (
                new_id(),
                json.dumps({"days": ["Tue", "Thu"], "from": "16:00", "timezone": "Europe/Zurich"}),
                stamp,
                stamp,
            ),
        )
        conn.execute("UPDATE policy_sections SET version=version+1 WHERE section='facts'")


def main():
    port = int(os.environ.get("OPENINGS_E2E_PORT") or free_port())
    token = os.environ.get("OPENINGS_E2E_TOKEN", "")
    # The default workspace is small; a performance check sets a large one, for
    # example OPENINGS_E2E_JOBS=5000 OPENINGS_E2E_APPLICATIONS=500.
    jobs = int(os.environ.get("OPENINGS_E2E_JOBS") or 60)
    applications = int(os.environ.get("OPENINGS_E2E_APPLICATIONS") or 53)
    with tempfile.TemporaryDirectory(prefix="openings-dashboard-") as directory:
        path = Path(directory) / "workspace.sqlite"
        app = create_app(path, start_worker=False)
        workspace, career = app.state.workspace, app.state.career
        # One client for setup and seeding: an application starts its MCP sessions once.
        with TestClient(app) as client:
            client.post("/api/v1/auth/setup", json={"password": "synthetic-browser-password"})
            for index in range(35):
                evidence = career.create_knowledge(
                    KnowledgeCreate(
                        kind="project",
                        title=f"Synthetic project {index:02d}",
                        organization="Example Labs",
                        narrative="Built reliable Python services.",
                        skills=["Python"],
                    )
                )
                career.create_claim(
                    ClaimCreate(
                        knowledge_id=evidence["id"],
                        text=f"Synthetic claim {index:02d}",
                        approved=True,
                    )
                )
                career.create_template(
                    TemplateCreate(
                        name=f"Synthetic CV {index:02d}", tex="Synthetic TeX", is_default=index == 0
                    )
                )
            # Before the numbered jobs, so those stay the newest records of every list.
            seed_today(app, client, lambda agent: seed_library(app, agent))
        # A large workspace (the performance budget) is written in one transaction.
        if jobs > LARGE:
            seed_large(workspace, jobs, applications)
        for index in range(0 if jobs > LARGE else jobs):
            job = workspace.ingest_job(
                {
                    "title": f"Synthetic engineer {index:02d}",
                    "company": "Example Labs",
                    "location": "Zurich / Remote",
                    "posting": "Build reliable services.\n\nResponsibilities\nDesign practical APIs and work with a small team.",
                    "url": f"https://example.test/jobs/{index}",
                }
            )
            if index < applications:
                application = workspace.create_application(
                    {
                        "job_id": job["id"],
                        "questions": [
                            {"id": "motivation", "label": "Why this role?", "type": "text"}
                        ],
                    }
                )
                application = workspace.update_application(
                    application["id"],
                    {
                        "expected_version": application["version"],
                        "answers": {"motivation": "Synthetic motivation."},
                    },
                )
                stage = ["draft", "applied", "interview", "offer", "closed"][index % 5]
                if stage != "draft":
                    workspace.update_application(
                        application["id"],
                        {
                            "expected_version": application["version"],
                            "status": stage,
                            **({"outcome": "rejected"} if stage == "closed" else {}),
                        },
                    )
                if index == 0:
                    app.state.documents.prepare_context(
                        ContextCreate(application_id=application["id"])
                    )
            elif index < applications + 3:
                workspace.set_triage(job["id"], "saved", job["version"])
        print(f"Synthetic workspace at http://127.0.0.1:{port}", flush=True)
        uvicorn.run(
            identified(create_app(path, start_worker=False), token),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )


if __name__ == "__main__":
    main()
