"""MCP server for the Job Search Tool.

Exposes tools that let an LLM become a job search assistant: DB access,
semantic search, and knowledge of the settings.yaml schema. The MCP server
does NOT read the user's settings.yaml or profile -- the user provides that
context in the conversation.

Run: ``job-search-mcp`` (MCP on port 3001).
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from job_search_tool.job_service import (
    filter_jobs,
    get_db,
    get_vs,
    logger,
    record_to_dict,
    record_to_summary,
    sort_jobs_by_score,
)
from job_search_tool.settings_reference import get_settings_reference

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = FastMCP("job-search-tool", host="0.0.0.0", port=3001)


# ---- DB read tools --------------------------------------------------------


@server.tool()
def list_jobs(
    limit: int = 20,
    min_score: int | None = None,
    max_score: int | None = None,
    site: str | None = None,
    bookmarked_only: bool = False,
    applied_only: bool = False,
) -> str:
    """List jobs from the database sorted by relevance score (descending).

    Returns compact summaries (no description). Use get_job() for full detail.
    Supports filtering by score range, site, bookmark, and applied status.
    """
    filtered = filter_jobs(
        get_db().get_all_jobs(),
        min_score=min_score,
        max_score=max_score,
        site=site,
        bookmarked=True if bookmarked_only else None,
        applied=True if applied_only else None,
    )
    sort_jobs_by_score(filtered)
    return json.dumps([record_to_summary(j) for j in filtered[:limit]])


@server.tool()
def get_job(job_id: str) -> str:
    """Get full details of a single job INCLUDING the description.

    Use this to evaluate whether a specific job is a good fit for the user.
    Returns an error message if the job_id is not found.
    """
    record = get_db().get_job_by_id(job_id)
    if record is None:
        return json.dumps({"error": f"Job not found: {job_id}"})
    return json.dumps(record_to_dict(record))


@server.tool()
def search_similar(query: str, n_results: int = 10) -> str:
    """Semantic search over the job database using natural language.

    Uses ChromaDB vector embeddings to find jobs similar to the query.
    Returns job_id, title, company, similarity score, and relevance score.
    """
    vs = get_vs()
    if vs is None:
        return json.dumps({"error": "Vector store not available"})
    results = vs.search(query=query, n_results=n_results)  # type: ignore[union-attr]
    return json.dumps(
        [
            {
                "job_id": r.job_id,
                "title": r.metadata.get("title"),
                "company": r.metadata.get("company"),
                "similarity": round(r.similarity, 4),
                "relevance_score": r.metadata.get("relevance_score"),
            }
            for r in results
        ]
    )


@server.tool()
def get_statistics() -> str:
    """Get summary statistics about the job database.

    Returns total jobs, jobs seen today, new today, applied count,
    blacklisted count, and average relevance score.
    """
    return json.dumps(get_db().get_statistics())


@server.tool()
def get_score_distribution(bin_size: int = 5) -> str:
    """Get the score distribution as [bin_start, count] pairs for histogramming.

    Useful for understanding the spread of job scores and advising on threshold tuning.
    """
    return json.dumps(get_db().get_score_distribution(bin_size))


# ---- DB write tools -------------------------------------------------------


@server.tool()
def bookmark_job(job_id: str) -> str:
    """Toggle the bookmark status of a job.

    Returns confirmation with the new bookmark state.
    """
    try:
        new_state = get_db().toggle_bookmark(job_id)
    except ValueError:
        return json.dumps({"error": f"Job not found: {job_id}"})
    return json.dumps({"job_id": job_id, "bookmarked": new_state})


@server.tool()
def apply_job(job_id: str) -> str:
    """Toggle the applied status of a job.

    Returns confirmation with the new applied state.
    """
    try:
        new_state = get_db().toggle_applied(job_id)
    except ValueError:
        return json.dumps({"error": f"Job not found: {job_id}"})
    return json.dumps({"job_id": job_id, "applied": new_state})


@server.tool()
def delete_job(job_id: str) -> str:
    """Blacklist a job so it never reappears in future searches.

    The job is removed from the active table and its ID is stored in the
    blacklist. This is permanent unless the blacklist is purged.
    """
    return json.dumps({"job_id": job_id, "deleted": get_db().blacklist_job(job_id)})


@server.tool()
def delete_jobs_below_score(score: int) -> str:
    """Bulk delete all jobs with relevance_score strictly below the given threshold.

    Bookmarked and applied jobs are always protected and will NOT be deleted.
    Returns the number of jobs removed.
    """
    count = get_db().delete_jobs_below_score(score)
    return json.dumps({"score_threshold": score, "deleted_count": count})


# ---- Knowledge tool -------------------------------------------------------


@server.tool()
def get_settings_documentation() -> str:
    """Get the complete settings.yaml reference documentation.

    Returns a structured description of every configuration section, field,
    type, default value, and constraint. Use this to advise users on how to
    tune their settings.yaml -- the MCP server does NOT read the user's
    actual settings file.
    """
    return get_settings_reference()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def run_mcp_server() -> None:
    """Start the MCP server with streamable HTTP on ``/mcp``."""
    logger.info("MCP server starting on port 3001 (streamable HTTP at /mcp)")
    server.run(transport="streamable-http")


if __name__ == "__main__":
    run_mcp_server()
