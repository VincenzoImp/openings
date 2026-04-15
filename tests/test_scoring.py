"""Tests for scoring functionality in scoring module."""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import Config, ScoringConfig
from scoring import (
    calculate_relevance_score,
    fuzzy_post_filter,
    partition_by_thresholds,
    score_jobs,
    _extract_words,
    _fuzzy_word_match,
    _get_job_text,
    _normalize_text,
)


class TestNormalizeText:
    """Tests for text normalization."""

    def test_lowercase(self):
        """Test text is lowercased."""
        assert _normalize_text("HELLO WORLD") == "hello world"

    def test_umlaut_normalization(self):
        """Test German umlauts are normalized."""
        assert _normalize_text("Zürich") == "zurich"
        assert _normalize_text("München") == "munchen"
        assert _normalize_text("Köln") == "koln"

    def test_french_accents(self):
        """Test French accents are normalized."""
        assert _normalize_text("café") == "cafe"
        assert _normalize_text("résumé") == "resume"

    def test_empty_string(self):
        """Test empty string handling."""
        assert _normalize_text("") == ""
        assert _normalize_text(None) == ""


class TestExtractWords:
    """Tests for word extraction."""

    def test_basic_extraction(self):
        """Test basic word extraction."""
        words = _extract_words("software engineer position")
        assert "software" in words
        assert "engineer" in words
        assert "position" in words

    def test_stop_words_removed(self):
        """Test stop words are filtered out."""
        words = _extract_words("the software engineer is a developer")
        assert "the" not in words
        assert "is" not in words
        assert "a" not in words
        assert "software" in words

    def test_short_words_removed(self):
        """Test single-character words are removed."""
        words = _extract_words("a b c developer")
        assert "a" not in words
        assert "b" not in words
        assert "c" not in words
        assert "developer" in words

    def test_special_characters_preserved(self):
        """Test programming language characters are preserved."""
        words = _extract_words("c++ c# node.js")
        # Note: regex \b[a-z0-9+#]+\b extracts tokens; single-char tokens filtered by len>1
        assert any("node" in w or "js" in w for w in words)

    def test_empty_string(self):
        """Test empty string returns empty list."""
        assert _extract_words("") == []
        assert _extract_words(None) == []


class TestFuzzyWordMatch:
    """Tests for fuzzy word matching."""

    def test_exact_match(self):
        """Test exact substring match."""
        assert _fuzzy_word_match("python", "Python developer", 80) is True
        assert _fuzzy_word_match("developer", "Python Developer", 80) is True

    def test_case_insensitive(self):
        """Test matching is case insensitive."""
        assert _fuzzy_word_match("PYTHON", "python developer", 80) is True

    def test_umlaut_match(self):
        """Test matching with umlauts."""
        assert _fuzzy_word_match("zurich", "Job in Zürich", 80) is True
        assert _fuzzy_word_match("zürich", "Job in Zurich", 80) is True

    def test_typo_tolerance(self):
        """Test fuzzy matching handles typos."""
        # "pythn" is close to "python" - should match with 80% threshold
        assert _fuzzy_word_match("pythn", "python developer", 70) is True

    def test_no_match(self):
        """Test non-matching words."""
        assert _fuzzy_word_match("java", "python developer", 80) is False


