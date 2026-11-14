"""Small invariant checks for career data and external document storage."""

import hashlib
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from openings.career import (
    EntryCreate,
    EntryUpdate,
    HighlightCreate,
    HighlightUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from openings.documents import (
    DocumentCreate,
    UploadReservation,
)
from openings.errors import DomainError
from timeline_fixtures import guided_application


@pytest.fixture
def seeded(app, client):
    workspace, career, documents = app.state.workspace, app.state.career, app.state.documents
    profile = career.get_profile()
    career.update_profile(
        ProfileUpdate(
            expected_version=profile["version"],
            name="Alex Example",
            headline="Backend engineer",
            summary="Built Python APIs.",
        )
    )
    evidence = career.create_entry(
        EntryCreate(
            kind="project",
            title="Example API",
            narrative="Built Python APIs and reduced latency by 20%.",
        )
    )
    claim = career.create_highlight(
        HighlightCreate(career_id=evidence["id"], text="Reduced latency by 20%.", approved=True)
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
    application = guided_application(workspace, job["id"], "Prefer practical examples.")
    return workspace, career, documents, client, evidence, claim, template, application


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


def test_document_revisions_validate_evidence_and_never_inherit_old_pdf(seeded):
    _, _, documents, client, evidence, claim, _, application = seeded
    first = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            highlight_ids=[claim["id"], claim["id"]],
            career_ids=[evidence["id"]],
            note="Leads with the latency work.",
            pdf={"name": "cv.pdf", "size": 1},
        )
    )
    assert (first["highlight_ids"], first["career_ids"]) == ([claim["id"]], [evidence["id"]])
    assert "content" not in first and first["text"] is None
    source = b"\\begin{document}\nReduced latency by 20\\%.\n\\end{document}\n"
    upload(documents, client, "document", first["id"], "cv.tex", source, "application/x-tex")
    assert documents.get_document(first["id"])["text"] == "Reduced latency by 20%."
    data = b"%PDF-1.4\nSynthetic storage fixture"
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=first["id"],
            name="cv.pdf",
            media_type="application/pdf",
            size=len(data),
            source_sha256=hashlib.sha256(source).hexdigest(),
        )
    )
    response = client.put(grant["url"], headers=grant["headers"], content=data)
    assert response.status_code == 200, response.text
    pdf = response.json()
    assert pdf["source_sha256"] == hashlib.sha256(source).hexdigest()
    # A complete revision is immutable.
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
            pdf={"name": "cv.pdf", "size": 1},
        )
    )
    assert second["revision_number"] == 2
    assert second["files"] == [] and "context_id" not in second
    assert client.get(pdf["url"]).content == data
    for invented, code in (
        ({"highlight_ids": ["unknown"]}, "unapproved_highlight"),
        ({"career_ids": ["unknown"]}, "unknown_evidence"),
        ({"content": {"text": "Free-form wording."}}, "content_not_accepted"),
    ):
        with pytest.raises(DomainError) as error:
            documents.create_document(
                DocumentCreate(
                    application_id=application["id"], **invented, pdf={"name": "cv.pdf", "size": 1}
                )
            )
        assert error.value.code == code


def test_transfer_scope_integrity_and_forget_prevent_late_resurrection(seeded):
    ws, _, documents, client, evidence, _, _, application = seeded
    # An upload without a declared hash (a LAN page without client crypto) is hashed exactly.
    asset, _ = upload(
        documents, client, "career", evidence["id"], "notes.txt", b"notes", declared_sha=False
    )
    assert asset["sha256"] == hashlib.sha256(b"notes").hexdigest()
    assert client.get(asset["url"]).content == b"notes"

    document = documents.create_document(
        DocumentCreate(application_id=application["id"], pdf={"name": "cv.pdf", "size": 1})
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
        UploadReservation(owner_type="document", owner_id=document["id"], name="late.txt", size=4)
    )
    ws.forget_job(application["job_id"], ws.get_job(application["job_id"])["version"])
    assert client.put(late["url"], headers=late["headers"], content=b"late").status_code == 401
    assert client.get(download["url"], headers=download["headers"]).status_code == 401
    assert ws.db.one("SELECT count(*) AS n FROM documents")["n"] == 0
    # Only the career file is left.
    assert ws.db.one("SELECT count(*) AS n FROM blobs")["n"] == 1


