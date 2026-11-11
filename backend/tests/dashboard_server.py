"""Synthetic, isolated server for browser workflows; no acquisition workers."""

import tempfile
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate, TemplateCreate
from openings.documents import ContextCreate


def main():
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
        for index in range(60):
            job = workspace.ingest_job(
                {
                    "title": f"Synthetic engineer {index:02d}",
                    "company": "Example Labs",
                    "location": "Zurich / Remote",
                    "posting": "Build reliable services.\n\nResponsibilities\nDesign practical APIs and work with a small team.",
                    "url": f"https://example.test/jobs/{index}",
                }
            )
            if index < 53:
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
            elif index < 56:
                workspace.set_triage(job["id"], "saved", job["version"])
        uvicorn.run(
            create_app(path, start_worker=False), host="127.0.0.1", port=18084, log_level="error"
        )


if __name__ == "__main__":
    main()