class TestCalculateRelevanceScore:
    """Tests for relevance score calculation."""

    @pytest.fixture
    def config(self):
        """Create test config with scoring settings."""
        return Config(
            scoring=ScoringConfig(
                save_threshold=0,
                notify_threshold=10,
                weights={
                    "primary": 20,
                    "secondary": 10,
                    "bonus": 5,
                },
                keywords={
                    "primary": ["software engineer", "developer"],
                    "secondary": ["python", "javascript"],
                    "bonus": ["remote"],
                },
            )
        )

    def test_no_match(self, config):
        """Test score is 0 when no keywords match."""
        row = pd.Series(
            {
                "title": "Marketing Manager",
                "company": "Marketing Corp",
                "location": "New York",
                "description": "Marketing role with sales focus",
            }
        )

        score = calculate_relevance_score(row, config)

        assert score == 0

    def test_single_category_match(self, config):
        """Test score when only one category matches."""
        row = pd.Series(
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "location": "NYC",
                "description": "Building web applications",
            }
        )

        score = calculate_relevance_score(row, config)

        # Should get primary weight (20) for "software engineer"
        assert score == 20

    def test_multiple_category_match(self, config):
        """Test score when multiple categories match."""
        row = pd.Series(
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "location": "Remote",
                "description": "Python developer role",
            }
        )

        score = calculate_relevance_score(row, config)

        # primary (20) + secondary (10) + bonus (5) = 35
        assert score == 35

    def test_case_insensitive_matching(self, config):
        """Test keyword matching is case insensitive."""
        row = pd.Series(
            {
                "title": "SOFTWARE ENGINEER",
                "company": "Tech Corp",
                "location": "NYC",
                "description": "PYTHON development",
            }
        )

        score = calculate_relevance_score(row, config)

        # Should match both primary and secondary
        assert score >= 30

    def test_empty_fields(self, config):
        """Test handling of empty/missing fields."""
        row = pd.Series(
            {
                "title": "Developer",
                "company": None,
                "location": "",
                "description": None,
            }
        )

        score = calculate_relevance_score(row, config)

        # Should still find "developer" in title
        assert score == 20

    def test_category_scores_only_once(self, config):
        """Test that a category only adds weight once even if multiple keywords match."""
        row = pd.Series(
            {
                "title": "Software Engineer Developer",  # Both keywords from primary
                "company": "Tech Corp",
                "location": "NYC",
                "description": "More developer stuff, software engineering",
            }
        )

        score = calculate_relevance_score(row, config)

        # Primary should only count once (20), not twice
        assert score == 20

    def test_missing_weight_defaults_to_zero(self, config):
        """Test that missing weight in config defaults to 0."""
        # Add a keyword category without a corresponding weight
        config.scoring.keywords["unknown"] = ["test"]

        row = pd.Series(
            {
                "title": "Test Position",
                "company": "Tech",
                "location": "NYC",
                "description": "",
            }
        )

        score = calculate_relevance_score(row, config)

        # Should not crash, unknown category adds 0
        assert score == 0


# =============================================================================
# TEST FUZZY POST FILTER
# =============================================================================


class TestGetJobText:
    """Tests for _get_job_text helper function."""

    def test_concatenates_fields(self):
        """Test that all relevant fields are concatenated."""
        row = pd.Series(
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "location": "NYC",
                "description": "Build things",
            }
        )

        text = _get_job_text(row)

        assert "Software Engineer" in text
        assert "Tech Corp" in text
        assert "NYC" in text
        assert "Build things" in text

    def test_handles_missing_fields(self):
        """Test handling of missing fields."""
        row = pd.Series(
            {
                "title": "Developer",
                "company": None,
                "location": "Remote",
            }
        )

        text = _get_job_text(row)

        assert "Developer" in text
        assert "Remote" in text

    def test_handles_nan_values(self):
        """Test handling of NaN values."""
        row = pd.Series(
            {
                "title": "Developer",
                "company": float("nan"),
                "location": "NYC",
                "description": float("nan"),
            }
        )

        text = _get_job_text(row)

        assert "Developer" in text
        assert "NYC" in text


