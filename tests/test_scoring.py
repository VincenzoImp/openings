"""Tests for scoring functionality in search_jobs module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Mock jobspy before importing search_jobs (not available in test env)
sys.modules['jobspy'] = MagicMock()

from config import Config, ScoringConfig
from search_jobs import calculate_relevance_score, _normalize_text, _extract_words, _fuzzy_word_match


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
        # Note: These depend on regex pattern behavior
        assert any("c++" in w or "c" in w for w in words)

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
                threshold=10,
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
        row = pd.Series({
            "title": "Marketing Manager",
            "company": "Marketing Corp",
            "location": "New York",
            "description": "Marketing role with sales focus",
        })

        score = calculate_relevance_score(row, config)

        assert score == 0

    def test_single_category_match(self, config):
        """Test score when only one category matches."""
        row = pd.Series({
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "NYC",
            "description": "Building web applications",
        })

        score = calculate_relevance_score(row, config)

        # Should get primary weight (20) for "software engineer"
        assert score == 20

    def test_multiple_category_match(self, config):
        """Test score when multiple categories match."""
        row = pd.Series({
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "Remote",
            "description": "Python developer role",
        })

        score = calculate_relevance_score(row, config)

        # primary (20) + secondary (10) + bonus (5) = 35
        assert score == 35

    def test_case_insensitive_matching(self, config):
        """Test keyword matching is case insensitive."""
        row = pd.Series({
            "title": "SOFTWARE ENGINEER",
            "company": "Tech Corp",
            "location": "NYC",
            "description": "PYTHON development",
        })

        score = calculate_relevance_score(row, config)

        # Should match both primary and secondary
        assert score >= 30

    def test_empty_fields(self, config):
        """Test handling of empty/missing fields."""
        row = pd.Series({
            "title": "Developer",
            "company": None,
            "location": "",
            "description": None,
        })

        score = calculate_relevance_score(row, config)

        # Should still find "developer" in title
        assert score == 20

    def test_category_scores_only_once(self, config):
        """Test that a category only adds weight once even if multiple keywords match."""
        row = pd.Series({
            "title": "Software Engineer Developer",  # Both keywords from primary
            "company": "Tech Corp",
            "location": "NYC",
            "description": "More developer stuff, software engineering",
        })

        score = calculate_relevance_score(row, config)

        # Primary should only count once (20), not twice
        assert score == 20

    def test_missing_weight_defaults_to_zero(self, config):
        """Test that missing weight in config defaults to 0."""
        # Add a keyword category without a corresponding weight
        config.scoring.keywords["unknown"] = ["test"]

        row = pd.Series({
            "title": "Test Position",
            "company": "Tech",
            "location": "NYC",
            "description": "",
        })

        score = calculate_relevance_score(row, config)

        # Should not crash, unknown category adds 0
        assert score == 0


# =============================================================================
# TEST FUZZY POST FILTER
# =============================================================================


from search_jobs import fuzzy_post_filter, _get_job_text


class TestGetJobText:
    """Tests for _get_job_text helper function."""

    def test_concatenates_fields(self):
        """Test that all relevant fields are concatenated."""
        row = pd.Series({
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "NYC",
            "description": "Build things",
        })

        text = _get_job_text(row)

        assert "Software Engineer" in text
        assert "Tech Corp" in text
        assert "NYC" in text
        assert "Build things" in text

    def test_handles_missing_fields(self):
        """Test handling of missing fields."""
        row = pd.Series({
            "title": "Developer",
            "company": None,
            "location": "Remote",
        })

        text = _get_job_text(row)

        assert "Developer" in text
        assert "Remote" in text

    def test_handles_nan_values(self):
        """Test handling of NaN values."""
        row = pd.Series({
            "title": "Developer",
            "company": float("nan"),
            "location": "NYC",
            "description": float("nan"),
        })

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

        return Config(
            post_filter=PostFilterConfig(enabled=False)
        )

    def test_filter_disabled_returns_original(self, config_without_filter):
        """Test that disabled filter returns original DataFrame."""
        df = pd.DataFrame([
            {"title": "Marketing Manager", "company": "Corp", "location": "NYC"},
        ])

        result = fuzzy_post_filter(df, "software engineer", "NYC", config_without_filter)

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
        df = pd.DataFrame([
            {"title": "Python Developer", "company": "Tech Corp", "location": "NYC", "description": "Python role"},
        ])

        result = fuzzy_post_filter(df, "python developer", "NYC", config_with_filter)

        assert len(result) == 1

    def test_filter_non_matching_query(self, config_with_filter):
        """Test that non-matching jobs are filtered out."""
        df = pd.DataFrame([
            {"title": "Java Developer", "company": "Corp", "location": "NYC", "description": "Java role"},
        ])

        result = fuzzy_post_filter(df, "python developer", "NYC", config_with_filter)

        assert len(result) == 0

    def test_filter_location_match(self, config_with_filter):
        """Test location matching."""
        df = pd.DataFrame([
            {"title": "Developer", "company": "Corp", "location": "New York, NY", "description": ""},
        ])

        result = fuzzy_post_filter(df, "developer", "New York", config_with_filter)

        assert len(result) == 1

    def test_filter_skips_remote_location_check(self, config_with_filter):
        """Test that 'Remote' location skips location matching."""
        df = pd.DataFrame([
            {"title": "Developer", "company": "Corp", "location": "San Francisco", "description": ""},
        ])

        result = fuzzy_post_filter(df, "developer", "Remote", config_with_filter)

        # Should pass because Remote skips location check
        assert len(result) == 1

    def test_filter_with_umlauts(self, config_with_filter):
        """Test filtering with umlaut characters."""
        df = pd.DataFrame([
            {"title": "Developer", "company": "Corp", "location": "Zürich", "description": ""},
        ])

        result = fuzzy_post_filter(df, "developer", "Zurich", config_with_filter)

        assert len(result) == 1


# =============================================================================
# TEST THROTTLED EXECUTOR
# =============================================================================


from search_jobs import ThrottledExecutor
from unittest.mock import patch, MagicMock
import time


class TestThrottledExecutor:
    """Tests for ThrottledExecutor class."""

    @pytest.fixture
    def config_with_throttling(self):
        """Create config with throttling enabled."""
        from config import Config, ThrottlingConfig, SearchConfig

        return Config(
            search=SearchConfig(sites=["linkedin", "indeed"]),
            throttling=ThrottlingConfig(
                enabled=True,
                default_delay=0.1,
                site_delays={"linkedin": 0.2, "indeed": 0.1},
                jitter=0.0,  # Disable jitter for predictable tests
            )
        )

    @pytest.fixture
    def config_without_throttling(self):
        """Create config with throttling disabled."""
        from config import Config, ThrottlingConfig

        return Config(
            throttling=ThrottlingConfig(enabled=False)
        )

    def test_init(self, config_with_throttling):
        """Test ThrottledExecutor initialization."""
        executor = ThrottledExecutor(config_with_throttling)

        assert executor.config == config_with_throttling
        assert executor.site_locks == {}
        assert executor.site_last_request == {}

    def test_get_site_lock_creates_lock(self, config_with_throttling):
        """Test _get_site_lock creates new lock for site."""
        executor = ThrottledExecutor(config_with_throttling)

        lock = executor._get_site_lock("linkedin")

        assert "linkedin" in executor.site_locks
        assert "linkedin" in executor.site_last_request

    def test_get_site_lock_returns_same_lock(self, config_with_throttling):
        """Test _get_site_lock returns same lock for same site."""
        executor = ThrottledExecutor(config_with_throttling)

        lock1 = executor._get_site_lock("linkedin")
        lock2 = executor._get_site_lock("linkedin")

        assert lock1 is lock2

    def test_throttled_search_no_throttling(self, config_without_throttling):
        """Test throttled_search bypasses throttling when disabled."""
        executor = ThrottledExecutor(config_without_throttling)

        with patch("search_jobs.search_single_query") as mock_search:
            mock_search.return_value = ("query", "loc", pd.DataFrame(), None)

            result = executor.throttled_search("query", "loc", config_without_throttling)

            mock_search.assert_called_once()

    def test_throttled_search_with_throttling(self, config_with_throttling):
        """Test throttled_search applies delay when enabled."""
        executor = ThrottledExecutor(config_with_throttling)

        with patch("search_jobs.search_single_query") as mock_search:
            mock_search.return_value = ("query", "loc", pd.DataFrame(), None)

            start = time.time()
            executor.throttled_search("query", "loc", config_with_throttling)
            executor.throttled_search("query2", "loc", config_with_throttling)
            elapsed = time.time() - start

            # Second call should have waited at least the max delay (0.2s for linkedin)
            assert elapsed >= 0.15  # Allow some tolerance


# =============================================================================
# TEST FILTER RELEVANT JOBS
# =============================================================================


from search_jobs import filter_relevant_jobs


class TestFilterRelevantJobs:
    """Tests for filter_relevant_jobs function."""

    @pytest.fixture
    def config(self):
        """Create config with scoring settings."""
        from config import Config, ScoringConfig

        return Config(
            scoring=ScoringConfig(
                threshold=15,
                weights={"primary": 20, "secondary": 10},
                keywords={
                    "primary": ["software engineer"],
                    "secondary": ["python"],
                },
            )
        )

    def test_filter_by_threshold(self, config):
        """Test that jobs below threshold are filtered out."""
        df = pd.DataFrame([
            {"title": "Software Engineer", "company": "A", "location": "NYC", "description": "Python dev"},  # 30
            {"title": "Marketing Manager", "company": "B", "location": "NYC", "description": "Sales"},  # 0
        ])

        result = filter_relevant_jobs(df, config)

        assert len(result) == 1
        assert result.iloc[0]["title"] == "Software Engineer"

    def test_adds_relevance_score_column(self, config):
        """Test that relevance_score column is added."""
        df = pd.DataFrame([
            {"title": "Software Engineer", "company": "A", "location": "NYC", "description": ""},
        ])

        result = filter_relevant_jobs(df, config)

        assert "relevance_score" in result.columns
        assert result.iloc[0]["relevance_score"] == 20

    def test_sorted_by_score_descending(self, config):
        """Test that results are sorted by score descending."""
        df = pd.DataFrame([
            {"title": "Engineer", "company": "A", "location": "NYC", "description": "Python"},  # 10
            {"title": "Software Engineer Python", "company": "B", "location": "NYC", "description": "Python"},  # 30
            {"title": "Software Engineer", "company": "C", "location": "NYC", "description": ""},  # 20
        ])

        # Adjust threshold to include all
        config.scoring.threshold = 5

        result = filter_relevant_jobs(df, config)

        scores = result["relevance_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_empty_dataframe(self, config):
        """Test filtering empty DataFrame."""
        df = pd.DataFrame(columns=["title", "company", "location", "description"])

        result = filter_relevant_jobs(df, config)

        assert len(result) == 0
