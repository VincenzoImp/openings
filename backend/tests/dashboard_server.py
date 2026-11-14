"""Synthetic, isolated server for browser workflows; no acquisition workers.

Two steps, so that every Playwright worker serves its own copy of one seeded
workspace:

    dashboard_server.py --seed SNAPSHOT
        builds the synthetic workspace into SNAPSHOT, a file in an empty
        directory that also receives the workspace's backups, and prints one
        JSON line with an owner session cookie valid in every copy of it;
    dashboard_server.py --snapshot SNAPSHOT [--port 0]
        serves a private copy of SNAPSHOT's directory and prints
        "Synthetic workspace at http://127.0.0.1:<port>" once it listens.

Without --snapshot the server seeds a temporary workspace first. Only this
server answers `POST /__e2e__/reset`, which restores its copy (the database and
the backup files beside it) to the snapshot between tests; the product
application has no such route.

$OPENINGS_E2E_JOBS and $OPENINGS_E2E_APPLICATIONS set the size of the workspace
(60 jobs and 53 applications by default). Above 500 jobs they are written in
bulk (large_fixtures.py), so 5,000 jobs and 500 applications take seconds.
"""

import argparse
import asyncio
import json
import os
import shutil
import socket
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

from jobs_fixtures import seed_jobs
from large_fixtures import seed_large
from openings import backups
from openings.actors import OWNER, acting_as
from openings.app import create_app
from openings.auth import COOKIE
from openings.career import ClaimCreate, KnowledgeCreate, ProfileUpdate, TemplateCreate
from openings.documents import ContextCreate
from today_fixtures import seed_today

RESET_PATH = "/__e2e__/reset"
PASSWORD = "synthetic-browser-password"
# Above this many jobs the workspace is seeded in bulk (large_fixtures.py).
LARGE = 500
ROOT = Path(__file__).resolve().parents[2]


def copy_side_files(snapshot, live):
    """Make the files beside `live` (backups, pre-upgrade copies) those beside `snapshot`."""
    for item in live.parent.iterdir():
        if not item.name.startswith(live.name):
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    for item in snapshot.parent.iterdir():
        if not item.name.startswith(snapshot.name):
            target = live.parent / item.name
            shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)


def resettable(app, snapshot):
    """Wrap the application so that RESET_PATH restores its workspace to the snapshot.

    The database is restored with SQLite's backup API and the backup files
    beside it are copied again; the in-memory state that depends on them (the
    duplicate index, sign-in limits and used operation grants) is cleared.
    """
    workspace, auth, guard = app.state.workspace, app.state.auth, app.state.login_guard

    def reset():
        with (
            workspace.db.lock,
            workspace.db.connect() as live,
            closing(sqlite3.connect(snapshot)) as origin,
        ):
            origin.backup(live)
            copy_side_files(snapshot, workspace.db.path)
        workspace.reset_duplicates()
        guard.clients.clear()
        guard.succeeded()
        with auth.used_operations.lock:
            auth.used_operations.expiries.clear()

    async def serve(scope, receive, send):
        if scope["type"] != "http" or scope["path"] != RESET_PATH:
            return await app(scope, receive, send)
        status = 405
        if scope["method"] == "POST":
            await asyncio.to_thread(reset)
            status = 204
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return serve


def seed_library(app, agent):
    """A Profile, typed claims, template limits and the example Preferences."""
    career, preferences = app.state.career, app.state.preferences
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
            for text, approved, always in (
                ("Built Python pipelines that process 40 million measurements a day.", 1, 1),
                ("Moved reporting queries to PostgreSQL and cut their time by 70%.", 1, 1),
                ("Introduced on-call handbooks used by all three platform teams.", 1, 0),
                ("Led the migration of 14 pipelines to a new scheduler.", 0, 0),
            ):
                career.create_claim(
                    ClaimCreate(
                        knowledge_id=entry["id"],
                        text=text,
                        approved=bool(approved),
                        always_include=bool(always),
                    )
                )
    career.create_template(
        TemplateCreate(
            name="Synthetic letter",
            kind="letter",
            tex="Synthetic letter TeX",
            guidance="Three short paragraphs.",
            rules={
                "max_pages": 1,
                "engine": "lualatex",
                "date_format": "MMM YYYY",
            },
        )
    )
    example = json.loads((ROOT / "examples/preferences.json").read_text())
    with acting_as(OWNER):
        for section, items in example["sections"].items():
            preferences.update_preferences(section, {"expected_version": 0, "items": items})
        preferences.update_settings({"expected_version": 0, **example["settings"]})
    # One statement an agent added.
    with acting_as(agent):
        current = preferences.get_preferences()["sections"][2]
        preferences.update_preferences(
            "facts",
            {
                "expected_version": current["version"],
                "items": [
                    *current["items"],
                    {"text": "Interviews on Tuesday or Thursday after 16:00."},
                ],
            },
        )


