"""Operations of document revisions and files. Raw bytes use transfer routes (transport.py)."""

from ..documents import DocumentCreate, UploadReservation
from ..documents.models import DocumentQuery, FileQuery
from ..responses import (
    Comparison,
    Deleted,
    Document,
    DocumentPage,
    FileGrant,
    FilePage,
    NewDocument,
    WorkspaceFile,
)
from .core import Version
from .operation import DESTRUCTIVE, WRITE, WS, Q, operation


@operation("GET /documents", tags=["documents"])
def documents_list(ws: WS, query: Q[DocumentQuery]) -> DocumentPage:
    """List document revisions.

    By application and kind (cv, letter, answers, other), each with complete; q searches
    titles, notes and text. summary=false adds text, content and files.
    """
    return ws.documents.list_documents(**query.model_dump())


@operation("POST /documents", access=WRITE, status=201, tags=["documents"])
def documents_create(ws: WS, body: DocumentCreate) -> NewDocument:
    """Create a document revision.

    A CV or letter gives pdf (name, size) and optionally its TeX source; PUT the bytes to the
    returned uploads grants, source first. Complete once its PDF is stored. Never sends.
    """
    return ws.documents.create_document(body)


@operation("GET /documents/{document_id}", tags=["documents"])
def documents_get(ws: WS, document_id: str) -> Document:
    """Read a document revision.

    complete, readable text and text_from (tex or pdf), cited evidence, note and files; for
    other kinds the structured content.
    """
    return ws.documents.get_document(document_id)


@operation("GET /documents/{document_id}/comparison", tags=["documents"])
def documents_compare(ws: WS, document_id: str, other_id: str = "") -> Comparison:
    """Compare two revisions line by line.

    With other_id, or by default the revision it replaces; CV and letter compare their text.
    """
    return ws.documents.compare_documents(document_id, other_id)


@operation("DELETE /documents/{document_id}", access=DESTRUCTIVE, tags=["documents"])
def documents_delete(ws: WS, document_id: str, expected_version: Version) -> Deleted:
    """Delete a document revision.

    Permanently, with its files and version; other revisions stay.
    """
    return ws.documents.delete_document(document_id, expected_version)


@operation("GET /files", tags=["files"])
def files_list(ws: WS, query: Q[FileQuery]) -> FilePage:
    """List file metadata.

    By owner, name, media type or an application's revisions. Bytes go through transfers.
    """
    return ws.documents.list_files(**query.model_dump())


@operation("POST /files/uploads", access=WRITE, status=201, tags=["files"])
def files_reserve_upload(ws: WS, body: UploadReservation) -> FileGrant:
    """Reserve a file upload.

    A short-lived PUT grant for one owner, name and size: send the raw bytes to its url with
    its headers. sha256 is verified when given.
    """
    return ws.documents.reserve_upload(body)


@operation("GET /files/{file_id}", tags=["files"])
def files_get(ws: WS, file_id: str) -> WorkspaceFile:
    """Read file metadata and its content URL."""
    return ws.documents.get_file(file_id)


@operation("POST /files/{file_id}/download", access=WRITE, tags=["files"])
def files_reserve_download(ws: WS, file_id: str) -> FileGrant:
    """Reserve a file download.

    A short-lived GET grant for one file; resolve its url against this workspace.
    """
    return ws.documents.reserve_download(file_id)


@operation("DELETE /files/{file_id}", access=DESTRUCTIVE, tags=["files"])
def files_delete(ws: WS, file_id: str, expected_version: Version) -> Deleted:
    """Delete a file.

    A career entry, template or job file, with version 1. Revision files are immutable:
    delete the revision.
    """
    return ws.documents.delete_file(file_id, expected_version)
