"""Company feeds and persisted collection tasks."""

from __future__ import annotations

import asyncio
import hashlib
import html
import ipaddress
import json
import logging
import re
import socket
import time
import xml.etree.ElementTree as ET
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import parse_qs, quote, urljoin, urlsplit

import httpcore
import httpx
from fastapi import Query
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .common import (
    check_version,
    decode_record,
    encode,
    missing,
    new_id,
    now,
)
from . import __version__
from .errors import DomainError, conflict
from .posting import posting_complete, posting_complete_sql, matches_filters
from .scheduling import Schedule, IntervalSchedule, schedule_adapter, next_due
from .collectors import company as company_collectors
from .collectors import jobspy as jobspy_collector
from .collectors.catalog import COMPANY_ADAPTERS, COMPANY_KINDS
from .collectors.policy import (
    ProviderBudget,
    ProviderDeferred,
    ProviderPatch,
    ProviderStore,
    provider_for_url,
)

LOG = logging.getLogger(__name__)
SourceKind = Literal["auto", "jobspy", "rss", *COMPANY_KINDS]


def automatic_collection_supported(kind):
    adapter = COMPANY_ADAPTERS.get(kind)
    return adapter is None or adapter.description_mode != "metadata"


def require_automatic_collection(kind):
    if not automatic_collection_supported(kind):
        raise DomainError(
            422,
            "source_description_unavailable",
            f"{kind.title()} supplies listing metadata without posting text. "
            "Use another public source for automatic collection, or add the full posting manually.",
        )


MAX_FEED_BYTES = 8 * 1024 * 1024
HTTP_BUDGET: ContextVar[ProviderBudget | None] = ContextVar("collection_http_budget", default=None)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Filters(Input):
    titles: list[str] = Field(default_factory=list, max_length=30)
    locations: list[str] = Field(default_factory=list, max_length=30)
    exclude_titles: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("titles", "locations", "exclude_titles")
    @classmethod
    def clean_terms(cls, values):
        return list(dict.fromkeys(v.strip()[:150] for v in values if v.strip()))


class SourcePreview(Input):
    name: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)
    kind: SourceKind = "auto"
    config: dict[str, Any] = Field(default_factory=dict)
    filters: Filters = Field(default_factory=Filters)


class SourceCreate(SourcePreview):
    enabled: bool = False
    schedule: Schedule = Field(default_factory=IntervalSchedule)


class RSSConfig(Input):
    url: str = Field(min_length=1, max_length=2000)
    max_results: int = Field(default=100, ge=1, le=2000)


class SourcePatch(Input):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    kind: SourceKind | None = None
    config: dict[str, Any] | None = None
    filters: Filters | None = None
    enabled: bool | None = None
    schedule: Schedule | None = None

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Source fields cannot be null; omit unchanged fields.")
        return self


class CollectionWrite(Input):
    enabled: bool
    expected_version: int = Field(ge=0)


class SourceVersion(Input):
    id: str
    expected_version: int = Field(ge=1)


class RunOverrides(Input):
    hours_old: int | None = Field(default=None, ge=1, le=8760)
    results_wanted: int | None = Field(default=None, ge=1, le=50)
    max_results: int | None = Field(default=None, ge=1, le=2000)

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Omit unchanged run options rather than sending null.")
        return self


class SourceRun(Input):
    expected_version: int = Field(ge=1)
    overrides: RunOverrides = Field(default_factory=RunOverrides)


class SourceConfigure(Input):
    schedule: Schedule | None = None
    config: dict[str, Any] | None = None
    filters: Filters | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null configuration field.")
        return self


class SourceBulk(Input):
    action: Literal["enable", "pause", "run", "delete", "configure"]
    items: list[SourceVersion] = Field(min_length=1, max_length=200)
    patch: SourceConfigure | None = None
    overrides: RunOverrides = Field(default_factory=RunOverrides)

    @model_validator(mode="after")
    def valid_options(self):
        if (self.action == "configure") != (self.patch is not None):
            raise ValueError("A configuration patch is required only for Configure.")
        if self.action != "run" and self.overrides.model_fields_set:
            raise ValueError("Run overrides apply only to Run.")
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("Select each source once.")
        return self


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


def public_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise DomainError(
            422, "invalid_url", "Use a public HTTP(S) URL without embedded credentials."
        )
    public_addresses(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    return value


def is_public_address(address: str) -> bool:
    return ipaddress.ip_address(address).is_global


def public_addresses(host: str, port: int) -> list[str]:
    """Resolve a host once; every address must be public or the request is refused."""
    try:
        rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise DomainError(
            422, "unreachable_url", "The URL's host could not be resolved."
        ) from error
    addresses = list(dict.fromkeys(str(row[4][0]) for row in rows))
    if not addresses or not all(is_public_address(item) for item in addresses):
        raise DomainError(
            422, "private_url", "Collection URLs must resolve to public network addresses."
        )
    return addresses


class PublicNetworkBackend(httpcore.SyncBackend):
    """Connect only to the public addresses checked for this connection.

    Resolving inside the connection and dialing the checked IP closes the DNS
    rebinding window between the URL check and httpx's own name resolution. TLS
    still verifies the certificate against the requested host name.
    """

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        failure = None
        for address in public_addresses(host, port):
            try:
                return super().connect_tcp(address, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                failure = error
        raise failure


class PublicTransport(httpx.HTTPTransport):
    """An httpx transport whose every connection, including redirect hops, is pinned."""

    def __init__(self):
        super().__init__(trust_env=False)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(trust_env=False),
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            network_backend=PublicNetworkBackend(),
        )


def fetch_bytes(
    url: str,
    *,
    public: bool = True,
    maximum: int = MAX_FEED_BYTES,
    budget: ProviderBudget | None = None,
    method="GET",
    body=None,
) -> bytes:
    budget = budget or HTTP_BUDGET.get()
    current = url
    try:
        with httpx.Client(
            timeout=httpx.Timeout(20, connect=8),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": f"Openings/{__version__} (job archive)"},
            transport=PublicTransport() if public else None,
        ) as client:
            for _ in range(5):
                if public:
                    public_url(current)
                if budget:
                    budget.before(method, current)
                try:
                    response_context = (
                        client.stream(method, current, json=body)
                        if body is not None
                        else client.stream(method, current)
                    )
                    response = response_context.__enter__()
                except httpx.HTTPError as error:
                    if budget:
                        budget.after(None, error=type(error).__name__)
                    raise
                except DomainError as error:
                    # The connection-time address check refused this hop.
                    if budget:
                        budget.after(None, error=error.code)
                    raise
                try:
                    if budget:
                        budget.after(response.status_code, response.headers)
                        if budget.blocked:
                            raise budget.blocked
                    if response.is_redirect:
                        target = response.headers.get("location")
                        if not target:
                            raise DomainError(
                                502, "source_redirect", "The source returned an invalid redirect."
                            )
                        current = urljoin(current, target)
                        if response.status_code == 303 or (
                            response.status_code in (301, 302) and method == "POST"
                        ):
                            method, body = "GET", None
                        continue
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > maximum:
                            raise DomainError(
                                422,
                                "source_too_large",
                                "This feed exceeds the bounded collection size.",
                            )
                    return bytes(content)
                finally:
                    response_context.__exit__(None, None, None)
    except httpx.HTTPStatusError as error:
        raise DomainError(
            502,
            "source_http",
            f"The source returned HTTP {error.response.status_code}.",
            {"http_status": error.response.status_code},
        ) from error
    except httpx.HTTPError as error:
        raise DomainError(
            502, "source_unavailable", "The source could not be reached. Try again later."
        ) from error
    raise DomainError(422, "source_redirect", "The source redirected too many times.")


def detect_source(url: str) -> dict:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    kind, board, region = None, None, "global"
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        kind = "greenhouse"
        board = query.get("for", [None])[0] if "embed" in parts else (parts[0] if parts else None)
    elif host == "boards-api.greenhouse.io" and len(parts) >= 3 and parts[:2] == ["v1", "boards"]:
        kind, board = "greenhouse", parts[2]
    elif host in ("jobs.lever.co", "jobs.eu.lever.co"):
        kind, board = "lever", parts[0] if parts else None
        region = "eu" if ".eu." in host else "global"
    elif (
        host in ("api.lever.co", "api.eu.lever.co")
        and len(parts) >= 3
        and parts[:2] == ["v0", "postings"]
    ):
        kind, board = "lever", parts[2]
        region = "eu" if ".eu." in host else "global"
    elif host == "jobs.ashbyhq.com":
        kind, board = "ashby", parts[0] if parts else None
    elif (
        host == "api.ashbyhq.com" and len(parts) >= 3 and parts[:2] == ["posting-api", "job-board"]
    ):
        kind, board = "ashby", parts[2]
    elif host.endswith(".recruitee.com"):
        kind, board = "recruitee", host.removesuffix(".recruitee.com")
    elif host.endswith(".jobs.personio.de"):
        kind, board = "personio", host.removesuffix(".jobs.personio.de")
    elif host == "apply.workable.com" and parts:
        kind, board = "workable", parts[0]
    elif host.endswith(".breezy.hr"):
        kind, board = "breezy", host.removesuffix(".breezy.hr")
    elif host.endswith(".bamboohr.com"):
        kind, board = "bamboohr", host.removesuffix(".bamboohr.com")
    elif host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and parts:
        kind, board = "smartrecruiters", parts[0]
    elif host == "ats.rippling.com" and parts:
        kind, board = "rippling", parts[0]
    elif host == "join.com" and len(parts) >= 2 and parts[0] == "companies":
        kind, board = "joincom", parts[1]
    elif re.fullmatch(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com", host) and parts:
        site = (
            parts[1]
            if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]) and len(parts) > 1
            else parts[0]
        )
        kind, board = "workday", host + "/" + site
    elif host.endswith(".oraclecloud.com") and "sites" in parts:
        index = parts.index("sites") + 1
        if len(parts) > index:
            kind, board = "oracle", host + "/" + parts[index]
    if not kind or not board:
        raise DomainError(
            422,
            "unsupported_source",
            "Paste a supported ATS board URL, select RSS, or configure the board identifier manually.",
        )
    validate_board(board, kind)
    config = {"board": board}
    if COMPANY_ADAPTERS[kind].region:
        config["region"] = region
    return {"kind": kind, "config": config, "url": url}