def seed(path, jobs=60, applications=53):
    """Build the synthetic workspace at `path`; return the owner's session cookie.

    The cookie is signed with the workspace's own secret, so it stays valid in
    every copy of the file and after every reset.
    """
    app = create_app(path, start_worker=False)
    workspace, career = app.state.workspace, app.state.career
    # One client for setup and seeding: an application starts its MCP sessions once.
    with TestClient(app) as client:
        client.post("/api/v1/auth/setup", json={"password": PASSWORD})
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
        seed_jobs(app)
        cookie = client.post("/api/v1/auth/login", json={"password": PASSWORD}).cookies[COOKIE]
    # A large workspace (the performance budget) is written in one transaction.
    if jobs > LARGE:
        seed_large(workspace, jobs, applications)
        # Its signals, as a started workspace computes them in the background.
        workspace.signals.backfill()
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
                    "questions": [{"id": "motivation", "label": "Why this role?", "type": "text"}],
                }
            )
            application = workspace.update_application(
                application["id"],
                {
                    "expected_version": application["version"],
                    "answers": {"motivation": "Synthetic motivation."},
                },
            )
            stage = ["shortlisted", "applied", "interview", "offer", "closed"][index % 5]
            if stage != "shortlisted":
                workspace.update_application(
                    application["id"],
                    {
                        "expected_version": application["version"],
                        "status": stage,
                        **({"outcome": "rejected"} if stage == "closed" else {}),
                    },
                )
            if index == 0:
                app.state.documents.prepare_context(ContextCreate(application_id=application["id"]))
        elif index < applications + 3:
            workspace.set_triage(job["id"], "shortlisted", job["version"])
    # One daily backup, and copies kept before earlier upgrades for the
    # browser tests to download and delete.
    daily = backups.run_backup(workspace.db, backups.backup_dir(workspace.db), 3)
    for day in range(1, 9):
        shutil.copyfile(
            backups.backup_dir(workspace.db) / daily["name"],
            path.parent / f"{path.stem}.pre-schema13-202601{day:02d}T080000Z.sqlite",
        )
    # One self-contained file: copies and resets read it without its WAL.
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return f"{COOKIE}={cookie}"


def serve(snapshot, directory, port=0):
    """Serve a private copy of `snapshot` and its side files from `directory` until interrupted."""
    live = Path(directory) / "live" / snapshot.name
    live.parent.mkdir()
    with closing(sqlite3.connect(snapshot)) as origin, closing(sqlite3.connect(live)) as copy:
        origin.backup(copy)
    copy_side_files(snapshot, live)
    app = create_app(live, start_worker=False)
    listener = socket.socket()
    listener.bind(("127.0.0.1", port))
    # Listening before the line below: a connection made right after it waits
    # in the backlog until uvicorn has started, instead of being refused.
    listener.listen(128)
    # The worker that started this process reads the address from this line.
    print(f"Synthetic workspace at http://127.0.0.1:{listener.getsockname()[1]}", flush=True)
    server = uvicorn.Server(uvicorn.Config(resettable(app, snapshot), log_level="error"))
    server.run(sockets=[listener])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=Path, help="build the workspace into this file and exit")
    parser.add_argument("--snapshot", type=Path, help="serve a copy of this seeded workspace")
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENINGS_E2E_PORT") or 0))
    args = parser.parse_args()
    # The default workspace is small; a performance check sets a large one, for
    # example OPENINGS_E2E_JOBS=5000 OPENINGS_E2E_APPLICATIONS=500.
    size = (
        int(os.environ.get("OPENINGS_E2E_JOBS") or 60),
        int(os.environ.get("OPENINGS_E2E_APPLICATIONS") or 53),
    )
    if args.seed:
        print(json.dumps({"session": seed(args.seed.resolve(), *size)}), flush=True)
        return
    with tempfile.TemporaryDirectory(prefix="openings-dashboard-") as directory:
        snapshot = args.snapshot and args.snapshot.resolve()
        if snapshot is None:
            snapshot = Path(directory) / "seed" / "snapshot.sqlite"
            snapshot.parent.mkdir()
            seed(snapshot, *size)
        serve(snapshot, directory, args.port)


if __name__ == "__main__":
    main()
