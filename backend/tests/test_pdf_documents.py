"""PDF-only CV and letter revisions: grants from the create, completeness and PDF text."""

import hashlib

import httpx
import pytest

from document_fixtures import PDF, SOURCE, TEXT, pdf_revision, tex, text_pdf
from openings.documents import DocumentCreate


def sha(data):
    return hashlib.sha256(data).hexdigest()


def code(response):
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture
def setup(app, client):
    workspace = app.state.workspace
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    return client, workspace, app.state.documents, application


def put(client, grant, data):
    return client.put(grant["url"], headers=grant["headers"], content=data)


def test_a_pdf_only_revision_is_complete_with_text_read_from_the_pdf(setup):
    client, workspace, documents, application = setup
    data = text_pdf("Alex Example", "Backend Engineer")
    created = client.post(
        "/api/v1/documents",
        json={
            "application_id": application["id"],
            "kind": "letter",
            "pdf": {"name": "letter.pdf", "size": len(data), "sha256": sha(data)},
        },
    )
    assert created.status_code == 201, created.text
    letter = created.json()
    assert letter["complete"] is False and letter["uploads"]["source"] is None
    assert workspace.get_application(application["id"])["missing"] == ["cv", "letter"]
    grant = letter["uploads"]["pdf"]
    # The grant is bound to the declared bytes.
    assert put(client, grant, b"%PDF-" + b"x" * (len(data) - 5)).status_code == 422
    stored = put(client, grant, data)
    assert stored.status_code == 200 and stored.json()["source_sha256"] is None
    read = client.get(f"/api/v1/documents/{letter['id']}").json()
    assert read["complete"] is True and read["source_sha256"] is None
    assert (read["text"], read["text_from"]) == ("Alex Example\nBackend Engineer", "pdf")
    assert workspace.get_application(application["id"])["missing"] == ["cv"]
    # A PDF without readable text is still complete; it simply has no text.
    blank = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="cv",
            pdf={"name": "cv.pdf", "size": len(PDF)},
        )
    )
    assert put(client, blank["uploads"]["pdf"], PDF).status_code == 200
    read = documents.get_document(blank["id"])
    assert read["complete"] is True and (read["text"], read["text_from"]) == (None, None)
    assert workspace.get_application(application["id"])["ready"] is True


def test_grants_are_absolute_on_the_public_origin_behind_a_reverse_proxy(setup, monkeypatch):
    client, _, _, application = setup
    data = text_pdf("Alex Example")

    def create():
        return client.post(
            "/api/v1/documents",
            json={
                "application_id": application["id"],
                "kind": "cv",
                "pdf": {"name": "cv.pdf", "size": len(data)},
            },
        ).json()["uploads"]["pdf"]

    # Without a public URL the grant names the origin the request reached.
    direct = create()
    assert direct["url"] == client.base_url.join("/api/v1/transfers")
    # Behind a reverse proxy the request reaches an internal address; the grant names
    # the public origin, so an agent uploads with the returned url alone.
    public = "https://jobs.example.test"
    monkeypatch.setenv("OPENINGS_PUBLIC_URL", public + "/")
    grant = create()
    assert grant["url"] == public + "/api/v1/transfers"
    assert grant["curl"].endswith(f"'{public}/api/v1/transfers'")
    exported = client.post("/api/v1/export/grant").json()
    assert exported["url"] == public + "/api/v1/export"
    # The proxy forwards the public path unchanged to the internal address.
    proxied = client.base_url.join(httpx.URL(grant["url"]).path)
    assert client.put(proxied, headers=grant["headers"], content=data).status_code == 200


def test_an_inline_source_binds_the_pdf_grant_to_its_hash(setup):
    client, _, documents, application = setup
    created = client.post(
        "/api/v1/documents",
        json={
            "application_id": application["id"],
            "kind": "cv",
            "source": SOURCE,
            "pdf": {"name": "cv.pdf", "size": len(PDF)},
        },
    ).json()
    assert (created["text"], created["text_from"]) == (TEXT, "tex")
    assert created["source_sha256"] == sha(SOURCE.encode()) and not created["complete"]
    pdf = put(client, created["uploads"]["pdf"], PDF).json()
    assert pdf["source_sha256"] == sha(SOURCE.encode())
    read = documents.get_document(created["id"])
    # The text from the source is kept; the PDF's never replaces it.
    assert read["complete"] and (read["text"], read["text_from"]) == (TEXT, "tex")

    # A source file is uploaded first with its own grant.
    data = tex("Second letter.")
    second = client.post(
        "/api/v1/documents",
        json={
            "application_id": application["id"],
            "kind": "letter",
            "source_file": {"name": "letter.tex", "size": len(data), "sha256": sha(data)},
            "pdf": {"name": "letter.pdf", "size": len(PDF)},
        },
    ).json()
    assert "uploads" in second, second
    pdf_grant, source_grant = second["uploads"]["pdf"], second["uploads"]["source"]
    assert code(put(client, pdf_grant, PDF)) == (409, "source_required")
    assert put(client, source_grant, data).status_code == 200
    assert put(client, pdf_grant, PDF).status_code == 200
    read = documents.get_document(second["id"])
    assert read["complete"] and read["text"] == "Second letter."


