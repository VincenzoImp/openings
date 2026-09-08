"""Shared building blocks for ingestion sources."""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable

import pandas as pd
import requests
from markdownify import markdownify

from openings.models import SourceRunStats
from openings.text import normalize_text

CANONICAL_COLUMNS = (
    "title",
    "company",
    "location",
    "source",
    "external_id",
    "job_url",
    "description",
    "date_posted",
    "job_type",
    "is_remote",
    "job_level",
    "min_amount",
    "max_amount",
    "currency",
    "salary_interval",
    "company_url",
    "raw_json",
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class SourceError(RuntimeError):
    """A source could not be read. Isolated per source; never aborts a run."""


@dataclass
class SourceResult:
    """Rows produced by one source plus what happened while producing them."""

    stats: SourceRunStats
    frame: pd.DataFrame = field(default_factory=lambda: empty_frame())


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CANONICAL_COLUMNS))


def frame_from_records(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Build a canonical frame, filling missing columns with ``None``."""
    rows = [{column: record.get(column) for column in CANONICAL_COLUMNS} for record in records]
    if not rows:
        return empty_frame()
    return pd.DataFrame(rows, columns=list(CANONICAL_COLUMNS))


def location_allowed(location: str | None, patterns: Iterable[str]) -> bool:
    """True when no patterns are configured or one of them appears in the location."""
    patterns = [normalize_text(pattern) for pattern in patterns if pattern]
    if not patterns:
        return True
    haystack = normalize_text(location or "")
    return any(pattern in haystack for pattern in patterns)


def html_to_markdown(value: str | None) -> str | None:
    """Convert an HTML fragment to Markdown; passes plain text through."""
    if not value:
        return None
    text = html.unescape(str(value))
    if "<" not in text:
        return text.strip() or None
    converted = markdownify(text, heading_style="ATX", strip=["img", "script", "style"])
    lines = [line.rstrip() for line in converted.splitlines()]
    cleaned = "\n".join(lines).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned or None


def to_date(value: Any) -> date | None:
    """Best-effort date from ISO strings, epoch seconds or milliseconds."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, time.struct_time):
        return date(value.tm_year, value.tm_mon, value.tm_mday)
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1e11:  # epoch milliseconds
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def raw_json(payload: Any) -> str:
    return json.dumps(payload, default=str, ensure_ascii=False)


def http_get(
    url: str,
    *,
    user_agent: str | None,
    timeout: float,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    request_headers = {
        "User-Agent": user_agent or DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        request_headers.update(headers)
    try:
        response = requests.get(url, params=params, headers=request_headers, timeout=timeout)
    except requests.RequestException as exc:
        raise SourceError(f"{url}: {exc}") from exc
    if response.status_code >= 400:
        raise SourceError(f"{url}: HTTP {response.status_code}")
    return response


def http_get_json(
    url: str,
    *,
    user_agent: str | None,
    timeout: float,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    response = http_get(url, user_agent=user_agent, timeout=timeout, params=params, headers=headers)
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError(f"{url}: response is not JSON") from exc
