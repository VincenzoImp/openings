#!/usr/bin/env python3
"""
Job Search Tool - Interactive Dashboard.

A Streamlit-based dashboard for analyzing and filtering job search results.
Provides filtering, sorting, statistics, and export capabilities.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Base directory configuration
# Handle both local execution and Docker/Streamlit execution
_script_dir = Path(__file__).resolve().parent
if _script_dir.name == "scripts":
    # Running from scripts directory (normal case)
    BASE_DIR = _script_dir.parent
else:
    # Fallback: try to find project root by looking for config directory
    BASE_DIR = _script_dir
    while BASE_DIR != BASE_DIR.parent:
        if (BASE_DIR / "config").exists() or (BASE_DIR / "results").exists():
            break
        BASE_DIR = BASE_DIR.parent

# Docker fallback: if we're in /app/scripts, BASE_DIR should be /app
if str(BASE_DIR).startswith("/app"):
    BASE_DIR = Path("/app")

RESULTS_DIR = BASE_DIR / "results"
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "jobs.db"


# =============================================================================
# DATA LOADING
# =============================================================================


@st.cache_data(ttl=60)
def load_csv_files() -> dict[str, pd.DataFrame]:
    """Load all CSV files from results directory."""
    csv_files = {}
    if RESULTS_DIR.exists():
        for csv_file in sorted(RESULTS_DIR.glob("*.csv"), reverse=True):
            try:
                csv_files[csv_file.name] = pd.read_csv(csv_file)
            except Exception as e:
                st.error(f"Error loading {csv_file.name}: {e}")
    return csv_files


@st.cache_data(ttl=60)
def load_database() -> pd.DataFrame | None:
    """Load jobs from SQLite database."""
    if not DATABASE_PATH.exists():
        return None

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        df = pd.read_sql_query("SELECT * FROM jobs", conn)
        conn.close()
        return df
    except Exception:
        return None


def get_unique_values(df: pd.DataFrame, column: str) -> list:
    """Get unique non-null values from a column."""
    if column not in df.columns:
        return []
    values = df[column].dropna().unique().tolist()
    return sorted([str(v) for v in values if v and str(v).strip()])


# =============================================================================
# FILTERING FUNCTIONS
# =============================================================================


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply all filters to the dataframe."""
    filtered_df = df.copy()

    # Text search in title/company/description
    if filters.get("search_text"):
        search_text = filters["search_text"].lower()
        mask = (
            filtered_df["title"].fillna("").str.lower().str.contains(search_text, regex=False) |
            filtered_df["company"].fillna("").str.lower().str.contains(search_text, regex=False) |
            filtered_df["description"].fillna("").str.lower().str.contains(search_text, regex=False)
        )
        filtered_df = filtered_df[mask]

    # Job level filter (LinkedIn only)
    if filters.get("job_levels") and "job_level" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["job_level"].fillna("").isin(filters["job_levels"]) |
            filtered_df["job_level"].isna()  # Keep jobs without level info
        ]

    # Site filter
    if filters.get("sites") and "site" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["site"].isin(filters["sites"])]

    # Company filter
    if filters.get("companies") and "company" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["company"].isin(filters["companies"])]

    # Location filter
    if filters.get("locations") and "location" in filtered_df.columns:
        location_mask = filtered_df["location"].fillna("").apply(
            lambda x: any(loc.lower() in str(x).lower() for loc in filters["locations"])
        )
        filtered_df = filtered_df[location_mask]

    # Job type filter
    if filters.get("job_types") and "job_type" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["job_type"].fillna("").str.lower().isin(
                [jt.lower() for jt in filters["job_types"]]
            ) |
            filtered_df["job_type"].isna()
        ]

    # Remote filter
    if filters.get("remote_only") and "is_remote" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["is_remote"] == True]

    # Salary range filter
    if filters.get("min_salary") and "min_amount" in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df["min_amount"].fillna(0) >= filters["min_salary"]) |
            filtered_df["min_amount"].isna()
        ]

    if filters.get("max_salary") and "max_amount" in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df["max_amount"].fillna(float("inf")) <= filters["max_salary"]) |
            filtered_df["max_amount"].isna()
        ]

    # Relevance score filter
    if filters.get("min_score") and "relevance_score" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["relevance_score"].fillna(0) >= filters["min_score"]
        ]

    # Date filter
    if filters.get("date_from") and "date_posted" in filtered_df.columns:
        filtered_df["date_posted"] = pd.to_datetime(filtered_df["date_posted"], errors="coerce")
        filtered_df = filtered_df[
            (filtered_df["date_posted"] >= pd.to_datetime(filters["date_from"])) |
            filtered_df["date_posted"].isna()
        ]

    # Applied filter (database only)
    if "applied" in filtered_df.columns:
        if filters.get("hide_applied"):
            filtered_df = filtered_df[filtered_df["applied"] != True]

    return filtered_df


