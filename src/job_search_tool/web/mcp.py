"""MCP tools mounted by the unified web server."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from typing import cast

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from job_search_tool.application.jobs import JobApplicationService
from job_search_tool.application.models import (
    BlacklistListQuery,
    CleanupPreview,
    JobExportFormat,
    JobCommandResult,
    JobListQuery,
    JobSort,
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


def _sort_value(sort: str) -> JobSort:
    if sort not in {"score", "date", "company", "title", "salary"}:
        return "score"
    return cast(JobSort, sort)


def _export_format(value: str) -> JobExportFormat:
    if value not in {"csv", "json"}:
        return "csv"
    return cast(JobExportFormat, value)


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
    sites: list[str] | None = None,
    company: str | None = None,
    location: str | None = None,
    locations: list[str] | None = None,
    bookmarked: bool | None = None,
    applied: bool | None = None,
    remote: bool | None = None,
    job_type: str | None = None,
    job_types: list[str] | None = None,
    min_salary: float | None = None,
    max_salary: float | None = None,
    date_posted_from: str | None = None,
    date_posted_to: str | None = None,
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    last_seen_from: str | None = None,
    last_seen_to: str | None = None,
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
            sites=sites,
            company=company,
            location=location,
            locations=locations,
            bookmarked=bookmarked,
            applied=applied,
            remote=remote,
            job_type=job_type,
            job_types=job_types,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted_from=date_posted_from,
            date_posted_to=date_posted_to,
            first_seen_from=first_seen_from,
            first_seen_to=first_seen_to,
            last_seen_from=last_seen_from,
            last_seen_to=last_seen_to,
            text=text,
            sort=_sort_value(sort),
        )
    )
    return _json(
        {
            "items": [record_to_summary(job) for job in result.jobs],
            "total": result.total,
            "limit": result.limit,
            "offset": result.offset,
        }
    )


def get_job(job_id: str) -> str:
    """Get full details for one job, including description."""
    record = _service().get_job(job_id)
    if record is None:
        return _json({"error": f"Job not found: {job_id}"})
    return _json(record_to_dict(record))


def list_blacklisted_jobs(
    limit: int = 100,
    offset: int = 0,
    text: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> str:
    """List blacklist entries with server-side filtering and pagination."""
    result = _service().list_blacklisted_jobs(
        BlacklistListQuery(
            limit=limit,
            offset=offset,
            text=text,
            company=company,
            location=location,
        )
    )
    return _json(
        {
            "items": [asdict(item) for item in result.items],
            "total": result.total,
            "limit": result.limit,
            "offset": result.offset,
        }
    )


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
    return _json(_service().get_statistics())


def get_score_distribution(bin_size: int = 5) -> str:
    """Get score distribution as [bin_start, count] pairs."""
    return _json(_service().get_score_distribution(bin_size))


def get_facets() -> str:
    """Get dashboard filter facets."""
    return _json(_service().get_facets())


def set_bookmarked(job_ids: list[str], bookmarked: bool) -> str:
    """Set bookmark state explicitly and idempotently for one or more jobs."""
    return _command_json(_service().set_bookmarked(job_ids, bookmarked))


def set_applied(job_ids: list[str], applied: bool) -> str:
    """Set applied state explicitly and idempotently for one or more jobs."""
    return _command_json(_service().set_applied(job_ids, applied))


def blacklist_jobs(job_ids: list[str]) -> str:
    """Blacklist active jobs by ID."""
    return _command_json(_service().blacklist_jobs(job_ids))


def unblacklist_jobs(job_ids: list[str]) -> str:
    """Remove job IDs from the blacklist without restoring active rows."""
    return _command_json(_service().unblacklist_jobs(job_ids))


def delete_jobs(job_ids: list[str]) -> str:
    """Permanently delete active jobs without blacklisting them."""
    return _command_json(_service().delete_jobs(job_ids))


def delete_jobs_below_score(score: int) -> str:
    """Delete unprotected active jobs below a relevance score."""
    return _command_json(_service().delete_jobs_below_score(score))


def delete_stale_jobs(days: int) -> str:
    """Delete unprotected active jobs older than a last-seen threshold."""
    return _command_json(_service().delete_stale_jobs(days))


def purge_blacklist(older_than_days: int | None = None) -> str:
    """Purge blacklist entries, optionally older than a threshold."""
    return _command_json(_service().purge_blacklist(older_than_days))


def export_jobs(
    format: str = "csv",
    job_ids: list[str] | None = None,
    site: str | None = None,
    text: str | None = None,
    sort: str = "score",
) -> str:
    """Export selected or filtered jobs."""
    exported = _service().export_jobs(
        job_ids=job_ids,
        query=None
        if job_ids is not None
        else JobListQuery(site=site, text=text, sort=_sort_value(sort)),
        fmt=_export_format(format),
    )
    if format == "json":
        return exported.content.decode("utf-8")
    return _json(
        {
            "content": exported.content.decode("utf-8"),
            "media_type": exported.media_type,
            "filename": exported.filename,
            "row_count": exported.row_count,
        }
    )


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
        list_blacklisted_jobs,
        search_similar,
        get_statistics,
        get_score_distribution,
        get_facets,
        set_bookmarked,
        set_applied,
        blacklist_jobs,
        unblacklist_jobs,
        delete_jobs,
        delete_jobs_below_score,
        delete_stale_jobs,
        purge_blacklist,
        preview_cleanup,
        run_cleanup,
        export_jobs,
        get_settings_documentation,
    ):
        server.tool()(tool)
    return server


def create_mcp_app() -> Starlette:
    """Create the ASGI app mounted at /mcp by the unified web server."""
    return create_mcp_server().streamable_http_app()
