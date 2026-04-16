"""MCP server for the Job Search Tool.

Exposes tools that let an LLM become a job search assistant: DB access,
semantic search, and knowledge of the settings.yaml schema. The MCP server
does NOT read the user's settings.yaml or profile -- the user provides that
context in the conversation.

Run: ``python mcp_server.py`` (SSE transport on port 3001).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from config import DATA_DIR
from database import JobDatabase
from logger import get_logger
from models import JobDBRecord

if TYPE_CHECKING:
    from vector_store import JobVectorStore

# ---------------------------------------------------------------------------
# Paths (derived from config.DATA_DIR — respects JOB_SEARCH_DATA_DIR env var)
# ---------------------------------------------------------------------------

DB_PATH = DATA_DIR / "db" / "jobs.db"
CHROMA_PATH = DATA_DIR / "chroma"

# ---------------------------------------------------------------------------
# Singletons (initialised lazily on first tool call)
# ---------------------------------------------------------------------------

logger = get_logger("mcp")

_db: JobDatabase | None = None
_vs: JobVectorStore | None = None


def _get_db() -> JobDatabase:
    global _db
    if _db is None:
        _db = JobDatabase(DB_PATH)
    return _db


def _get_vs() -> JobVectorStore | None:
    global _vs
    if _vs is None:
        try:
            from vector_store import get_vector_store

            _vs = get_vector_store(CHROMA_PATH)
        except Exception:
            pass
    return _vs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_to_summary(r: JobDBRecord) -> dict:
    """Compact summary suitable for list views (no description)."""
    return {
        "job_id": r.job_id,
        "title": r.title,
        "company": r.company,
        "location": r.location,
        "relevance_score": r.relevance_score,
        "site": r.site,
        "bookmarked": r.bookmarked,
        "applied": r.applied,
        "first_seen": str(r.first_seen) if r.first_seen else None,
        "job_url": r.job_url,
    }


def _record_to_full(r: JobDBRecord) -> dict:
    """Full record including description."""
    d = asdict(r)  # type: ignore[arg-type]
    for key in ("date_posted", "first_seen", "last_seen"):
        val = d.get(key)
        if val is not None and hasattr(val, "isoformat"):
            d[key] = val.isoformat()
    return d


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
    db = _get_db()
    jobs = db.get_all_jobs()

    if min_score is not None:
        jobs = [j for j in jobs if j.relevance_score >= min_score]
    if max_score is not None:
        jobs = [j for j in jobs if j.relevance_score <= max_score]
    if site is not None:
        site_lower = site.lower()
        jobs = [j for j in jobs if (j.site or "").lower() == site_lower]
    if bookmarked_only:
        jobs = [j for j in jobs if j.bookmarked]
    if applied_only:
        jobs = [j for j in jobs if j.applied]

    jobs.sort(key=lambda j: j.relevance_score, reverse=True)
    page = jobs[:limit]
    return json.dumps([_record_to_summary(j) for j in page])


@server.tool()
def get_job(job_id: str) -> str:
    """Get full details of a single job INCLUDING the description.

    Use this to evaluate whether a specific job is a good fit for the user.
    Returns an error message if the job_id is not found.
    """
    db = _get_db()
    record = db.get_job_by_id(job_id)
    if record is None:
        return json.dumps({"error": f"Job not found: {job_id}"})
    return json.dumps(_record_to_full(record))


@server.tool()
def search_similar(query: str, n_results: int = 10) -> str:
    """Semantic search over the job database using natural language.

    Uses ChromaDB vector embeddings to find jobs similar to the query.
    Returns job_id, title, company, similarity score, and relevance score.
    """
    vs = _get_vs()
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
    db = _get_db()
    stats = db.get_statistics()
    return json.dumps(stats)


@server.tool()
def get_score_distribution(bin_size: int = 5) -> str:
    """Get the score distribution as [bin_start, count] pairs for histogramming.

    Useful for understanding the spread of job scores and advising on threshold tuning.
    """
    db = _get_db()
    dist = db.get_score_distribution(bin_size)
    return json.dumps(dist)


# ---- DB write tools -------------------------------------------------------


@server.tool()
def bookmark_job(job_id: str) -> str:
    """Toggle the bookmark status of a job.

    Returns confirmation with the new bookmark state.
    """
    db = _get_db()
    try:
        new_state = db.toggle_bookmark(job_id)
    except ValueError:
        return json.dumps({"error": f"Job not found: {job_id}"})
    return json.dumps({"job_id": job_id, "bookmarked": new_state})


@server.tool()
def apply_job(job_id: str) -> str:
    """Toggle the applied status of a job.

    Returns confirmation with the new applied state.
    """
    db = _get_db()
    try:
        new_state = db.toggle_applied(job_id)
    except ValueError:
        return json.dumps({"error": f"Job not found: {job_id}"})
    return json.dumps({"job_id": job_id, "applied": new_state})


@server.tool()
def delete_job(job_id: str) -> str:
    """Blacklist a job so it never reappears in future searches.

    The job is removed from the active table and its ID is stored in the
    blacklist. This is permanent unless the blacklist is purged.
    """
    db = _get_db()
    deleted = db.blacklist_job(job_id)
    return json.dumps({"job_id": job_id, "deleted": deleted})


@server.tool()
def delete_jobs_below_score(score: int) -> str:
    """Bulk delete all jobs with relevance_score strictly below the given threshold.

    Bookmarked and applied jobs are always protected and will NOT be deleted.
    Returns the number of jobs removed.
    """
    db = _get_db()
    count = db.delete_jobs_below_score(score)
    return json.dumps({"score_threshold": score, "deleted_count": count})


# ---- Knowledge tool -------------------------------------------------------


_SETTINGS_DOCUMENTATION = """\
# settings.yaml Reference Documentation