def validate_board(board: str, kind=None):
    pattern = r"[A-Za-z0-9_.-]{1,120}"
    if kind == "workday":
        pattern = r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com/[A-Za-z0-9_-]{1,120}"
    elif kind == "oracle":
        pattern = r"[a-z0-9.-]+\.oraclecloud\.com/[A-Za-z0-9_-]{1,120}"
    if not isinstance(board, str) or not re.fullmatch(pattern, board):
        raise DomainError(
            422, "invalid_board", "The ATS board identifier contains unsupported characters."
        )


def resolve_source(value: dict) -> dict:
    kind, config, url = (
        value.get("kind", "auto"),
        dict(value.get("config") or {}),
        value.get("url", ""),
    )
    if kind == "auto":
        try:
            resolved = detect_source(url)
        except DomainError:
            if not url:
                raise
            page = fetch_bytes(url, maximum=2 * 1024 * 1024).decode("utf-8", errors="replace")
            parser = TextParser()
            parser.feed(page)
            found = {}
            for target in parser.links[:200]:
                try:
                    candidate = detect_source(urljoin(url, target))
                    found[(candidate["kind"], candidate["config"]["board"])] = candidate
                except DomainError:
                    continue
            if len(found) != 1:
                raise DomainError(
                    422,
                    "unsupported_source",
                    "A single supported ATS board could not be identified. Paste its board URL or select a source type.",
                )
            resolved = next(iter(found.values()))
        kind, config = resolved["kind"], {**config, **resolved["config"]}
        url = resolved["url"]
    elif kind == "jobspy":
        cls = jobspy_collector.JobSpyConfig
        try:
            config = cls.model_validate(
                {key: val for key, val in config.items() if key not in ("url", "filters")}
            ).model_dump()
        except ValidationError as error:
            raise DomainError(
                422,
                "source_config",
                "The saved search configuration is invalid.",
                error.errors(include_url=False, include_context=False),
            ) from error
    elif kind == "rss":
        url = url or config.get("url", "")
        try:
            config = RSSConfig.model_validate(
                {
                    **{key: val for key, val in config.items() if key not in ("url", "filters")},
                    "url": url,
                }
            ).model_dump()
        except ValidationError as error:
            raise DomainError(
                422,
                "source_config",
                "The RSS configuration is invalid.",
                error.errors(include_url=False, include_context=False),
            ) from error
        public_url(url)
    else:
        if not config.get("board") and url:
            resolved = detect_source(url)
            if resolved["kind"] != kind:
                raise DomainError(
                    422, "source_mismatch", "The URL does not match the selected ATS type."
                )
            config.update(resolved["config"])
    if kind not in ("jobspy", "rss"):
        validate_board(config.get("board", ""), kind)
        if config.get("region", "global") not in ("global", "eu"):
            raise DomainError(422, "invalid_region", "Lever region must be global or eu.")
        try:
            config = (
                company_collectors.config_model(kind)
                .model_validate(
                    {key: val for key, val in config.items() if key not in ("url", "filters")}
                )
                .model_dump()
            )
        except ValidationError as error:
            raise DomainError(
                422,
                "source_config",
                "The company board configuration is invalid.",
                error.errors(include_url=False, include_context=False),
            ) from error
    config["url"] = url
    config["filters"] = (
        value.get("filters")
        or config.get("filters")
        or {"titles": [], "locations": [], "exclude_titles": []}
    )
    return {"kind": kind, "config": config, "url": url}


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
                datetime.fromtimestamp(date / 1000 if date > 100000000000 else date, timezone.utc)
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

            def text(tag):
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


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class DiscoveryService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        self.providers = ProviderStore(self.db)

    def http_budget(self, provider_id, active=None):
        """Shared per-request gate for collectors, previews and manual URL import."""
        return ProviderBudget(self.providers, provider_id, active=active, validate_url=public_url)

    provider_for_url = staticmethod(provider_for_url)

    def fetch_bytes(
        self,
        url,
        *,
        provider_id="manual",
        maximum=MAX_FEED_BYTES,
        budget=None,
        method="GET",
        body=None,
    ):
        if provider_id == "manual":
            provider_id = provider_for_url(url)
        return fetch_bytes(
            url,
            maximum=maximum,
            budget=budget or self.http_budget(provider_id),
            method=method,
            body=body,
        )

    def _resolve_source(self, value):
        token = HTTP_BUDGET.set(self.http_budget("manual"))
        try:
            return resolve_source(value)
        finally:
            HTTP_BUDGET.reset(token)

    def get_collection(self):
        stored = self.workspace.get_settings("collection", {"enabled": True})
        enabled = bool((stored["data"] or {}).get("enabled", True))
        counts = self.db.one(
            "SELECT COUNT(*) AS source_count,COALESCE(SUM(enabled),0) AS enabled_sources FROM sources"
        )
        tasks = self.db.one(
            "SELECT SUM(state='queued') AS queued_tasks,SUM(state='running') AS running_tasks,MIN(CASE WHEN state='queued' THEN next_run_at END) AS next_run_at FROM tasks WHERE kind='collect'"
        )
        upcoming = [tasks["next_run_at"]] if tasks["next_run_at"] else []
        if enabled:
            upcoming.extend(
                next_due(
                    json.loads(row["schedule"]), row["last_scheduled_at"] or row["created_at"]
                ).isoformat(timespec="microseconds")
                for row in self.db.all(
                    "SELECT schedule,last_scheduled_at,created_at FROM sources WHERE enabled=1 AND NOT EXISTS(SELECT 1 FROM tasks WHERE source_id=sources.id AND kind='collect' AND state IN ('queued','running'))"
                )
            )
        return {
            "enabled": enabled,
            "version": stored["version"],
            **counts,
            "queued_tasks": tasks["queued_tasks"] or 0,
            "running_tasks": tasks["running_tasks"] or 0,
            "next_run_at": min(upcoming) if upcoming else None,
        }

    def update_collection(self, value: CollectionWrite):
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM settings WHERE key='collection'").fetchone()
            current = row["version"] if row else 0
            if current != value.expected_version:
                conflict(
                    "Collection settings changed. Reload before saving.",
                    details={"current_version": current},
                )
            stamp = now()
            connection.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES('collection',?,1,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=settings.version+1,updated_at=excluded.updated_at",
                (encode({"enabled": value.enabled}), stamp),
            )
        return self.get_collection()

    def list_providers(self):
        return self.providers.list()

    def update_provider(self, provider_id, value: ProviderPatch):
        result = self.providers.update(provider_id, value)
        if result["policy"]["enabled"]:
            # Policy changes may make a previously deferred queued request eligible.
            self.db.execute(
                "UPDATE tasks SET next_run_at=?,updated_at=? WHERE kind='collect' AND state='queued' AND json_extract(payload,'$.provider')=? AND error LIKE '%provider paused%'",
                (now(), now(), provider_id),
            )
        return result

    def bulk_sources(self, value: SourceBulk):
        items = []
        for selected in value.items:
            try:
                if value.action in ("enable", "pause"):
                    result = self.update_source(
                        selected.id,
                        SourcePatch(
                            expected_version=selected.expected_version,
                            enabled=value.action == "enable",
                        ),
                    )
                elif value.action == "configure":
                    result = self.update_source(
                        selected.id,
                        SourcePatch(
                            expected_version=selected.expected_version,
                            **value.patch.model_dump(exclude_unset=True),
                        ),
                    )
                else:
                    with self.db.lock:
                        source = self._source(selected.id)
                        check_version(source, selected.expected_version)
                        result = (
                            self.delete_source(selected.id, selected.expected_version)
                            if value.action == "delete"
                            else self.queue_collection(
                                selected.id,
                                expected_version=selected.expected_version,
                                overrides=value.overrides,
                            )
                        )
                items.append({"id": selected.id, "result": result})
            except DomainError as error:
                items.append(
                    {
                        "id": selected.id,
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "status": error.status,
                            "details": error.details,
                        },
                    }
                )
        failed = sum("error" in item for item in items)
        return {
            "items": items,
            "total": len(items),
            "succeeded": len(items) - failed,
            "failed": failed,
        }

    def _source(self, source_id):
        row = self.db.one("SELECT * FROM sources WHERE id=?", (source_id,))
        if row is None:
            missing("Source")
        return self._source_records([row])[0]

    @staticmethod
    def _run_summary(record):
        """Drop the frozen source snapshot and task payload/result bodies from a run record."""
        summary = {key: value for key, value in record.items() if key != "source_snapshot"}
        summary["tasks"] = [
            {
                "id": task["id"],
                "kind": task["kind"],
                "provider": task["payload"].get("provider"),
                "state": task["state"],
                "attempts": task["attempts"],
                "error": task["error"],
                "next_run_at": task["next_run_at"],
                "updated_at": task["updated_at"],
            }
            for task in record["tasks"]
        ]
        return summary

    def _source_records(self, rows, summary=False):
        if not rows:
            return []
        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        runs = self.db.all(
            "SELECT * FROM (SELECT *,ROW_NUMBER() OVER (PARTITION BY source_id ORDER BY created_at DESC,id DESC) AS position FROM collection_runs WHERE source_id IN ("
            + placeholders
            + ")) WHERE position=1",
            ids,
        )
        run_ids = [row["id"] for row in runs]
        tasks = (
            self.db.all(
                "SELECT * FROM tasks WHERE run_id IN (" + ",".join("?" for _ in run_ids) + ")",
                run_ids,
            )
            if run_ids
            else []
        )
        grouped = {run_id: [] for run_id in run_ids}
        for task in tasks:
            grouped[task["run_id"]].append(task)
        latest = {row["source_id"]: self._run_record(row, grouped[row["id"]]) for row in runs}
        enabled = (self.workspace.get_settings("collection", {"enabled": True})["data"] or {}).get(
            "enabled", True
        )
        result = []
        for raw in rows:
            row = decode_record(raw, ("config", "schedule"))
            row["enabled"] = bool(row["enabled"])
            row["automatic_collection"] = automatic_collection_supported(row["kind"])
            row["url"] = row["config"].get("url", "")
            row["filters"] = {
                "titles": [],
                "locations": [],
                "exclude_titles": [],
                **row["config"].get("filters", {}),
            }
            run = latest.get(row["id"])
            row["last_run"] = run
            row["last_outcome"] = run["state"] if run else None
            row["last_task_id"] = run["task_ids"][0] if run and run["task_ids"] else None
            row["last_counts"] = run["counts"] if run else {}
            diagnostics = (
                [diag for task in run["tasks"] for diag in task["result"].get("diagnostics", [])]
                if run
                else []
            )
            if summary:
                row["last_diagnostic_count"] = len(diagnostics)
            else:
                row["last_diagnostics"] = diagnostics
            row["last_error"] = (
                "; ".join(
                    task["error"]
                    for task in run["tasks"]
                    if task["error"] and task["state"] == "failed"
                )[:1000]
                or None
                if run
                else None
            )
            row["next_run_at"] = (
                run["next_run_at"]
                if run and run["state"] in ("queued", "running")
                else (
                    next_due(
                        row["schedule"], row["last_scheduled_at"] or row["created_at"]
                    ).isoformat(timespec="microseconds")
                    if row["enabled"] and enabled
                    else None
                )
            )
            if summary and run:
                row["last_run"] = self._run_summary(run)
            result.append(row)
        return result

    def _run_record(self, row, tasks):
        record = decode_record(row, ("source_snapshot", "overrides"))
        record.pop("position", None)
        decoded = [decode_record(task, ("payload", "result")) for task in tasks]
        states = {task["state"] for task in decoded}
        record["state"] = next(
            (
                state
                for state in ("running", "queued", "failed", "cancelled", "succeeded")
                if state in states
            ),
            "cancelled",
        )
        record["counts"] = {
            key: sum(task["result"].get(key, 0) for task in decoded)
            for key in (
                "received",
                "created",
                "existing",
                "invalid",
                "pending_descriptions",
                "unavailable_descriptions",
            )
        }
        record["task_ids"] = [task["id"] for task in decoded]
        record["started_at"] = min(
            (task["result"]["started_at"] for task in decoded if task["result"].get("started_at")),
            default=None,
        )
        record["finished_at"] = (
            max((task["updated_at"] for task in decoded), default=None)
            if not states.intersection(("queued", "running"))
            else None
        )
        ending = parse_time(record["finished_at"]) or datetime.now(timezone.utc)
        record["total_seconds"] = max(
            0, round((ending - parse_time(record["created_at"])).total_seconds(), 3)
        )
        record["processing_seconds"] = round(
            sum(task["result"].get("processing_seconds", 0) for task in decoded), 3
        )
        record["waiting_seconds"] = max(
            0, round(record["total_seconds"] - record["processing_seconds"], 3)
        )
        record["http_requests"] = sum(task["result"].get("http_requests", 0) for task in decoded)
        record["next_run_at"] = min(
            (task["next_run_at"] for task in decoded if task["state"] == "queued"), default=None
        )
        record["partial"] = any(
            task["result"].get("candidate_capped")
            or task["result"].get("result_capped")
            or task["result"].get("unavailable_descriptions")
            for task in decoded
        )
        record["tasks"] = [
            {key: value for key, value in task.items() if key not in ("lease_owner", "lease_until")}
            for task in decoded
        ]
        for task in record["tasks"]:
            task["payload"] = {
                key: value
                for key, value in task["payload"].items()
                if key not in ("checkpoint", "observed_identities")
            }
        return record

    def list_runs(self, limit=50, offset=0, source_id=None, state=None, summary=True):
        """List collection runs; summary=true omits frozen source snapshots and task payload/result bodies."""
        if state not in (None, "queued", "running", "succeeded", "failed", "cancelled"):
            raise DomainError(422, "run_state", "Use a supported collection run state.")
        states_sql = (
            "CASE "
            + " ".join(
                "WHEN EXISTS(SELECT 1 FROM tasks t WHERE t.run_id=r.id AND t.state='"
                + item
                + "') THEN '"
                + item
                + "'"
                for item in ("running", "queued", "failed", "cancelled", "succeeded")
            )
            + " ELSE 'cancelled' END"
        )
        clauses, params = [], []
        if source_id:
            clauses.append("source_id=?")
            params.append(source_id)
        if state:
            clauses.append("state=?")
            params.append(state)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        query = "SELECT r.*," + states_sql + " AS state FROM collection_runs r"
        rows = self.db.all(
            "SELECT * FROM ("
            + query
            + ")"
            + where
            + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (*params, min(max(limit, 1), 200), max(offset, 0)),
        )
        ids = [row["id"] for row in rows]
        tasks = (
            self.db.all(
                "SELECT * FROM tasks WHERE run_id IN ("
                + ",".join("?" for _ in ids)
                + ") ORDER BY created_at,id",
                ids,
            )
            if ids
            else []
        )
        grouped = {run_id: [] for run_id in ids}
        for task in tasks:
            grouped[task["run_id"]].append(task)
        records = [self._run_record(row, grouped[row["id"]]) for row in rows]
        return {
            "items": [self._run_summary(record) for record in records] if summary else records,
            "total": self.db.one("SELECT COUNT(*) AS n FROM (" + query + ")" + where, params)["n"],
        }

    def get_run(self, run_id):
        row = self.db.one("SELECT * FROM collection_runs WHERE id=?", (run_id,))
        if row is None:
            missing("Collection run")
        return self._run_record(
            row, self.db.all("SELECT * FROM tasks WHERE run_id=? ORDER BY created_at,id", (run_id,))
        )

    def cancel_run(self, run_id):
        self.get_run(run_id)
        self.db.execute(
            "UPDATE tasks SET state='cancelled',error=NULL,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE run_id=? AND state IN ('queued','running')",
            (now(), run_id),
        )
        return self.get_run(run_id)

    def source_schemas(self):
        items = []
        for kind in SourceKind.__args__:
            if kind == "auto":
                continue
            cls = (
                jobspy_collector.JobSpyConfig
                if kind == "jobspy"
                else RSSConfig
                if kind == "rss"
                else company_collectors.config_model(kind)
            )
            items.append(
                {
                    "kind": kind,
                    "label": "Saved portal search"
                    if kind == "jobspy"
                    else "RSS / Atom feed"
                    if kind == "rss"
                    else kind.title(),
                    "config_schema": cls.model_json_schema(),
                    "capabilities": {
                        "automatic_collection": automatic_collection_supported(kind),
                        "search": kind == "jobspy",
                        "lookback": kind == "jobspy",
                        "details": kind == "jobspy"
                        or (
                            kind in COMPANY_ADAPTERS
                            and COMPANY_ADAPTERS[kind].description_mode == "separate"
                        ),
                        "description_mode": "portal"
                        if kind == "jobspy"
                        else "inline"
                        if kind == "rss"
                        else COMPANY_ADAPTERS[kind].description_mode,
                    },
                }
            )
        return {
            "items": items,
            "schedule_schema": schedule_adapter.json_schema(),
            "run_overrides_schema": RunOverrides.model_json_schema(),
        }

    def list_sources(self, limit=100, offset=0, summary=True):
        """List sources; summary=true returns a compact last run and a diagnostic count instead of diagnostics."""
        rows = self.db.all(
            "SELECT * FROM sources ORDER BY name,id LIMIT ? OFFSET ?",
            (min(max(limit, 1), 500), max(offset, 0)),
        )
        return {
            "items": self._source_records(rows, summary=summary),
            "total": self.db.one("SELECT COUNT(*) AS n FROM sources")["n"],
        }

    def get_source(self, source_id):
        return self._source(source_id)

    def preview_source(self, value: SourcePreview):
        resolved = self._resolve_source(value.model_dump())
        source = {**resolved, "name": value.name or resolved["config"].get("board", "RSS source")}
        config = {
            key: val for key, val in source["config"].items() if key not in ("url", "filters")
        }
        providers = (
            source["config"]["providers"] if source["kind"] == "jobspy" else [source["kind"]]
        )

        def estimate(preview):
            if source["kind"] == "jobspy":
                return jobspy_collector.request_estimate(config, preview=preview)
            adapter = COMPANY_ADAPTERS.get(source["kind"])
            count = source["config"].get("max_results", 100)
            count = min(count, 3) if preview else count
            requests = 1 + (count if adapter and adapter.description_mode == "separate" else 0)
            return {
                "total": requests,
                "providers": [{"id": providers[0], "min": 1, "max": requests}],
                "note": "Listing pagination, redirects and retries may add requests; cached text can reduce detail fetches.",
            }

        items, diagnostics = [], []
        for provider in providers:
            budget = self.http_budget(provider)
            token = HTTP_BUDGET.set(budget)
            attempt = {**source, "provider": provider, "preview": True}
            try:
                items.extend(fetch_postings(attempt))
                diagnostics.append(attempt.get("diagnostic") or budget.diagnostics())
            except DomainError as error:
                diagnostic = budget.diagnostics()
                diagnostic.update(
                    state="deferred" if isinstance(error, ProviderDeferred) else "error",
                    message=error.message,
                )
                diagnostics.append(diagnostic)
            finally:
                HTTP_BUDGET.reset(token)
        return {
            **resolved,
            "items": [
                {key: val for key, val in item.items() if key != "raw"} for item in items[:20]
            ],
            "total": len(items),
            "preview_limit": 20,
            "request_estimate": estimate(True),
            "full_request_estimate": estimate(False),
            "automatic_collection": automatic_collection_supported(source["kind"]),
            "diagnostics": diagnostics,
        }

    def create_source(self, value: SourceCreate):
        if not value.name.strip():
            raise DomainError(422, "source_name", "Give the company or feed a name.")
        resolved = self._resolve_source(value.model_dump())
        require_automatic_collection(resolved["kind"])
        record_id, stamp = new_id(), now()
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO sources(id,name,kind,config,enabled,schedule,last_scheduled_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.name.strip(),
                    resolved["kind"],
                    encode(resolved["config"]),
                    int(value.enabled),
                    encode(value.schedule.model_dump()),
                    stamp,
                    stamp,
                    stamp,
                ),
            )
        return self._source(record_id)

    def update_source(self, source_id, value: SourcePatch):
        old = self._source(source_id)
        check_version(old, value.expected_version)
        updates = value.model_dump(exclude_unset=True)
        merged = {
            **old,
            **{
                key: val
                for key, val in updates.items()
                if key != "expected_version" and val is not None
            },
        }
        if "kind" in updates and updates["kind"] != old["kind"]:
            raise DomainError(
                422, "source_kind_immutable", "Create a new source to use a different service."
            )
        if "config" in updates:
            merged["config"] = {**old["config"], **updates["config"]}
        if "filters" in updates:
            merged["filters"] = {**old["filters"], **updates["filters"]}
        if not merged["name"].strip():
            raise DomainError(422, "source_name", "Give the company or feed a name.")
        if any(key in updates for key in ("url", "kind", "config", "filters")):
            resolved = self._resolve_source(merged)
        else:
            resolved = old
        if merged["enabled"]:
            require_automatic_collection(resolved["kind"])
        schedule = schedule_adapter.validate_python(merged["schedule"]).model_dump()
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            check_version(row, value.expected_version)
            connection.execute(
                "UPDATE sources SET name=?,kind=?,config=?,enabled=?,schedule=?,last_scheduled_at=?,version=version+1,updated_at=? WHERE id=?",
                (
                    merged["name"].strip(),
                    resolved["kind"],
                    encode(resolved["config"]),
                    int(merged["enabled"]),
                    encode(schedule),
                    now()
                    if "schedule" in updates or (merged["enabled"] and not old["enabled"])
                    else old["last_scheduled_at"],
                    now(),
                    source_id,
                ),
            )
        return self._source(source_id)

    def delete_source(self, source_id, expected_version=None):
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if row is None:
                missing("Source")
            check_version(row, expected_version)
            connection.execute(
                "UPDATE tasks SET state='cancelled',error=NULL,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE source_id=? AND state IN ('queued','running')",
                (now(), source_id),
            )
            connection.execute("DELETE FROM sources WHERE id=?", (source_id,))
        return {"deleted": True, "id": source_id}

    def queue_collection(
        self,
        source_id,
        *,
        manual=True,
        _stopping=None,
        expected_version=None,
        overrides=None,
        planned_at=None,
    ):
        options = (
            overrides
            if isinstance(overrides, RunOverrides)
            else RunOverrides.model_validate(overrides or {})
        ).model_dump(exclude_none=True)
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if row is None:
                missing("Source")
            check_version(row, expected_version)
            if _stopping is not None and _stopping.is_set():
                return None
            setting = connection.execute(
                "SELECT data FROM settings WHERE key='collection'"
            ).fetchone()
            if not manual and (
                not row["enabled"]
                or (setting and not json.loads(setting["data"]).get("enabled", True))
            ):
                return None
            source = decode_record(row, ("config", "schedule"))
            require_automatic_collection(source["kind"])
            allowed_overrides = (
                {"hours_old", "results_wanted"} if source["kind"] == "jobspy" else {"max_results"}
            )
            if set(options) - allowed_overrides:
                raise DomainError(
                    422, "run_options", "These run options do not apply to this source service."
                )
            active = connection.execute(
                "SELECT * FROM tasks WHERE source_id=? AND kind='collect' AND state IN ('queued','running') ORDER BY created_at,id",
                (source_id,),
            ).fetchall()
            if active:
                if not manual:
                    connection.execute(
                        "UPDATE sources SET last_scheduled_at=? WHERE id=?",
                        (planned_at or now(), source_id),
                    )
                active_run = connection.execute(
                    "SELECT overrides FROM collection_runs WHERE id=?", (active[0]["run_id"],)
                ).fetchone()
                if options and (not active_run or json.loads(active_run["overrides"]) != options):
                    raise DomainError(
                        409,
                        "collection_active",
                        "A collection is already active. Wait or stop it before running different options.",
                    )
                if manual:
                    connection.execute(
                        "UPDATE tasks SET payload=json_set(payload,'$.manual',json('true')),updated_at=? WHERE source_id=? AND kind='collect' AND state IN ('queued','running')",
                        (now(), source_id),
                    )
                task_ids = [task["id"] for task in active]
                task = self._task_record(active[0])
                task["payload"]["manual"] = manual or task["payload"].get("manual", False)
                return {**task, "task_ids": task_ids, "run_id": active[0]["run_id"]}
            source["config"] = {**source["config"], **options}
            # Validate the frozen effective configuration, not a temporary edit of the saved source.
            if source["kind"] == "jobspy":
                jobspy_collector.JobSpyConfig.model_validate(
                    {k: v for k, v in source["config"].items() if k not in ("url", "filters")}
                )
            providers = (
                source["config"]["providers"] if source["kind"] == "jobspy" else [source["kind"]]
            )
            run_id, stamp = new_id(), now()
            snapshot = {
                key: source[key] for key in ("id", "name", "kind", "config", "version", "schedule")
            }
            connection.execute(
                "INSERT INTO collection_runs(id,source_id,source_name,source_version,source_snapshot,overrides,planned_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    source_id,
                    source["name"],
                    source["version"],
                    encode(snapshot),
                    encode(options),
                    planned_at,
                    stamp,
                ),
            )
            task_ids = []
            for provider in providers:
                task_id = new_id()
                connection.execute(
                    "INSERT INTO tasks(id,kind,source_id,run_id,payload,dedupe_key,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        task_id,
                        "collect",
                        source_id,
                        run_id,
                        encode(
                            {
                                "manual": manual,
                                "source_version": source["version"],
                                "provider": provider,
                                "run_id": run_id,
                            }
                        ),
                        "collect:" + source_id + ":" + provider + ":" + task_id,
                        stamp,
                        stamp,
                        stamp,
                    ),
                )
                task_ids.append(task_id)
            if not manual:
                connection.execute(
                    "UPDATE sources SET last_scheduled_at=? WHERE id=?",
                    (planned_at or stamp, source_id),
                )
        task_ids.sort()
        return {**self.get_task(task_ids[0]), "task_ids": task_ids, "run_id": run_id}

    def list_tasks(self, limit=50, offset=0, state=None, kind=None, source_id=None, job_id=None):
        clauses, params = [], []
        for key, value in (
            ("state", state),
            ("kind", kind),
            ("source_id", source_id),
            ("job_id", job_id),
        ):
            if value is not None:
                if key == "state" and value not in (
                    "queued",
                    "running",
                    "succeeded",
                    "failed",
                    "cancelled",
                ):
                    raise DomainError(422, "task_state", "Use a supported task state.")
                if key == "kind" and value != "collect":
                    raise DomainError(422, "task_kind", "Use collect.")
                clauses.append("t." + key + "=?")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.all(
            "SELECT t.*,s.name AS source_name,j.title AS job_title FROM tasks t LEFT JOIN sources s ON s.id=t.source_id LEFT JOIN jobs j ON j.id=t.job_id"
            + where
            + " ORDER BY t.created_at DESC,t.id DESC LIMIT ? OFFSET ?",
            (*params, min(max(limit, 1), 200), max(offset, 0)),
        )
        return {
            "items": [self._task_record(row) for row in rows],
            "total": self.db.one("SELECT COUNT(*) AS n FROM tasks t" + where, params)["n"],
        }

    @staticmethod
    def _task_record(row, include_checkpoint=False):
        task = decode_record(row, ("payload", "result"))
        if not include_checkpoint:
            task["payload"] = {
                key: value
                for key, value in task["payload"].items()
                if key not in ("checkpoint", "observed_identities")
            }
        return task

    def get_task(self, task_id, *, include_checkpoint=False):
        row = self.db.one(
            "SELECT t.*,s.name AS source_name,j.title AS job_title FROM tasks t LEFT JOIN sources s ON s.id=t.source_id LEFT JOIN jobs j ON j.id=t.job_id WHERE t.id=?",
            (task_id,),
        )
        if row is None:
            missing("Task")
        return self._task_record(row, include_checkpoint)

    def cancel_task(self, task_id):
        self.get_task(task_id)
        self.db.execute(
            "UPDATE tasks SET state='cancelled',error=NULL,lease_until=NULL,lease_owner=NULL,updated_at=? WHERE id=? AND state IN ('queued','running')",
            (now(), task_id),
        )
        return self.get_task(task_id)

    def retry_task(self, task_id):
        task = self.get_task(task_id, include_checkpoint=True)
        if task["state"] not in ("failed", "cancelled"):
            raise DomainError(409, "task_state", "Only a failed or cancelled task can be retried.")
        if task["source_id"] is None:
            raise DomainError(
                409, "source_removed", "Create a source before starting another collection."
            )
        payload = {**task["payload"], "manual": True}
        active = self.db.one(
            "SELECT id FROM tasks WHERE id<>? AND kind=? AND state IN ('queued','running') AND (job_id=? OR (source_id=? AND json_extract(payload,'$.provider')=?)) LIMIT 1",
            (task_id, task["kind"], task["job_id"], task["source_id"], payload.get("provider")),
        )
        if active:
            raise DomainError(409, "task_active", "Equivalent work is already queued or running.")
        self.db.execute(
            "UPDATE tasks SET state='queued',payload=?,result=?,next_run_at=?,lease_until=NULL,lease_owner=NULL,error=NULL,updated_at=? WHERE id=? AND state IN ('failed','cancelled')",
            (
                encode(payload),
                encode({**task["result"], "failure_attempts": 0}),
                now(),
                now(),
                task_id,
            ),
        )
        return self.get_task(task_id)

    def schedule_due(self, stopping=None):
        moment = datetime.now(timezone.utc)
        for row in (
            self.db.all("SELECT * FROM sources WHERE enabled=1 ORDER BY created_at LIMIT 2000")
            if (self.workspace.get_settings("collection", {"enabled": True})["data"] or {}).get(
                "enabled", True
            )
            else []
        ):
            if stopping is not None and stopping.is_set():
                return
            source = decode_record(row, ("schedule", "config"))
            due = next_due(
                source["schedule"], source["last_scheduled_at"] or source["created_at"], moment
            )
            if due <= moment:
                self.queue_collection(
                    source["id"],
                    manual=False,
                    _stopping=stopping,
                    planned_at=(
                        moment if source["schedule"]["kind"] == "interval" else due
                    ).isoformat(timespec="microseconds"),
                )

    def claim_task(self, owner, kind=None):
        stamp = now()
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE tasks SET state='queued',lease_until=NULL,lease_owner=NULL,updated_at=? WHERE state='running' AND lease_until<?",
                (stamp, stamp),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE state='queued' AND next_run_at<=?"
                + (" AND kind=?" if kind else "")
                + " ORDER BY next_run_at,created_at,id LIMIT 1",
                (stamp, kind) if kind else (stamp,),
            ).fetchone()
            if row is None:
                return None
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(
                timespec="microseconds"
            )
            connection.execute(
                "UPDATE tasks SET state='running',attempts=attempts+1,lease_owner=?,lease_until=?,updated_at=? WHERE id=?",
                (owner, expiry, stamp, row["id"]),
            )
        return self.get_task(row["id"], include_checkpoint=True)

    def heartbeat(self, task_id, owner):
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(
            timespec="microseconds"
        )
        return bool(
            self.db.execute(
                "UPDATE tasks SET lease_until=? WHERE id=? AND state='running' AND lease_owner=?",
                (expiry, task_id, owner),
            )
        )

    def _active(self, task_id, owner):
        return (
            self.db.one(
                "SELECT id FROM tasks WHERE id=? AND state='running' AND lease_owner=?",
                (task_id, owner),
            )
            is not None
        )

    def _collect(self, task, owner):
        current_source = self.db.one("SELECT id FROM sources WHERE id=?", (task["source_id"],))
        if current_source is None:
            return {"cancelled": True}
        run = self.db.one(
            "SELECT source_snapshot FROM collection_runs WHERE id=?", (task["run_id"],)
        )
        if run is None:
            raise DomainError(409, "collection_run", "The collection invocation is missing.")
        source = json.loads(run["source_snapshot"])
        provider = task["payload"]["provider"]
        source["provider"] = provider
        prefix = (
            provider + ":"
            if source["kind"] == "jobspy"
            else f"{source['kind']}:{source['config'].get('board', '')}:"
        )
        known_rows = self.db.all(
            "SELECT i.identity,j.metadata,j.posting,d.checked_at,"
            + posting_complete_sql()
            + " AS complete "
            "FROM job_identities i JOIN jobs j ON j.id=i.job_id "
            "LEFT JOIN posting_details d ON d.identity=i.identity AND d.job_id=j.id "
            "WHERE i.identity>=? AND i.identity<?",
            (prefix, prefix + "\uffff"),
        )
        source["known"] = {
            row["identity"]: json.loads(row["metadata"]) for row in known_rows if row["complete"]
        }
        source["known_postings"] = {
            row["identity"]: row["posting"] for row in known_rows if row["complete"]
        }
        source["detail_checked"] = {
            row["identity"]: row["checked_at"] for row in known_rows if row["checked_at"]
        }
        source["checkpoint"] = dict(task["payload"].get("checkpoint") or {})
        budget = self.http_budget(
            provider,
            active=lambda: self._active(task["id"], owner),
        )
        task["budget"] = budget
        result = dict(task["result"])
        for key in ("received", "created", "existing", "invalid"):
            result.setdefault(key, 0)
        result.setdefault("started_at", now())
        task["partial_result"] = result
        observed = set(task["payload"].get("observed_identities") or [])

        def persist():
            self.db.execute(
                "UPDATE tasks SET payload=?,result=?,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
                (encode(task["payload"]), encode(result), now(), task["id"], owner),
            )

        def checkpoint(value):
            if not self._active(task["id"], owner):
                raise DomainError(409, "task_cancelled", "Collection was cancelled.")
            source["checkpoint"] = value
            task["payload"]["checkpoint"] = value
            for key, target in (
                ("pending_details", "pending_descriptions"),
                ("unavailable_descriptions", "unavailable_descriptions"),
            ):
                count = value.get(key, 0)
                result[target] = len(count) if isinstance(count, (list, dict)) else int(count or 0)
            persist()

        def store(posting):
            if not matches_filters(posting, source["config"].get("filters") or {}):
                return
            with self.db.lock:
                if not self._active(task["id"], owner):
                    raise DomainError(409, "task_cancelled", "Collection was cancelled.")
                posting = normalize_posting({**posting, "source_id": source["id"]})
                if not posting_complete(posting.get("posting"), posting.get("metadata"), {}):
                    # Incomplete candidates remain in the adapter checkpoint, outside the archive.
                    return
                identity = (
                    posting.get("source_key")
                    or posting.get("url")
                    or hashlib.sha256(encode(posting).encode()).hexdigest()
                )
                first_observation = identity not in observed
                try:
                    saved = self.workspace.ingest_job(posting)
                except (ValidationError, DomainError) as error:
                    if (
                        isinstance(error, DomainError)
                        and error.status != 422
                        and error.code != "identity_conflict"
                    ):
                        raise
                    if first_observation:
                        result["received"] += 1
                        result["invalid"] += 1
                        observed.add(identity)
                    if isinstance(error, DomainError) and error.code == "identity_conflict":
                        result["conflict_count"] = result.get("conflict_count", 0) + 1
                        conflicts = result.setdefault("identity_conflicts", [])
                        if len(conflicts) < 20:
                            conflicts.append(
                                {"source_key": posting.get("source_key"), **error.details}
                            )
                else:
                    checked_at = (source.get("detail_checks") or {}).get(posting.get("source_key"))
                    if checked_at:
                        self.db.execute(
                            "INSERT INTO posting_details(identity,job_id,checked_at) VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET job_id=excluded.job_id,checked_at=excluded.checked_at",
                            (posting["source_key"], saved["id"], checked_at),
                        )
                    if first_observation:
                        result["received"] += 1
                        result["created"] += int(bool(saved.get("created")))
                        result["existing"] += int(not saved.get("created", False))
                        observed.add(identity)
                task["payload"]["observed_identities"] = sorted(observed)
                persist()

        source["on_item"] = store
        source["on_checkpoint"] = checkpoint
        if not self._active(task["id"], owner):
            return {"cancelled": True}
        self.db.execute(
            "UPDATE sources SET last_run_at=?,last_error=NULL WHERE id=?",
            (result["started_at"], source["id"]),
        )
        token = HTTP_BUDGET.set(budget)
        try:
            postings = fetch_postings(source)
        finally:
            HTTP_BUDGET.reset(token)
        if len(postings) > 2000:
            raise DomainError(
                422,
                "collection_limit",
                "This feed has more than 2000 matching postings. Narrow the source filters.",
            )
        if not source.get("streamed"):
            result["unavailable_descriptions"] = sum(
                not posting_complete(posting.get("posting"), posting.get("metadata"), {})
                for posting in postings
                if matches_filters(posting, source["config"].get("filters") or {})
            )
            for posting in postings:
                store(posting)
        diagnostic = source.get("diagnostic") or budget.diagnostics()
        for key, message in (
            (
                "candidate_capped",
                "Only a bounded part of this board was inspected; additional matching jobs may exist.",
            ),
            (
                "result_capped",
                "More jobs match than this source's result limit. Increase the result limit or narrow its filters.",
            ),
        ):
            if source.get(key):
                result[key] = True
                diagnostic.setdefault("warnings", []).append(message)
        result["diagnostics"] = [diagnostic]
        if budget.blocked:
            raise budget.blocked
        if source.get("collection_error"):
            raise source["collection_error"]
        if result.get("identity_conflicts"):
            raise DomainError(
                409,
                "identity_conflict",
                "Some postings have conflicting archived identities. Other results were retained; merge the verified duplicates before retrying.",
            )
        if source["checkpoint"].get("complete") is False:
            result["continuing"] = True
        else:
            result.pop("continuing", None)
        return result

    def run_task(self, task, owner):
        if not self._active(task["id"], owner):
            return
        started = time.monotonic()
        result = task.get("result", {})
        state, message, next_run = "failed", None, now()
        error_code = None
        try:
            result = self._collect(task, owner)
            state = (
                "cancelled"
                if result.get("skipped") or result.get("cancelled") or result.get("discarded")
                else "queued"
                if result.pop("continuing", False)
                else "succeeded"
            )
            if state == "queued":
                next_run = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(
                    timespec="microseconds"
                )
        except Exception as error:
            message = (
                error.message
                if isinstance(error, DomainError)
                else "The background task failed. Review the settings and retry."
            )
            error_code = getattr(error, "code", type(error).__name__)
            deferred = isinstance(error, ProviderDeferred)
            retryable = not isinstance(error, DomainError) or error.status >= 500
            # Quota waits do not consume the transient error retry allowance.
            failures = task.get("result", {}).get("failure_attempts", 0) + int(not deferred)
            retry = deferred or (retryable and failures < 3)
            state = "queued" if retry else "failed"
            delay = min(3600, 15 * 4 ** min(max(failures - 1, 0), 8))
            if deferred and error.code == "collection_batch":
                delay = 1
            next_run = getattr(error, "next_run_at", None) or (
                datetime.now(timezone.utc) + timedelta(seconds=delay)
            ).isoformat(timespec="microseconds")
            result = task.get("partial_result", dict(task.get("result", {})))
            result["failure_attempts"] = failures
            if task.get("budget"):
                result["diagnostics"] = [task["budget"].diagnostics()]
            LOG.warning("Background task %s paused or failed (%s).", task["id"], error_code)
        if task["kind"] == "collect":
            result["processing_seconds"] = round(
                result.get("processing_seconds", 0) + time.monotonic() - started, 3
            )
            result["http_requests"] = result.get("http_requests", 0) + (
                task["budget"].requests if task.get("budget") else 0
            )
            history = result.setdefault("attempt_history", [])
            history.append(
                {
                    "attempt": task["attempts"],
                    "finished_at": now(),
                    "state": state,
                    "reason": error_code,
                    "requests": task["budget"].requests if task.get("budget") else 0,
                }
            )
            result["attempt_history"] = history[-50:]
        with self.db.transaction() as connection:
            changed = connection.execute(
                "UPDATE tasks SET state=?,result=?,error=?,next_run_at=?,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE id=? AND state='running' AND lease_owner=?",
                (
                    state,
                    encode(result),
                    message[:1000] if message else None,
                    next_run,
                    now(),
                    task["id"],
                    owner,
                ),
            )
            if changed.rowcount and task["source_id"]:
                connection.execute(
                    "UPDATE sources SET last_error=? WHERE id=?",
                    (message[:1000] if state == "failed" and message else None, task["source_id"]),
                )


