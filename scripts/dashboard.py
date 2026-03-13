#!/usr/bin/env python3
"""
Job Search Tool - Interactive Dashboard.

A Streamlit-based dashboard for analyzing and filtering job search results.
Provides tabbed navigation (Jobs, Analytics, Database), advanced filtering,
score-based color coding, and export capabilities.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration -- MUST be the first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Job Search Dashboard",
    page_icon="briefcase",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILTER_OPTIONS: int = 100
TABLE_HEIGHT: int = 600
SCORE_HIGH_THRESHOLD: int = 50
SCORE_MEDIUM_THRESHOLD: int = 25
JOBS_PER_PAGE: int = 50
TOP_COMPANIES_LIMIT: int = 15

# ---------------------------------------------------------------------------
# Base directory resolution
# ---------------------------------------------------------------------------

_script_dir: Path = Path(__file__).resolve().parent
if _script_dir.name == "scripts":
    BASE_DIR: Path = _script_dir.parent
else:
    BASE_DIR = _script_dir
    while BASE_DIR != BASE_DIR.parent:
        if (BASE_DIR / "config").exists() or (BASE_DIR / "results").exists():
            break
        BASE_DIR = BASE_DIR.parent

if str(BASE_DIR).startswith("/app"):
    BASE_DIR = Path("/app")

RESULTS_DIR: Path = BASE_DIR / "results"
DATA_DIR: Path = BASE_DIR / "data"
DATABASE_PATH: Path = DATA_DIR / "jobs.db"

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

_CUSTOM_CSS: str = """
<style>
    /* Tighten default Streamlit padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 1rem;
    }

    /* Header area */
    .dashboard-header {
        padding-bottom: 0.25rem;
        border-bottom: 2px solid #e0e0e0;
        margin-bottom: 1.25rem;
    }
    .dashboard-header h1 {
        margin-bottom: 0;
    }
    .dashboard-header p {
        color: #6b7280;
        margin-top: 0;
        font-size: 0.95rem;
    }

    /* Score badges */
    .score-high {
        background-color: #dcfce7;
        color: #166534;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .score-medium {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .score-low {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
    }

    /* Sidebar filter count */
    .filter-count {
        font-size: 0.8rem;
        color: #6366f1;
        font-weight: 600;
    }

    /* Table tweaks */
    [data-testid="stDataFrame"] th {
        background-color: #f1f5f9 !important;
    }

    /* Stat card in Database tab */
    .stat-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .stat-card h3 {
        margin: 0;
        font-size: 1.6rem;
        color: #1e293b;
    }
    .stat-card p {
        margin: 0;
        color: #64748b;
        font-size: 0.85rem;
    }
