"""REST routes and MCP tools of documents."""

from typing import Literal

from fastapi import Request
from mcp.types import ToolAnnotations

from ..common import encode
from ..documents import (
    ContextCreate,
    DocumentCreate,
    DocumentService,
    OwnerType,
    ReviewUpdate,
    StalenessStage,
    UploadReservation,
)
from .registry import Exemption, Operation, Param, Route, Surface, Tool, bind_mcp, bind_rest

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

OPERATIONS = (
    Operation(
        "contexts.list",
        "contexts",
        "list",
        "Applications and documents",
        "List/filter compact frozen-context metadata",
        params=(
            Param("application_id", str, ""),
            Param("limit", int, 100),
            Param("offset", int, 0),
            Param("summary", bool, False),
            Param("q", str, ""),
        ),
        call=lambda s, application_id, limit, offset, summary, q: s.list_contexts(
            application_id, limit, offset, summary, q
        ),
        rest=(Route("GET", "/contexts", "list_contexts"),),
        tool=Tool("contexts_list", LOOKUP, method="list_contexts"),
    ),
    Operation(
        "contexts.create",
        "contexts",
        "create",
        "Applications and documents",
        "Prepare an immutable context for external generation",
        params=(Param("value", ContextCreate),),
        call=lambda s, value: s.prepare_context(value),
        rest=(Route("POST", "/contexts", "prepare_context", status_code=201),),
        tool=Tool("application_prepare_context", ADD, method="prepare_context"),
    ),
    Operation(
        "contexts.read",
        "contexts",
        "get",
        "Applications and documents",
        "Read full frozen context and signature",
        params=(Param("context_id", str),),
        call=lambda s, context_id: s.get_context(context_id),
        rest=(Route("GET", "/contexts/{context_id}", "get_context"),),
        tool=Tool("contexts_get", LOOKUP, method="get_context"),
    ),
    Operation(
        "documents.list",
        "documents",
        "list",
        "Applications and documents",
        "List/filter paginated revision summaries",
        params=(
            Param("application_id", str, ""),
            Param("kind", str, ""),
            Param("limit", int, 100),
            Param("offset", int, 0),
            Param("summary", bool, True),
            Param("q", str, ""),
            Param("review_state", Literal["draft", "approved"] | None, None),
        ),
        call=lambda s, application_id, kind, limit, offset, summary, q, review_state: (
            s.list_documents(application_id, kind, limit, offset, summary, q, review_state)
        ),
        rest=(Route("GET", "/documents", "list_documents"),),
        tool=Tool("documents_list", LOOKUP, method="list_documents"),
    ),
    Operation(
        "documents.create",
        "documents",
        "create",
        "Applications and documents",
        "Save content as a new immutable revision",
        params=(Param("value", DocumentCreate),),
        call=lambda s, value: s.create_document(value),
        rest=(Route("POST", "/documents", "create_document", status_code=201),),
        tool=Tool("documents_create", REPLACE, method="create_document"),
    ),
    Operation(
        "documents.read",
        "documents",
        "get",
        "Applications and documents",
        "Read exact revision content, chain number and files",
        params=(Param("document_id", str),),
        call=lambda s, document_id: s.get_document(document_id),
        rest=(Route("GET", "/documents/{document_id}", "get_document"),),
        tool=Tool("documents_get", LOOKUP, method="get_document"),
    ),
    Operation(
        "documents.consistency",
        "documents",
        "consistency",
        "Applications and documents",
        "Compare structured content text with the attached .tex source",
        params=(Param("document_id", str),),
        call=lambda s, document_id: s.check_consistency(document_id),
        rest=(Route("GET", "/documents/{document_id}/consistency", "check_consistency"),),
        tool=Tool("documents_consistency", LOOKUP, method="check_consistency"),
    ),
    Operation(
        "applications.staleness_list",
        "staleness",
        "list",
        "Applications and documents",
        "List attempts whose current revisions use outdated inputs",
        params=(
            Param("status", StalenessStage, "draft"),
            Param("stale_only", bool, True),
            Param("limit", int, 50),
            Param("offset", int, 0),
        ),
        call=lambda s, status, stale_only, limit, offset: s.list_staleness(
            status, stale_only, limit, offset
        ),
        rest=(Route("GET", "/staleness", "list_staleness"),),
        tool=Tool("applications_staleness", LOOKUP, method="list_staleness"),
    ),
    Operation(
        "applications.staleness",
        "staleness",
        "get",
        "Applications and documents",
        "Report whether an attempt's current revisions use outdated inputs",
        params=(Param("application_id", str),),
        call=lambda s, application_id: s.application_staleness(application_id),
        rest=(Route("GET", "/applications/{application_id}/staleness", "application_staleness"),),
        tool=Tool("application_staleness", LOOKUP, method="application_staleness"),
    ),
    Operation(
        "documents.review",
        "documents",
        "review",
        "Applications and documents",
        "Approve the exact revision content/files",
        params=(Param("document_id", str), Param("value", ReviewUpdate)),
        call=lambda s, document_id, value: s.review_document(document_id, value),
        rest=(Route("POST", "/documents/{document_id}/review", "review_document"),),
        tool=Tool("documents_review", REPLACE, method="review_document"),
    ),
    Operation(
        "documents.delete",
        "documents",
        "delete",
        "Applications and documents",
        "Delete an entire revision and its files",
        params=(Param("document_id", str),),
        call=lambda s, document_id: s.delete_document(document_id),
        rest=(Route("DELETE", "/documents/{document_id}", "delete_document"),),
        tool=Tool("documents_delete", DELETE, method="delete_document"),
    ),
    Operation(
        "files.list",
        "files",
        "list",
        "Applications and documents",
        "List/filter paginated file metadata",
        params=(
            Param("owner_type", OwnerType | None, None),
            Param("owner_id", str, ""),
            Param("limit", int, 100),
            Param("offset", int, 0),
            Param("summary", bool, False),
            Param("q", str, ""),
            Param("media_type", str, ""),
            Param("application_id", str, ""),
        ),
        call=lambda s, owner_type, owner_id, limit, offset, summary, q, media_type, application_id: (
            s.list_files(
                owner_type, owner_id, limit, offset, summary, q, media_type, application_id
            )
        ),
        rest=(Route("GET", "/files", "list_files"),),
        tool=Tool("files_list", LOOKUP, method="list_files"),
    ),
    Operation(
        "files.upload",
        "files",
        "upload",
        "Applications and documents",
        "Upload exact raw bytes to a mutable owner",
        params=(Param("value", UploadReservation),),
        call=lambda s, value: s.reserve_upload(value),
        rest=(
            Route("POST", "/files/uploads", "reserve_upload", status_code=201),
            Route("PUT", "/transfers", "upload", custom=True),
        ),
        tool=Tool("files_reserve_upload", ADD, method="reserve_upload"),
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
        tool=Tool("files_get", LOOKUP, method="get_file"),
    ),
    Operation(
        "files.download",
        "files",
        "download",
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
        tool=Tool("files_reserve_download", ADD, method="reserve_download"),
    ),
    Operation(
        "files.delete",
        "files",
        "delete",
        "Applications and documents",
        "Delete a live knowledge/template/job asset",
        params=(Param("file_id", str),),
        call=lambda s, file_id: s.delete_file(file_id),
        rest=(Route("DELETE", "/files/{file_id}", "delete_file"),),
        tool=Tool("files_delete", DELETE, method="delete_file"),
    ),
)

EXEMPTIONS = (
    Exemption(
        "immutable.records",
        "Frozen contexts and lifecycle history have no arbitrary PATCH/DELETE. Document content changes create revisions; approved revisions stay immutable. Context deletion is scoped to deleting the owning application/job.",
    ),
    Exemption(
        "binary.transfers",
        "Logical file actions are equivalent across interfaces; raw HTTP bytes use scoped grants rather than base64 MCP payloads. Backup/export use their own scoped operational grants.",
        rest=(
            Route("PUT", "/transfers", "upload", custom=True),
            Route("GET", "/transfers", "download", custom=True),
        ),
        tools=("files_reserve_upload", "files_reserve_download"),
    ),
)
SURFACES = (Surface("resource", "openings://contexts/{context_id}"),)


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

    @mcp.resource("openings://contexts/{context_id}")
    def context_resource(context_id: str) -> str:
        """Read an immutable application context, including stored template instructions."""
        return encode(documents.get_context(context_id))