def test_inputs_of_a_cv_or_letter_only_are_refused_elsewhere(setup):
    client, _, _, application = setup
    for value in (
        {"kind": "answers", "content": {}, "pdf": {"name": "a.pdf", "size": 1}},
        {"kind": "cv", "source": "x", "source_file": {"name": "cv.tex", "size": 1}},
        {"kind": "cv", "source": "x" * (256 * 1024 + 1)},
        {"kind": "resume"},
        # A CV or letter is its PDF: a revision that could never be completed is refused.
        {"kind": "letter"},
        # The PDF names its source's hash, so a source file declares it.
        {
            "kind": "cv",
            "source_file": {"name": "cv.tex", "size": 1},
            "pdf": {"name": "cv.pdf", "size": 1},
        },
    ):
        body = {"application_id": application["id"], **value}
        assert client.post("/api/v1/documents", json=body).status_code == 422, value["kind"]


def test_the_pdf_header_is_checked_whatever_the_case_of_the_media_type(setup):
    client, _, documents, application = setup
    created = documents.create_document(
        DocumentCreate(
            application_id=application["id"], kind="cv", pdf={"name": "cv.pdf", "size": 9}
        )
    )
    grant = client.post(
        "/api/v1/files/uploads",
        json={
            "owner_type": "document",
            "owner_id": created["id"],
            "name": "cv.pdf",
            "media_type": "Application/PDF",
            "size": 9,
        },
    ).json()
    assert code(put(client, grant, b"not a pdf")) == (422, "pdf_header")
    assert documents.get_document(created["id"])["complete"] is False


def test_every_grant_works_once(setup):
    client, _, documents, application = setup
    revision = pdf_revision(documents, client.put, application["id"])
    grant = client.post(f"/api/v1/files/{revision['files'][0]['id']}/download").json()
    headers = grant["headers"]
    assert client.get(grant["url"], headers=headers).content == PDF
    assert code(client.get(grant["url"], headers=headers)) == (401, "transfer_used")
    # A used upload grant takes no other bytes; the same bytes again replay the file.
    created = documents.create_document(
        DocumentCreate(
            application_id=application["id"], kind="letter", pdf={"name": "l.pdf", "size": len(PDF)}
        )
    )
    upload = created["uploads"]["pdf"]
    stored = put(client, upload, PDF).json()
    assert put(client, upload, PDF).json()["id"] == stored["id"]
    other = PDF[:-1] + b"!"
    assert code(put(client, upload, other)) == (401, "transfer_used")


def test_text_of_a_pdf_stored_without_text_is_read_on_first_read(setup):
    client, workspace, documents, application = setup
    data = text_pdf("Synthetic upgraded CV")
    document = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="cv",
            pdf={"name": "cv.pdf", "size": len(data)},
        )
    )
    assert put(client, document["uploads"]["pdf"], data).status_code == 200
    # As a revision upgraded from 0.23 with a PDF and no text.
    workspace.db.execute(
        "UPDATE documents SET text=NULL,text_from=NULL WHERE id=?", (document["id"],)
    )
    read = documents.get_document(document["id"])
    assert (read["text"], read["text_from"]) == ("Synthetic upgraded CV", "pdf")
    stored = workspace.db.one("SELECT text FROM documents WHERE id=?", (document["id"],))
    assert stored["text"] == "Synthetic upgraded CV"


def test_retried_creates_return_fresh_grants_for_an_incomplete_revision(app, client):
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    value = {
        "application_id": application["id"],
        "kind": "cv",
        "pdf": {"name": "cv.pdf", "size": len(PDF)},
        "idempotency_key": "cv-1",
    }
    first = documents.create_document(value)
    retry = documents.create_document(value)
    assert retry["id"] == first["id"]
    assert retry["uploads"]["pdf"]["headers"] != first["uploads"]["pdf"]["headers"]
    assert put(client, retry["uploads"]["pdf"], PDF).status_code == 200
    # Once complete, a retry returns the revision without grants to use.
    assert documents.create_document(value)["uploads"] == {"pdf": None, "source": None}