def register_api(router, service: DiscoveryService):
    @router.get("/collection")
    def collection_get():
        return service.get_collection()

    @router.patch("/collection")
    def collection_update(value: CollectionWrite):
        return service.update_collection(value)

    @router.get("/providers")
    def providers_list():
        return service.list_providers()

    @router.patch("/providers/{provider_id}")
    def providers_update(provider_id: str, value: ProviderPatch):
        return service.update_provider(provider_id, value)

    @router.get("/collection/runs")
    def collection_runs_list(
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
        state: str | None = None,
        summary: bool = True,
    ):
        return service.list_runs(limit, offset, source_id, state, summary)

    @router.get("/collection/runs/{run_id}")
    def collection_runs_get(run_id: str):
        return service.get_run(run_id)

    @router.post("/collection/runs/{run_id}/cancel")
    def collection_runs_cancel(run_id: str):
        return service.cancel_run(run_id)

    @router.get("/sources/schemas")
    def sources_schemas():
        return service.source_schemas()

    @router.get("/sources")
    def sources_list(limit: int = 100, offset: int = 0, summary: bool = True):
        return service.list_sources(limit, offset, summary)

    @router.post("/sources/preview")
    def sources_preview(value: SourcePreview):
        return service.preview_source(value)

    @router.post("/sources", status_code=201)
    def sources_create(value: SourceCreate):
        return service.create_source(value)

    @router.post("/sources/bulk")
    def sources_bulk(value: SourceBulk):
        return service.bulk_sources(value)

    @router.get("/sources/{source_id}")
    def sources_get(source_id: str):
        return service.get_source(source_id)

    @router.patch("/sources/{source_id}")
    def sources_update(source_id: str, value: SourcePatch):
        return service.update_source(source_id, value)

    @router.delete("/sources/{source_id}")
    def sources_delete(source_id: str, expected_version: int = Query(ge=1)):
        return service.delete_source(source_id, expected_version)

    @router.post("/sources/{source_id}/run")
    def sources_run(source_id: str, value: SourceRun):
        return service.queue_collection(
            source_id, expected_version=value.expected_version, overrides=value.overrides
        )

    @router.get("/tasks")
    def tasks_list(
        limit: int = 50,
        offset: int = 0,
        state: str | None = None,
        kind: str | None = None,
        source_id: str | None = None,
        job_id: str | None = None,
    ):
        return service.list_tasks(limit, offset, state, kind, source_id, job_id)

    @router.get("/tasks/{task_id}")
    def tasks_get(task_id: str):
        return service.get_task(task_id)

    @router.post("/tasks/{task_id}/cancel")
    def tasks_cancel(task_id: str):
        return service.cancel_task(task_id)

    @router.post("/tasks/{task_id}/retry")
    def tasks_retry(task_id: str):
        return service.retry_task(task_id)