Complete reference for all configuration sections, fields, types, defaults,
constraints, and interactions.

## search
Controls which job boards are queried and how.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| results_wanted | int | 50 | Max results per query per site |
| hours_old | int | 168 | Only return postings newer than this (hours) |
| job_types | list[str] | [] | Filter: "fulltime", "contract", "parttime", "internship" |
| sites | list[str] | ["indeed","linkedin"] | Job boards: "indeed", "linkedin", "glassdoor", "google", "zip_recruiter", "bayt", "naukri" |
| locations | list[str] | [] | Geographic targets, e.g. "San Francisco, CA", "Remote" |
| distance | int | 50 | Search radius in miles |
| is_remote | bool | false | If true, only remote positions |
| linkedin_fetch_description | bool | true | Fetch full LinkedIn descriptions (slower) |
| description_format | str | "markdown" | "markdown", "html", or "plain" |
| country | str | "USA" | Country code for Indeed/Glassdoor |

## queries
Dict mapping category names to lists of search query strings.
Categories are purely organizational -- every query string is submitted to every site+location combination.
Example: `software_engineering: ["software engineer", "backend developer"]`

## scoring
Controls relevance scoring and the save/notify threshold split.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| save_threshold | int | 0 | Minimum score to persist a job to the DB |
| notify_threshold | int | 0 | Minimum score to trigger notifications |
| weights | dict[str,int] | {} | Points per category. Can be negative for penalties |
| keywords | dict[str,list[str]] | {} | Keywords per category. Case-insensitive matching |

**Constraints:**
- notify_threshold MUST be >= save_threshold (enforced at load; config is rejected otherwise)
- Category names in weights should match keywords (mismatches emit warnings)
- Weights can be negative (e.g. avoid: -30)
- Matching is case-insensitive with Unicode NFKD normalization

## parallel
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| max_workers | int | 4 | Concurrent search threads. Must be >= 1 |

## retry
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| max_attempts | int | 3 | Retries per query. Must be >= 1 |
| base_delay | float | 2 | Initial delay (seconds). Must be >= 0 |
| backoff_factor | float | 2.0 | Multiplier per retry. Must be >= 1.0 |

## throttling
Per-site rate limiting to avoid bans.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | true | Enable throttling |
| default_delay | float | 1.5 | Default seconds between requests |
| site_delays | dict[str,float] | {} | Per-site overrides, e.g. linkedin: 3.0 |
| jitter | float | 0.3 | Random variation factor (0-1) |
| rate_limit_cooldown | float | 30.0 | Pause after hitting rate limit |

## post_filter
Fuzzy matching validation after scraping.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | true | Enable post-filter |
| min_similarity | int | 80 | Minimum fuzzy match score (0-100) |

## logging
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| level | str | "INFO" | Python log level |

## database
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| retention.max_age_days | int | 30 | Delete jobs older than this. Must be >= 1. Bookmarked/applied protected |
| retention.purge_blacklist_after_days | int | 90 | Purge blacklist entries older than this. Must be >= 1 |

Retention is applied at every boot via reconcile_with_config(). Bookmarked and
applied jobs are ALWAYS protected at the SQL level in every automatic DELETE.

## profile
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| name | str | "" | User's name (used in notifications) |

## scheduler
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| interval_hours | int | 24 | Hours between search runs |
| run_on_startup | bool | true | Run immediately on start |
| retry_on_failure | bool | true | Retry failed searches |
| retry_delay_minutes | int | 30 | Delay between retries |
| max_retries | int | 3 | Max consecutive retries (0 = unlimited) |

## notifications
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | false | Master notifications switch |
| telegram.enabled | bool | false | Enable Telegram channel |
| telegram.bot_token | str | "" | Bot token from @BotFather. Supports "$ENV_VAR" syntax |
| telegram.chat_ids | list[str] | [] | Telegram chat IDs to notify |
| telegram.max_jobs_in_message | int | 50 | Max jobs per notification batch |
| telegram.jobs_per_chunk | int | 10 | Jobs per Telegram message |
| telegram.include_top_overall | bool | true | Show top jobs from entire DB |
| telegram.max_top_overall | int | 10 | Max top-overall jobs to show |

The notification floor is scoring.notify_threshold -- there is no per-channel override.

## vector_search
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | true | Enable semantic search |
| embed_on_save | bool | true | Auto-embed new jobs |
| default_results | int | 20 | Default semantic search result count |
| backfill_on_startup | bool | true | Embed existing jobs at startup |
| batch_size | int | 100 | Embedding batch size |

Uses ChromaDB's built-in ONNX embedder (all-MiniLM-L6-v2). No torch required.
Persistence path is fixed at {JOB_SEARCH_DATA_DIR}/chroma/.

## Path layout
All paths are derived from JOB_SEARCH_DATA_DIR (default: /data in Docker, repo root locally):
  {DATA_DIR}/config/settings.yaml
  {DATA_DIR}/db/jobs.db
  {DATA_DIR}/chroma/
  {DATA_DIR}/results/
  {DATA_DIR}/logs/search.log
None of these are configurable through settings.yaml.
"""


@server.tool()
def get_settings_documentation() -> str:
    """Get the complete settings.yaml reference documentation.

    Returns a structured description of every configuration section, field,
    type, default value, and constraint. Use this to advise users on how to
    tune their settings.yaml -- the MCP server does NOT read the user's
    actual settings file.
    """
    return _SETTINGS_DOCUMENTATION


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("MCP server starting | DB: %s | Chroma: %s", DB_PATH, CHROMA_PATH)
    server.run(transport="sse")