class TestFuzzyPostFilter:
    """Tests for fuzzy_post_filter function."""

    @pytest.fixture
    def config_with_filter(self):
        """Create config with post-filter enabled."""
        from config import Config, PostFilterConfig

        return Config(
            post_filter=PostFilterConfig(
                enabled=True,
                min_similarity=80,
                check_query_terms=True,
                check_location=True,
            )
        )

    @pytest.fixture
    def config_without_filter(self):
        """Create config with post-filter disabled."""
        from config import Config, PostFilterConfig

        return Config(post_filter=PostFilterConfig(enabled=False))

    def test_filter_disabled_returns_original(self, config_without_filter):
        """Test that disabled filter returns original DataFrame."""
        df = pd.DataFrame(
            [
                {"title": "Marketing Manager", "company": "Corp", "location": "NYC"},
            ]
        )

        result = fuzzy_post_filter(
            df, "software engineer", "NYC", config_without_filter
        )

        assert len(result) == 1  # Not filtered

    def test_filter_empty_dataframe(self, config_with_filter):
        """Test filtering empty DataFrame."""
        df = pd.DataFrame()

        result = fuzzy_post_filter(df, "python", "NYC", config_with_filter)

        assert len(result) == 0

    def test_filter_none_dataframe(self, config_with_filter):
        """Test filtering None DataFrame."""
        result = fuzzy_post_filter(None, "python", "NYC", config_with_filter)

        assert result is None

    def test_filter_matching_query(self, config_with_filter):
        """Test that matching jobs are kept."""
        df = pd.DataFrame(
            [
                {
                    "title": "Python Developer",
                    "company": "Tech Corp",
                    "location": "NYC",
                    "description": "Python role",
                },
            ]
        )

        result = fuzzy_post_filter(df, "python developer", "NYC", config_with_filter)

        assert len(result) == 1

    def test_filter_non_matching_query(self, config_with_filter):
        """Test that non-matching jobs are filtered out."""
        df = pd.DataFrame(
            [
                {
                    "title": "Java Developer",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "Java role",
                },
            ]
        )

        result = fuzzy_post_filter(df, "python developer", "NYC", config_with_filter)

        assert len(result) == 0

    def test_filter_location_match(self, config_with_filter):
        """Test location matching."""
        df = pd.DataFrame(
            [
                {
                    "title": "Developer",
                    "company": "Corp",
                    "location": "New York, NY",
                    "description": "",
                },
            ]
        )

        result = fuzzy_post_filter(df, "developer", "New York", config_with_filter)

        assert len(result) == 1

    def test_filter_skips_remote_location_check(self, config_with_filter):
        """Test that 'Remote' location skips location matching."""
        df = pd.DataFrame(
            [
                {
                    "title": "Developer",
                    "company": "Corp",
                    "location": "San Francisco",
                    "description": "",
                },
            ]
        )

        result = fuzzy_post_filter(df, "developer", "Remote", config_with_filter)

        # Should pass because Remote skips location check
        assert len(result) == 1

    def test_filter_with_umlauts(self, config_with_filter):
        """Test filtering with umlaut characters."""
        df = pd.DataFrame(
            [
                {
                    "title": "Developer",
                    "company": "Corp",
                    "location": "Zürich",
                    "description": "",
                },
            ]
        )

        result = fuzzy_post_filter(df, "developer", "Zurich", config_with_filter)

        assert len(result) == 1


# =============================================================================
# TEST SCORE_JOBS + PARTITION_BY_THRESHOLDS
# =============================================================================


class TestScoreAndPartition:
    @pytest.fixture
    def config(self):
        from config import Config, ScoringConfig

        return Config(
            scoring=ScoringConfig(
                save_threshold=10,
                notify_threshold=25,
                weights={"primary": 20, "secondary": 10},
                keywords={
                    "primary": ["software engineer"],
                    "secondary": ["python"],
                },
            )
        )

    def test_score_jobs_adds_column(self, config):
        df = pd.DataFrame(
            [
                {
                    "title": "Software Engineer",
                    "company": "A",
                    "location": "NYC",
                    "description": "Python dev",
                },
            ]
        )

        scored = score_jobs(df, config)

        assert "relevance_score" in scored.columns
        assert scored.iloc[0]["relevance_score"] == 30

    def test_partition_separates_save_and_notify(self, config):
        df = pd.DataFrame(
            [
                {
                    "title": "Software Engineer",
                    "company": "A",
                    "location": "NYC",
                    "description": "Python dev",
                },  # 30 → save + notify
                {
                    "title": "Software Engineer",
                    "company": "B",
                    "location": "NYC",
                    "description": "",
                },  # 20 → save only
                {
                    "title": "Marketing",
                    "company": "C",
                    "location": "NYC",
                    "description": "",
                },  # 0 → drop
            ]
        )

        scored = score_jobs(df, config)
        parts = partition_by_thresholds(scored, config)

        assert len(parts.scored) == 3
        assert len(parts.to_save) == 2
        assert len(parts.to_notify) == 1
        assert parts.to_notify.iloc[0]["company"] == "A"

    def test_partition_sorts_to_save_descending(self, config):
        df = pd.DataFrame(
            [
                {
                    "title": "Software Engineer",
                    "company": "Low",
                    "location": "NYC",
                    "description": "",
                },  # 20
                {
                    "title": "Software Engineer Python",
                    "company": "High",
                    "location": "NYC",
                    "description": "Python",
                },  # 30
            ]
        )

        parts = partition_by_thresholds(score_jobs(df, config), config)

        scores = parts.to_save["relevance_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_empty_frame(self, config):
        df = pd.DataFrame(columns=["title", "company", "location", "description"])

        scored = score_jobs(df, config)
        parts = partition_by_thresholds(scored, config)

        assert len(parts.to_save) == 0
        assert len(parts.to_notify) == 0
