"""A CV or letter revision is its .tex source and PDF; its text is derived from the source."""

import hashlib
import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from document_fixtures import PDF, make_schema_twelve, source_revision, tex, upload
from openings.app import create_app
from openings.db import SCHEMA_VERSION, Database
from openings.documents import DocumentCreate, ReviewUpdate
from openings.documents.text import derive_text, revision_text, tokens
from openings.documents.upgrade import cited_ids
from openings.errors import DomainError
from openings.operations import restore_database
from openings.workspace import Workspace
from schema_fixtures import columns

SOURCE = r"""\documentclass{article}
\usepackage{hyperref}
\newcommand{\role}[2]{\textbf{#1} \hfill #2}
\newcommand{\myname}{Alex Example}
\begin{document}
{\LARGE \myname}\\[3pt]
\href{https://example.test}{example.test}
\section*{Experience}
\role{Backend Engineer --- Example Cloud}{2021--present}
\begin{itemize}[leftmargin=*]
  \item Reduced API p95 latency by 20\% through tracing. % measured on staging
  \item Built \textcolor{blue}{Python} services for Caf\'e~Example in M\"{u}nchen.
\end{itemize}
\vspace{4pt}{\small Skills: Python, SQL.}

Thank you for
your time.
\end{document}
"""
TEXT = """Alex Example
example.test

Experience
Backend Engineer — Example Cloud 2021–present
• Reduced API p95 latency by 20% through tracing.
• Built Python services for Café Example in München.
Skills: Python, SQL.

Thank you for your time."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_text_is_the_body_without_markup_with_the_breaks_tex_makes():
    assert derive_text(SOURCE) == TEXT
    # The preamble and comments are not text; a fragment without a body is read whole.
    assert derive_text("% only a comment\nPlain \\emph{fragment}.") == "Plain fragment."
    assert derive_text("\\def\\who#1{Dr.~#1}\\who{Example}") == "Dr. Example"
    # Recursive macros stop after a bounded number of expansions.
    assert len(derive_text("\\newcommand{\\loop}{a\\loop}\\loop")) < 100
    assert revision_text([]) is None
    assert revision_text([("b.tex", "Second."), ("a.tex", "First.")]) == "First.\n\nSecond."
    assert tokens(r"Stra\ss e \v{S}koda na\"{\i}ve") == ["strasse", "skoda", "naive"]


def test_cited_ids_are_read_from_legacy_content_in_first_seen_order():
    content = {
        "header": {"claim_ids": ["c2"]},
        "bullets": [
            {"text": "x", "evidence_ids": ["k1"], "claim_ids": ["c1", "c2"]},
            {"knowledge_ids": ["k2", "k1", 3]},
        ],
    }
    assert cited_ids(content) == (["c2", "c1"], ["k1", "k2"])
    assert cited_ids("text") == ([], [])


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "sources.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic document client")["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://localhost:8080", headers=headers) as client:
        client.app_state = app.state
        yield client


def tool(client, name, arguments):
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    result = response.json()["result"]
    if result.get("isError"):
        return None, result["content"][0]["text"]
    return result.get("structuredContent") or json.loads(result["content"][0]["text"]), None


def reserve(client, document_id, name, data, media_type, source_sha256=None):
    value = {
        "owner_type": "document",
        "owner_id": document_id,
        "name": name,
        "media_type": media_type,
        "size": len(data),
    }
    if source_sha256:
        value["source_sha256"] = source_sha256
    return client.post("/api/v1/files/uploads", json=value)


def send(client, document_id, name, data, media_type, source_sha256=None):
    grant = reserve(client, document_id, name, data, media_type, source_sha256)
    assert grant.status_code == 201, grant.text
    grant = grant.json()
    return client.put(grant["url"], headers=grant["headers"], content=data)


def code(response):
    return response.status_code, response.json()["error"]["code"]


def test_a_cv_is_its_source_and_the_pdf_built_from_it(client):
    workspace = client.app_state.workspace
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    refused = client.post(
        "/api/v1/documents",
        json={"application_id": application["id"], "kind": "resume", "content": {"text": "CV"}},
    )
    assert code(refused) == (422, "content_not_accepted")
    _, error = tool(
        client,
        "documents_create",
        {"value": {"application_id": application["id"], "content": {"text": "CV"}}},
    )
    assert "content_not_accepted" in error or "source and PDF" in error
    created = client.post(
        "/api/v1/documents",
        json={"application_id": application["id"], "title": "CV", "note": "First draft."},
    )
    assert created.status_code == 201
    cv = created.json()
    assert "content" not in cv and (cv["text"], cv["legacy_content"]) == (None, None)
    assert (cv["note"], cv["claim_ids"], cv["knowledge_ids"]) == ("First draft.", [], [])

    # The PDF comes after its source and names it.
    assert code(reserve(client, cv["id"], "cv.pdf", PDF, "application/pdf")) == (
        422,
        "source_required",
    )
    source = SOURCE.encode()
    assert code(reserve(client, cv["id"], "cv.pdf", PDF, "application/pdf", sha(source))) == (
        409,
        "source_required",
    )
    assert code(send(client, cv["id"], "cv.tex", b"caf\xe9", "application/x-tex")) == (
        422,
        "source_encoding",
    )
    assert send(client, cv["id"], "cv.tex", source, "application/x-tex").status_code == 200
    read = client.get(f"/api/v1/documents/{cv['id']}").json()
    assert (read["text"], read["source_sha256"]) == (TEXT, sha(source))
    assert code(reserve(client, cv["id"], "other.tex", b"x", "application/x-tex")) == (
        409,
        "source_exists",
    )
    other = sha(b"another source")
    assert code(reserve(client, cv["id"], "cv.pdf", PDF, "application/pdf", other)) == (
        409,
        "source_mismatch",
    )
    assert code(
        reserve(client, cv["id"], "cv.pdf", PDF, "application/octet-stream", sha(source))
    ) == (
        422,
        "pdf_media_type",
    )
    assert code(reserve(client, cv["id"], "photo.png", b"png", "image/png", sha(source))) == (
        422,
        "source_sha256",
    )
    review = f"/api/v1/documents/{cv['id']}/review"
    version = client.get(f"/api/v1/documents/{cv['id']}").json()["version"]
    assert code(client.post(review, json={"expected_version": version})) == (409, "pdf_required")
    pdf = send(client, cv["id"], "cv.pdf", PDF, "application/pdf", sha(source)).json()
    assert pdf["source_sha256"] == sha(source)
    assert code(reserve(client, cv["id"], "copy.pdf", PDF, "application/pdf", sha(source))) == (
        409,
        "pdf_exists",
    )
    # The consistency override is gone with the check.
    version = client.get(f"/api/v1/documents/{cv['id']}").json()["version"]
    assert (
        client.post(
            review, json={"expected_version": version, "allow_content_mismatch": True}
        ).status_code
        == 422
    )
    assert client.get(f"/api/v1/documents/{cv['id']}/consistency").status_code in {404, 405}
    assert tool(client, "documents_consistency", {"document_id": cv["id"]})[0] is None
    approved = client.post(review, json={"expected_version": version}).json()
    assert approved["review_state"] == "approved" and approved["text"] == TEXT
    mcp, _ = tool(client, "documents_get", {"document_id": cv["id"]})
    assert mcp == approved

    # A new revision is compared with the one it replaces, line by line.
    revised = client.post(
        "/api/v1/documents",
        json={"application_id": application["id"], "title": "CV", "previous_id": cv["id"]},
    ).json()
    changed = SOURCE.replace("Python, SQL.", "Python, SQL, Rust.").encode()
    assert send(client, revised["id"], "cv.tex", changed, "application/x-tex").status_code == 200
    comparison = client.get(f"/api/v1/documents/{revised['id']}/comparison").json()
    assert (comparison["other_id"], comparison["added"], comparison["removed"]) == (cv["id"], 1, 1)
    assert [line for line in comparison["lines"] if line["change"] != "same"] == [
        {"change": "removed", "text": "Skills: Python, SQL."},
        {"change": "added", "text": "Skills: Python, SQL, Rust."},
    ]
    assert comparison["text"] == {"document": True, "other": True}
    assert tool(client, "documents_compare", {"document_id": revised["id"]})[0] == comparison
    backwards = client.get(
        f"/api/v1/documents/{cv['id']}/comparison", params={"other_id": revised["id"]}
    ).json()
    assert (backwards["added"], backwards["removed"]) == (1, 1)
    assert code(client.get(f"/api/v1/documents/{cv['id']}/comparison")) == (
        422,
        "comparison_target",
    )
    # The derived text is searched with titles and notes.
    found = client.get("/api/v1/documents", params={"q": "Rust"}).json()
    assert [item["id"] for item in found["items"]] == [revised["id"]]
    assert client.get("/api/v1/documents", params={"q": "First draft"}).json()["total"] == 1


def test_form_answers_keep_structured_content_and_compare_it(client):
    workspace, documents = client.app_state.workspace, client.app_state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    first = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="answers",
            content={"answers": {"why": "Reliable services."}},
        )
    )
    assert first["content"] == {"answers": {"why": "Reliable services."}}
    # Approving form answers needs no file.
    documents.review_document(first["id"], ReviewUpdate(expected_version=first["version"]))
    second = documents.create_document(
        DocumentCreate(
            application_id=application["id"],
            kind="answers",
            previous_id=first["id"],
            content={"answers": {"why": "Reliable data services."}},
        )
    )
    comparison = documents.compare_documents(second["id"])
    assert [line for line in comparison["lines"] if line["change"] != "same"] == [
        {"change": "removed", "text": "answers.why: Reliable services."},
        {"change": "added", "text": "answers.why: Reliable data services."},
    ]
    other = workspace.create_application(
        {"job_id": workspace.ingest_job({"title": "Other", "posting": "Other."})["id"]}
    )
    elsewhere = documents.create_document(
        DocumentCreate(application_id=other["id"], kind="answers", content={})
    )
    with pytest.raises(DomainError) as error:
        documents.compare_documents(second["id"], elsewhere["id"])
    assert error.value.code == "comparison_target"


def test_a_retry_returns_only_an_empty_draft(tmp_path):
    app = create_app(tmp_path / "retry.sqlite", start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    value = DocumentCreate(application_id=application["id"], title="CV")
    first = documents.create_document(value)
    assert documents.create_document(value)["id"] == first["id"]
    with TestClient(app) as client:
        upload(documents, client.put, first["id"], "cv.tex", tex(), "application/x-tex")
    assert documents.create_document(value)["id"] != first["id"]


def schema_twelve_workspace(path):
    """A schema 12 file: CV and letter revisions with content, sources and PDFs, approved or not."""
    app = create_app(path, start_worker=False)
    workspace, documents = app.state.workspace, app.state.documents
    job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build services."})
    application = workspace.create_application({"job_id": job["id"]})
    ids, content = {}, {}
    with TestClient(app) as client:
        put = client.put
        approved = source_revision(
            documents, put, application["id"], text="Approved CV text.", approve=True
        )
        ids["approved"] = approved["id"]
        content[approved["id"]] = json.dumps(
            {
                "bullets": [
                    {"text": "Approved CV text.", "claim_ids": ["c1"], "evidence_ids": ["k1"]}
                ]
            }
        )
        draft = source_revision(
            documents, put, application["id"], "cover_letter", "Letter that differs."
        )
        ids["draft"] = draft["id"]
        content[draft["id"]] = json.dumps({"body": "Letter as it was saved."})
        bare = documents.create_document(
            DocumentCreate(application_id=application["id"], kind="resume", title="No source")
        )
        ids["bare"] = bare["id"]
        content[bare["id"]] = json.dumps({"text": "Only structured content."})
        empty = documents.create_document(
            DocumentCreate(application_id=application["id"], kind="resume", title="Empty")
        )
        ids["empty"] = empty["id"]
        answers = documents.create_document(
            DocumentCreate(
                application_id=application["id"],
                kind="answers",
                content={"answers": {"why": "Because."}, "claim_ids": []},
            )
        )
        ids["answers"] = answers["id"]
        # Two sources, as an older client could attach.
        twice = documents.create_document(
            DocumentCreate(application_id=application["id"], kind="other", title="Two sources")
        )
        ids["twice"] = twice["id"]
        upload(documents, put, twice["id"], "b.tex", tex("Second part."), "application/x-tex")
        upload(documents, put, twice["id"], "a.tex", tex("First part."), "application/x-tex")
        legacy_pdf = source_revision(documents, put, application["id"], text="Legacy PDF.")
        ids["legacy_pdf"] = legacy_pdf["id"]
    with closing(sqlite3.connect(path)) as conn:
        # A PDF uploaded before 0.22 named no source.
        conn.execute("UPDATE files SET source_sha256=NULL")
        conn.commit()
    make_schema_twelve(path, content)
    return ids, content


def document_rows(conn):
    return {
        row[0]: row
        for row in conn.execute(
            "SELECT id,application_id,context_id,kind,title,previous_id,review_state,version,created_at,content "
            "FROM documents"
        )
    }


def file_rows(conn):
    return sorted(
        conn.execute(
            "SELECT id,sha256,name,media_type,size,document_id,created_at FROM files ORDER BY id"
        ).fetchall()
    )


def test_upgrade_moves_cv_content_to_legacy_and_derives_text(tmp_path):
    path = tmp_path / "schema12.sqlite"
    ids, content = schema_twelve_workspace(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 12
        before, files = document_rows(conn), file_rows(conn)
    workspace = Workspace(path)
    fresh = Database(tmp_path / "fresh.sqlite")
    with closing(sqlite3.connect(path)) as conn, closing(sqlite3.connect(fresh.path)) as reference:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 13
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        for table in ("documents", "files"):
            assert columns(conn, table) == columns(reference, table), table
        for view in ("all_files", "context_files"):
            sql = "SELECT sql FROM sqlite_master WHERE name=?"
            assert (
                conn.execute(sql, (view,)).fetchone() == reference.execute(sql, (view,)).fetchone()
            )
        after = document_rows(conn)
        # Approved revisions keep their files, hashes, review state and version.
        assert file_rows(conn) == files
        assert not conn.execute("SELECT 1 FROM files WHERE source_sha256 IS NOT NULL").fetchall()
        legacy = dict(conn.execute("SELECT id,legacy_content FROM documents"))
    for document_id, row in before.items():
        assert after[document_id][:9] == row[:9]
    from openings.documents import DocumentService

    documents = DocumentService(workspace)
    approved = documents.get_document(ids["approved"])
    assert approved["review_state"] == "approved" and "content" not in approved
    assert approved["text"] == "Approved CV text."
    assert legacy[ids["approved"]] == content[ids["approved"]]
    assert approved["legacy_content"] == json.loads(content[ids["approved"]])
    assert (approved["claim_ids"], approved["knowledge_ids"]) == (["c1"], ["k1"])
    draft = documents.get_document(ids["draft"])
    assert (draft["text"], draft["legacy_content"]) == (
        "Letter that differs.",
        {"body": "Letter as it was saved."},
    )
    bare = documents.get_document(ids["bare"])
    assert (bare["text"], bare["legacy_content"]) == (None, {"text": "Only structured content."})
    assert documents.get_document(ids["empty"])["legacy_content"] is None
    answers = documents.get_document(ids["answers"])
    assert answers["content"] == {"answers": {"why": "Because."}, "claim_ids": []}
    assert answers["legacy_content"] is None and answers["text"] is None
    assert documents.get_document(ids["twice"])["text"] == "First part.\n\nSecond part."
    # A legacy draft without a source cannot be approved; one with a source and an
    # unpaired PDF still can, and approving it changes nothing else.
    with pytest.raises(DomainError) as error:
        documents.review_document(ids["bare"], ReviewUpdate(expected_version=bare["version"]))
    assert error.value.code == "source_required"
    legacy_pdf = documents.get_document(ids["legacy_pdf"])
    assert (
        documents.review_document(
            ids["legacy_pdf"], ReviewUpdate(expected_version=legacy_pdf["version"])
        )["text"]
        == "Legacy PDF."
    )


def test_a_schema_twelve_backup_is_restored_upgraded(tmp_path):
    source = tmp_path / "backup12.sqlite"
    ids, content = schema_twelve_workspace(source)
    original = source.read_bytes()
    target = Workspace(tmp_path / "live.sqlite")
    restore_database(target, source)
    assert source.read_bytes() == original
    with target.db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        row = conn.execute(
            "SELECT legacy_content,text,content FROM documents WHERE id=?", (ids["draft"],)
        ).fetchone()
    assert tuple(row) == (content[ids["draft"]], "Letter that differs.", "{}")