</style>
"""


# =============================================================================
# DATA LOADING
# =============================================================================


@st.cache_data(ttl=60)
def load_csv_files() -> dict[str, pd.DataFrame]:
    """Load all CSV files from the results directory.

    Returns:
        Mapping of filename to DataFrame, sorted newest first.
    """
    csv_files: dict[str, pd.DataFrame] = {}
    if RESULTS_DIR.exists():
        for csv_file in sorted(RESULTS_DIR.glob("*.csv"), reverse=True):
            try:
                csv_files[csv_file.name] = pd.read_csv(csv_file)
            except Exception as e:
                st.error(f"Error loading {csv_file.name}: {e}")
    return csv_files


@st.cache_data(ttl=60)
def load_database() -> pd.DataFrame | None:
    """Load all jobs from the SQLite database.

    Returns:
        DataFrame with all jobs, or None if unavailable.
    """
    if not DATABASE_PATH.exists():
        return None
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            df = pd.read_sql_query("SELECT * FROM jobs", conn)
        return df
    except Exception as e:
        st.error(f"Error loading database: {e}")
        return None


@st.cache_data(ttl=60)
def load_database_statistics() -> dict[str, Any] | None:
    """Load summary statistics directly from the database.

    Returns:
        Dict of statistics or None if database is unavailable.
    """
    if not DATABASE_PATH.exists():
        return None
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.cursor()
            stats: dict[str, Any] = {}

            cur.execute("SELECT COUNT(*) FROM jobs")
            stats["total_jobs"] = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM jobs WHERE first_seen = ?",
                (date.today().isoformat(),),
            )
            stats["new_today"] = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM jobs WHERE last_seen = ?",
                (date.today().isoformat(),),
            )
            stats["seen_today"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM jobs WHERE applied = 1")
            stats["applied"] = cur.fetchone()[0]

            cur.execute("SELECT AVG(relevance_score) FROM jobs")
            avg = cur.fetchone()[0]
            stats["avg_score"] = round(avg, 1) if avg else 0.0

            cur.execute("SELECT MAX(relevance_score) FROM jobs")
            mx = cur.fetchone()[0]
            stats["max_score"] = mx if mx else 0

            cur.execute("SELECT MIN(first_seen) FROM jobs")
            stats["oldest_entry"] = cur.fetchone()[0]

            cur.execute("SELECT MAX(last_seen) FROM jobs")
            stats["latest_update"] = cur.fetchone()[0]

            # DB file size
            stats["db_size_mb"] = round(DATABASE_PATH.stat().st_size / (1024 * 1024), 2)

        return stats
    except Exception as e:
        st.error(f"Error loading database statistics: {e}")
        return None


def get_unique_values(df: pd.DataFrame, column: str) -> list[str]:
    """Return sorted unique non-null string values from *column*.

    Args:
        df: Source DataFrame.
        column: Column name.

    Returns:
        Sorted list of unique string values.
    """
    if column not in df.columns:
        return []
    values = df[column].dropna().unique().tolist()
    return sorted([str(v) for v in values if v and str(v).strip()])


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert date columns once and ensure consistent types.

    Args:
        df: Raw DataFrame (from CSV or DB).

    Returns:
        DataFrame with parsed date columns.
    """
    df = df.copy()
    for col in ("date_posted", "first_seen", "last_seen"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "relevance_score" in df.columns:
        df["relevance_score"] = (
            pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0).astype(int)
        )
    return df


# =============================================================================
# FILTERING
# =============================================================================


def apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """Apply all active filters to the DataFrame.

    Args:
        df: Input DataFrame.
        filters: Dict of filter name to value.

    Returns:
        Filtered DataFrame.
    """
    out = df.copy()

    # Text search
    if filters.get("search_text"):
        term = filters["search_text"].lower()
        mask = (
            out["title"].fillna("").str.lower().str.contains(term, regex=False)
            | out["company"].fillna("").str.lower().str.contains(term, regex=False)
            | out["description"].fillna("").str.lower().str.contains(term, regex=False)
        )
        out = out[mask]

    # Multiselect filters (column, keep-nulls flag)
    _multi_filters: list[tuple[str, str, bool]] = [
        ("sites", "site", False),
        ("job_levels", "job_level", True),
        ("job_types", "job_type", True),
        ("companies", "company", False),
    ]
    for key, col, keep_null in _multi_filters:
        vals = filters.get(key)
        if vals and col in out.columns:
            if keep_null:
                out = out[out[col].fillna("").isin(vals) | out[col].isna()]
            else:
                out = out[out[col].isin(vals)]

    # Location text filter
    if filters.get("locations") and "location" in out.columns:
        loc_terms = filters["locations"]
        out = out[
            out["location"]
            .fillna("")
            .apply(lambda x: any(t.lower() in str(x).lower() for t in loc_terms))
        ]

    # Remote only
    if filters.get("remote_only") and "is_remote" in out.columns:
        out = out[out["is_remote"].fillna(False).astype(bool)]

    # Salary
    if filters.get("min_salary") and "min_amount" in out.columns:
        out = out[
            (out["min_amount"].fillna(0) >= filters["min_salary"])
            | out["min_amount"].isna()
        ]
    if filters.get("max_salary") and "max_amount" in out.columns:
        out = out[
            (out["max_amount"].fillna(float("inf")) <= filters["max_salary"])
            | out["max_amount"].isna()
        ]

    # Relevance score
    if filters.get("min_score") and "relevance_score" in out.columns:
        out = out[out["relevance_score"].fillna(0) >= filters["min_score"]]

    # Date filter
    if filters.get("date_from") and "date_posted" in out.columns:
        out = out[
            (out["date_posted"] >= pd.to_datetime(filters["date_from"]))
            | out["date_posted"].isna()
        ]

    # Hide applied
    if filters.get("hide_applied") and "applied" in out.columns:
        out = out[~out["applied"].fillna(False).astype(bool)]

    return out


