"""Operations of document revisions and files. Raw bytes use transfer routes (transport.py).

An application's revisions are listed by applications_get; the file listings of a
career entry and a template come with career_get and templates_get.
"""

from ..documents import DocumentCreate, UploadReservation
from ..documents.models import DocumentQuery, FileQuery
from ..responses import (
    Comparison,
    Deleted,
    DocumentDetail,
    DocumentPage,
    FileGrant,
    FilePage,
    NewDocument,
    WorkspaceFile,
)
from .core import Version, with_curl
from .operation import DESTRUCTIVE, READ, WRITE, WS, Q, operation


@operation("GET /documents", tags=["documents"], mcp="applications_get")
def documents_list(ws: WS, query: Q[DocumentQuery]) -> DocumentPage:
    """List document revisions by application and kind; q searches their text."""
    return ws.documents.list_documents(**query.model_dump())


@operation("POST /documents", access=WRITE, status=201, tags=["documents"])
def documents_create(ws: WS, body: DocumentCreate) -> NewDocument:
    """Create a CV, letter or answers revision of an application.

    CV/letter: pdf {name, size}, optional TeX source; PUT the PDF to uploads.pdf's absolute
    url (curl line given). Complete once its PDF is stored. Never sends.
    """
    document = ws.documents.create_document(body)
    names = {"pdf": body.pdf.name if body.pdf else "", "source": "source.tex"}
    if body.source_file:
        names["source"] = body.source_file.name
    for key, grant in (document.get("uploads") or {}).items():
        if grant:
            with_curl(grant, names.get(key) or key)
    return document


@operation("GET /documents/{document_id}", tags=["documents"])
def documents_get(ws: WS, document_id: str, compare_to: str = "") -> DocumentDetail:
    """Read a revision: complete, readable text, cited ids, note and files.

    compare_to adds a line diff against that revision (previous for the one it replaces).
    """
    document = ws.documents.get_document(document_id)
    if compare_to:
        other = "" if compare_to == "previous" else compare_to
        document["comparison"] = ws.documents.compare_documents(document_id, other)
    return document


@operation("GET /documents/{document_id}/comparison", tags=["documents"], mcp="documents_get")
def documents_compare(ws: WS, document_id: str, other_id: str = "") -> Comparison:
    """Compare two revisions line by line (by default with the one it replaces)."""
    return ws.documents.compare_documents(document_id, other_id)


@operation("DELETE /documents/{document_id}", access=DESTRUCTIVE, tags=["documents"])
def documents_delete(ws: WS, document_id: str, expected_version: Version) -> Deleted:
    """Delete a revision permanently, with its files; other revisions stay."""
    return ws.documents.delete_document(document_id, expected_version)


@operation("GET /files", tags=["files"], mcp="career_get")
def files_list(ws: WS, query: Q[FileQuery]) -> FilePage:
    """List file metadata by owner, name, media type or an application's revisions."""
    return ws.documents.list_files(**query.model_dump())


@operation("POST /files/uploads", access=WRITE, status=201, tags=["files"])
def files_upload(ws: WS, body: UploadReservation) -> FileGrant:
    """Reserve an upload for a career, template, job or revision file.

    Returns a one-shot grant: PUT the exact bytes to its absolute url with its headers (curl
    line given). sha256 is checked when given.
    """
    return with_curl(ws.documents.reserve_upload(body), body.name)


@operation("GET /files/{file_id}", tags=["files"], mcp="files_download")
def files_get(ws: WS, file_id: str) -> WorkspaceFile:
    """Read file metadata and its content URL."""
    return ws.documents.get_file(file_id)


@operation("POST /files/{file_id}/download", access=READ, tags=["files"])
def files_download(ws: WS, file_id: str) -> FileGrant:
    """Reserve a download of a file.

    A short-lived GET grant: fetch its url with its headers (curl line given).
    """
    return with_curl(ws.documents.reserve_download(file_id), "file")


@operation("DELETE /files/{file_id}", access=DESTRUCTIVE, tags=["files"])
def files_delete(ws: WS, file_id: str, expected_version: Version) -> Deleted:
    """Delete a career, template or job file (version 1).

    A revision's files go with the revision (documents_delete).
    """
    return ws.documents.delete_file(file_id, expected_version)
