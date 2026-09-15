import pandas as pd
import pytest

from openings.config import parse_config
from openings.scoring import (
    calculate_relevance_score,
    explain_score,
    extract_words,
    fuzzy_post_filter,
    fuzzy_word_match,
    job_text,
    matched_categories,
    normalize_text,
    partition_by_thresholds,
    score_jobs,
)
from tests.conftest import make_job, minimal_settings


def config_with(category: str, definition) -> object:
    """A configuration whose ``category`` is replaced by ``definition``."""
    data = minimal_settings()
    data["scoring"]["keywords"][category] = definition
    return parse_config(data)


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


# ---------------------------------------------------------------------------
# Matching options: match_in and whole_word
# ---------------------------------------------------------------------------


def legacy_score(obj, config) -> int:
    """The matcher exactly as it was before ``match_in`` and ``whole_word``.

    A bare case-insensitive substring test over the four fields concatenated,
    one weight per matching category. Kept verbatim so the guard below is
    independent of the current implementation.
    """
    text = normalize_text(job_text(obj))
    if not text.strip():
        return 0
    total = 0
    for category, keywords in config.scoring.keywords.items():
        if any(normalize_text(term) in text for term in keywords.terms):
            total += config.scoring.weights.get(category, 0)
    return total


CORPUS = [
    make_job(),
    make_job(title="Software Engineer", description="Python, PostgreSQL, 10+ years"),
    make_job(title="Backend Engineer", company="Google", location="Lugano"),
    make_job(title="Sales Manager", description="going to work on ongoing categories"),
    make_job(title="", company="", location="", description=""),
    make_job(title="Ingénieur Backend", location="Zürich", description="Straße 10"),
    make_job(title="BACKEND ENGINEER,", description="backend.  Backend! (backend)"),
    make_job(title="Intern", description="internal and international teams"),
    make_job(description=None),
    make_job(title="Data Engineer", description="10+ years of python"),
]


@pytest.mark.parametrize("job", CORPUS, ids=lambda job: job.title or "empty")
def test_bare_keyword_lists_score_exactly_as_before(job, config):
    """A configuration that uses no new option must not move a single score."""
    assert calculate_relevance_score(job, config) == legacy_score(job, config)


def test_bare_keyword_lists_score_exactly_as_before_on_the_example_settings():
    import yaml

    from tests.conftest import EXAMPLE_SETTINGS

    example = parse_config(yaml.safe_load(EXAMPLE_SETTINGS.read_text(encoding="utf-8")))
    for job in CORPUS:
        assert calculate_relevance_score(job, example) == legacy_score(job, example)


def test_match_in_title_ignores_a_term_that_only_appears_in_the_description():
    scoped = config_with("role", {"match_in": ["title"], "terms": ["backend"]})
    in_description = make_job(title="Forward-Deployed Engineer", description="our backend team")
    assert "role" not in matched_categories(in_description, scoped)
    assert "role" in matched_categories(make_job(title="Backend Engineer"), scoped)


def test_match_in_reads_every_named_field_and_only_those():
    scoped = config_with("role", {"match_in": ["company", "location"], "terms": ["acme"]})
    assert "role" in matched_categories(make_job(company="Acme"), scoped)
    assert "role" in matched_categories(make_job(company="X", location="Acme Park"), scoped)
    assert "role" not in matched_categories(make_job(company="X", description="acme"), scoped)


def test_match_in_does_not_change_the_other_categories():
    scoped = config_with("role", {"match_in": ["title"], "terms": ["backend"]})
    job = make_job(title="Consultant", description="python and postgresql")
    assert matched_categories(job, scoped) == ["stack"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("go", True),  # the whole text
        ("we use go", True),  # end of the text
        ("go is our language", True),  # start of the text
        ("Go, Python, Rust", True),  # followed by punctuation
        ("(go)", True),  # wrapped in punctuation
        ("Google", False),
        ("Lugano", False),
        ("going", False),
        ("ongoing", False),
        ("category", False),
        ("governance", False),
        ("go_lang", False),  # underscore is a word character
    ],
)
def test_whole_word_matches_a_token_and_not_a_substring(text, expected):
    whole = config_with("role", {"whole_word": True, "terms": ["go"]})
    assert ("role" in matched_categories(make_job(description=text), whole)) is expected


def test_whole_word_is_off_by_default_so_substrings_still_match():
    loose = config_with("role", {"terms": ["go"]})
    assert "role" in matched_categories(make_job(description="Google"), loose)


def test_whole_word_bounds_the_whole_term_not_each_word():
    whole = config_with("role", {"whole_word": True, "terms": ["site reliability engineer"]})
    assert "role" in matched_categories(make_job(title="Site Reliability Engineer"), whole)
    assert "role" in matched_categories(make_job(title="Senior Site Reliability Engineer!"), whole)
    assert "role" not in matched_categories(make_job(title="Site Reliability Engineering"), whole)


def test_whole_word_accepts_terms_that_end_in_punctuation():
    """``c#`` and ``8+ years`` have no word character to bound on one side."""
    whole = config_with("stack", {"whole_word": True, "terms": ["c#", "8+ years", ".net"]})
    assert "stack" in matched_categories(make_job(description="We write C# daily"), whole)
    assert "stack" in matched_categories(make_job(description="8+ years of experience"), whole)
    assert "stack" in matched_categories(make_job(description="Built on .NET Core"), whole)
    assert "stack" not in matched_categories(make_job(description="8+ yearsish"), whole)


def test_whole_word_is_unicode_aware_after_normalization():
    whole = config_with("role", {"whole_word": True, "terms": ["ingenieur"]})
    assert "role" in matched_categories(make_job(title="Ingénieur DevOps"), whole)
    assert "role" not in matched_categories(make_job(title="Ingénieurs DevOps"), whole)


def test_match_in_and_whole_word_combine():
    strict = config_with("role", {"match_in": ["title"], "whole_word": True, "terms": ["go"]})
    assert "role" in matched_categories(make_job(title="Go Engineer"), strict)
    assert "role" not in matched_categories(make_job(title="Google Engineer"), strict)
    assert "role" not in matched_categories(make_job(title="Engineer", description="go"), strict)


def test_explain_reports_the_breakdown_under_the_new_options():
    scoped = config_with("role", {"match_in": ["title"], "whole_word": True, "terms": ["backend"]})
    explanation = explain_score(make_job(title="Backend Engineer"), scoped)
    assert [item["category"] for item in explanation.matched] == ["role", "stack"]
    assert explanation.score == 35
    demoted = explain_score(make_job(title="Consultant"), scoped)
    assert [item["category"] for item in demoted.matched] == ["stack"]
    assert demoted.score == 10