def count_active_filters(filters: dict[str, Any], df: pd.DataFrame) -> int:
    """Count the number of currently active (non-default) filters.

    Args:
        filters: Current filter dict.
        df: Original unfiltered DataFrame.

    Returns:
        Number of active filters.
    """
    count = 0
    if filters.get("search_text"):
        count += 1
    if filters.get("min_score"):
        count += 1
    if filters.get("remote_only"):
        count += 1
    if filters.get("hide_applied"):
        count += 1
    if filters.get("min_salary"):
        count += 1
    if filters.get("max_salary"):
        count += 1
    if filters.get("date_from"):
        count += 1
    if filters.get("locations"):
        count += 1
    # Multiselect: active if user deselected something
    for key, col in [
        ("sites", "site"),
        ("job_levels", "job_level"),
        ("job_types", "job_type"),
        ("companies", "company"),
    ]:
        vals = filters.get(key)
        if vals is not None:
            all_vals = get_unique_values(df, col)
            if vals and set(vals) != set(all_vals):
                count += 1
    return count


# =============================================================================
# SIDEBAR
# =============================================================================


def _render_multiselect_filter(
    df: pd.DataFrame,
    column: str,
    label: str,
    *,
    default_all: bool = True,
    help_text: str = "",
) -> list[str] | None:
    """Render a multiselect sidebar filter, de-duplicating the pattern.

    Args:
        df: Source DataFrame.
        column: Column to extract options from.
        label: Display label for the widget.
        default_all: Whether all options are selected by default.
        help_text: Tooltip text.

    Returns:
        List of selected values, or None if column missing / no options.
    """
    if column not in df.columns:
        return None
    options = get_unique_values(df, column)
    if not options:
        return None
    options = options[:MAX_FILTER_OPTIONS]
    default = options if default_all else []
    return st.sidebar.multiselect(
        label, options=options, default=default, help=help_text
    )


