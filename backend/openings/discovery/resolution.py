"""Source resolution: detecting a board from a URL and validating a source's configuration."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit

from pydantic import ValidationError

from ..collectors import company as company_collectors, jobspy as jobspy_collector
from ..collectors.catalog import COMPANY_ADAPTERS
from ..errors import DomainError
from .feeds import TextParser
from .models import RSSConfig
from .network import fetch_bytes, public_url


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
