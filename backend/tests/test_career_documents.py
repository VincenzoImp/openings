"""Small invariant checks for career data and external document storage."""

import hashlib
import json
import sqlite3

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from openings.career import (
    CareerService,
    ClaimCreate,
    InstructionsUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.documents import (
    ContextCreate,
    DocumentCreate,
    DocumentService,
    ReviewUpdate,
    UploadReservation,
    register_api,
)
from openings.errors import DomainError
from openings.workspace import Workspace


@pytest.fixture
def workspace(tmp_path):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    career = CareerService(workspace)
    documents = DocumentService(workspace, max_file_bytes=1024 * 1024)
    profile = career.get_profile()
    career.update_profile(
        ProfileUpdate(
            expected_version=profile["version"],
            name="Alex Example",
            roles="Backend engineer",
            summary="Built Python APIs.",
        )
    )
    evidence = career.create_knowledge(
        KnowledgeCreate(
            kind="project",
            title="Example API",
            narrative="Built Python APIs and reduced latency by 20%.",
        )
    )
    claim = career.create_claim(
        ClaimCreate(knowledge_id=evidence["id"], text="Reduced latency by 20%.", approved=True)
    )
    template = career.create_template(
        TemplateCreate(
            name="Example CV",
            tex="Synthetic user TeX",
            guidance="Use concise wording.",
            rules={"max_bullet_chars": 100},
        )
    )
    job = workspace.ingest_job(
        {"title": "Backend Engineer", "company": "Example Co", "posting": "Build Python APIs."}
    )
    application = workspace.create_application(
        {"job_id": job["id"], "note": "Prefer practical examples."}
    )
    api = FastAPI()

    @api.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse({"error": {"code": error.code, "message": error.message}}, error.status)

    router = APIRouter(prefix="/api/v1")
    register_api(router, documents)
    api.include_router(router)
    with TestClient(api) as client:
        yield workspace, career, documents, client, evidence, claim, template, application


def upload(
    documents,
    client,
    owner_type,
    owner_id,
    name,
    data,
    media="application/octet-stream",
    declared_sha=True,
):
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type=owner_type,
            owner_id=owner_id,
            name=name,
            size=len(data),
            media_type=media,
            sha256=hashlib.sha256(data).hexdigest() if declared_sha else None,
        )
    )
    response = client.put(grant["url"], headers=grant["headers"], content=data)
    assert response.status_code == 200, response.text
    return response.json(), grant


def test_relevant_profile_edits_are_distinct_from_contacts_and_templates(workspace):
    ws, career, _, _, evidence, _, template, _ = workspace
    score_revision = ws.scoring_profile_version()
    profile = career.get_profile()
    changed = career.update_profile(
        ProfileUpdate(expected_version=profile["version"], email="alex@example.test")
    )
    assert ws.scoring_profile_version() == score_revision
    career.update_profile(
        ProfileUpdate(
            expected_version=changed["version"],
            scoring_summary="Python API engineer; remote roles.",
        )
    )
    assert ws.scoring_profile_version() == score_revision + 1
    career.update_template(
        template["id"],
        TemplateUpdate(expected_version=template["version"], guidance="Prefer short bullets."),
    )
    assert ws.scoring_profile_version() == score_revision + 1
    with pytest.raises(DomainError) as stale:
        career.update_profile(
            ProfileUpdate(expected_version=profile["version"], summary="Stale overwrite")
        )
    assert stale.value.status == 409
    assert career.get_knowledge(evidence["id"])["narrative"].startswith("Built Python")