def test_filtered_summary_pages_keep_large_content_in_detail_and_batch_revision_reads(seeded):
    _, career, documents, client, evidence, claim, template, application = seeded
    evidence = career.update_entry(
        evidence["id"],
        EntryUpdate(
            expected_version=evidence["version"],
            narrative="evidence " * 10000,
            metadata={"long": "metadata " * 1000},
        ),
    )
    first = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            title="Candidate CV",
            pdf={"name": "cv.pdf", "size": 1},
        )
    )
    source = b"document " * 10000
    asset, _ = upload(documents, client, "document", first["id"], "candidate.tex", source)
    pdf = b"%PDF-1.4\nSynthetic candidate"
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=first["id"],
            name="candidate.pdf",
            media_type="application/pdf",
            size=len(pdf),
            source_sha256=asset["sha256"],
        )
    )
    assert client.put(grant["url"], headers=grant["headers"], content=pdf).status_code == 200
    previous = first
    for number in range(25):
        previous = documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                previous_id=previous["id"],
                title=f"Candidate CV {number}",
                pdf={"name": "cv.pdf", "size": 1},
            )
        )
    with (
        patch.object(documents.db, "all", wraps=documents.db.all) as reads,
        patch.object(documents.db, "one", wraps=documents.db.one) as singles,
    ):
        result = client.get(
            "/api/v1/documents",
            params={
                "summary": "true",
                "application_id": application["id"],
                "q": "Candidate",
                "limit": 30,
            },
        ).json()
    assert result["total"] == 26
    # The other single read is the session check of the request.
    assert reads.call_count == 3 and singles.call_count == 2
    assert {row["revision_number"] for row in result["items"]} == set(range(1, 27))
    assert sum(row["file_count"] for row in result["items"]) == 2
    assert all(not {"content", "files", "text"} & row.keys() for row in result["items"])
    # The text derived from the source is searched too.
    found = client.get("/api/v1/documents", params={"q": "document document"}).json()
    assert [row["id"] for row in found["items"]] == [first["id"]]
    assert client.get("/api/v1/documents", params={"review_state": "approved"}).status_code == 422
    detail = client.get(f"/api/v1/documents/{first['id']}").json()
    assert detail["text"] == " ".join(["document"] * 10000) and "content" not in detail
    compact = client.get(
        "/api/v1/career/entries", params={"summary": "true", "q": "evidence", "limit": 1}
    ).json()
    assert compact["total"] == 1
    assert len(compact["items"][0]["narrative_preview"]) == 240
    assert compact["items"][0]["highlight_count"] == 1
    assert "metadata" not in compact["items"][0] and "narrative" not in compact["items"][0]
    # Lists return summaries by default; summary=false gives the full records.
    assert "narrative" not in career.list_entries()["items"][0]
    assert career.list_entries(summary=False)["items"][0]["narrative"] == evidence["narrative"]
    full = client.get("/api/v1/career/entries", params={"summary": "false"}).json()
    assert full["items"][0]["narrative"] == evidence["narrative"]
    assert (full["limit"], full["offset"]) == (100, 0)
    claim_summary = client.get(
        "/api/v1/career/highlights",
        params={"summary": "true", "q": "Example API", "approved": "true"},
    ).json()
    assert claim_summary["items"][0]["id"] == claim["id"]
    assert "text" not in claim_summary["items"][0] and "metadata" not in claim_summary["items"][0]
    template_summary = career.list_templates(q="Example", summary=True)["items"][0]
    assert template_summary["id"] == template["id"]
    assert not {"tex", "rules", "guidance"} & template_summary.keys()
    assert (
        documents.list_files(
            owner_type="document", application_id=application["id"], q="candidate", summary=True
        )["items"][0]["id"]
        == asset["id"]
    )
    assert documents.list_documents(summary=True, limit=1, offset=25)["total"] == 26
    assert (
        client.get("/api/v1/documents", params={"summary": "true", "limit": 201}).status_code == 422
    )


def test_career_patch_omissions_clear_values_and_finite_metadata_are_explicit(seeded):
    _, career, _, _, evidence, claim, template, _ = seeded
    profile = career.get_profile()
    with pytest.raises(DomainError) as stale:
        career.update_profile(ProfileUpdate(expected_version=profile["version"] - 1, summary="Old"))
    assert stale.value.status == 409
    for model, fields in [
        (ProfileUpdate, {"name": None}),
        (EntryUpdate, {"metadata": None}),
        (HighlightUpdate, {"approved": None}),
        (TemplateUpdate, {"rules": None}),
    ]:
        with pytest.raises(ValidationError):
            model(expected_version=1, **fields)
        with pytest.raises(ValidationError):
            model(expected_version=True)
    with pytest.raises(ValidationError):
        EntryUpdate(expected_version=1, metadata={"metric": float("inf")})
    changed = career.update_entry(
        evidence["id"],
        EntryUpdate(
            expected_version=evidence["version"],
            narrative="",
            metadata={},
        ),
    )
    assert changed["narrative"] == "" and changed["metadata"] == {}
    assert career.get_highlight(claim["id"])["approved"] is True
    assert career.get_template(template["id"])["rules"] == {"max_bullet_chars": 100}
