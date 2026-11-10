"""Stale-context reports and content/source consistency across REST, MCP and review."""

import json

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.career import (
    ClaimCreate,
    ClaimUpdate,
    InstructionsUpdate,
    KnowledgeCreate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.consistency import compare, tokens
from openings.documents import ContextCreate, DocumentCreate, ReviewUpdate, UploadReservation
from openings.errors import DomainError

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


def content(**changes):
    value = {
        "kind": "resume",
        "name": "Alex Example",
        "website": "https://example.test",
        "experience": [
            {
                "title": "Backend Engineer",
                "organization": "Example Cloud",
                "dates": "2021 – present",
                "bullets": [
                    {"text": "Reduced API p95 latency by 20% through tracing.", "claim_ids": []},
                    "Built Python services for Café Example.",
                ],
            }
        ],
        "skills": ["Python", "SQL"],
    }
    value.update(changes)
    return value


def test_comparison_ignores_markup_spacing_and_reports_changed_words():
    assert compare(content(), [("cv.tex", SOURCE)])["status"] == "consistent"
    changed = content(skills=["Python", "Rust"])
    report = compare(changed, [("cv.tex", SOURCE)])
    assert report["status"] == "mismatch"
    assert report["mismatches"] == [{"path": "skills[1]", "text": "Rust"}]
    commented = content(
        experience=[{"bullets": ["Reduced API p95 latency by 20% through tracing measured"]}]
    )
    assert compare(commented, [("cv.tex", SOURCE)])["status"] == "mismatch"
    assert compare(content(), [])["status"] == "not_checked"
    assert compare({"claim_ids": ["a"]}, [("cv.tex", SOURCE)])["status"] == "not_checked"
    assert tokens(r"Stra\ss e \v{S}koda na\"{\i}ve") == ["strasse", "skoda", "naive"]


def upload(documents, client, document_id, name, data, media="application/octet-stream"):
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document", owner_id=document_id, name=name, size=len(data), media_type=media
        )
    )
    response = client.put(grant["url"], headers=grant["headers"], content=data)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_review_refuses_source_mismatch_unless_explicitly_allowed(tmp_path):
    app = create_app(tmp_path / "consistency.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    stale_text = documents.create_document(
        DocumentCreate(
            application_id=application["id"], kind="resume", content=content(skills=["Rust"])
        )
    )
    with TestClient(app) as client:
        session = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        upload(documents, client, stale_text["id"], "cv.tex", SOURCE.encode())
        version = documents.get_document(stale_text["id"])["version"]

        report = client.get(f"/api/v1/documents/{stale_text['id']}/consistency").json()
        assert report["status"] == "mismatch" and report["sources"][0]["name"] == "cv.tex"
        mcp = await app.state.mcp.call_tool(
            "documents_consistency", {"document_id": stale_text["id"]}
        )
        assert json.loads(mcp[0].text) == report

        refused = client.post(
            f"/api/v1/documents/{stale_text['id']}/review",
            json={"review_state": "approved", "expected_version": version},
        )
        assert refused.status_code == 409
        error = refused.json()["error"]
        assert error["code"] == "content_mismatch"
        assert error["details"]["mismatches"] == [{"path": "skills[0]", "text": "Rust"}]
        assert documents.get_document(stale_text["id"])["review_state"] == "draft"

        allowed = client.post(
            f"/api/v1/documents/{stale_text['id']}/review",
            json={"expected_version": version, "allow_content_mismatch": True},
        )
        assert allowed.status_code == 200 and allowed.json()["review_state"] == "approved"

        matching = documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                kind="resume",
                previous_id=stale_text["id"],
                content=content(),
            )
        )
        upload(documents, client, matching["id"], "cv.tex", SOURCE.encode())
        upload(
            documents, client, matching["id"], "cv.pdf", b"%PDF-1.4\nsynthetic", "application/pdf"
        )
        matching = documents.get_document(matching["id"])
        approved = documents.review_document(
            matching["id"], ReviewUpdate(expected_version=matching["version"])
        )
        assert approved["review_state"] == "approved"
        assert (
            client.get(f"/api/v1/documents/{matching['id']}/consistency").json()["status"]
            == "consistent"
        )

        without_source = documents.create_document(
            DocumentCreate(
                application_id=application["id"], kind="cover_letter", content={"body": "x"}
            )
        )
        assert documents.check_consistency(without_source["id"])["status"] == "not_checked"
        documents.review_document(without_source["id"], ReviewUpdate(expected_version=1))


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
                content=content(),
            )
        )
    signature = contexts[0]["signature"]

    assert documents.list_staleness() == {"items": [], "total": 0}
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
    career.update_instructions(
        InstructionsUpdate(
            expected_version=career.get_instructions()["version"], general="Be concise."
        )
    )
    career.update_claim(claim["id"], ClaimUpdate(expected_version=claim["version"], approved=False))

    report = documents.application_staleness(applications[0]["id"])
    assert report["stale"] is True
    assert report["inputs"] == ["profile", "instructions", "template", "claim"]
    changes = {(item["input"], item["state"]) for item in report["changes"]}
    assert changes == {
        ("profile", "changed"),
        ("instructions", "changed"),
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
            content=content(),
        )
    )
    assert documents.application_staleness(applications[0]["id"])["stale"] is False
    result = await app.state.mcp.call_tool("applications_staleness", {})
    listed = json.loads(result[0].text)
    assert [item["application_id"] for item in listed["items"]] == [applications[1]["id"]]
    single = await app.state.mcp.call_tool(
        "application_staleness", {"application_id": applications[1]["id"]}
    )
    assert json.loads(single[0].text)["inputs"] == report["inputs"]

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


def test_review_conflict_reports_version_before_content(tmp_path):
    app = create_app(tmp_path / "version.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    document = documents.create_document(
        DocumentCreate(application_id=application["id"], content={"text": "Synthetic."})
    )
    with pytest.raises(DomainError) as error:
        documents.review_document(document["id"], ReviewUpdate(expected_version=2))
    assert error.value.code == "conflict"


def test_context_input_summaries_are_stored_and_rebuilt(tmp_path):
    import sqlite3

    from openings.db import Database

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
            content=content(),
        )
    )
    with sqlite3.connect(path) as conn:
        stored = conn.execute(
            "SELECT profile_version,templates,knowledge FROM context_inputs WHERE context_id=?",
            (context["id"],),
        ).fetchone()
        assert stored is not None and template["id"] in stored[1] and entry["id"] in stored[2]
        # A restored or older workspace may lack summaries: reads and startup derive them.
        conn.execute("DELETE FROM context_inputs")
    assert documents.list_staleness(stale_only=False)["total"] == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM context_inputs").fetchone()[0] == 1
        conn.execute("DROP TABLE context_inputs")
    Database(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM context_inputs").fetchone()[0] == 1
