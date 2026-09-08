import pandas as pd

from openings.scoring import (
    calculate_relevance_score,
    explain_score,
    extract_words,
    fuzzy_post_filter,
    fuzzy_word_match,
    normalize_text,
    partition_by_thresholds,
    score_jobs,
)
from tests.conftest import make_job


def test_normalize_text_strips_diacritics():
    assert normalize_text("Zürich") == "zurich"
    assert normalize_text("Straße") == "strasse"
    assert normalize_text(None) == ""


def test_extract_words_drops_stop_words():
    assert extract_words("the software engineer is a developer") == [
        "software",
        "engineer",
        "developer",
    ]


def test_fuzzy_word_match_handles_typos_and_accents():
    assert fuzzy_word_match("zurich", "Based in Zürich", 80)
    assert fuzzy_word_match("python", "we use pytohn daily", 80)
    assert not fuzzy_word_match("developer", "development team", 95)


def test_score_counts_each_category_once(config):
    job = make_job(description="python python postgresql backend backend")
    assert calculate_relevance_score(job, config) == 35


def test_negative_weights_subtract(config):
    job = make_job(description="Backend role, 10+ years required")
    assert calculate_relevance_score(job, config) == 25 - 40


def test_explain_lists_matched_categories(config):
    explanation = explain_score(make_job(), config)
    assert explanation.score == 35
    assert [item["category"] for item in explanation.matched] == ["role", "stack"]


def test_scoring_accepts_dataframe_rows(config):
    frame = pd.DataFrame(
        [{"title": "Backend Engineer", "company": "A", "location": "L", "description": None}]
    )
    scored = score_jobs(frame, config)
    assert list(scored["relevance_score"]) == [25]


def test_partition_by_thresholds(config):
    frame = pd.DataFrame(
        [
            {"title": "Backend Engineer", "company": "A", "location": "L", "description": "python"},
            {"title": "Sales", "company": "B", "location": "L", "description": "10+ years"},
        ]
    )
    partitions = partition_by_thresholds(score_jobs(frame, config), config)
    assert len(partitions.to_save) == 1  # save_threshold 0 drops the -40 row
    assert len(partitions.to_notify) == 1


def test_post_filter_keeps_only_query_and_location_matches(config):
    settings = config.sources.jobspy
    frame = pd.DataFrame(
        [
            {"title": "Python Developer", "company": "A", "location": "Zürich", "description": ""},
            {"title": "Sales Manager", "company": "B", "location": "Zurich", "description": ""},
            {"title": "Python Developer", "company": "C", "location": "Geneva", "description": ""},
        ]
    )
    kept = fuzzy_post_filter(frame, "python developer", "Zurich, Switzerland", settings)
    assert list(kept["company"]) == ["A"]


def test_post_filter_skips_location_for_remote(config):
    settings = config.sources.jobspy
    frame = pd.DataFrame(
        [{"title": "Python Developer", "company": "A", "location": "Anywhere", "description": ""}]
    )
    assert len(fuzzy_post_filter(frame, "python developer", "Remote", settings)) == 1
