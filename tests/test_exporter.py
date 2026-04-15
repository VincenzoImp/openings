"""Tests for exporter module."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from exporter import (
    _sanitize_dataframe_for_excel,
    _sanitize_excel_value,
    dataframe_to_csv_bytes,
    dataframe_to_excel_bytes,
    export_dataframe,
)


class TestSanitizeExcelValue:
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
        assert _sanitize_excel_value(value) == expected

    def test_safe_dash_not_escaped(self):
        assert _sanitize_excel_value("-some text") == "-some text"
        assert _sanitize_excel_value("- bullet point") == "- bullet point"

    def test_safe_string_unchanged(self):
        assert _sanitize_excel_value("Software Engineer") == "Software Engineer"
        assert _sanitize_excel_value("https://example.com") == "https://example.com"

    def test_empty_string_unchanged(self):
        assert _sanitize_excel_value("") == ""

    def test_non_string_passthrough(self):
        assert _sanitize_excel_value(42) == 42
        assert _sanitize_excel_value(None) is None
        assert _sanitize_excel_value(True) is True


class TestSanitizeDataframeForExcel:
    def test_sanitizes_dangerous_values(self):
        df = pd.DataFrame(
            {
                "title": ["=CMD()", "Safe Title"],
                "company": ["+1Evil Corp", "Good Corp"],
                "score": [10, 20],
            }
        )

        result = _sanitize_dataframe_for_excel(df)

        assert result.iloc[0]["title"] == "'=CMD()"
        assert result.iloc[1]["title"] == "Safe Title"
        assert result.iloc[0]["company"] == "'+1Evil Corp"
        assert result.iloc[0]["score"] == 10

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"title": ["=EVIL()"]})
        original = df.iloc[0]["title"]

        _sanitize_dataframe_for_excel(df)

        assert df.iloc[0]["title"] == original

    def test_handles_nan_values(self):
        df = pd.DataFrame({"title": ["=CMD()", None, float("nan")]})

        result = _sanitize_dataframe_for_excel(df)

        assert result.iloc[0]["title"] == "'=CMD()"
        assert pd.isna(result.iloc[1]["title"])


class TestExportDataframe:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame(
            {
                "title": ["Software Engineer", "Data Scientist"],
                "company": ["Corp A", "Corp B"],
                "location": ["NYC", "SF"],
                "relevance_score": [30, 25],
                "job_url": ["https://example.com/1", "https://example.com/2"],
            }
        )

    def test_export_csv(self, sample_df, tmp_path):
        out = export_dataframe(sample_df, tmp_path, "jobs", "csv")

        assert out.exists()
        assert out.suffix == ".csv"
        loaded = pd.read_csv(out)
        assert len(loaded) == 2

    def test_export_excel(self, sample_df, tmp_path):
        out = export_dataframe(sample_df, tmp_path, "jobs", "excel")

        assert out.exists()
        assert out.suffix == ".xlsx"
        loaded = pd.read_excel(out)
        assert len(loaded) == 2

    def test_export_csv_sanitizes_formulas(self, tmp_path):
        dangerous_df = pd.DataFrame(
            {
                "title": ['=HYPERLINK("http://evil","click")'],
                "company": ["Corp"],
            }
        )

        out = export_dataframe(dangerous_df, tmp_path, "dangerous", "csv")

        loaded = pd.read_csv(out)
        assert loaded.iloc[0]["title"].startswith("'=")

    def test_export_excel_sanitizes_formulas(self, tmp_path):
        dangerous_df = pd.DataFrame(
            {
                "title": ["=CMD()", "Safe"],
                "company": ["Corp", "Corp"],
                "location": ["NYC", "SF"],
            }
        )

        out = export_dataframe(dangerous_df, tmp_path, "dangerous", "excel")

        loaded = pd.read_excel(out)
        assert loaded.iloc[0]["title"] == "'=CMD()"

    def test_export_creates_output_dir_lazily(self, sample_df, tmp_path):
        target = tmp_path / "nested" / "results"
        assert not target.exists()

        out = export_dataframe(sample_df, target, "jobs", "csv")

        assert target.exists()
        assert out.exists()

    def test_invalid_format_raises(self, sample_df, tmp_path):
        with pytest.raises(ValueError, match="fmt must be"):
            export_dataframe(sample_df, tmp_path, "jobs", "json")


class TestDataframeToExcelBytes:
    def test_returns_empty_bytes_for_empty_dataframe(self):
        assert dataframe_to_excel_bytes(pd.DataFrame()) == b""


class TestDataframeToCsvBytes:
    def test_sanitizes_formula_values(self):
        csv_bytes = dataframe_to_csv_bytes(
            pd.DataFrame({"title": ["=CMD()"], "company": ["Corp"]})
        )

        loaded = pd.read_csv(BytesIO(csv_bytes))
        assert loaded.iloc[0]["title"] == "'=CMD()"

    def test_sanitizes_excel_output(self):
        df = pd.DataFrame(
            {"title": ["=CMD()"], "company": ["Corp"], "relevance_score": [42]}
        )

        excel_bytes = dataframe_to_excel_bytes(df)

        workbook = load_workbook(BytesIO(excel_bytes))
        worksheet = workbook["Jobs"]
        assert worksheet["A2"].value == "'=CMD()"
