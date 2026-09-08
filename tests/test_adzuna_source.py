from unittest.mock import patch

from openings.config import parse_config
from openings.sources.adzuna import _record, run_adzuna
from openings.sources.base import SourceError
from tests.conftest import minimal_settings

RESULT = {
    "id": 123,
    "title": "Backend Engineer",
    "company": {"display_name": "Acme"},
    "location": {"display_name": "Berlin, Germany"},
    "redirect_url": "https://adzuna.example/123",
    "description": "Python and PostgreSQL",
    "created": "2026-09-07T10:00:00Z",
    "contract_time": "full_time",
    "salary_min": 60000,
    "salary_max": 80000,
}


def adzuna_config(data_dir, **overrides):
    data = minimal_settings()
    data["sources"]["adzuna"] = {
        "enabled": True,
        "country": "de",
        "queries": ["backend engineer"],
        "app_id": "id",
        "app_key": "key",
        "results_per_page": 50,
        "max_pages": 2,
        **overrides,
    }
    return parse_config(data, data_dir=data_dir)


def test_record_maps_fields():
    record = _record(RESULT)
    assert record["source"] == "adzuna"
    assert record["external_id"] == "123"
    assert record["company"] == "Acme"
    assert record["location"] == "Berlin, Germany"
    assert str(record["date_posted"]) == "2026-09-07"
    assert record["job_type"] == "fulltime"
    assert _record({**RESULT, "contract_time": "part_time"})["job_type"] == "parttime"
    assert _record({**RESULT, "contract_type": "contract"})["job_type"] == "contract"


def test_run_adzuna_disabled(config):
    result = run_adzuna(config)
    assert result.stats.tasks == 0 and result.frame.empty


def test_run_adzuna_collects_and_filters_locations(data_dir):
    config = adzuna_config(data_dir, locations=["Berlin"])
    other = {**RESULT, "id": 124, "location": {"display_name": "Munich, Germany"}}
    with patch(
        "openings.sources.adzuna.http_get_json", return_value={"results": [RESULT, other]}
    ) as get:
        result = run_adzuna(config)
    assert result.stats.tasks == 1 and result.stats.succeeded == 1
    assert list(result.frame["external_id"]) == ["123"]
    params = get.call_args.kwargs["params"]
    assert params["what"] == "backend engineer" and params["where"] == "Berlin"
    assert "/jobs/de/search/1" in get.call_args.args[0]


def test_run_adzuna_paginates_until_a_short_page(data_dir):
    config = adzuna_config(data_dir, results_per_page=1, max_pages=3)
    pages = [{"results": [RESULT]}, {"results": [{**RESULT, "id": 2}]}, {"results": []}]
    with patch("openings.sources.adzuna.http_get_json", side_effect=pages) as get:
        result = run_adzuna(config)
    assert get.call_count == 3
    assert result.stats.rows == 2


def test_run_adzuna_reports_source_errors(data_dir):
    config = adzuna_config(data_dir)
    with patch("openings.sources.adzuna.http_get_json", side_effect=SourceError("401")):
        result = run_adzuna(config)
    assert result.stats.failed == 1
    assert result.stats.errors == ["backend engineer @ anywhere: 401"]