def render_sidebar_filters(df: pd.DataFrame) -> dict[str, Any]:
    """Build the sidebar filter panel and return current filter values.

    Args:
        df: Unfiltered DataFrame (used to derive filter options).

    Returns:
        Dict of filter key to value.
    """
    filters: dict[str, Any] = {}

    # -- Search -----------------------------------------------------------
    st.sidebar.markdown("### Search")
    filters["search_text"] = st.sidebar.text_input(
        "Keyword search",
        placeholder="Title, company, or description...",
        help="Case-insensitive search across title, company, and description",
    )

    # -- Relevance --------------------------------------------------------
    if "relevance_score" in df.columns:
        st.sidebar.markdown("### Relevance")
        max_score = (
            int(df["relevance_score"].max())
            if not df["relevance_score"].isna().all()
            else 100
        )
        filters["min_score"] = st.sidebar.slider(
            "Minimum score",
            min_value=0,
            max_value=max(max_score, 1),
            value=0,
            help="Show only jobs at or above this relevance score",
        )

    # -- Source & Type ----------------------------------------------------
    st.sidebar.markdown("### Source & Type")
    filters["sites"] = _render_multiselect_filter(
        df, "site", "Job sites", help_text="Filter by job board"
    )
    filters["job_types"] = _render_multiselect_filter(
        df,
        "job_type",
        "Job type",
        default_all=False,
        help_text="fulltime, contract, etc.",
    )
    filters["job_levels"] = _render_multiselect_filter(
        df,
        "job_level",
        "Job level",
        default_all=False,
        help_text="entry, mid, senior (LinkedIn)",
    )

    # -- Location ---------------------------------------------------------
    st.sidebar.markdown("### Location")
    if "is_remote" in df.columns:
        filters["remote_only"] = st.sidebar.checkbox(
            "Remote only", help="Show only remote positions"
        )
    loc_text = st.sidebar.text_input(
        "Location contains", placeholder="e.g. Zurich, Geneva..."
    )
    if loc_text:
        filters["locations"] = [loc_text]

    # -- Salary -----------------------------------------------------------
    if "min_amount" in df.columns or "max_amount" in df.columns:
        with st.sidebar.expander("Salary range"):
            c1, c2 = st.columns(2)
            with c1:
                filters["min_salary"] = st.number_input(
                    "Min", min_value=0, value=0, step=10000
                )
            with c2:
                val = st.number_input("Max (0 = any)", min_value=0, value=0, step=10000)
                filters["max_salary"] = val if val > 0 else None

    # -- Company ----------------------------------------------------------
    if "company" in df.columns:
        with st.sidebar.expander("Company"):
            companies = get_unique_values(df, "company")[:MAX_FILTER_OPTIONS]
            if companies:
                sel = st.multiselect("Select companies", options=companies)
                if sel:
                    filters["companies"] = sel

    # -- Date -------------------------------------------------------------
    if "date_posted" in df.columns:
        with st.sidebar.expander("Date posted"):
            filters["date_from"] = st.date_input(
                "From", value=None, help="Jobs posted on or after this date"
            )

    # -- Applied ----------------------------------------------------------
    if "applied" in df.columns:
        filters["hide_applied"] = st.sidebar.checkbox("Hide applied jobs")

    # -- Reset button & active count --------------------------------------
    st.sidebar.markdown("---")
    active = count_active_filters(filters, df)
    if active > 0:
        st.sidebar.markdown(
            f'<p class="filter-count">{active} filter(s) active</p>',
            unsafe_allow_html=True,
        )
    if st.sidebar.button("Reset filters"):
        st.query_params.clear()
        st.rerun()

    return filters


# =============================================================================
# JOBS TAB
# =============================================================================


def _score_badge(score: int) -> str:
    """Return an HTML score badge with color coding.

    Args:
        score: Relevance score.

    Returns:
        HTML string for the badge.
    """
    if score >= SCORE_HIGH_THRESHOLD:
        cls = "score-high"
    elif score >= SCORE_MEDIUM_THRESHOLD:
        cls = "score-medium"
    else:
        cls = "score-low"
    return f'<span class="{cls}">{score}</span>'


