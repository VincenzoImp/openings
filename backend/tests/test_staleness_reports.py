"""Stale-context reports across REST, MCP and the application reads."""

import json

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.career import (
    ClaimCreate,
    ClaimUpdate,
    KnowledgeCreate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.documents import ContextCreate, DocumentCreate
from openings.preferences import PreferencesService

SOURCE = r"""\documentclass{article}
\usepackage{hyperref}
\newcommand{\role}[2]{\textbf{#1} \hfill #2}
\begin{document}
{\LARGE Alex Example}\\[3pt]
\href{https://example.test}{example.test}
\section*{Experience}
\role{Backend Engineer --- Example Cloud}{2021--present}
\begin{itemize}[leftmargin=*]
  \item Reduced API p95 latency by 20\% through tracing. % measured on staging
  \item Built \textcolor{blue}{Python} services for Caf\'e~Example.
\end{itemize}
\vspace{4pt}{\small Skills: Python, SQL.}
\end{document}
"""


@pytest.mark.asyncio
async def test_staleness_reports_changed_inputs_without_rewriting_contexts(tmp_path):
    app = create_app(tmp_path / "staleness.sqlite", start_worker=False)
    workspace, career, documents = app.state.workspace, app.state.career, app.state.documents
    template = career.create_template(
        TemplateCreate(name="MASTER CV", kind="resume", tex=SOURCE, is_default=True)
    )
    entry = career.create_knowledge(KnowledgeCreate(title="Backend Engineer"))
    other = career.create_knowledge(KnowledgeCreate(title="Unselected entry"))
    claim = career.create_claim(
        ClaimCreate(knowledge_id=entry["id"], text="Reduced latency by 20%.", approved=True)
    )
    jobs = [
        workspace.ingest_job({"title": f"Synthetic role {index}", "posting": "Build services."})
        for index in range(2)
    ]
    applications = [workspace.create_application({"job_id": job["id"]}) for job in jobs]
    contexts = []
    for application in applications:
        context = documents.prepare_context(
            ContextCreate(
                application_id=application["id"],
                template_ids=[template["id"]],
                knowledge_ids=[entry["id"]],
            )
        )
        contexts.append(context)
        documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                context_id=context["id"],
                kind="resume",
            )
        )
    signature = contexts[0]["signature"]

    assert documents.list_staleness() == {"items": [], "total": 0, "limit": 50, "offset": 0}
    assert documents.list_staleness(stale_only=False)["total"] == 2
    assert workspace.get_application(applications[0]["id"])["stale_inputs"] == []

    career.update_knowledge(other["id"], _knowledge_patch(other))
    assert documents.list_staleness()["total"] == 0  # unselected entries do not matter

    template = career.update_template(
        template["id"], TemplateUpdate(expected_version=template["version"], guidance="New rule.")
    )
    profile = career.get_profile()
    career.update_profile(
        ProfileUpdate(expected_version=profile["version"], headline="Platform engineer")
    )
    PreferencesService(workspace).update_preferences(
        "writing", {"expected_version": 0, "items": [{"text": "Be concise."}]}
    )
    career.update_claim(claim["id"], ClaimUpdate(expected_version=claim["version"], approved=False))

    report = documents.application_staleness(applications[0]["id"])
    assert report["stale"] is True
    assert report["inputs"] == ["profile", "preferences", "template", "claim"]
    changes = {(item["input"], item["state"]) for item in report["changes"]}
    assert changes == {
        ("profile", "changed"),
        ("preferences", "added"),
        ("preferences", "removed"),
        ("template", "changed"),
        ("claim", "unapproved"),
    }
    template_change = next(item for item in report["changes"] if item["input"] == "template")
    assert template_change["label"] == "MASTER CV"
    assert template_change["frozen_version"] == 1
    assert template_change["current_version"] == template["version"]
    assert report["documents"][0]["status"] == "stale"
    assert documents.get_context(contexts[0]["id"])["signature"] == signature

    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        listed = client.get("/api/v1/staleness").json()
        assert listed["total"] == 2
        assert {item["application_id"] for item in listed["items"]} == {
            item["id"] for item in applications
        }
        assert client.get("/api/v1/staleness?status=applied").json()["total"] == 0
        assert client.get("/api/v1/staleness?status=all").json()["total"] == 2
        assert client.get("/api/v1/staleness?status=unknown").status_code == 422
        assert client.get(f"/api/v1/applications/{applications[0]['id']}/staleness").json() == (
            documents.application_staleness(applications[0]["id"])
        )
        summary = client.get("/api/v1/applications").json()["items"]
        assert all(item["stale_inputs"] == report["inputs"] for item in summary)
        assert client.get("/api/v1/applications/unknown/staleness").status_code == 404

    # Refreshing means a new context and a new revision; the old leaf stops counting.
    refreshed = documents.prepare_context(
        ContextCreate(
            application_id=applications[0]["id"],
            template_ids=[template["id"]],
            knowledge_ids=[entry["id"]],
        )
    )
    leaf = documents.application_staleness(applications[0]["id"])["documents"][0]
    documents.create_document(
        DocumentCreate(
            application_id=applications[0]["id"],
            context_id=refreshed["id"],
            previous_id=leaf["document_id"],
            kind="resume",
        )
    )
    assert documents.application_staleness(applications[0]["id"])["stale"] is False
    result = await app.state.mcp.call_tool("staleness_list", {})
    listed = json.loads(result.content[0].text)
    assert [item["application_id"] for item in listed["items"]] == [applications[1]["id"]]
    single = await app.state.mcp.call_tool(
        "staleness_get", {"application_id": applications[1]["id"]}
    )
    assert json.loads(single.content[0].text)["inputs"] == report["inputs"]

    entry = career.get_knowledge(entry["id"])
    career.delete_knowledge(entry["id"], entry["version"])
    states = {
        (item["input"], item["state"])
        for item in documents.application_staleness(applications[1]["id"])["changes"]
    }
    assert {("knowledge", "deleted"), ("claim", "deleted")} <= states


def _knowledge_patch(entry):
    from openings.career import KnowledgeUpdate

    return KnowledgeUpdate(expected_version=entry["version"], narrative="Changed.")


def test_context_input_summaries_are_stored_and_rebuilt(tmp_path):
    import sqlite3

    path = tmp_path / "summaries.sqlite"
    app = create_app(path, start_worker=False)
    workspace, career, documents = app.state.workspace, app.state.career, app.state.documents
    template = career.create_template(
        TemplateCreate(name="MASTER CV", kind="resume", tex=SOURCE, is_default=True)
    )
    entry = career.create_knowledge(KnowledgeCreate(title="Backend Engineer"))
    job = workspace.ingest_job({"title": "Synthetic role", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    context = documents.prepare_context(
        ContextCreate(
            application_id=application["id"],
            template_ids=[template["id"]],
            knowledge_ids=[entry["id"]],
        )
    )
    documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            context_id=context["id"],
            kind="resume",
        )
    )
    with sqlite3.connect(path) as conn:
        stored = conn.execute(
            "SELECT profile_version,templates,knowledge FROM context_inputs WHERE context_id=?",
            (context["id"],),
        ).fetchone()
        assert stored is not None and template["id"] in stored[1] and entry["id"] in stored[2]
        # A restored workspace may lack summaries: reads derive them.
        conn.execute("DELETE FROM context_inputs")
    assert documents.list_staleness(stale_only=False)["total"] == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM context_inputs").fetchone()[0] == 1
