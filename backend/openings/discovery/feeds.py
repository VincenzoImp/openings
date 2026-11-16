"""Reading postings from a source: HTML text, Lever, Ashby, RSS, HN and adapters."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import partial
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

from ..collectors import (
    company as company_collectors,
    hnhiring as hnhiring_collector,
    jobspy as jobspy_collector,
)
from ..errors import DomainError
from ..posting import matches_filters
from .network import HTTP_BUDGET, MAX_LISTING_BYTES, fetch_bytes

# A board's employment types in JobSpy's terms, the values the job_type filter takes.
JOB_TYPES = (
    ("internship", r"intern(?!ation)|trainee|apprentic|praktik"),
    ("parttime", r"parttime|workingstudent|werkstudent|teilzeit|(salaried|hourly)pt"),
    ("fulltime", r"fulltime|vollzeit|(salaried|hourly)ft"),
    ("contract", r"contract|freelance"),
    ("temporary", r"temporary|fixedterm|seasonal"),
)


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


def _json(url: str, kind: str, board: str):
    try:
        return json.loads(fetch_bytes(url, maximum=MAX_LISTING_BYTES, home_is_missing=True))
    except DomainError as error:
        raise company_collectors.board_error(error, kind, board) from error
    except (ValueError, UnicodeError) as error:
        # Often an error or maintenance page during an outage: tried again later.
        raise DomainError(
            503,
            "source_unavailable",
            "The source answered with a page that is not JSON; it is tried again later.",
        ) from error


def job_types(values) -> list[str]:
    """fulltime, parttime, contract, internship or temporary, in the board's order."""
    found = []
    for value in values:
        word = re.sub(r"[^a-z]", "", str(value).casefold())
        if word in ("fullorparttime", "fullparttime"):
            found.append("fulltime")
        found.extend(name for name, pattern in JOB_TYPES if re.search(pattern, word))
    return list(dict.fromkeys(found))


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
    elif isinstance(date, str) and not re.match(r"\d{4}-\d{2}-\d{2}", date):
        # RSS 2.0 dates are RFC 822: "Wed, 21 Oct 2026 12:54:56 +0000".
        try:
            date = parsedate_to_datetime(date).date().isoformat()
        except TypeError, ValueError:
            date = None
    metadata["date_posted"] = (
        str(date)[:10] if date and re.match(r"\d{4}-\d{2}-\d{2}", str(date)) else None
    )
    raw = metadata.get("job_types") or metadata.get("job_type") or metadata.get("employment_type")
    values = raw.split(",") if isinstance(raw, str) else raw if isinstance(raw, list) else []
    types = job_types(values)
    if raw and [str(value) for value in values] != types:
        metadata["job_type_raw"] = raw  # the board's own value; normalized values keep it
    metadata["job_type"] = types[0] if types else None
    if len(types) > 1:
        metadata["job_types"] = types
    else:
        metadata.pop("job_types", None)
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
    elif kind == "hnhiring":
        items = hnhiring_collector.collect(
            partial(fetch_bytes, maximum=MAX_LISTING_BYTES), html_text, config, source
        )
    elif kind not in ("lever", "ashby", "rss"):
        source["streamed"] = source.get("on_item") is not None
        items = company_collectors.collect(
            source,
            partial(fetch_bytes, maximum=MAX_LISTING_BYTES, home_is_missing=True),
            html_text,
            known=source.get("known"),
            preview=source.get("preview", False),
            on_item=source.get("on_item"),
        )
    elif kind == "lever":
        host = "api.eu.lever.co" if config.get("region") == "eu" else "api.lever.co"
        raw = company_collectors.records(
            _json(f"https://{host}/v0/postings/{slug}?mode=json", kind, board)
        )
        source["listing_empty"] = not raw
        for row in raw:
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
                    "location": company_collectors.places(
                        (row.get("categories") or {}).get("location"),
                        *((row.get("categories") or {}).get("allLocations") or []),
                    ),
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
        raw = company_collectors.records(
            _json(
                f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
                kind,
                board,
            ),
            "jobs",
        )
        source["listing_empty"] = not raw
        for row in raw:
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
                    "location": company_collectors.places(
                        row.get("location"),
                        *(
                            item.get("location") if isinstance(item, dict) else item
                            for item in row.get("secondaryLocations") or []
                        ),
                    ),
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
        root = company_collectors.xml(body, "The feed returned invalid XML.")
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
    # Normalized first: the filters read the remote flag of a workplace type.
    items = [normalize_posting(item) for item in items]
    return [item for item in items if matches_filters(item, filters)][
        : min(config.get("max_results", 2000), 20 if source.get("preview") else 2000)
    ]