def render_jobs_tab(df: pd.DataFrame, filtered_df: pd.DataFrame) -> None:
    """Render the Jobs tab content.

    Args:
        df: Unfiltered DataFrame (for delta calculations).
        filtered_df: Filtered DataFrame to display.
    """
    # -- Key metrics ------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        delta = None
        if len(filtered_df) != len(df):
            delta = f"{len(filtered_df) - len(df)} filtered"
        st.metric("Total jobs", len(filtered_df), delta=delta)

    with col2:
        if "relevance_score" in filtered_df.columns and len(filtered_df) > 0:
            avg = filtered_df["relevance_score"].mean()
            st.metric("Avg score", f"{avg:.1f}" if pd.notna(avg) else "N/A")
        else:
            st.metric("Avg score", "N/A")

    with col3:
        if "first_seen" in filtered_df.columns and len(filtered_df) > 0:
            today = pd.Timestamp(date.today())
            new_today = int((filtered_df["first_seen"] == today).sum())
            st.metric("New today", new_today)
        elif "date_posted" in filtered_df.columns and len(filtered_df) > 0:
            today = pd.Timestamp(date.today())
            new_today = int((filtered_df["date_posted"] == today).sum())
            st.metric("Posted today", new_today)
        else:
            st.metric("New today", "N/A")

    with col4:
        if "relevance_score" in filtered_df.columns and len(filtered_df) > 0:
            top = int(filtered_df["relevance_score"].max())
            st.metric("Top score", top)
        else:
            st.metric("Top score", "N/A")

    st.markdown("")  # spacer

    # -- Empty state ------------------------------------------------------
    if len(filtered_df) == 0:
        st.info("No jobs match the current filters. Try broadening your criteria.")
        return

    # -- Sort controls ----------------------------------------------------
    available_columns = filtered_df.columns.tolist()
    default_display = [
        c
        for c in [
            "title",
            "company",
            "location",
            "relevance_score",
            "site",
            "job_level",
            "job_type",
            "date_posted",
            "is_remote",
            "job_url",
        ]
        if c in available_columns
    ]

    with st.expander("Configure columns"):
        selected_columns: list[str] = st.multiselect(
            "Columns to display",
            options=available_columns,
            default=default_display,
        )
    if not selected_columns:
        selected_columns = default_display

    # Ensure job_url present for link rendering
    display_cols = list(selected_columns)
    if "job_url" in filtered_df.columns and "job_url" not in display_cols:
        display_cols.append("job_url")
    # Ensure job_id present for applied toggle
    if "job_id" in filtered_df.columns and "job_id" not in display_cols:
        display_cols.append("job_id")

    sc1, sc2 = st.columns([3, 1])
    with sc1:
        sort_col = st.selectbox(
            "Sort by",
            options=selected_columns,
            index=selected_columns.index("relevance_score")
            if "relevance_score" in selected_columns
            else 0,
        )
    with sc2:
        sort_asc = st.selectbox("Order", ["Descending", "Ascending"]) == "Ascending"

    sorted_df = (
        filtered_df[display_cols]
        .sort_values(by=sort_col, ascending=sort_asc, na_position="last")
        .reset_index(drop=True)
    )

    # -- Data table -------------------------------------------------------
    column_config: dict[str, Any] = {
        "job_url": st.column_config.LinkColumn(
            "Job link", display_text="Open", help="Open posting"
        ),
        "job_url_direct": st.column_config.LinkColumn(
            "Direct link", display_text="Direct"
        ),
        "company_url": st.column_config.LinkColumn("Company", display_text="Company"),
        "relevance_score": st.column_config.ProgressColumn(
            "Score", min_value=0, max_value=100
        ),
        "is_remote": st.column_config.CheckboxColumn("Remote"),
        "min_amount": st.column_config.NumberColumn("Min salary", format="$%d"),
        "max_amount": st.column_config.NumberColumn("Max salary", format="$%d"),
    }

    st.dataframe(
        sorted_df,
        use_container_width=True,
        height=TABLE_HEIGHT,
        column_config=column_config,
        hide_index=True,
    )

    # -- Mark as applied --------------------------------------------------
    if (
        "applied" in filtered_df.columns
        and "job_id" in filtered_df.columns
        and DATABASE_PATH.exists()
    ):
        with st.expander("Mark as applied"):
            job_options = [
                f"{r['title']}  --  {r['company']}"
                for _, r in sorted_df.head(JOBS_PER_PAGE).iterrows()
                if pd.notna(r.get("title"))
            ]
            if job_options:
                sel_idx = st.selectbox(
                    "Select job",
                    range(len(job_options)),
                    format_func=lambda i: job_options[i],
                )
                if sel_idx is not None and st.button("Toggle applied"):
                    job_id = sorted_df.iloc[sel_idx].get("job_id")
                    if job_id:
                        try:
                            with sqlite3.connect(DATABASE_PATH) as conn:
                                cur = conn.cursor()
                                cur.execute(
                                    "SELECT applied FROM jobs WHERE job_id = ?",
                                    (str(job_id),),
                                )
                                row = cur.fetchone()
                                if row is not None:
                                    new_val = 0 if row[0] else 1
                                    cur.execute(
                                        "UPDATE jobs SET applied = ? WHERE job_id = ?",
                                        (new_val, str(job_id)),
                                    )
                                    conn.commit()
                                    st.success(
                                        "Applied status toggled. Refresh to see changes."
                                    )
                                    st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Failed to update: {e}")

    # -- Job detail viewer ------------------------------------------------
    with st.expander("Job details"):
        if len(sorted_df) == 0:
            st.info("No jobs to display.")
        else:
            detail_options = [
                f"{r.get('title', 'N/A')}  @  {r.get('company', 'N/A')}"
                for _, r in sorted_df.head(JOBS_PER_PAGE).iterrows()
            ]
            chosen = st.selectbox(
                "Select a job",
                range(len(detail_options)),
                format_func=lambda i: detail_options[i],
            )
            if chosen is not None:
                job = sorted_df.iloc[chosen]
                _render_job_detail(job)

    # -- Export -----------------------------------------------------------
    st.markdown("---")
    _render_export(sorted_df)


