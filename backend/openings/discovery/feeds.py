"""Reading postings from a source: HTML text, Lever, Ashby and RSS, and adapters."""

from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

from ..collectors import company as company_collectors, jobspy as jobspy_collector
from ..errors import DomainError
from ..posting import matches_filters
from .network import HTTP_BUDGET, fetch_bytes


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "section"):
            self.parts.append("\n")
        values = dict(attrs)
        if tag in ("a", "iframe"):
            target = values.get("href") or values.get("src")
            if target:
                self.links.append(target)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li", "section"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(value: str) -> str:
    parser = TextParser()
    parser.feed(html.unescape(html.unescape(value or "")))
    return "\n".join(
        line
        for line in (
            re.sub(r"\s+", " ", item).strip() for item in "".join(parser.parts).splitlines()
        )
        if line
    )


def _json(url: str):
    try:
        return json.loads(fetch_bytes(url))
    except (ValueError, UnicodeError) as error:
        raise DomainError(502, "source_format", "The source returned invalid JSON.") from error


def normalize_posting(item: dict) -> dict:
    """All collectors emit the archive's canonical filter metadata."""
    metadata = dict(item.get("metadata") or {})
    if "remote" in metadata:
        metadata["is_remote"] = metadata.pop("remote")
    if "is_remote" not in metadata:
        workplace = str(metadata.get("workplace_type") or "").casefold()
        metadata["is_remote"] = (
            True if workplace == "remote" else False if workplace in ("onsite", "on-site") else None
        )
    date = metadata.pop("published_at", None) or metadata.get("date_posted")
    if isinstance(date, (int, float)) and not isinstance(date, bool):
        try:
            date = (
                datetime.fromtimestamp(date / 1000 if date > 100000000000 else date, UTC)
                .date()
                .isoformat()
            )
        except ValueError, OverflowError, OSError:
            date = None
    metadata["date_posted"] = (
        str(date)[:10] if date and re.match(r"\d{4}-\d{2}-\d{2}", str(date)) else None
    )
    types = metadata.get("job_types") or metadata.get("job_type") or metadata.get("employment_type")
    if isinstance(types, str):
        types = [part.strip() for part in types.split(",") if part.strip()]
    types = types if isinstance(types, list) else []
    types = [
        str(value).strip().casefold().replace("-", "").replace(" ", "") for value in types if value
    ]
    metadata["job_type"] = types[0] if types else None
    if len(types) > 1:
        metadata["job_types"] = types
    if "salary" not in metadata:
        metadata["salary"] = metadata.get("salary_range") or metadata.get("compensation") or None
    return {**item, "metadata": metadata}


