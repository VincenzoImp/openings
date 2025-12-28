#!/usr/bin/env python3
"""
Job Analysis Tool.

Analyzes saved job search results and generates insights.
Provides statistics on companies, locations, keywords, and more.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from config import get_config
from database import get_database
from logger import get_logger, log_section, log_subsection, setup_logging

if TYPE_CHECKING:
    from config import Config


# Required columns for analysis
REQUIRED_COLUMNS = ["title", "company", "location"]


def load_latest_results(config: Config) -> pd.DataFrame | None:
    """
    Load the most recent job search results.

    Args:
        config: Configuration object.

    Returns:
        DataFrame with job data, or None if not found.
    """
    logger = get_logger("analyze")
    results_dir = config.results_path

    if not results_dir.exists():
        logger.error("No results directory found. Run search_jobs.py first.")
        return None

    # Find latest CSV file (prefer relevant_jobs over all_jobs)
    csv_files = list(results_dir.glob("relevant_jobs_*.csv"))

    if not csv_files:
        csv_files = list(results_dir.glob("all_jobs_*.csv"))

    if not csv_files:
        logger.error("No job results found. Run search_jobs.py first.")
        return None

    latest_file = max(csv_files, key=lambda f: f.stat().st_ctime)
    logger.info(f"Loading: {latest_file.name}")

    try:
        df = pd.read_csv(latest_file)

        # Validate required columns
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            return None

        logger.info(f"Loaded {len(df)} jobs")
        return df

    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        return None


def analyze_companies(df: pd.DataFrame) -> pd.Series:
    """
    Analyze companies hiring.

    Args:
        df: DataFrame with job data.

    Returns:
        Series with company counts.
    """
    logger = get_logger("analyze")

    log_subsection(logger, "TOP COMPANIES HIRING")

    company_counts = df["company"].value_counts().head(15)

    for company, count in company_counts.items():
        logger.info(f"  {company}: {count} positions")

    return company_counts


def analyze_locations(df: pd.DataFrame) -> pd.Series:
    """
    Analyze job locations.

    Args:
        df: DataFrame with job data.

    Returns:
        Series with location counts.
    """
    logger = get_logger("analyze")

    log_subsection(logger, "JOB LOCATIONS")

    location_counts = df["location"].value_counts().head(10)

    for location, count in location_counts.items():
        logger.info(f"  {location}: {count} jobs")

    return location_counts


def analyze_keywords(df: pd.DataFrame) -> list[tuple[str, int]]:
    """
    Extract and analyze common keywords in job titles.

    Args:
        df: DataFrame with job data.

    Returns:
        List of (keyword, count) tuples.
    """
    logger = get_logger("analyze")

    log_subsection(logger, "MOST COMMON KEYWORDS IN JOB TITLES")

    # Combine all titles
    all_titles = " ".join(df["title"].dropna().astype(str).str.lower())

    # Split into words and count
    words = all_titles.split()

    # Filter out common words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "at",
        "to",
        "for",
        "of",
        "on",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "be",
        "-",
        "&",
        "/",
        "(",
        ")",
        "m/f/d",
        "f/m/d",
        "m/w/d",
        "all",
        "genders",
    }

    filtered_words = [
        word.strip("()[].,;:")
        for word in words
        if word not in stop_words and len(word) > 2
    ]

    word_counts = Counter(filtered_words).most_common(20)

    for word, count in word_counts:
        logger.info(f"  {word}: {count}")

    return word_counts


def analyze_salary(df: pd.DataFrame) -> dict[str, float | int] | None:
    """
    Analyze salary information if available.

    Args:
        df: DataFrame with job data.

    Returns:
        Dictionary with salary statistics, or None if no data.
    """
    logger = get_logger("analyze")

    log_subsection(logger, "SALARY INFORMATION")

    if "min_amount" not in df.columns:
        logger.info("  No salary data in results")
        return None

    salary_data = df[df["min_amount"].notna()]

    if len(salary_data) == 0:
        logger.info("  No salary information available in results")
        return None

    stats = {
        "jobs_with_salary": len(salary_data),
        "avg_min_salary": salary_data["min_amount"].mean(),
        "avg_max_salary": (
            salary_data["max_amount"].mean()
            if "max_amount" in salary_data.columns
            else None
        ),
    }

    logger.info(f"  Jobs with salary info: {stats['jobs_with_salary']}")
    logger.info(f"  Average min salary: {stats['avg_min_salary']:.0f}")

    if stats["avg_max_salary"]:
        logger.info(f"  Average max salary: {stats['avg_max_salary']:.0f}")

    if "currency" in df.columns:
        currencies = salary_data["currency"].value_counts()
        logger.info("  Currencies:")
        for curr, count in currencies.items():
            logger.info(f"    {curr}: {count} jobs")

    return stats


def analyze_job_types(df: pd.DataFrame) -> pd.Series | None:
    """
    Analyze job types.

    Args:
        df: DataFrame with job data.

    Returns:
        Series with job type counts, or None if no data.
    """
    logger = get_logger("analyze")

    if "job_type" not in df.columns:
        return None

    log_subsection(logger, "JOB TYPES")

    job_types = df["job_type"].value_counts()
    for jtype, count in job_types.items():
        logger.info(f"  {jtype}: {count}")

    return job_types


def analyze_remote(df: pd.DataFrame) -> pd.Series | None:
    """
    Analyze remote work options.

    Args:
        df: DataFrame with job data.

    Returns:
        Series with remote status counts, or None if no data.
    """
    logger = get_logger("analyze")

    if "is_remote" not in df.columns:
        return None

    log_subsection(logger, "REMOTE WORK OPTIONS")

    remote_counts = df["is_remote"].value_counts()
    for remote, count in remote_counts.items():
        label = "Remote" if remote else "On-site"
        logger.info(f"  {label}: {count} jobs")

    return remote_counts


def generate_report(df: pd.DataFrame, config: Config) -> dict[str, Any]:
    """
    Generate a comprehensive analysis report.

    Args:
        df: DataFrame with job data.
        config: Configuration object.

    Returns:
        Dictionary with all analysis results.
    """
    logger = get_logger("analyze")

    log_section(logger, "JOB SEARCH ANALYSIS REPORT")

    # Overview
    log_subsection(logger, "OVERVIEW")
    logger.info(f"  Total jobs analyzed: {len(df)}")

    report = {
        "total_jobs": len(df),
    }

    if "relevance_score" in df.columns:
        avg_score = df["relevance_score"].mean()
        max_score = df["relevance_score"].max()
        logger.info(f"  Average relevance score: {avg_score:.1f}")
        logger.info(f"  Highest relevance score: {max_score:.0f}")
        report["avg_relevance_score"] = avg_score
        report["max_relevance_score"] = max_score

    if "search_date" in df.columns:
        search_date = df["search_date"].iloc[0]
        logger.info(f"  Search date: {search_date}")
        report["search_date"] = search_date

    # Detailed analysis
    report["companies"] = analyze_companies(df)
    report["locations"] = analyze_locations(df)
    report["keywords"] = analyze_keywords(df)
    report["salary"] = analyze_salary(df)
    report["job_types"] = analyze_job_types(df)
    report["remote"] = analyze_remote(df)

    return report


def analyze_database(config: Config) -> None:
    """
    Analyze jobs from database.

    Args:
        config: Configuration object.
    """
    logger = get_logger("analyze")

    db = get_database(config)
    stats = db.get_statistics()

    log_section(logger, "DATABASE STATISTICS")

    logger.info(f"  Total jobs tracked: {stats['total_jobs']}")
    logger.info(f"  Jobs seen today: {stats['seen_today']}")
    logger.info(f"  New today: {stats['new_today']}")
    logger.info(f"  Jobs marked as applied: {stats['applied']}")
    logger.info(f"  Average relevance score: {stats['avg_relevance_score']}")


def export_filtered_by_company(
    df: pd.DataFrame, companies: list[str], config: Config
) -> Path | None:
    """
    Export jobs filtered by specific companies.

    Args:
        df: DataFrame with job data.
        companies: List of company names to filter.
        config: Configuration object.

    Returns:
        Path to exported file, or None if no matches.
    """
    logger = get_logger("analyze")

    if not companies:
        return None

    logger.info(f"Filtering jobs from: {', '.join(companies)}")

    filtered = df[df["company"].str.lower().isin([c.lower() for c in companies])]

    if len(filtered) == 0:
        logger.warning("No jobs found from specified companies")
        return None

    output_path = config.results_path / "filtered_by_company.csv"
    filtered.to_csv(output_path, index=False)
    logger.info(f"Saved {len(filtered)} jobs to: {output_path}")

    return output_path


def main() -> None:
    """Main analysis function."""
    # Load configuration
    config = get_config()

    # Setup logging
    logger = setup_logging(config)

    # Load results
    df = load_latest_results(config)

    if df is None:
        return

    # Generate report
    generate_report(df, config)

    # Database analysis
    analyze_database(config)

    # Optional: Filter by specific companies
    # Uncomment and customize this list:
    # target_companies = ['Google', 'ETH Zurich', 'EPFL', 'IBM Research']
    # export_filtered_by_company(df, target_companies, config)

    log_section(logger, "ANALYSIS COMPLETE")


if __name__ == "__main__":
    main()