def _render_job_detail(job: pd.Series) -> None:
    """Render a single job's detail card.

    Args:
        job: A row from the jobs DataFrame.
    """
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"### {job.get('title', 'N/A')}")
        st.markdown(f"**Company:** {job.get('company', 'N/A')}")
        st.markdown(f"**Location:** {job.get('location', 'N/A')}")
        if pd.notna(job.get("job_url")):
            st.markdown(f"[View job posting]({job['job_url']})")
    with c2:
        if "relevance_score" in job.index and pd.notna(job["relevance_score"]):
            score = int(job["relevance_score"])
            st.markdown(f"**Score:** {_score_badge(score)}", unsafe_allow_html=True)
        for field, label in [
            ("job_level", "Level"),
            ("job_type", "Type"),
            ("site", "Source"),
        ]:
            if field in job.index and pd.notna(job.get(field)):
                st.markdown(f"**{label}:** {job[field]}")

    # Salary
    parts: list[str] = []
    if pd.notna(job.get("min_amount")):
        parts.append(f"${int(job['min_amount']):,}")
    if pd.notna(job.get("max_amount")):
        parts.append(f"${int(job['max_amount']):,}")
    if parts:
        salary = " - ".join(parts)
        if pd.notna(job.get("currency")):
            salary += f" {job['currency']}"
        if pd.notna(job.get("interval")):
            salary += f" ({job['interval']})"
        st.markdown(f"**Salary:** {salary}")

    if "description" in job.index and pd.notna(job.get("description")):
        with st.expander("Job description", expanded=False):
            st.markdown(job["description"])


# =============================================================================
# ANALYTICS TAB
# =============================================================================


