"""Synthetic, isolated server for browser workflows; no acquisition workers.

Listens on 127.0.0.1:$OPENINGS_E2E_PORT (a free port when unset) and answers
`/__e2e__/run` with $OPENINGS_E2E_TOKEN, so a Playwright run can verify that it
reached the server it started. The route exists only in this test server.

$OPENINGS_E2E_JOBS and $OPENINGS_E2E_APPLICATIONS set the size of the workspace
(60 jobs and 53 applications by default).
"""

import os
import socket
import tempfile
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate, TemplateCreate
from openings.documents import ContextCreate

RUN_PATH = "/__e2e__/run"


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
                    knowledge_id=evidence["id"], text=f"Synthetic claim {index:02d}", approved=True
                )
            )
            career.create_template(
                TemplateCreate(
                    name=f"Synthetic CV {index:02d}", tex="Synthetic TeX", is_default=index == 0
                )
            )
        for index in range(jobs):
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
