"""CV and letter revisions as their source and PDF."""

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
