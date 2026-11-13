"""CV and letter revisions as their source and PDF, and undoing their part of schema 13."""

import hashlib

from openings.documents import DocumentCreate, ReviewUpdate, UploadReservation

PDF = b"%PDF-1.4\nSynthetic test PDF"


def tex(text="Synthetic content."):
    """A small synthetic LaTeX source whose derived text is ``text``."""
    return (
        "\\documentclass{article}\n\\begin{document}\n"
        + text.replace("%", "\\%")
        + "\n\\end{document}\n"
    ).encode()


def upload(documents, put, document_id, name, data, media_type, source_sha256=None):
    """Reserve and send one file of a revision; ``put`` is a test client's put."""
    grant = documents.reserve_upload(
        UploadReservation(
            owner_type="document",
            owner_id=document_id,
            name=name,
            size=len(data),
            media_type=media_type,
            source_sha256=source_sha256,
        )
    )
    return put(grant["url"], headers=grant["headers"], content=data)


def attach_pdf(documents, put, document_id, text="Synthetic content.", name="document"):
    """Upload the PDF built from the source ``tex(text)`` the revision already has."""
    response = upload(
        documents,
        put,
        document_id,
        f"{name}.pdf",
        PDF,
        "application/pdf",
        hashlib.sha256(tex(text)).hexdigest(),
    )
    assert response.status_code == 200, response.text
    return documents.get_document(document_id)


def attach(documents, put, document_id, text="Synthetic content.", pdf=True, name="document"):
    """Upload a revision's source and, when ``pdf``, the PDF built from it."""
    response = upload(documents, put, document_id, f"{name}.tex", tex(text), "application/x-tex")
    assert response.status_code == 200, response.text
    if pdf:
        return attach_pdf(documents, put, document_id, text, name)
    return documents.get_document(document_id)


def source_revision(
    documents, put, application_id, kind="resume", text="Synthetic content.", **options
):
    """A CV or letter revision with its source, its PDF (unless pdf=False) and, if asked, approved."""
    pdf, approve = options.pop("pdf", True), options.pop("approve", False)
    document = documents.create_document(
        DocumentCreate(application_id=application_id, kind=kind, **options)
    )
    document = attach(documents, put, document["id"], text, pdf)
    if approve:
        document = documents.review_document(
            document["id"], ReviewUpdate(expected_version=document["version"])
        )
    return document


# What schema 13 (0.22) added to a schema 12 file.
SCHEMA_THIRTEEN_COLUMNS = {
    "documents": ("text", "legacy_content", "note", "claim_ids", "knowledge_ids"),
    "files": ("source_sha256",),
}
# The file views as released with schema 9 to 12.
FILE_VIEWS_TWELVE = (
    """CREATE VIEW context_files AS
 SELECT cp.file_id AS id, p.blob AS sha256, json_extract(p.content,'$.path') AS name,
  json_extract(p.content,'$.media_type') AS media_type, json_extract(p.content,'$.size') AS size,
  NULL AS knowledge_id, NULL AS template_id, cp.context_id AS context_id,
  NULL AS document_id, NULL AS job_id, coalesce(cp.file_created_at,c.created_at) AS created_at
 FROM context_parts cp JOIN snapshot_parts p ON p.id=cp.part_id JOIN contexts c ON c.id=cp.context_id
 WHERE cp.file_id IS NOT NULL""",
    """CREATE VIEW all_files AS
 SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at FROM files
 UNION ALL SELECT id,sha256,name,media_type,size,knowledge_id,template_id,context_id,document_id,job_id,created_at FROM context_files""",
)


def undo_documents(conn, content=None):
    """Remove the documents part of schema 13 from an open workspace file.

    A CV or letter revision gets back its legacy content, else ``content[id]`` when
    given, else ``{}``: the structured content it stored before 0.22.
    """
    conn.execute("UPDATE documents SET content=legacy_content WHERE legacy_content IS NOT NULL")
    for document_id, value in (content or {}).items():
        conn.execute("UPDATE documents SET content=? WHERE id=?", (value, document_id))
    conn.execute("DROP VIEW all_files")
    conn.execute("DROP VIEW context_files")
    for table, names in SCHEMA_THIRTEEN_COLUMNS.items():
        for name in names:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")
    for view in FILE_VIEWS_TWELVE:
        conn.execute(view)
