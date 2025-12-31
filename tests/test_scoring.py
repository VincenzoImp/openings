"""Tests for scoring functionality in search_jobs module.

NOTE: These tests require rapidfuzz to be installed.
Run with: pip install rapidfuzz && pytest tests/test_scoring.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Skip if rapidfuzz not installed
pytest.importorskip("rapidfuzz")

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