# =============================================================================
# UI COMPONENTS
# =============================================================================


def render_sidebar_filters(df: pd.DataFrame) -> dict:
    """Render sidebar filters and return filter values."""
    st.sidebar.header("Filters")

    filters = {}

    # Text search
    filters["search_text"] = st.sidebar.text_input(
        "Search",
        placeholder="Search in title, company, description...",
        help="Search across job title, company name, and description"
    )

    # Relevance score filter
    if "relevance_score" in df.columns:
        max_score = int(df["relevance_score"].max()) if not df["relevance_score"].isna().all() else 100
        filters["min_score"] = st.sidebar.slider(
            "Minimum Relevance Score",
            min_value=0,
            max_value=max_score,
            value=0,
            help="Filter jobs by minimum relevance score"
        )

    # Site filter
    if "site" in df.columns:
        sites = get_unique_values(df, "site")
        if sites:
            filters["sites"] = st.sidebar.multiselect(
                "Job Sites",
                options=sites,
                default=sites,
                help="Filter by job board source"
            )

    # Job level filter (LinkedIn)
    if "job_level" in df.columns:
        job_levels = get_unique_values(df, "job_level")
        if job_levels:
            filters["job_levels"] = st.sidebar.multiselect(
                "Job Level (LinkedIn only)",
                options=job_levels,
                help="Filter by seniority level"
            )

    # Job type filter
    if "job_type" in df.columns:
        job_types = get_unique_values(df, "job_type")
        if job_types:
            filters["job_types"] = st.sidebar.multiselect(
                "Job Type",
                options=job_types,
                help="Filter by contract type"
            )

    # Remote filter
    if "is_remote" in df.columns:
        filters["remote_only"] = st.sidebar.checkbox(
            "Remote Only",
            help="Show only remote positions"
        )

    # Location filter
    st.sidebar.subheader("Location")
    location_search = st.sidebar.text_input(
        "Filter by location",
        placeholder="e.g., Zurich, Geneva...",
        help="Filter jobs containing this location"
    )
    if location_search:
        filters["locations"] = [location_search]

    # Salary filter
    if "min_amount" in df.columns or "max_amount" in df.columns:
        st.sidebar.subheader("Salary Range (Annual)")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            filters["min_salary"] = st.number_input(
                "Min",
                min_value=0,
                value=0,
                step=10000,
                help="Minimum annual salary"
            )
        with col2:
            filters["max_salary"] = st.number_input(
                "Max",
                min_value=0,
                value=0,
                step=10000,
                help="Maximum annual salary (0 = no limit)"
            )
        if filters["max_salary"] == 0:
            filters["max_salary"] = None

    # Company filter
    if "company" in df.columns:
        with st.sidebar.expander("Filter by Company"):
            companies = get_unique_values(df, "company")
            if len(companies) > 0:
                selected_companies = st.multiselect(
                    "Select companies",
                    options=companies[:100],  # Limit to first 100
                    help="Filter by specific companies"
                )
                if selected_companies:
                    filters["companies"] = selected_companies

    # Applied filter (database)
    if "applied" in df.columns:
        filters["hide_applied"] = st.sidebar.checkbox(
            "Hide Applied Jobs",
            help="Hide jobs you've already applied to"
        )

    # Date filter
    if "date_posted" in df.columns:
        st.sidebar.subheader("Date Posted")
        filters["date_from"] = st.sidebar.date_input(
            "From date",
            value=None,
            help="Show jobs posted after this date"
        )

    return filters


