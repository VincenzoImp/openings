"""Relevance scoring and query post-filtering.

Scoring is entirely configuration-driven: every category in
``scoring.keywords`` adds its weight from ``scoring.weights`` when any of its
terms appears in the job text. Negative weights penalize. Matching is a
case-insensitive substring test over title, description, company and
location, with Unicode normalization so accented and unaccented spellings
match alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd
from rapidfuzz import fuzz

from openings.config import Config, JobSpyConfig
from openings.logger import get_logger
from openings.text import extract_words, normalize_text

TEXT_FIELDS = ("title", "description", "company", "location")


def fuzzy_word_match(word: str, text: str, min_similarity: int) -> bool:
    """True when ``word`` appears in ``text`` exactly or within ``min_similarity``."""
    normalized_word = normalize_text(word)
    normalized_text = normalize_text(text)
    if normalized_word in normalized_text:
        return True
    for candidate in extract_words(text):
        similarity = max(
            fuzz.ratio(normalized_word, candidate),
            fuzz.partial_ratio(normalized_word, candidate),
        )
        if similarity >= min_similarity:
            return True
    return False


def _field(obj: Any, name: str) -> str:
    """Read a text field from a DataFrame row, a mapping or a ``Job``."""
    if isinstance(obj, Mapping):
        value = obj.get(name)
    elif isinstance(obj, pd.Series):
        value = obj.get(name)
    else:
        value = getattr(obj, name, None)
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def job_text(obj: Any) -> str:
    """Concatenated text used for both scoring and post-filtering."""
    return " ".join(part for part in (_field(obj, name) for name in TEXT_FIELDS) if part)


def matched_categories(obj: Any, config: Config) -> list[str]:
    """Categories whose keywords appear in the job text, in config order."""
    text = normalize_text(job_text(obj))
    if not text.strip():
        return []
    matched: list[str] = []
    for category, terms in config.scoring.keywords.items():
        if any(normalize_text(term) in text for term in terms):
            matched.append(category)
    return matched


def calculate_relevance_score(obj: Any, config: Config) -> int:
    """Sum of the weights of every matched category."""
    weights = config.scoring.weights
    return sum(weights.get(category, 0) for category in matched_categories(obj, config))


@dataclass(frozen=True)
class ScoreExplanation:
    score: int
    matched: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, "matched": self.matched}


def explain_score(obj: Any, config: Config) -> ScoreExplanation:
    """Score plus the category-by-category breakdown behind it."""
    weights = config.scoring.weights
    matched: list[dict[str, Any]] = [
        {"category": category, "weight": int(weights.get(category, 0))}
        for category in matched_categories(obj, config)
    ]
    score = sum(int(item["weight"]) for item in matched)
    return ScoreExplanation(score=score, matched=matched)


def score_jobs(jobs_df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Return a copy of ``jobs_df`` with a ``relevance_score`` column."""
    logger = get_logger("scoring")
    scored = jobs_df.copy()
    if scored.empty:
        scored["relevance_score"] = pd.Series(dtype="int64")
        return scored
    scored["relevance_score"] = scored.apply(
        lambda row: calculate_relevance_score(row, config), axis=1
    )
    logger.info(
        "Scored %d jobs (max=%d, avg=%.1f)",
        len(scored),
        int(scored["relevance_score"].max()),
        float(scored["relevance_score"].mean()),
    )
    return scored


@dataclass
class Partitions:
    """Scored rows split by the save and notify thresholds."""

    scored: pd.DataFrame
    to_save: pd.DataFrame
    to_notify: pd.DataFrame


def partition_by_thresholds(scored: pd.DataFrame, config: Config) -> Partitions:
    save_threshold = config.scoring.save_threshold
    notify_threshold = config.scoring.notify_threshold
    if scored.empty or "relevance_score" not in scored.columns:
        empty = scored.iloc[0:0]
        return Partitions(scored=scored, to_save=empty, to_notify=empty)
    to_save = scored[scored["relevance_score"] >= save_threshold].sort_values(
        "relevance_score", ascending=False
    )
    to_notify = to_save[to_save["relevance_score"] >= notify_threshold]
    get_logger("scoring").info(
        "Partitions: %d scored, %d to save (>=%d), %d to notify (>=%d)",
        len(scored),
        len(to_save),
        save_threshold,
        len(to_notify),
        notify_threshold,
    )
    return Partitions(scored=scored, to_save=to_save, to_notify=to_notify)


def fuzzy_post_filter(
    jobs_df: pd.DataFrame, query: str, location: str, settings: JobSpyConfig
) -> pd.DataFrame:
    """Keep only rows that actually contain the query terms (and the location).

    Boards return "related" results; this removes them before scoring.
    """
    post_filter = settings.post_filter
    if not post_filter.enabled or jobs_df is None or jobs_df.empty:
        return jobs_df

    query_terms = extract_words(query) if post_filter.check_query_terms else []
    location_terms = (
        extract_words(location)
        if post_filter.check_location and location.strip().lower() != "remote"
        else []
    )
    if not query_terms and not location_terms:
        return jobs_df

    keep: list[Any] = []
    for index, row in jobs_df.iterrows():
        text = job_text(row)
        query_ok = all(
            fuzzy_word_match(term, text, post_filter.min_similarity) for term in query_terms
        )
        location_ok = not location_terms or any(
            fuzzy_word_match(term, text, post_filter.min_similarity) for term in location_terms
        )
        if query_ok and location_ok:
            keep.append(index)
    filtered = jobs_df.loc[keep].copy()
    removed = len(jobs_df) - len(filtered)
    if removed:
        get_logger("post_filter").debug(
            "Post-filter removed %d rows for %r @ %r", removed, query, location
        )
    return filtered
