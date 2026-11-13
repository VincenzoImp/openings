"""REST routes and MCP tools of documents."""

from typing import Literal

from fastapi import Request

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


def register_api(router, documents: DocumentService):
    @router.get("/contexts")
    def list_contexts(
        application_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ):
        return documents.list_contexts(application_id, limit, offset, summary, q)

    @router.post("/contexts", status_code=201)
    def prepare_context(value: ContextCreate):
        return documents.prepare_context(value)

    @router.get("/contexts/{context_id}")
    def get_context(context_id: str):
        return documents.get_context(context_id)

    @router.get("/documents")
    def list_documents(
        application_id: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
        q: str = "",
        review_state: Literal["draft", "approved"] | None = None,
    ):
        return documents.list_documents(
            application_id, kind, limit, offset, summary, q, review_state
        )

    @router.post("/documents", status_code=201)
    def create_document(value: DocumentCreate):
        return documents.create_document(value)

    @router.get("/documents/{document_id}")
    def get_document(document_id: str):
        return documents.get_document(document_id)

    @router.get("/documents/{document_id}/consistency")
    def check_consistency(document_id: str):
        return documents.check_consistency(document_id)

    @router.get("/staleness")
    def list_staleness(
        status: StalenessStage = "draft",
        stale_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ):
        return documents.list_staleness(status, stale_only, limit, offset)

    @router.get("/applications/{application_id}/staleness")
    def application_staleness(application_id: str):
        return documents.application_staleness(application_id)

    @router.post("/documents/{document_id}/review")
    def review_document(document_id: str, value: ReviewUpdate):
        return documents.review_document(document_id, value)

    @router.delete("/documents/{document_id}")
    def delete_document(document_id: str):
        return documents.delete_document(document_id)

    @router.get("/files")
    def list_files(
        owner_type: OwnerType | None = None,
        owner_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
        media_type: str = "",
        application_id: str = "",
    ):
        return documents.list_files(
            owner_type, owner_id, limit, offset, summary, q, media_type, application_id
        )

    @router.post("/files/uploads", status_code=201)
    def reserve_upload(value: UploadReservation):
        return documents.reserve_upload(value)

    @router.get("/files/{file_id}")
    def get_file(file_id: str):
        return documents.get_file(file_id)

    @router.get("/files/{file_id}/content")
    def get_file_content(file_id: str, inline: bool = True):
        return documents.file_response(file_id, inline)

    @router.post("/files/{file_id}/download")
    def reserve_download(file_id: str):
        return documents.reserve_download(file_id)

    @router.delete("/files/{file_id}")
    def delete_file(file_id: str):
        return documents.delete_file(file_id)

    @router.put("/transfers")
    async def upload(request: Request):
        return await documents.upload(request)

    @router.get("/transfers")
    def download(request: Request):
        return documents.download(request)


def register_mcp(mcp, documents: DocumentService):
    from mcp.types import ToolAnnotations

    for name, handler in [
        ("application_prepare_context", documents.prepare_context),
        ("contexts_get", documents.get_context),
        ("contexts_list", documents.list_contexts),
        ("documents_create", documents.create_document),
        ("documents_get", documents.get_document),
        ("documents_list", documents.list_documents),
        ("documents_review", documents.review_document),
        ("documents_delete", documents.delete_document),
        ("documents_consistency", documents.check_consistency),
        ("application_staleness", documents.application_staleness),
        ("applications_staleness", documents.list_staleness),
        ("files_list", documents.list_files),
        ("files_get", documents.get_file),
        ("files_reserve_upload", documents.reserve_upload),
        ("files_reserve_download", documents.reserve_download),
        ("files_delete", documents.delete_file),
    ]:
        read_only = name.endswith(("_get", "_list", "_consistency", "_staleness"))
        mcp.add_tool(
            handler,
            name=name,
            annotations=ToolAnnotations(
                readOnlyHint=read_only,
                destructiveHint=name.endswith("_delete"),
                idempotentHint=read_only or name in {"documents_review", "documents_create"},
                openWorldHint=False,
            ),
        )

    @mcp.resource("openings://contexts/{context_id}")
    def context_resource(context_id: str) -> str:
        """Read an immutable application context, including stored template instructions."""
        return encode(documents.get_context(context_id))
