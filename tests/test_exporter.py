"""Tests for exporter module."""

from __future__ import annotations

from io import BytesIO
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from openpyxl import load_workbook

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from exporter import (
    _sanitize_dataframe_for_excel,
    _sanitize_excel_value,
    dataframe_to_excel_bytes,
    save_results,
)


# =============================================================================
# TEST _sanitize_excel_value
# =============================================================================


class TestSanitizeExcelValue:
    """Tests for _sanitize_excel_value function."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("=SUM(A1:A10)", "'=SUM(A1:A10)"),
            ("+1234567890", "'+1234567890"),
            ("-5 years experience", "'-5 years experience"),
            ("@mention", "'@mention"),
        ],
    )
    def test_formula_injection_prevention(self, value, expected):
        """Test that values starting with =, +, -, @ are escaped when dangerous."""
        assert _sanitize_excel_value(value) == expected

    def test_safe_dash_not_escaped(self):
        """Test that text starting with dash followed by letter is not escaped."""
        assert _sanitize_excel_value("-some text") == "-some text"
        assert _sanitize_excel_value("- bullet point") == "- bullet point"

    def test_safe_string_unchanged(self):
        """Test that safe strings are not modified."""
        assert _sanitize_excel_value("Software Engineer") == "Software Engineer"
        assert _sanitize_excel_value("Hello World") == "Hello World"
        assert _sanitize_excel_value("https://example.com") == "https://example.com"

    def test_empty_string_unchanged(self):
        """Test that empty string is not modified."""
        assert _sanitize_excel_value("") == ""

    def test_non_string_passthrough(self):
        """Test that non-string values pass through unchanged."""
        assert _sanitize_excel_value(42) == 42
        assert _sanitize_excel_value(3.14) == 3.14
        assert _sanitize_excel_value(None) is None
        assert _sanitize_excel_value(True) is True


# =============================================================================
# TEST _sanitize_dataframe_for_excel
# =============================================================================


class TestSanitizeDataframeForExcel:
    """Tests for _sanitize_dataframe_for_excel function."""

    def test_sanitizes_dangerous_values(self):
        """Test that dangerous values in text columns are sanitized."""
        df = pd.DataFrame(
            {
                "title": ["=CMD()", "Safe Title"],
                "company": ["+1Evil Corp", "Good Corp"],
                "score": [10, 20],  # numeric column should not be touched
            }
        )

        result = _sanitize_dataframe_for_excel(df)

        assert result.iloc[0]["title"] == "'=CMD()"
        assert result.iloc[1]["title"] == "Safe Title"
        assert result.iloc[0]["company"] == "'+1Evil Corp"
        assert result.iloc[1]["company"] == "Good Corp"
        # Numeric columns are unchanged
        assert result.iloc[0]["score"] == 10

    def test_does_not_modify_original(self):
        """Test that original DataFrame is not modified."""
        df = pd.DataFrame({"title": ["=EVIL()"]})
        original_value = df.iloc[0]["title"]

        _sanitize_dataframe_for_excel(df)

        assert df.iloc[0]["title"] == original_value

    def test_handles_nan_values(self):
        """Test that NaN values are preserved."""
        df = pd.DataFrame({"title": ["=CMD()", None, float("nan")]})

        result = _sanitize_dataframe_for_excel(df)

        assert result.iloc[0]["title"] == "'=CMD()"
        assert pd.isna(result.iloc[1]["title"])
        assert pd.isna(result.iloc[2]["title"])


# =============================================================================
# TEST save_results
# =============================================================================


class TestSaveResults:
    """Tests for save_results function."""

    @pytest.fixture
    def output_config(self, tmp_path):
        """Create a mock config that writes to a temp directory."""
        config = MagicMock()
        config.output.save_csv = True
        config.output.save_excel = True
        config.results_path = tmp_path
        return config

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for export tests."""
        return pd.DataFrame(
            {
                "title": ["Software Engineer", "Data Scientist"],
                "company": ["Corp A", "Corp B"],
                "location": ["NYC", "SF"],
                "relevance_score": [30, 25],
                "job_url": ["https://example.com/1", "https://example.com/2"],
            }
        )

    def test_save_csv(self, output_config, sample_df, tmp_path):
        """Test saving to CSV creates a file."""
        output_config.output.save_excel = False

        csv_path, excel_path = save_results(sample_df, output_config)

        assert csv_path != ""
        assert Path(csv_path).exists()
        assert excel_path == ""

        # Verify CSV content
        loaded = pd.read_csv(csv_path)
        assert len(loaded) == 2
        assert "title" in loaded.columns

    def test_save_excel(self, output_config, sample_df, tmp_path):
        """Test saving to Excel creates a file."""
        output_config.output.save_csv = False

        csv_path, excel_path = save_results(sample_df, output_config)

        assert csv_path == ""
        assert excel_path != ""
        assert Path(excel_path).exists()

    def test_save_both(self, output_config, sample_df, tmp_path):
        """Test saving both CSV and Excel."""
        csv_path, excel_path = save_results(sample_df, output_config)

        assert csv_path != ""
        assert excel_path != ""
        assert Path(csv_path).exists()
        assert Path(excel_path).exists()

    def test_save_empty_dataframe(self, output_config, tmp_path):
        """Test saving empty DataFrame."""
        empty_df = pd.DataFrame(
            columns=["title", "company", "location", "relevance_score"]
        )

        csv_path, excel_path = save_results(empty_df, output_config)

        # CSV should still be created (even if empty)
        assert csv_path != ""
        assert Path(csv_path).exists()
        # Excel should be skipped for empty DataFrame
        assert excel_path == ""

    def test_save_csv_disabled(self, output_config, sample_df, tmp_path):
        """Test that CSV is not saved when disabled."""
        output_config.output.save_csv = False
        output_config.output.save_excel = False

        csv_path, excel_path = save_results(sample_df, output_config)

        assert csv_path == ""
        assert excel_path == ""

    def test_save_excel_disabled(self, output_config, sample_df, tmp_path):
        """Test that Excel is not saved when disabled."""
        output_config.output.save_csv = True
        output_config.output.save_excel = False

        csv_path, excel_path = save_results(sample_df, output_config)

        assert csv_path != ""
        assert excel_path == ""

    def test_both_disabled(self, output_config, sample_df, tmp_path):
        """Test both outputs disabled returns empty strings."""
        output_config.output.save_csv = False
        output_config.output.save_excel = False

        csv_path, excel_path = save_results(sample_df, output_config)

        assert csv_path == ""
        assert excel_path == ""

    def test_creates_results_directory(self, sample_df, tmp_path):
        """Test that results directory is created if it doesn't exist."""
        config = MagicMock()
        config.output.save_csv = True
        config.output.save_excel = False
        config.results_path = tmp_path / "nested" / "results"

        csv_path, _ = save_results(sample_df, config)

        assert csv_path != ""
        assert Path(csv_path).exists()

    def test_excel_sanitizes_formulas(self, output_config, tmp_path):
        """Test that Excel output sanitizes formula injection values."""
        dangerous_df = pd.DataFrame(
            {
                "title": ["=CMD()", "Safe Title"],
                "company": ["Corp", "Corp"],
                "location": ["NYC", "SF"],
            }
        )
        output_config.output.save_csv = False

        csv_path, excel_path = save_results(dangerous_df, output_config)

        assert excel_path != ""
        # Read back and verify sanitization
        loaded = pd.read_excel(excel_path)
        assert loaded.iloc[0]["title"] == "'=CMD()"


class TestDataframeToExcelBytes:
    """Tests for in-memory Excel rendering."""

    def test_returns_empty_bytes_for_empty_dataframe(self):
        """Test empty DataFrames short-circuit cleanly."""
        assert dataframe_to_excel_bytes(pd.DataFrame()) == b""

    def test_sanitizes_excel_output(self):
        """Test exported in-memory Excel keeps formula-like strings escaped."""
        df = pd.DataFrame(
            {
                "title": ["=CMD()"],
                "company": ["Corp"],
                "relevance_score": [42],
            }
        )

        excel_bytes = dataframe_to_excel_bytes(df)

        workbook = load_workbook(BytesIO(excel_bytes))
        worksheet = workbook["Jobs"]
        assert worksheet["A2"].value == "'=CMD()"
