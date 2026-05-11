"""MCP tools mounted by the unified web server."""

from __future__ import annotations

from dataclasses import asdict
import json
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from job_search_tool.application.jobs import JobApplicationService
from job_search_tool.application.models import (
    CleanupPreview,
    JobCommandResult,
    JobListQuery,
)
from job_search_tool.config import get_config
from job_search_tool.job_service import (
    get_db,
    get_vs,
    record_to_dict,
    record_to_summary,
)
from job_search_tool.settings_reference import get_settings_reference


DEFAULT_MCP_ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
DEFAULT_MCP_ALLOWED_ORIGINS = [
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
]


def _service() -> JobApplicationService:
    return JobApplicationService(get_db())


def _json(data: object) -> str:
    return json.dumps(data)


def _command_json(result: JobCommandResult) -> str:
    return _json(asdict(result))


def _cleanup_json(cleanup: CleanupPreview) -> str:
    data = asdict(cleanup)
    data["total_deleted"] = cleanup.total_deleted
    return _json(data)


def _env_csv(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def get_transport_security_settings() -> TransportSecuritySettings:
    """Return MCP transport security settings for local/LAN deployments."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_dedupe(
            DEFAULT_MCP_ALLOWED_HOSTS + _env_csv("JOB_SEARCH_WEB_ALLOWED_HOSTS")
        ),
        allowed_origins=_dedupe(
            DEFAULT_MCP_ALLOWED_ORIGINS + _env_csv("JOB_SEARCH_WEB_ALLOWED_ORIGINS")
        ),
    )


def list_jobs(
    limit: int = 20,
    offset: int = 0,
    min_score: int | None = None,
    max_score: int | None = None,
    site: str | None = None,
    company: str | None = None,
    bookmarked: bool | None = None,
    applied: bool | None = None,
    remote: bool | None = None,
    job_type: str | None = None,
    text: str | None = None,
    sort: str = "score",
) -> str:
    """List compact job summaries with server-side filtering and pagination."""
    result = _service().list_jobs(
        JobListQuery(
            limit=limit,
            offset=offset,
            min_score=min_score,
            max_score=max_score,
            site=site,
            company=company,
            bookmarked=bookmarked,
            applied=applied,
            remote=remote,
            job_type=job_type,
            text=text,
            sort="date" if sort == "date" else "score",
        )
    )
    return _json([record_to_summary(job) for job in result.jobs])


def get_job(job_id: str) -> str:
    """Get full details for one job, including description."""
    record = _service().get_job(job_id)
    if record is None:
        return _json({"error": f"Job not found: {job_id}"})
    return _json(record_to_dict(record))


def search_similar(query: str, n_results: int = 10) -> str:
    """Search semantically similar jobs using the vector store when available."""
    vs = get_vs()
    if vs is None:
        return _json({"error": "Vector store not available"})

    results = vs.search(query=query, n_results=n_results)
    return _json(
        [
            {
                "job_id": result.job_id,
                "title": result.metadata.get("title"),
                "company": result.metadata.get("company"),
                "similarity": round(result.similarity, 4),
                "relevance_score": result.metadata.get("relevance_score"),
            }
            for result in results
        ]
    )


def get_statistics() -> str:
    """Get summary statistics about the job database."""
    return _json(get_db().get_statistics())


def get_score_distribution(bin_size: int = 5) -> str:
    """Get score distribution as [bin_start, count] pairs."""
    return _json(get_db().get_score_distribution(bin_size))


def set_bookmarked(job_id: str, bookmarked: bool) -> str:
    """Set bookmark state explicitly and idempotently."""
    return _command_json(_service().set_bookmarked(job_id, bookmarked))


def set_applied(job_id: str, applied: bool) -> str:
    """Set applied state explicitly and idempotently."""
    return _command_json(_service().set_applied(job_id, applied))


def blacklist_jobs(job_ids: list[str]) -> str:
    """Blacklist active jobs by ID."""
    return _command_json(_service().blacklist_jobs(job_ids))


def preview_cleanup() -> str:
    """Preview configured cleanup without deleting data."""
    return _cleanup_json(_service().preview_cleanup(get_config()))


def run_cleanup() -> str:
    """Run configured cleanup and return deletion counts."""
    return _cleanup_json(_service().run_cleanup(get_config()))


def get_settings_documentation() -> str:
    """Get the generated settings.yaml reference documentation."""
    return get_settings_reference()


def create_mcp_server() -> FastMCP:
    """Create a FastMCP server with all Job Search Tool tools registered."""
    server = FastMCP(
        "job-search-tool",
        streamable_http_path="/",
        transport_security=get_transport_security_settings(),
    )
    for tool in (
        list_jobs,
        get_job,
        search_similar,
        get_statistics,
        get_score_distribution,
        set_bookmarked,
        set_applied,
        blacklist_jobs,
        preview_cleanup,
        run_cleanup,
        get_settings_documentation,
    ):
        server.tool()(tool)
    return server


def create_mcp_app() -> Starlette:
    """Create the ASGI app mounted at /mcp by the unified web server."""
    return create_mcp_server().streamable_http_app()
