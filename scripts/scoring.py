"""
Scoring and filtering module for Job Search Tool.

Provides relevance scoring, fuzzy matching, and post-filtering
for job search results. All scoring logic is configuration-driven
with no hardcoded categories or keywords.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd
from rapidfuzz import fuzz

from config import Config
from logger import get_logger, log_section


def _normalize_text(text: str) -> str:
    """
    Normalize text for fuzzy matching.

    Uses Unicode NFKD normalization to handle all diacritical marks
    (ü->u, ö->o, é->e, etc.) instead of a manual replacement table.
    """
    if not text:
        return ""

    # NFKD decomposes characters, then strip combining marks (accents, umlauts, etc.)
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))

    # Handle special ligature that NFKD doesn't decompose to "ss"
    stripped = stripped.replace("ß", "ss")

    return stripped.lower()


def _extract_words(text: str) -> list[str]:
    """Extract words from text, filtering out common stop words."""
    if not text:
        return []

    # Normalize and split
    normalized = _normalize_text(text)
    words = re.findall(r"\b[a-z0-9+#]+\b", normalized)

    # Filter stop words (common words that don't add value to matching)
    stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "been",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "we",
        "you",
        "they",
        "i",
        "he",
        "she",
        "who",
        "what",
        "which",
        "where",
        "when",
        "why",
        "how",
    }

    return [w for w in words if w not in stop_words and len(w) > 1]


def _fuzzy_word_match(word: str, text: str, min_similarity: int) -> bool:
    """
    Check if a word fuzzy-matches anywhere in the text.

    Uses token set ratio for flexibility with word order and partial matches.
    """
    normalized_word = _normalize_text(word)
    normalized_text = _normalize_text(text)

    # Direct substring match (fastest check)
    if normalized_word in normalized_text:
        return True

    # Extract words from text and check each one
    text_words = _extract_words(text)
    for text_word in text_words:
        # Use partial ratio for handling substrings and fuzz ratio for typos
        similarity = max(
            fuzz.ratio(normalized_word, text_word),
            fuzz.partial_ratio(normalized_word, text_word),
        )
        if similarity >= min_similarity:
            return True

    return False


def _get_job_text(row: pd.Series) -> str:
    """Concatenate all relevant job fields for matching."""
    fields = ["title", "description", "company", "location"]
    parts = []
    for field in fields:
        value = row.get(field)
        if value and pd.notna(value):
            parts.append(str(value))
    return " ".join(parts)


def fuzzy_post_filter(
    jobs_df: pd.DataFrame,
    query: str,
    location: str,
    config: Config,
) -> pd.DataFrame:
    """
    Filter jobs to ensure query terms are present in job data.

    Uses fuzzy matching to handle typos and character variations.

    Args:
        jobs_df: DataFrame with job results.
        query: Original search query.
        location: Search location.
        config: Configuration with post_filter settings.

    Returns:
        Filtered DataFrame with only matching jobs.
    """
    if not config.post_filter.enabled:
        return jobs_df

    if jobs_df is None or len(jobs_df) == 0:
        return jobs_df

    logger = get_logger("post_filter")
    min_similarity = config.post_filter.min_similarity

    # Extract query terms to check
    query_terms = _extract_words(query)

    # Also check location if enabled
    if config.post_filter.check_location and location.lower() != "remote":
        location_terms = _extract_words(location)
    else:
        location_terms = []

    if not query_terms and not location_terms:
        return jobs_df

    logger.debug(
        f"Post-filtering: query_terms={query_terms}, location_terms={location_terms}"
    )

    # Filter rows
    matching_indices = []
    for idx, row in jobs_df.iterrows():
        job_text = _get_job_text(row)

        # Check if all query terms match
        if config.post_filter.check_query_terms:
            query_match = all(
                _fuzzy_word_match(term, job_text, min_similarity)
                for term in query_terms
            )
        else:
            query_match = True

        # Check if location matches (at least one location term should match)
        if location_terms:
            location_match = any(
                _fuzzy_word_match(term, job_text, min_similarity)
                for term in location_terms
            )
        else:
            location_match = True

        if query_match and location_match:
            matching_indices.append(idx)

    filtered_df = jobs_df.loc[matching_indices].copy()

    filtered_count = len(jobs_df) - len(filtered_df)
    if filtered_count > 0:
        logger.debug(
            f"Post-filter removed {filtered_count} jobs "
            f"(kept {len(filtered_df)}/{len(jobs_df)})"
        )

    return filtered_df


def calculate_relevance_score(row: pd.Series, config: Config) -> int:
    """
    Calculate relevance score based entirely on user configuration.

    The scoring system is fully dynamic: it iterates over all keyword categories
    defined in config.scoring.keywords and applies the corresponding weight from
    config.scoring.weights. No hardcoded categories or keywords.

    Args:
        row: DataFrame row with job data.
        config: Configuration with scoring weights and keywords.

    Returns:
        Relevance score as integer (sum of matched category weights).

    Example config:
        scoring:
          weights:
            primary_skills: 20
            technologies: 15
          keywords:
            primary_skills:
              - "software engineer"
              - "backend"
            technologies:
              - "python"
              - "docker"
    """
    # Build searchable text from job fields
    text = " ".join(
        str(row.get(field, "") or "")
        for field in ("title", "description", "company", "location")
    ).lower()

    if not text.strip():
        return 0

    score = 0
    weights = config.scoring.weights
    keywords = config.scoring.keywords

    # Iterate over all keyword categories defined in configuration
    for category, keyword_list in keywords.items():
        if not keyword_list:
            continue

        # Check if any keyword from this category matches
        if any(keyword.lower() in text for keyword in keyword_list):
            # Get weight for this category (default 0 if not specified)
            weight = weights.get(category, 0)
            score += weight

    return score


@dataclass
class Partitions:
    """Three-way view of scored search results.

    ``scored`` keeps every row (useful for debug/metrics). ``to_save`` is what
    will land in the DB. ``to_notify`` is a subset of ``to_save`` above the
    notification threshold.
    """

    scored: pd.DataFrame
    to_save: pd.DataFrame
    to_notify: pd.DataFrame


def score_jobs(jobs_df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Return a copy of ``jobs_df`` with a ``relevance_score`` column added."""
    logger = get_logger("scoring")
    log_section(logger, "SCORING JOBS")

    scored = jobs_df.copy()
    scored["relevance_score"] = scored.apply(
        lambda row: calculate_relevance_score(row, config), axis=1
    )

    if len(scored) > 0:
        logger.info(
            "Scored %d jobs (max=%d, avg=%.1f)",
            len(scored),
            int(scored["relevance_score"].max()),
            float(scored["relevance_score"].mean()),
        )
    return scored


def partition_by_thresholds(scored: pd.DataFrame, config: Config) -> Partitions:
    """Carve the scored frame into save/notify partitions."""
    save_threshold = config.scoring.save_threshold
    notify_threshold = config.scoring.notify_threshold

    logger = get_logger("scoring")

    if scored.empty or "relevance_score" not in scored.columns:
        empty = scored.iloc[0:0] if not scored.empty else scored
        return Partitions(scored=scored, to_save=empty, to_notify=empty)

    to_save = scored[scored["relevance_score"] >= save_threshold].sort_values(
        "relevance_score", ascending=False
    )
    to_notify = to_save[to_save["relevance_score"] >= notify_threshold]

    logger.info(
        "Partitions: %d scored, %d to save (≥%d), %d to notify (≥%d)",
        len(scored),
        len(to_save),
        save_threshold,
        len(to_notify),
        notify_threshold,
    )
    return Partitions(scored=scored, to_save=to_save, to_notify=to_notify)