def render_statistics(df: pd.DataFrame, filtered_df: pd.DataFrame):
    """Render statistics section."""
    st.subheader("Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Jobs",
            len(filtered_df),
            delta=f"{len(filtered_df) - len(df)} filtered" if len(filtered_df) != len(df) else None
        )

    with col2:
        if "relevance_score" in filtered_df.columns:
            avg_score = filtered_df["relevance_score"].mean()
            st.metric("Avg Score", f"{avg_score:.1f}" if pd.notna(avg_score) else "N/A")
        elif "company" in filtered_df.columns:
            st.metric("Companies", filtered_df["company"].nunique())

    with col3:
        if "site" in filtered_df.columns:
            sites = filtered_df["site"].value_counts()
            top_site = sites.index[0] if len(sites) > 0 else "N/A"
            st.metric("Top Source", top_site)
        else:
            st.metric("Sources", "N/A")

    with col4:
        if "is_remote" in filtered_df.columns:
            remote_count = filtered_df["is_remote"].sum()
            st.metric("Remote Jobs", int(remote_count) if pd.notna(remote_count) else 0)
        elif "location" in filtered_df.columns:
            st.metric("Locations", filtered_df["location"].nunique())

    # Additional stats in expander
    with st.expander("Detailed Statistics"):
        col1, col2 = st.columns(2)

        with col1:
            if "site" in filtered_df.columns:
                st.write("**Jobs by Source:**")
                site_counts = filtered_df["site"].value_counts()
                st.dataframe(site_counts, use_container_width=True)

        with col2:
            if "job_type" in filtered_df.columns:
                st.write("**Jobs by Type:**")
                type_counts = filtered_df["job_type"].value_counts()
                st.dataframe(type_counts, use_container_width=True)

        if "job_level" in filtered_df.columns:
            st.write("**Jobs by Level (LinkedIn):**")
            level_counts = filtered_df["job_level"].value_counts()
            st.dataframe(level_counts, use_container_width=True)

        if "company" in filtered_df.columns:
            st.write("**Top 10 Companies:**")
            company_counts = filtered_df["company"].value_counts().head(10)
            st.dataframe(company_counts, use_container_width=True)


def render_job_table(df: pd.DataFrame):
    """Render the job results table."""
    st.subheader(f"Job Results ({len(df)} jobs)")

    # Column selection
    available_columns = df.columns.tolist()
    default_columns = [
        col for col in ["title", "company", "location", "job_level", "job_type",
                        "relevance_score", "site", "date_posted", "is_remote", "job_url"]
        if col in available_columns
    ]

    with st.expander("Configure Columns"):
        selected_columns = st.multiselect(
            "Select columns to display",
            options=available_columns,
            default=default_columns
        )

    if not selected_columns:
        selected_columns = default_columns

    # Ensure job_url is included for the link column
    display_columns = selected_columns.copy()
    if "job_url" in df.columns and "job_url" not in display_columns:
        display_columns.append("job_url")

    # Sorting
    col1, col2 = st.columns([3, 1])
    with col1:
        sort_column = st.selectbox(
            "Sort by",
            options=selected_columns,
            index=selected_columns.index("relevance_score") if "relevance_score" in selected_columns else 0
        )
    with col2:
        sort_order = st.selectbox("Order", ["Descending", "Ascending"])

    # Apply sorting
    ascending = sort_order == "Ascending"
    sorted_df = df[display_columns].sort_values(by=sort_column, ascending=ascending, na_position="last")

    # Display table with clickable job links
    st.dataframe(
        sorted_df,
        use_container_width=True,
        height=500,
        column_config={
            "job_url": st.column_config.LinkColumn(
                "Job Link",
                display_text="Open Job ↗",
                help="Click to open job posting in a new tab"
            ),
            "job_url_direct": st.column_config.LinkColumn(
                "Direct Link",
                display_text="Direct ↗"
            ),
            "company_url": st.column_config.LinkColumn(
                "Company",
                display_text="Company ↗"
            ),
            "relevance_score": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
            ),
            "is_remote": st.column_config.CheckboxColumn("Remote"),
            "min_amount": st.column_config.NumberColumn("Min Salary", format="$%d"),
            "max_amount": st.column_config.NumberColumn("Max Salary", format="$%d"),
        }
    )

    return sorted_df


