"""
Job Search Hub - Interactive Streamlit Dashboard.

Provides semantic search, advanced filtering, inline job actions,
analytics, and database management for the Job Search Tool.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration -- MUST be the first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Job Search Hub",
    page_icon="briefcase",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, load_config  # noqa: E402
from database import JobDatabase  # noqa: E402
from models import JobDBRecord  # noqa: E402

# ---------------------------------------------------------------------------
# Optional vector search (graceful fallback when deps missing)
# ---------------------------------------------------------------------------
try:
    from vector_store import get_vector_store  # noqa: E402

    VECTOR_AVAILABLE: bool = True
except Exception:
    VECTOR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
JOBS_PER_PAGE: int = 20
SCORE_HIGH: int = 60
SCORE_MED: int = 30

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
_CSS = """
<style>
/* Score badges */
.score-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 0.85rem;
}
.score-high  { background: #d4edda; color: #155724; }
.score-med   { background: #fff3cd; color: #856404; }
.score-low   { background: #f8d7da; color: #721c24; }

/* Similarity badge */
.sim-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.8rem;
    background: #d1ecf1;
    color: #0c5460;
    margin-left: 6px;
}

/* Meta line */
.meta-line {
    color: #666;
    font-size: 0.88rem;
    margin-top: 2px;
}

/* Status tags */
.tag {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.78rem;
    margin-right: 4px;
}
.tag-applied    { background: #cce5ff; color: #004085; }
.tag-bookmarked { background: #fff3cd; color: #856404; }
.tag-remote     { background: #d4edda; color: #155724; }
</style>
"""


# ═══════════════════════════════════════════════════════════════════════════
# Cached loaders
# ═══════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=10)
def _load_config_cached() -> Config:
    """Load YAML configuration (short TTL so changes are picked up)."""
    return load_config()


@st.cache_data(ttl=30)
def _fetch_all_jobs(db_path: str) -> list[dict[str, Any]]:
    """Fetch every job from SQLite as dicts (hashable cache key)."""
    db = JobDatabase(Path(db_path))
    records = db.get_all_jobs()
    db.close()
    return [_record_to_dict(r) for r in records]


@st.cache_data(ttl=30)
def _fetch_statistics(db_path: str) -> dict[str, Any]:
    """Fetch database statistics."""
    db = JobDatabase(Path(db_path))
    stats = db.get_statistics()
    db.close()
    return stats


@st.cache_resource
def _get_vector_store_cached(data_dir: str, model_name: str) -> Any:
    """Return a persistent JobVectorStore instance."""
    if not VECTOR_AVAILABLE:
        return None
    try:
        return get_vector_store(Path(data_dir), model_name=model_name)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _record_to_dict(r: JobDBRecord) -> dict[str, Any]:
    """Convert a JobDBRecord to a plain dict for caching."""
    return {
        "job_id": r.job_id,
        "title": r.title,
        "company": r.company,
        "location": r.location,
        "job_url": r.job_url,
        "site": r.site,
        "job_type": r.job_type,
        "is_remote": r.is_remote,
        "job_level": r.job_level,
        "description": r.description,
        "date_posted": str(r.date_posted) if r.date_posted else None,
        "min_amount": r.min_amount,
        "max_amount": r.max_amount,
        "currency": r.currency,
        "company_url": r.company_url,
        "first_seen": str(r.first_seen) if r.first_seen else None,
        "last_seen": str(r.last_seen) if r.last_seen else None,
        "relevance_score": r.relevance_score,
        "applied": r.applied,
        "bookmarked": r.bookmarked,
    }


def _score_badge_html(score: int) -> str:
    """Return an HTML badge span for the relevance score."""
    if score >= SCORE_HIGH:
        cls = "score-high"
    elif score >= SCORE_MED:
        cls = "score-med"
    else:
        cls = "score-low"
    return f'<span class="score-badge {cls}">Score: {score}</span>'


def _format_salary(job: dict[str, Any]) -> str:
    """Build a compact salary string."""
    lo = job.get("min_amount")
    hi = job.get("max_amount")
    cur = job.get("currency") or "$"
    if cur.upper() == "USD":
        cur = "$"
    if lo and hi:
        return f"{cur}{_short_num(lo)}-{cur}{_short_num(hi)}"
    if lo:
        return f"{cur}{_short_num(lo)}+"
    if hi:
        return f"Up to {cur}{_short_num(hi)}"
    return ""


def _short_num(n: float) -> str:
    """Format a number compactly (e.g. 120000 -> '120k')."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return f"{n:,.0f}"


def _days_ago(date_str: str | None) -> str:
    """Return a human-friendly 'X days ago' string."""
    if not date_str:
        return ""
    try:
        d = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        delta = (date.today() - d).days
        if delta == 0:
            return "Today"
        if delta == 1:
            return "Yesterday"
        return f"{delta}d ago"
    except (ValueError, TypeError):
        return ""


def _clear_caches() -> None:
    """Invalidate all data caches so the next rerun fetches fresh data."""
    _fetch_all_jobs.clear()
    _fetch_statistics.clear()


def _get_db(config: Config) -> JobDatabase:
    """Get a fresh (non-cached) database handle for write operations."""
    return JobDatabase(config.database_path)


def _init_session_state() -> None:
    """Initialise session-state keys with defaults if absent."""
    defaults: dict[str, Any] = {
        "current_page": 0,
        "selected_jobs": set(),
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar -- filters, quick stats, actions
# ═══════════════════════════════════════════════════════════════════════════


def _render_sidebar(
    jobs: list[dict[str, Any]],
    config: Config,
) -> list[dict[str, Any]]:
    """Draw sidebar controls and return the filtered job list."""

    with st.sidebar:
        st.markdown("### Filters")

        # -- Score range --
        all_scores = [j["relevance_score"] for j in jobs] or [0]
        lo_s, hi_s = int(min(all_scores)), int(max(all_scores))
        if lo_s == hi_s:
            hi_s = lo_s + 1
        score_range: tuple[int, int] = st.slider(
            "Score range",
            min_value=lo_s,
            max_value=hi_s,
            value=(lo_s, hi_s),
            key="filter_score",
        )

        # -- Site --
        sites = sorted({j["site"] for j in jobs if j.get("site")})
        sel_sites: list[str] = st.multiselect(
            "Site", sites, default=[], key="filter_sites"
        )

        # -- Job type --
        job_types = sorted({j["job_type"] for j in jobs if j.get("job_type")})
        sel_types: list[str] = st.multiselect(
            "Job type", job_types, default=[], key="filter_types"
        )

        # -- Remote --
        remote_opt: str = st.radio(
            "Remote",
            ["All", "Remote only", "On-site only"],
            horizontal=True,
            key="filter_remote",
        )

        # -- Company --
        companies = sorted({j["company"] for j in jobs if j.get("company")})
        if len(companies) > 150:
            companies = companies[:150]
        sel_companies: list[str] = st.multiselect(
            "Company",
            companies,
            default=[],
            key="filter_companies",
        )

        # -- Date range --
        date_range: tuple[date, date] | None = None
        date_strings = [j["first_seen"] for j in jobs if j.get("first_seen")]
        if date_strings:
            parsed_dates: list[date] = []
            for ds in date_strings:
                try:
                    parsed_dates.append(datetime.strptime(str(ds), "%Y-%m-%d").date())
                except (ValueError, TypeError):
                    pass
            if parsed_dates:
                min_d, max_d = min(parsed_dates), max(parsed_dates)
                if min_d == max_d:
                    max_d = min_d + timedelta(days=1)
                dr = st.date_input(
                    "First seen range",
                    value=(min_d, max_d),
                    min_value=min_d,
                    max_value=max_d,
                    key="filter_dates",
                )
                if isinstance(dr, (tuple, list)) and len(dr) == 2:
                    date_range = (dr[0], dr[1])

        # -- Status --
        status_opt: str = st.radio(
            "Status",
            ["All", "Applied", "Bookmarked", "New"],
            horizontal=True,
            key="filter_status",
        )

        st.markdown("---")

        # -- Quick Stats --
        st.markdown("### Quick Stats")
        stats = _fetch_statistics(str(config.database_path))
        q1, q2 = st.columns(2)
        q1.metric("Total", stats.get("total_jobs", 0))
        q2.metric("New today", stats.get("new_today", 0))
        q3, q4 = st.columns(2)
        q3.metric("Applied", stats.get("applied", 0))
        bookmarked_count = sum(1 for j in jobs if j.get("bookmarked"))
        q4.metric("Bookmarked", bookmarked_count)
        st.caption(f"Avg score: {stats.get('avg_relevance_score', 0)}")

        st.markdown("---")

        # -- Export / Reset --
        if jobs:
            csv_bytes = pd.DataFrame(jobs).to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export filtered CSV",
                csv_bytes,
                file_name=f"jobs_{date.today().isoformat()}.csv",
                mime="text/csv",
                key="sidebar_dl_csv",
                use_container_width=True,
            )

        if st.button("Reset filters", use_container_width=True, key="btn_reset"):
            for k in [
                "filter_score",
                "filter_sites",
                "filter_types",
                "filter_remote",
                "filter_companies",
                "filter_dates",
                "filter_status",
            ]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state["current_page"] = 0
            st.rerun()

    # ---- Apply filters ----
    filtered = list(jobs)

    filtered = [
        j for j in filtered if score_range[0] <= j["relevance_score"] <= score_range[1]
    ]
    if sel_sites:
        filtered = [j for j in filtered if j.get("site") in sel_sites]
    if sel_types:
        filtered = [j for j in filtered if j.get("job_type") in sel_types]
    if sel_companies:
        filtered = [j for j in filtered if j.get("company") in sel_companies]

    if remote_opt == "Remote only":
        filtered = [j for j in filtered if j.get("is_remote")]
    elif remote_opt == "On-site only":
        filtered = [j for j in filtered if not j.get("is_remote")]

    if status_opt == "Applied":
        filtered = [j for j in filtered if j.get("applied")]
    elif status_opt == "Bookmarked":
        filtered = [j for j in filtered if j.get("bookmarked")]
    elif status_opt == "New":
        today_str = date.today().isoformat()
        filtered = [j for j in filtered if j.get("first_seen") == today_str]

    if date_range is not None:
        d_start, d_end = date_range

        def _in_range(j: dict[str, Any]) -> bool:
            fs = j.get("first_seen")
            if not fs:
                return True
            try:
                d = datetime.strptime(str(fs), "%Y-%m-%d").date()
                return d_start <= d <= d_end
            except (ValueError, TypeError):
                return True

        filtered = [j for j in filtered if _in_range(j)]

    return filtered


# ═══════════════════════════════════════════════════════════════════════════
# Semantic search
# ═══════════════════════════════════════════════════════════════════════════


def _apply_semantic_search(
    query: str,
    jobs: list[dict[str, Any]],
    config: Config,
) -> list[dict[str, Any]]:
    """Run vector search, merge similarity scores, return reordered list.

    Jobs not in the vector search results are excluded so semantic search
    acts as a filter.
    """
    vs = _get_vector_store_cached(
        str(config.data_path), config.vector_search.model_name
    )
    if vs is None:
        return jobs

    try:
        results = vs.search(
            query,
            n_results=min(config.vector_search.default_results, len(jobs), 200),
        )
    except Exception:
        return jobs

    if not results:
        return jobs

    sim_map: dict[str, float] = {r.job_id: r.similarity for r in results}
    matched: list[dict[str, Any]] = []
    for j in jobs:
        if j["job_id"] in sim_map:
            j = dict(j)  # shallow copy to avoid mutating cached data
            j["_similarity"] = sim_map[j["job_id"]]
            matched.append(j)

    matched.sort(key=lambda x: x.get("_similarity", 0), reverse=True)
    return matched


# ═══════════════════════════════════════════════════════════════════════════
# Job card renderer
# ═══════════════════════════════════════════════════════════════════════════


def _render_job_card(job: dict[str, Any], idx: int, config: Config) -> None:
    """Render a single job as a bordered card with inline actions."""
    jid: str = job["job_id"]
    title: str = job.get("title") or "Untitled"
    company: str = job.get("company") or "Unknown"
    location: str = job.get("location") or ""
    score: int = job.get("relevance_score", 0)
    is_remote: bool | None = job.get("is_remote")
    job_type: str = job.get("job_type") or ""
    site: str = job.get("site") or ""
    date_posted: str | None = job.get("date_posted")
    salary: str = _format_salary(job)
    sim: float | None = job.get("_similarity")

    with st.container(border=True):
        # ---- Header row: title + tags | score badge ----
        hdr_left, hdr_right = st.columns([5, 1])
        with hdr_left:
            tags = ""
            if job.get("applied"):
                tags += '<span class="tag tag-applied">Applied</span>'
            if job.get("bookmarked"):
                tags += '<span class="tag tag-bookmarked">Bookmarked</span>'
            if is_remote:
                tags += '<span class="tag tag-remote">Remote</span>'
            st.markdown(f"**{title}** &nbsp;{tags}", unsafe_allow_html=True)

        with hdr_right:
            badge = _score_badge_html(score)
            if sim is not None:
                badge += f' <span class="sim-badge">{sim:.0%} match</span>'
            st.markdown(badge, unsafe_allow_html=True)

        # ---- Meta lines ----
        meta_parts: list[str] = [p for p in [company, location] if p]
        if job_type:
            meta_parts.append(job_type.replace("_", " ").title())
        meta1 = " &middot; ".join(meta_parts)

        meta2_parts: list[str] = []
        if site:
            meta2_parts.append(site.title())
        posted_ago = _days_ago(date_posted)
        if posted_ago:
            meta2_parts.append(f"Posted {posted_ago}")
        if salary:
            meta2_parts.append(salary)
        job_level = job.get("job_level")
        if job_level:
            meta2_parts.append(job_level.title())
        meta2 = " &middot; ".join(meta2_parts)

        st.markdown(
            f'<div class="meta-line">{meta1}</div><div class="meta-line">{meta2}</div>',
            unsafe_allow_html=True,
        )

        # ---- Action buttons ----
        a1, a2, a3, a4, a5 = st.columns(5)

        with a1:
            label_app = "Unapply" if job.get("applied") else "Mark applied"
            if st.button(label_app, key=f"app_{jid}_{idx}", use_container_width=True):
                db = _get_db(config)
                db.mark_as_applied(jid)
                db.close()
                _clear_caches()
                st.toast(f"Updated '{title[:30]}'")
                st.rerun()

        with a2:
            label_bm = "Unbookmark" if job.get("bookmarked") else "Bookmark"
            if st.button(label_bm, key=f"bm_{jid}_{idx}", use_container_width=True):
                db = _get_db(config)
                db.toggle_bookmark(jid)
                db.close()
                _clear_caches()
                action_word = (
                    "Bookmarked" if not job.get("bookmarked") else "Unbookmarked"
                )
                st.toast(f"{action_word} '{title[:30]}'")
                st.rerun()

        with a3:
            if st.button(
                "Delete",
                key=f"del_{jid}_{idx}",
                type="secondary",
                use_container_width=True,
            ):
                db = _get_db(config)
                db.delete_job(jid)
                db.close()
                _clear_caches()
                st.toast(f"Deleted '{title[:30]}'")
                st.rerun()

        with a4:
            url = job.get("job_url")
            if url:
                st.link_button("Open", url, use_container_width=True)
            else:
                st.button(
                    "No URL",
                    disabled=True,
                    key=f"nourl_{jid}_{idx}",
                    use_container_width=True,
                )

        with a5:
            selected_set: set[str] = st.session_state.get("selected_jobs", set())
            cb = st.checkbox(
                "Select",
                value=jid in selected_set,
                key=f"sel_{jid}_{idx}",
            )
            if cb:
                st.session_state["selected_jobs"].add(jid)
            else:
                st.session_state["selected_jobs"].discard(jid)

        # ---- Expandable description ----
        desc = job.get("description") or ""
        if desc:
            with st.expander("View description"):
                st.markdown(desc[:5000], unsafe_allow_html=False)


# ═══════════════════════════════════════════════════════════════════════════
# Pagination
# ═══════════════════════════════════════════════════════════════════════════


def _render_pagination(total: int, position: str = "top") -> None:
    """Render previous/next page controls."""
    total_pages = max(1, (total + JOBS_PER_PAGE - 1) // JOBS_PER_PAGE)
    page: int = st.session_state.get("current_page", 0)
    if page >= total_pages:
        page = total_pages - 1
        st.session_state["current_page"] = page

    if total_pages <= 1:
        return

    c_prev, c_info, c_next = st.columns([1, 2, 1])
    with c_prev:
        if st.button(
            "Previous",
            disabled=page <= 0,
            use_container_width=True,
            key=f"pg_prev_{position}",
        ):
            st.session_state["current_page"] = max(0, page - 1)
            st.rerun()
    with c_info:
        st.markdown(
            f"<div style='text-align:center;padding-top:6px;'>"
            f"Page {page + 1} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button(
            "Next",
            disabled=page >= total_pages - 1,
            use_container_width=True,
            key=f"pg_next_{position}",
        ):
            st.session_state["current_page"] = min(total_pages - 1, page + 1)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# Analytics tab
# ═══════════════════════════════════════════════════════════════════════════


def _render_analytics(jobs: list[dict[str, Any]]) -> None:
    """Render charts and statistics about the job data."""
    if not jobs:
        st.info("No data available for analytics.")
        return

    df = pd.DataFrame(jobs)

    # Row 1: Score distribution | Jobs by site
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Score distribution")
        if "relevance_score" in df.columns:
            bins = pd.cut(
                df["relevance_score"],
                bins=[-10000, 0, SCORE_MED, SCORE_HIGH, 10000],
                labels=[
                    "Negative/0",
                    f"1 - {SCORE_MED}",
                    f"{SCORE_MED + 1} - {SCORE_HIGH}",
                    f"{SCORE_HIGH + 1}+",
                ],
            )
            dist = bins.value_counts().sort_index()
            st.bar_chart(dist)

    with col_b:
        st.subheader("Jobs by site")
        if "site" in df.columns:
            site_counts = df["site"].dropna().value_counts()
            if not site_counts.empty:
                st.bar_chart(site_counts)
            else:
                st.caption("No site data available.")

    # Row 2: Jobs over time | Top 10 companies
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("Jobs discovered over time")
        if "first_seen" in df.columns:
            df_ts = df.copy()
            df_ts["first_seen_dt"] = pd.to_datetime(
                df_ts["first_seen"], errors="coerce"
            )
            valid = df_ts["first_seen_dt"].notna()
            if valid.any():
                daily = (
                    df_ts.loc[valid]
                    .groupby(df_ts.loc[valid, "first_seen_dt"].dt.date)
                    .size()
                )
                daily.index = pd.to_datetime(daily.index)
                st.line_chart(daily)
            else:
                st.caption("No valid date data.")

    with col_d:
        st.subheader("Top 10 companies")
        if "company" in df.columns:
            top_co = df["company"].value_counts().head(10)
            st.bar_chart(top_co)

    # Row 3: Remote vs On-site | Job types
    col_e, col_f = st.columns(2)
    with col_e:
        st.subheader("Remote vs On-site")
        if "is_remote" in df.columns:
            remote_map = {True: "Remote", False: "On-site", None: "Unknown"}
            rc = df["is_remote"].map(remote_map).fillna("Unknown").value_counts()
            st.bar_chart(rc)

    with col_f:
        st.subheader("Job types")
        if "job_type" in df.columns:
            tc = df["job_type"].dropna().value_counts()
            if not tc.empty:
                st.bar_chart(tc)
            else:
                st.caption("No job type data.")


# ═══════════════════════════════════════════════════════════════════════════
# Database management tab
# ═══════════════════════════════════════════════════════════════════════════


def _render_db_management(jobs: list[dict[str, Any]], config: Config) -> None:
    """Render database stats, export options, and bulk operations."""
    stats = _fetch_statistics(str(config.database_path))

    st.subheader("Database overview")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total jobs", stats.get("total_jobs", 0))
    m2.metric("Seen today", stats.get("seen_today", 0))
    m3.metric("New today", stats.get("new_today", 0))
    m4.metric("Applied", stats.get("applied", 0))
    m5.metric("Avg score", stats.get("avg_relevance_score", 0))

    st.markdown("---")

    # ---- Export ----
    st.subheader("Export")
    ex1, ex2 = st.columns(2)

    with ex1:
        if st.button("Generate CSV export", key="db_csv"):
            db = _get_db(config)
            export_df = db.export_to_dataframe()
            db.close()
            if export_df.empty:
                st.warning("Database is empty.")
            else:
                csv = export_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download full CSV",
                    csv,
                    file_name=f"jobs_full_{date.today().isoformat()}.csv",
                    mime="text/csv",
                    key="dl_full_csv",
                )

    with ex2:
        if st.button("Generate Excel export", key="db_xlsx"):
            db = _get_db(config)
            export_df = db.export_to_dataframe()
            db.close()
            if export_df.empty:
                st.warning("Database is empty.")
            else:
                buf = BytesIO()
                export_df.to_excel(buf, index=False, engine="openpyxl")
                st.download_button(
                    "Download Excel",
                    buf.getvalue(),
                    file_name=f"jobs_full_{date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_full_xlsx",
                )

    st.markdown("---")

    # ---- Bulk operations ----
    st.subheader("Bulk operations")
    selected: set[str] = st.session_state.get("selected_jobs", set())

    if selected:
        st.info(f"{len(selected)} job(s) selected.")
        b1, b2, b3 = st.columns(3)

        with b1:
            if st.button(
                f"Delete {len(selected)} selected",
                type="primary",
                key="bulk_del",
            ):
                db = _get_db(config)
                count = db.delete_jobs(list(selected))
                db.close()
                st.session_state["selected_jobs"] = set()
                _clear_caches()
                st.toast(f"Deleted {count} job(s)")
                st.rerun()

        with b2:
            if st.button(f"Mark {len(selected)} applied", key="bulk_apply"):
                db = _get_db(config)
                for jid in selected:
                    db.mark_as_applied(jid)
                db.close()
                st.session_state["selected_jobs"] = set()
                _clear_caches()
                st.toast(f"Marked {len(selected)} job(s) as applied")
                st.rerun()

        with b3:
            if st.button("Clear selection", key="bulk_clear"):
                st.session_state["selected_jobs"] = set()
                st.rerun()
    else:
        st.caption(
            "Select jobs using the checkboxes on job cards to enable bulk operations."
        )

    st.markdown("---")

    # ---- Danger zone ----
    st.subheader("Danger zone")
    with st.expander("Delete ALL jobs"):
        st.warning(
            "This will permanently remove every job from the database. "
            "This action cannot be undone."
        )
        confirm_text = st.text_input(
            'Type "DELETE" to confirm',
            key="confirm_delete_all",
        )
        if st.button(
            "Delete all jobs",
            type="primary",
            disabled=confirm_text != "DELETE",
            key="btn_delete_all",
        ):
            db = _get_db(config)
            all_ids = [j["job_id"] for j in jobs]
            if all_ids:
                db.delete_jobs(all_ids)
            db.close()
            _clear_caches()
            st.toast("All jobs deleted.")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Entry point for the Streamlit dashboard."""
    st.markdown(_CSS, unsafe_allow_html=True)
    _init_session_state()

    # ---- Load configuration ----
    try:
        config = _load_config_cached()
    except Exception as exc:
        st.error(f"Failed to load configuration: {exc}")
        st.info(
            "Ensure `config/settings.yaml` exists. "
            "Copy `config/settings.example.yaml` as a starting point."
        )
        return

    # ---- Check database ----
    db_path = config.database_path
    if not db_path.exists():
        st.warning("No database found. Run a job search first to populate data.")
        st.code("python scripts/main.py", language="bash")
        return

    # ---- Fetch jobs ----
    all_jobs = _fetch_all_jobs(str(db_path))
    if not all_jobs:
        st.info("The database is empty. Run a job search to populate it.")
        st.code("python scripts/main.py", language="bash")
        return

    # ── Header ──────────────────────────────────────────────────────────
    st.markdown("## Job Search Hub")

    # ── Semantic search bar ─────────────────────────────────────────────
    vs_available: bool = (
        VECTOR_AVAILABLE
        and config.vector_search.enabled
        and _get_vector_store_cached(
            str(config.data_path),
            config.vector_search.model_name,
        )
        is not None
    )

    query: str = st.text_input(
        "Search jobs by meaning...",
        placeholder="e.g. remote python backend distributed systems",
        key="search_query_input",
    )

    if query.strip():
        if vs_available:
            display_jobs = _apply_semantic_search(query.strip(), all_jobs, config)
            if not display_jobs:
                st.info("No semantic matches. Showing all jobs instead.")
                display_jobs = all_jobs
        else:
            # Fallback: simple substring match
            if VECTOR_AVAILABLE:
                st.info(
                    "Semantic search index is empty or unavailable. Using text filter."
                )
            else:
                st.info(
                    "Semantic search unavailable (install chromadb + "
                    "sentence-transformers). Using text filter."
                )
            q_lower = query.strip().lower()
            display_jobs = [
                j
                for j in all_jobs
                if q_lower in (j.get("title") or "").lower()
                or q_lower in (j.get("company") or "").lower()
                or q_lower in (j.get("description") or "").lower()
                or q_lower in (j.get("location") or "").lower()
            ]
            if not display_jobs:
                st.info("No text matches. Showing all jobs.")
                display_jobs = all_jobs
    else:
        # Default: sort by relevance score
        display_jobs = sorted(
            all_jobs,
            key=lambda j: j.get("relevance_score", 0),
            reverse=True,
        )

    # ── Sidebar filters ────────────────────────────────────────────────
    filtered_jobs = _render_sidebar(display_jobs, config)

    # ── Summary bar ────────────────────────────────────────────────────
    total_filtered = len(filtered_jobs)
    sum_cols = st.columns([2, 1, 1, 1])
    sum_cols[0].markdown(f"**{total_filtered}** jobs matching filters")
    sum_cols[1].caption(f"Total in DB: {len(all_jobs)}")
    sel_count = len(st.session_state.get("selected_jobs", set()))
    if sel_count:
        sum_cols[2].caption(f"Selected: {sel_count}")
    if query.strip() and vs_available:
        sum_cols[3].caption("Sorted by semantic similarity")

    # ── Tabs ───────────────────────────────────────────────────────────
    tab_jobs, tab_analytics, tab_db = st.tabs(["Jobs", "Analytics", "Database"])

    with tab_jobs:
        if not filtered_jobs:
            st.info("No jobs match the current filters. Try adjusting your criteria.")
        else:
            _render_pagination(total_filtered, position="top")

            page = st.session_state.get("current_page", 0)
            start = page * JOBS_PER_PAGE
            end = min(start + JOBS_PER_PAGE, total_filtered)

            for i, job in enumerate(filtered_jobs[start:end]):
                _render_job_card(job, start + i, config)

            _render_pagination(total_filtered, position="bottom")

    with tab_analytics:
        _render_analytics(filtered_jobs)

    with tab_db:
        _render_db_management(all_jobs, config)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
else:
    # Invoked via `streamlit run scripts/dashboard.py`
    main()
