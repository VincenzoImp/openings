"""RSS and Atom feeds of postings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import feedparser

from openings.sources.base import SourceError, html_to_markdown, http_get, raw_json, to_date

if TYPE_CHECKING:
    from openings.config import FeedSourceConfig

_LOCATION_KEYS = ("location", "job_location", "joblocation", "georss_featurename", "region")


def _entry_location(entry: Any) -> str:
    for key in _LOCATION_KEYS:
        value = entry.get(key)
        if value:
            return str(value)
    return ""


def _entry_company(entry: Any, feed_title: str, default: str) -> str:
    for key in ("company", "author", "dc_creator"):
        value = entry.get(key)
        if value:
            return str(value)
    return feed_title or default


def fetch(feed: FeedSourceConfig, user_agent: str | None, timeout: float) -> list[dict[str, Any]]:
    response = http_get(
        feed.url,
        user_agent=user_agent,
        timeout=timeout,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
        },
    )
    parsed = feedparser.parse(response.content)
    if parsed.get("bozo") and not parsed.get("entries"):
        raise SourceError(f"{feed.url}: not a readable feed ({parsed.get('bozo_exception')})")
    feed_title = str((parsed.get("feed") or {}).get("title") or "")

    records: list[dict[str, Any]] = []
    for entry in parsed.get("entries") or []:
        content = entry.get("content") or []
        body = content[0].get("value") if content else None
        description = html_to_markdown(body or entry.get("summary") or entry.get("description"))
        published = (
            entry.get("published_parsed")
            or entry.get("updated_parsed")
            or entry.get("published")
            or entry.get("updated")
        )
        records.append(
            {
                "title": str(entry.get("title") or ""),
                "company": _entry_company(entry, feed_title, feed.name),
                "location": _entry_location(entry),
                "source": "rss",
                "external_id": entry.get("id") or entry.get("link"),
                "job_url": entry.get("link"),
                "description": description,
                "date_posted": to_date(published),
                "company_url": (parsed.get("feed") or {}).get("link"),
                "raw_json": raw_json({key: entry.get(key) for key in entry.keys()}),
            }
        )
    return records