def register_mcp(mcp, service: DiscoveryService):
    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def sources_schemas() -> dict:
        """Discover supported source fields/defaults, schedule variants and temporary run options."""
        return service.source_schemas()

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_runs_list(
        limit: int = 50,
        offset: int = 0,
        source_id: str | None = None,
        state: str | None = None,
        summary: bool = True,
    ) -> dict:
        """List logical collections with cumulative provider counts, waiting and processing time. summary=false adds frozen source snapshots and full task payloads/results."""
        return service.list_runs(limit, offset, source_id, state, summary)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_runs_get(run_id: str) -> dict:
        """Read frozen acquisition settings and provider tasks for one collection invocation."""
        return service.get_run(run_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def collection_runs_cancel(run_id: str) -> dict:
        """Stop current collection work while retaining jobs already archived."""
        return service.cancel_run(run_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def collection_get() -> dict:
        """Read the global automatic collection switch, counts and next queued run."""
        return service.get_collection()

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def collection_update(value: CollectionWrite) -> dict:
        """Pause/resume automatic collection with version protection; manual run remains available."""
        return service.update_collection(value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def providers_list() -> dict:
        """Read supported providers, editable HTTP safeguards and persisted window/cooldown diagnostics."""
        return service.list_providers()

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def providers_update(provider_id: str, value: ProviderPatch) -> dict:
        """Edit a provider policy using its version. Runtime/cooldown are read-only and shared by all runs."""
        return service.update_provider(provider_id, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
    )
    def sources_bulk(value: SourceBulk) -> dict:
        """Enable, pause, run, configure or delete selected versioned sources; inspect each result/error."""
        return service.bulk_sources(value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def sources_list(limit: int = 100, offset: int = 0, summary: bool = True) -> dict:
        """List saved portal searches and selected company/feed sources, schedules and outcomes. summary=false adds last-run diagnostics and full task records."""
        return service.list_sources(limit, offset, summary)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def sources_get(source_id: str) -> dict:
        """Read a source's complete editable configuration and version."""
        return service.get_source(source_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
    )
    async def sources_preview(value: SourcePreview) -> dict:
        """Preview a saved-search/company/feed configuration without saving jobs; shared request spacing and cooldowns apply."""
        return await asyncio.to_thread(service.preview_source, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    async def sources_create(value: SourceCreate) -> dict:
        """Create one explicit saved query/location or company/feed source; individually paused by default."""
        return await asyncio.to_thread(service.create_source, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    async def sources_update(source_id: str, value: SourcePatch) -> dict:
        """Update or pause a source with optimistic version protection."""
        return await asyncio.to_thread(service.update_source, source_id, value)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)
    )
    def sources_delete(source_id: str, expected_version: int) -> dict:
        """Remove a versioned source while retaining archived jobs and collection history."""
        return service.delete_source(source_id, expected_version)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def sources_run(source_id: str, value: SourceRun) -> dict:
        """Run a versioned source with frozen optional overrides; shared request spacing and cooldowns apply."""
        return service.queue_collection(
            source_id, expected_version=value.expected_version, overrides=value.overrides
        )

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def tasks_list(
        limit: int = 50,
        offset: int = 0,
        state: str | None = None,
        kind: str | None = None,
        source_id: str | None = None,
        job_id: str | None = None,
    ) -> dict:
        """Filter collection work by state/kind/source/job, with readable labels and diagnostics."""
        return service.list_tasks(limit, offset, state, kind, source_id, job_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    )
    def tasks_get(task_id: str) -> dict:
        """Read one task's inputs, result, HTTP diagnostics, lease and next run time."""
        return service.get_task(task_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    )
    def tasks_cancel(task_id: str) -> dict:
        """Cancel queued/running work; already stored jobs and documents are kept."""
        return service.cancel_task(task_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    )
    def tasks_retry(task_id: str) -> dict:
        """Retry failed/cancelled work; collection keeps its frozen inputs and saved progress."""
        return service.retry_task(task_id)