def fetch_postings(source: dict) -> list[dict]:
    config, kind = source["config"], source["kind"]
    name = source.get("name") or config.get("board") or "RSS source"
    board = config.get("board", "")
    slug = quote(board, safe="")
    items = []
    if kind == "jobspy":
        budget = HTTP_BUDGET.get()
        if budget is None:
            raise DomainError(
                500, "provider_gate", "The shared HTTP gate is required for portal collection."
            )
        items, diagnostic = jobspy_collector.collect(
            {key: val for key, val in config.items() if key not in ("url", "filters")},
            source["provider"],
            budget,
            preview=source.get("preview", False),
            source=source,
        )
        source["streamed"] = source.get("on_item") is not None
        source["diagnostic"] = diagnostic
    elif kind not in ("lever", "ashby", "rss"):
        source["streamed"] = source.get("on_item") is not None
        items = company_collectors.collect(
            source,
            fetch_bytes,
            html_text,
            known=source.get("known"),
            preview=source.get("preview", False),
            on_item=source.get("on_item"),
        )
    elif kind == "lever":
        host = "api.eu.lever.co" if config.get("region") == "eu" else "api.lever.co"
        raw = _json(f"https://{host}/v0/postings/{slug}?mode=json")
        for row in company_collectors.records(raw):
            lists = [
                f"{item.get('text', '')}\n{html_text(item.get('content', ''))}"
                for item in row.get("lists", [])
            ]
            posting = "\n\n".join(
                part
                for part in [
                    row.get("descriptionPlain") or html_text(row.get("description", "")),
                    *lists,
                    row.get("additionalPlain") or html_text(row.get("additional", "")),
                ]
                if part
            )
            items.append(
                {
                    "source_key": f"lever:{board}:{row['id']}",
                    "title": row.get("text", "Untitled role"),
                    "company": name,
                    "location": (row.get("categories") or {}).get("location", ""),
                    "url": row.get("hostedUrl", ""),
                    "posting": posting,
                    "metadata": {
                        "ats": kind,
                        "board": board,
                        "external_id": row["id"],
                        "categories": row.get("categories", {}),
                        "workplace_type": row.get("workplaceType"),
                        "salary_range": row.get("salaryRange"),
                        "published_at": row.get("createdAt"),
                    },
                    "raw": row,
                }
            )
    elif kind == "ashby":
        try:
            raw = _json(
                f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
            )
        except DomainError as error:
            if error.code == "source_http" and (error.details or {}).get("http_status") == 404:
                raise DomainError(
                    422,
                    "ashby_board_unavailable",
                    f"Ashby does not expose a public board for '{board}' (HTTP 404). "
                    "Check the exact board URL and identifier. Disabled, removed or private "
                    "boards require another public source or manual job entry.",
                    {"http_status": 404, "board": board},
                ) from error
            raise
        for row in company_collectors.records(raw, "jobs"):
            if row.get("isListed") is False:
                continue
            url = row.get("jobUrl", "")
            identity = str(row.get("id") or urlsplit(url).path.rstrip("/").split("/")[-1])
            if not identity:
                continue
            items.append(
                {
                    "source_key": f"ashby:{board}:{identity}",
                    "title": row.get("title", "Untitled role"),
                    "company": name,
                    "location": row.get("location", ""),
                    "url": url,
                    "posting": row.get("descriptionPlain")
                    or html_text(row.get("descriptionHtml", "")),
                    "metadata": {
                        "ats": kind,
                        "board": board,
                        "external_id": identity,
                        "department": row.get("department"),
                        "remote": row.get("isRemote"),
                        "workplace_type": row.get("workplaceType"),
                        "employment_type": row.get("employmentType"),
                        "compensation": row.get("compensation"),
                        "published_at": row.get("publishedAt"),
                    },
                    "raw": row,
                }
            )
    elif kind == "rss":
        body = fetch_bytes(config["url"], maximum=2 * 1024 * 1024)
        if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
            raise DomainError(
                422, "source_format", "RSS declarations with entities are not supported."
            )
        try:
            root = ET.fromstring(body)
        except ET.ParseError as error:
            raise DomainError(502, "source_format", "The feed returned invalid XML.") from error
        if root.tag not in (
            "rss",
            "{http://www.w3.org/2005/Atom}feed",
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF",
        ):
            raise DomainError(502, "source_format", "The URL did not return an RSS or Atom feed.")
        for row in list(root.findall(".//item")) + list(
            root.findall("{http://www.w3.org/2005/Atom}entry")
        ):

            def text(tag, row=row):
                element = row.find(tag)
                if element is None:
                    element = row.find("{http://www.w3.org/2005/Atom}" + tag)
                return (element.text or "").strip() if element is not None else ""

            link = text("link")
            if not link:
                link = next(
                    (
                        item.get("href", "")
                        for item in row.findall("{http://www.w3.org/2005/Atom}link")
                        if item.get("rel", "alternate") == "alternate"
                    ),
                    "",
                )
            identity = text("guid") or text("id") or link
            if not identity:
                continue
            description = text("description") or text("content") or text("summary")
            items.append(
                {
                    "source_key": "rss:"
                    + hashlib.sha256((config["url"] + "\0" + identity).encode()).hexdigest(),
                    "title": text("title") or "Untitled role",
                    "company": name,
                    "location": "",
                    "url": urljoin(config["url"], link),
                    "posting": html_text(description),
                    "metadata": {
                        "feed": config["url"],
                        "external_id": identity,
                        "published_at": text("pubDate") or text("published"),
                    },
                    "raw": {"guid": identity, "description": description},
                }
            )
    else:
        raise DomainError(422, "unsupported_source", "This source type is not supported.")
    filters = config.get("filters") or {}
    return [normalize_posting(item) for item in items if matches_filters(item, filters)][
        : min(config.get("max_results", 2000), 20 if source.get("preview") else 2000)
    ]