def render_job_details(df: pd.DataFrame):
    """Render detailed view for a selected job."""
    st.subheader("Job Details")

    if len(df) == 0:
        st.info("No jobs to display. Adjust your filters.")
        return

    # Job selector
    job_options = [
        f"{row['title']} @ {row['company']}"
        for _, row in df.head(50).iterrows()
    ]

    if not job_options:
        return

    selected_job = st.selectbox(
        "Select a job to view details",
        options=range(len(job_options)),
        format_func=lambda x: job_options[x]
    )

    if selected_job is not None:
        job = df.iloc[selected_job]

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"### {job.get('title', 'N/A')}")
            st.markdown(f"**Company:** {job.get('company', 'N/A')}")
            st.markdown(f"**Location:** {job.get('location', 'N/A')}")

            if pd.notna(job.get("job_url")):
                st.markdown(f"[View Job Posting]({job['job_url']})")

        with col2:
            if "relevance_score" in job and pd.notna(job["relevance_score"]):
                st.metric("Relevance Score", int(job["relevance_score"]))
            if "job_level" in job and pd.notna(job["job_level"]):
                st.metric("Level", job["job_level"])
            if "job_type" in job and pd.notna(job["job_type"]):
                st.metric("Type", job["job_type"])

        # Salary info
        if pd.notna(job.get("min_amount")) or pd.notna(job.get("max_amount")):
            salary_str = ""
            if pd.notna(job.get("min_amount")):
                salary_str += f"${int(job['min_amount']):,}"
            if pd.notna(job.get("max_amount")):
                salary_str += f" - ${int(job['max_amount']):,}"
            if pd.notna(job.get("currency")):
                salary_str += f" {job['currency']}"
            if pd.notna(job.get("interval")):
                salary_str += f" ({job['interval']})"
            st.markdown(f"**Salary:** {salary_str}")

        # Description
        if "description" in job and pd.notna(job["description"]):
            with st.expander("Job Description", expanded=True):
                st.markdown(job["description"])


def render_export_section(df: pd.DataFrame):
    """Render export options."""
    st.subheader("Export")

    col1, col2 = st.columns(2)

    with col1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"filtered_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    with col2:
        # Excel export
        try:
            from io import BytesIO
            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            st.download_button(
                label="Download Excel",
                data=buffer.getvalue(),
                file_name=f"filtered_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            st.info("Excel export requires openpyxl")


# =============================================================================
# MAIN APPLICATION
# =============================================================================


def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="Job Search Dashboard",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("💼 Job Search Dashboard")
    st.markdown("Interactive dashboard for analyzing and filtering job search results.")

    # Data source selection
    st.sidebar.header("Data Source")

    csv_files = load_csv_files()
    db_data = load_database()

    data_sources = []
    if csv_files:
        data_sources.extend([f"CSV: {name}" for name in csv_files.keys()])
    if db_data is not None:
        data_sources.append("Database: jobs.db")

    if not data_sources:
        st.warning("No data found. Run the job search first to generate results.")
        st.info("""
        To generate data:
        ```bash
        docker-compose up --build
        ```
        or
        ```bash
        cd scripts && python search_jobs.py
        ```
        """)
        # Refresh button to clear cache
        if st.button("🔄 Refresh Data (Clear Cache)"):
            st.cache_data.clear()
            st.rerun()
        # Debug info
        with st.expander("Debug Info"):
            st.write(f"BASE_DIR: {BASE_DIR}")
            st.write(f"RESULTS_DIR: {RESULTS_DIR}")
            st.write(f"RESULTS_DIR exists: {RESULTS_DIR.exists()}")
            st.write(f"DATABASE_PATH: {DATABASE_PATH}")
            st.write(f"DATABASE_PATH exists: {DATABASE_PATH.exists()}")
            if RESULTS_DIR.exists():
                files = list(RESULTS_DIR.glob("*"))
                st.write(f"Files in results: {[f.name for f in files]}")
        return

    selected_source = st.sidebar.selectbox(
        "Select data source",
        options=data_sources,
        help="Choose which dataset to analyze"
    )

    # Load selected data
    if selected_source.startswith("CSV:"):
        csv_name = selected_source.replace("CSV: ", "")
        df = csv_files[csv_name]
        st.sidebar.success(f"Loaded {len(df)} jobs from {csv_name}")
    else:
        df = db_data
        st.sidebar.success(f"Loaded {len(df)} jobs from database")

    # Render filters
    filters = render_sidebar_filters(df)

    # Apply filters
    filtered_df = apply_filters(df, filters)

    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "📋 Job Table", "🔍 Job Details"])

    with tab1:
        render_statistics(df, filtered_df)

        # Quick charts
        if len(filtered_df) > 0:
            col1, col2 = st.columns(2)

            with col1:
                if "site" in filtered_df.columns:
                    st.subheader("Jobs by Source")
                    site_data = filtered_df["site"].value_counts()
                    st.bar_chart(site_data)

            with col2:
                if "relevance_score" in filtered_df.columns:
                    st.subheader("Score Distribution")
                    st.bar_chart(filtered_df["relevance_score"].value_counts().sort_index())

    with tab2:
        sorted_df = render_job_table(filtered_df)
        render_export_section(sorted_df)

    with tab3:
        render_job_details(filtered_df)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Job Search Dashboard**  \n"
        f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