def render_analytics_tab(filtered_df: pd.DataFrame) -> None:
    """Render the Analytics tab with charts and breakdowns.

    Args:
        filtered_df: Filtered DataFrame.
    """
    if len(filtered_df) == 0:
        st.info("No data available for analytics. Adjust filters or load data first.")
        return

    # -- Row 1: Score distribution + Jobs by site -------------------------
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Score distribution")
        if "relevance_score" in filtered_df.columns:
            hist_data = filtered_df["relevance_score"].dropna()
            if len(hist_data) > 0:
                bins = pd.cut(hist_data, bins=10)
                bin_counts = bins.value_counts().sort_index()
                chart_df = pd.DataFrame(
                    {"range": bin_counts.index.astype(str), "count": bin_counts.values}
                )
                chart_df = chart_df.set_index("range")
                st.bar_chart(chart_df)
            else:
                st.caption("No score data available.")
        else:
            st.caption("No relevance_score column in data.")

    with c2:
        st.markdown("#### Jobs by site")
        if "site" in filtered_df.columns:
            site_counts = filtered_df["site"].value_counts()
            if len(site_counts) > 0:
                st.bar_chart(site_counts)
            else:
                st.caption("No site data available.")
        else:
            st.caption("No site column in data.")

    st.markdown("")

    # -- Row 2: Jobs over time + Top companies ----------------------------
    c3, c4 = st.columns(2)

    with c3:
        st.markdown("#### Jobs over time")
        date_col = "date_posted" if "date_posted" in filtered_df.columns else None
        if date_col is None and "first_seen" in filtered_df.columns:
            date_col = "first_seen"
        if date_col and len(filtered_df) > 0:
            time_df = filtered_df[[date_col]].dropna().copy()
            if len(time_df) > 0:
                time_df[date_col] = pd.to_datetime(time_df[date_col], errors="coerce")
                time_df = time_df.dropna()
                if len(time_df) > 0:
                    time_df["date"] = time_df[date_col].dt.date
                    daily = time_df.groupby("date").size().reset_index(name="jobs")
                    daily = daily.set_index("date").sort_index()
                    st.line_chart(daily)
                else:
                    st.caption("No valid dates to chart.")
            else:
                st.caption("No date data available.")
        else:
            st.caption("No date column in data.")

    with c4:
        st.markdown("#### Top companies")
        if "company" in filtered_df.columns:
            company_counts = (
                filtered_df["company"].value_counts().head(TOP_COMPANIES_LIMIT)
            )
            if len(company_counts) > 0:
                st.bar_chart(company_counts)
            else:
                st.caption("No company data.")
        else:
            st.caption("No company column in data.")

    st.markdown("")

    # -- Row 3: Breakdowns ------------------------------------------------
    c5, c6 = st.columns(2)

    with c5:
        st.markdown("#### Job type breakdown")
        if "job_type" in filtered_df.columns:
            type_counts = filtered_df["job_type"].value_counts()
            if len(type_counts) > 0:
                st.dataframe(type_counts.rename("count"), use_container_width=True)
            else:
                st.caption("No job type data.")

    with c6:
        st.markdown("#### Job level breakdown")
        if "job_level" in filtered_df.columns:
            level_counts = filtered_df["job_level"].value_counts()
            if len(level_counts) > 0:
                st.dataframe(level_counts.rename("count"), use_container_width=True)
            else:
                st.caption("No job level data.")

    # -- Remote vs on-site ------------------------------------------------
    if "is_remote" in filtered_df.columns:
        st.markdown("#### Remote vs On-site")
        remote_counts = (
            filtered_df["is_remote"]
            .map({True: "Remote", False: "On-site", None: "Unknown"})
            .fillna("Unknown")
            .value_counts()
        )
        st.bar_chart(remote_counts)


# =============================================================================
# DATABASE TAB
# =============================================================================


def render_database_tab(db_df: pd.DataFrame | None) -> None:
    """Render the Database tab with stats, health, and export.

    Args:
        db_df: DataFrame loaded from database, or None.
    """
    if db_df is None:
        st.info("No database found. Run a job search first to populate the database.")
        st.caption(f"Expected path: `{DATABASE_PATH}`")
        return

    # -- Statistics -------------------------------------------------------
    stats = load_database_statistics()

    st.markdown("#### Database overview")
    if stats:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total jobs", stats["total_jobs"])
        with c2:
            st.metric("New today", stats["new_today"])
        with c3:
            st.metric("Applied", stats["applied"])
        with c4:
            st.metric("Avg score", stats["avg_score"])

        st.markdown("")
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.metric("Top score", stats["max_score"])
        with c6:
            st.metric("Seen today", stats["seen_today"])
        with c7:
            st.metric("DB size", f"{stats['db_size_mb']} MB")
        with c8:
            st.metric("Last update", str(stats.get("latest_update", "N/A")))
    else:
        st.warning("Could not load database statistics.")

    st.markdown("---")

    # -- Health info ------------------------------------------------------
    st.markdown("#### Database health")
    health_items: list[str] = []
    if DATABASE_PATH.exists():
        health_items.append(f"Path: `{DATABASE_PATH}`")
        health_items.append(f"File size: {DATABASE_PATH.stat().st_size / 1024:.1f} KB")
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check")
                integrity = cur.fetchone()[0]
                health_items.append(f"Integrity check: **{integrity}**")
                cur.execute("PRAGMA journal_mode")
                jmode = cur.fetchone()[0]
                health_items.append(f"Journal mode: **{jmode}**")
        except Exception as e:
            health_items.append(f"Health check error: {e}")
    else:
        health_items.append("Database file does not exist.")

    for item in health_items:
        st.markdown(f"- {item}")

    st.markdown("---")

    # -- Export -----------------------------------------------------------
    st.markdown("#### Export")
    _render_export(db_df)


