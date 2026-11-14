"""REST routes and MCP tools of documents."""

from typing import Annotated

from fastapi import Query, Request
from mcp.types import ToolAnnotations

from ..documents import (
    DocumentCreate,
    DocumentService,
    UploadReservation,
)
from ..documents.models import DocumentQuery, FileQuery
from .registry import (
    REQUIRED,
    Exemption,
    Operation,
    Param,
    Route,
    Tool,
    bind_mcp,
    bind_rest,
    query_model,
)

LOOKUP = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
REPLACE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
ADD = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)

# Every delete names the version it deletes (a file's version is always 1).
EXPECTED_VERSION = Param("expected_version", int, rest=(Annotated[int, Query(ge=1)], REQUIRED))

OPERATIONS = (
    Operation(
        "documents.list",
        "documents",
        "list",
        "Applications and documents",
        "List/filter paginated revision summaries",
        params=(query_model(DocumentQuery),),
        call=lambda s, value: s.list_documents(**(value or DocumentQuery()).model_dump()),
        rest=(Route("GET", "/documents", "list_documents"),),
        tool=Tool(
            LOOKUP,
            DocumentService.list_documents.__doc__,
        ),
    ),
    Operation(
        "documents.create",
        "documents",
        "create",
        "Applications and documents",
        "Create a new revision (CV/letter: a PDF and an optional TeX source, uploaded with the grants it returns)",
        params=(Param("value", DocumentCreate),),
        call=lambda s, value: s.create_document(value),
        rest=(Route("POST", "/documents", "create_document", status_code=201),),
        tool=Tool(REPLACE, method="create_document"),
    ),
    Operation(
        "documents.read",
        "documents",
        "get",
        "Applications and documents",
        "Read a revision: derived text or form content, evidence, chain number and files",
        params=(Param("document_id", str),),
        call=lambda s, document_id: s.get_document(document_id),
        rest=(Route("GET", "/documents/{document_id}", "get_document"),),
        tool=Tool(LOOKUP, method="get_document"),
    ),
    Operation(
        "documents.compare",
        "documents",
        "compare",
        "Applications and documents",
        "Compare the text of two revisions line by line",
        params=(Param("document_id", str), Param("other_id", str, "")),
        call=lambda s, document_id, other_id: s.compare_documents(document_id, other_id),
        rest=(Route("GET", "/documents/{document_id}/comparison", "compare_documents"),),
        tool=Tool(LOOKUP, method="compare_documents"),
    ),
    Operation(
        "documents.delete",
        "documents",
        "delete",
        "Applications and documents",
        "Delete an entire revision and its files",
        params=(Param("document_id", str), EXPECTED_VERSION),
        call=lambda s, document_id, expected_version: s.delete_document(
            document_id, expected_version
        ),
        rest=(Route("DELETE", "/documents/{document_id}", "delete_document"),),
        tool=Tool(DELETE, DocumentService.delete_document.__doc__),
    ),
    Operation(
        "files.list",
        "files",
        "list",
        "Applications and documents",
        "List/filter paginated file metadata",
        params=(query_model(FileQuery),),
        call=lambda s, value: s.list_files(**(value or FileQuery()).model_dump()),
        rest=(Route("GET", "/files", "list_files"),),
        tool=Tool(LOOKUP, DocumentService.list_files.__doc__),
    ),
    Operation(
        "files.upload",
        "files",
        "reserve_upload",
        "Applications and documents",
        "Upload exact raw bytes to a mutable owner",
        params=(Param("value", UploadReservation),),
        call=lambda s, value: s.reserve_upload(value),
        rest=(
            Route("POST", "/files/uploads", "reserve_upload", status_code=201),
            Route("PUT", "/transfers", "upload", custom=True),
        ),
        tool=Tool(ADD, method="reserve_upload"),
    ),
    Operation(
        "files.read",
        "files",
        "get",
        "Applications and documents",
        "Read immutable file metadata and content URL",
        params=(Param("file_id", str),),
        call=lambda s, file_id: s.get_file(file_id),
        rest=(Route("GET", "/files/{file_id}", "get_file"),),
        tool=Tool(LOOKUP, method="get_file"),
    ),
    Operation(
        "files.download",
        "files",
        "reserve_download",
        "Applications and documents",
        "Download/preview exact file bytes",
        params=(Param("file_id", str),),
        call=lambda s, file_id: s.reserve_download(file_id),
        rest=(
            Route(
                "GET",
                "/files/{file_id}/content",
                "get_file_content",
                params=(Param("file_id", str), Param("inline", bool, True)),
                call=lambda s, file_id, inline: s.file_response(file_id, inline),
            ),
            Route("POST", "/files/{file_id}/download", "reserve_download"),
            Route("GET", "/transfers", "download", custom=True),
        ),
        tool=Tool(ADD, method="reserve_download"),
    ),
    Operation(
        "files.delete",
        "files",
        "delete",
        "Applications and documents",
        "Delete a live knowledge/template/job asset",
        params=(Param("file_id", str), EXPECTED_VERSION),
        call=lambda s, file_id, expected_version: s.delete_file(file_id, expected_version),
        rest=(Route("DELETE", "/files/{file_id}", "delete_file"),),
        tool=Tool(DELETE, DocumentService.delete_file.__doc__),
    ),
)

EXEMPTIONS = (
    Exemption(
        "immutable.records",
        "Lifecycle history has no arbitrary PATCH/DELETE. Document content changes create revisions; a complete revision (its PDF stored) stays immutable.",
    ),
    Exemption(
        "binary.transfers",
        "Logical file actions are equivalent across interfaces; raw HTTP bytes use scoped grants rather than base64 MCP payloads. Backup/export use their own scoped operational grants.",
    ),
)


def register_api(router, documents: DocumentService):
    bind_rest(router, OPERATIONS, documents)

    # Raw bytes under a scoped grant (custom routes of files.upload and files.download).
    @router.put("/transfers")
    async def upload(request: Request):
        return await documents.upload(request)

    @router.get("/transfers")
    def download(request: Request):
        return documents.download(request)


def register_mcp(mcp, documents: DocumentService):
    bind_mcp(mcp, OPERATIONS, documents)