def test_context_freezes_stored_instructions_evidence_and_file_bytes(workspace):
    ws, career, documents, client, evidence, _, template, application = workspace
    asset, _ = upload(
        documents, client, "template", template["id"], "assets/logo.txt", b"synthetic logo"
    )
    instruction = career.get_instructions()
    career.update_instructions(
        InstructionsUpdate(
            expected_version=instruction["version"], general="Use supplied facts only."
        )
    )
    request = ContextCreate(
        application_id=application["id"],
        idempotency_key="prepare-once",
        note="Keep the technical details.",
    )
    frozen = documents.prepare_context(request)
    assert frozen["payload"]["instructions"]["general"] == "Use supplied facts only."
    assert (
        frozen["payload"]["instructions"]["template_append"][template["id"]]
        == "Use concise wording."
    )
    assert frozen["payload"]["knowledge"][0]["narrative"] == evidence["narrative"]
    assert (
        hashlib.sha256(
            json.dumps(
                frozen["payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        == frozen["signature"]
    )
    career.update_knowledge(
        evidence["id"],
        KnowledgeUpdate(
            expected_version=evidence["version"], narrative="Edited after preparation."
        ),
    )
    documents.delete_file(asset["id"])
    assert documents.prepare_context(request)["id"] == frozen["id"]
    old = documents.get_context(frozen["id"])
    file_id = old["payload"]["files"][0]["id"]
    assert client.get(f"/api/v1/files/{file_id}/content").content == b"synthetic logo"
    assert old["payload"]["knowledge"][0]["narrative"] == evidence["narrative"]
    with pytest.raises(DomainError):
        documents.prepare_context(
            ContextCreate(
                application_id=application["id"],
                idempotency_key="prepare-once",
                note="Different command",
            )
        )
    assert ws.get_application(application["id"])["status"] == "draft"


def test_document_revisions_validate_evidence_and_never_inherit_old_pdf(workspace, tmp_path):
    ws, _, documents, client, evidence, claim, _, application = workspace
    context = documents.prepare_context(ContextCreate(application_id=application["id"]))
    content = {
        "bullets": [
            {
                "text": "Reduced latency by 20%.",
                "evidence_ids": [evidence["id"]],
                "claim_ids": [claim["id"]],
            }
        ]
    }
    first = documents.create_document(
        DocumentCreate(application_id=application["id"], context_id=context["id"], content=content)
    )
    data = b"%PDF-1.4\nSynthetic storage fixture"
    pdf, _ = upload(documents, client, "document", first["id"], "cv.pdf", data, "application/pdf")
    documents.review_document(first["id"], ReviewUpdate())
    with pytest.raises(DomainError):
        documents.reserve_upload(
            UploadReservation(
                owner_type="document",
                owner_id=first["id"],
                name="replacement.pdf",
                media_type="application/pdf",
                size=20,
            )
        )
    second = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            previous_id=first["id"],
            content={"text": "Revised wording."},
        )
    )
    assert second["revision_number"] == 2
    assert second["files"] == []
    assert client.get(pdf["url"]).content == data
    with pytest.raises(DomainError):
        documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                context_id=context["id"],
                content={"bullets": [{"text": "Invented", "evidence_ids": ["unknown"]}]},
            )
        )
    ws.db.backup(tmp_path / "portable.sqlite")
    with sqlite3.connect(tmp_path / "portable.sqlite") as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            restored.execute(
                "SELECT content FROM blobs WHERE sha256=?", (pdf["sha256"],)
            ).fetchone()[0]
            == data
        )


def test_transfer_scope_integrity_and_forget_prevent_late_resurrection(workspace):
    ws, _, documents, client, _, _, _, application = workspace
    document = documents.create_document(
        DocumentCreate(application_id=application["id"], content={"text": "Draft"})
    )
    data = b"filled source"
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=document["id"],
            name="cv.tex",
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
    )
    assert client.get(grant["url"], headers=grant["headers"]).status_code == 403
    assert (
        client.put(grant["url"], headers=grant["headers"], content=b"wrong size").status_code == 422
    )
    response = client.put(grant["url"], headers=grant["headers"], content=data)
    assert response.status_code == 200
    assert (
        client.put(grant["url"], headers=grant["headers"], content=data).json()["id"]
        == response.json()["id"]
    )
    download = documents.reserve_download(response.json()["id"])
    assert client.get(download["url"], headers=download["headers"]).content == data
    late = documents.reserve_upload(
        UploadReservation(owner_type="document", owner_id=document["id"], name="late.tex", size=4)
    )
    ws.forget_job(application["job_id"])
    assert client.put(late["url"], headers=late["headers"], content=b"late").status_code == 401
    assert client.get(download["url"], headers=download["headers"]).status_code == 401
    assert ws.db.one("SELECT count(*) AS n FROM documents")["n"] == 0
    assert ws.db.one("SELECT count(*) AS n FROM blobs")["n"] == 0


def test_lan_upload_without_client_crypto_still_hashes_exact_bytes(workspace):
    _, _, documents, client, evidence, _, _, _ = workspace
    asset, _ = upload(
        documents,
        client,
        "knowledge",
        evidence["id"],
        "notes.txt",
        b"public synthetic notes",
        declared_sha=False,
    )
    assert asset["sha256"] == hashlib.sha256(b"public synthetic notes").hexdigest()
    assert client.get(asset["url"]).content == b"public synthetic notes"