# =============================================================================
# SHARED COMPONENTS
# =============================================================================


def _render_export(df: pd.DataFrame) -> None:
    """Render CSV and Excel download buttons.

    Args:
        df: DataFrame to export.
    """
    if len(df) == 0:
        st.caption("No data to export.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    c1, c2 = st.columns(2)

    with c1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"jobs_{ts}.csv",
            mime="text/csv",
        )

    with c2:
        try:
            buf = BytesIO()
            df.to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                label="Download Excel",
                data=buf.getvalue(),
                file_name=f"jobs_{ts}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except ImportError:
            st.caption("Excel export requires openpyxl.")


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Main dashboard entry point."""
    # Inject custom CSS
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    # -- Header -----------------------------------------------------------
    st.markdown(
        '<div class="dashboard-header">'
        "<h1>Job Search Dashboard</h1>"
        "<p>Browse, filter, and analyze your aggregated job search results.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # -- Data source selection --------------------------------------------
    st.sidebar.markdown("## Data source")

    csv_files = load_csv_files()
    db_data = load_database()

    data_sources: list[str] = []
    if db_data is not None:
        data_sources.append("Database: jobs.db")
    if csv_files:
        data_sources.extend([f"CSV: {name}" for name in csv_files])

    if not data_sources:
        st.warning("No data found. Run a job search first to generate results.")
        st.code(
            "docker-compose up --build\n# or\ncd scripts && python main.py",
            language="bash",
        )
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()
        with st.expander("Debug info"):
            st.text(f"BASE_DIR:      {BASE_DIR}")
            st.text(f"RESULTS_DIR:   {RESULTS_DIR}  (exists: {RESULTS_DIR.exists()})")
            st.text(
                f"DATABASE_PATH: {DATABASE_PATH}  (exists: {DATABASE_PATH.exists()})"
            )
            if RESULTS_DIR.exists():
                st.text(f"Result files:  {[f.name for f in RESULTS_DIR.glob('*')]}")
        return

    selected_source: str = st.sidebar.selectbox(
        "Source", options=data_sources, help="Choose which dataset to explore"
    )

    is_db_source = selected_source.startswith("Database")
    if is_db_source:
        raw_df = db_data
        assert raw_df is not None
    else:
        csv_name = selected_source.replace("CSV: ", "")
        raw_df = csv_files[csv_name]

    st.sidebar.caption(f"{len(raw_df)} jobs loaded")

    # Prepare dates once
    df = prepare_dataframe(raw_df)

    # -- Sidebar filters --------------------------------------------------
    st.sidebar.markdown("---")
    filters = render_sidebar_filters(df)
    filtered_df = apply_filters(df, filters)

    # -- Sidebar footer ---------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

    # -- Tabs -------------------------------------------------------------
    tab_jobs, tab_analytics, tab_database = st.tabs(["Jobs", "Analytics", "Database"])

    with tab_jobs:
        render_jobs_tab(df, filtered_df)

    with tab_analytics:
        render_analytics_tab(filtered_df)

    with tab_database:
        render_database_tab(db_data)


if __name__ == "__main__":
    main()
