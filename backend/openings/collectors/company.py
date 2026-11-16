"""Bounded clients for public company ATS boards.

These adapters read public JSON/XML or embedded page data. They do not execute
JavaScript, traverse arbitrary pages or import user-provided Python code.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timedelta
from functools import cache
from typing import Annotated
from urllib.parse import quote, urlencode
from xml.parsers import expat

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model

from ..common import now
from ..errors import DomainError
from ..posting import matches_filters
from .catalog import COMPANY_ADAPTERS
from .policy import ProviderDeferred


class BoardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    board: str = Field(min_length=1, max_length=250)
    region: str = "global"
    max_results: int = Field(default=100, ge=1, le=2000)
    max_candidates: int = Field(default=2000, ge=20, le=10000)
    # Workday search facets, such as {"locationHierarchy1": ["<id>"]}: one region of a
    # large board, read past the listing's cap of about 2,000 roles.
    facets: dict[
        Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_]{1,80}$")],
        Annotated[
            list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,120}$")]],
            Field(min_length=1, max_length=20),
        ],
    ] = Field(default_factory=dict, max_length=5)


@cache
def config_model(kind):
    adapter = COMPANY_ADAPTERS[kind]
    return create_model(
        kind.title() + "Config",
        __config__=BoardConfig.model_config,
        **{
            name: (
                BoardConfig.model_fields[name].annotation,
                deepcopy(BoardConfig.model_fields[name]),
            )
            for name in adapter.fields
        },
    )


INLINE_IMAGE = re.compile(rb"data:image/[\w.+-]+;base64,(?:[A-Za-z0-9+/=]|\\/)+")


INVALID_XML = "The source did not return a valid XML feed. Check that its public feed is enabled."


def xml(body, invalid=INVALID_XML):
    """Parse an untrusted feed: a document type, an entity declaration or an external
    reference stops expat at its declaration, before any expansion, in any encoding."""

    def refuse(*args):
        raise DomainError(
            422, "source_xml_declarations", "XML document types and entities are refused."
        )

    guard = expat.ParserCreate()
    guard.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    guard.StartDoctypeDeclHandler = guard.EntityDeclHandler = refuse
    guard.ExternalEntityRefHandler = refuse
    try:
        guard.Parse(body, True)
        return ET.fromstring(body)
    except (expat.ExpatError, ET.ParseError) as error:
        raise DomainError(502, "source_format", invalid) from error


def location(value):
    if isinstance(value, str):
        return value
    value = value or {}
    if value.get("name"):
        return value["name"]
    parts = [value.get("city"), value.get("state") or value.get("region"), value.get("country")]
    return ", ".join(
        str(item.get("name") if isinstance(item, dict) else item) for item in parts if item
    )


# Names boards give a posting or office that has no place.
PLACEHOLDERS = frozenset(
    {"no office", "no location", "none", "n/a", "na", "tbd", "unassigned", "unknown", "-"}
)


def places(*values):
    """Every location of a posting once, the primary first: "Paris · Zurich".

    Placeholders ("No Office") go, and so does a place an earlier one already
    names: "Poland" after "Remote, Poland".
    """
    named = {}
    for place in values:
        place = " ".join(str(place or "").split())
        parts = {part.strip().casefold() for part in place.split(",")}
        if place.casefold() not in PLACEHOLDERS | {""} and not any(
            parts <= seen for seen in named.values()
        ):
            named[place] = parts
    return " · ".join(named)


def board_error(error, kind, board):
    """A board's listing that is missing or too large, named for its owner."""
    status = (error.details or {}).get("http_status")
    if error.code == "source_http" and status in (404, 410):
        return DomainError(
            422,
            "board_unavailable",
            f"{kind.title()} does not expose a public board for '{board}' (HTTP {status}). "
            "Check the exact board URL and identifier. Disabled, removed or private "
            "boards require another public source or manual job entry.",
            {"http_status": status, "board": board},
        )
    if error.code == "source_too_large":
        limit = (error.details or {}).get("maximum_bytes", 0) // (1024 * 1024)
        return DomainError(
            422,
            "source_too_large",
            f"The {kind.title()} board '{board}' is larger than the {limit} MB a collection "
            "reads. Add its jobs by URL, or follow a smaller board of the same company.",
            {"board": board, "maximum_bytes": (error.details or {}).get("maximum_bytes")},
        )
    return error


def records(payload, key=None):
    rows = payload.get(key) if isinstance(payload, dict) and key else payload
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DomainError(
            502,
            "source_format",
            "The source returned an unexpected listing shape; check its public feed and configuration.",
        )
    return rows


def collect(source, request, text, *, known=None, preview=False, on_item=None):
    kind, config, name = source["kind"], source["config"], source["name"]
    board = config.get("board", "")
    maximum = min(
        config.get("max_results", config.get("results_wanted", 100)), 3 if preview else 2000
    )
    items = []
    checkpoint = source.get("checkpoint", {}) if not preview else {}
    cache = checkpoint.setdefault("responses", {})
    attempts = checkpoint.setdefault("detail_attempts", {})
    detail_requests = checkpoint.setdefault("detail_requests", {})
    pending = set()
    unavailable = set()
    max_candidates = min(config.get("max_candidates", 2000), 3 if preview else 10000)
    # A Test's first answer: the listing alone, without one request per posting.
    listing_only = preview and not source.get("details", True)

    def save():
        checkpoint["complete"] = False
        checkpoint["pending_details"] = len(pending)
        if source.get("on_checkpoint") and not preview:
            source["on_checkpoint"](checkpoint)

    def response(url, *, body=None):
        key = json.dumps([url, body], sort_keys=True)
        if key not in cache:
            try:
                answer = request(url) if body is None else request(url, method="POST", body=body)
            except DomainError as error:
                raise board_error(error, kind, board) from error
            # Inline images (40 MB at some Recruitee boards) are not posting text.
            cache[key] = INLINE_IMAGE.sub(b"", answer).decode("utf-8")
            save()
        return cache[key].encode("utf-8")

    known = known or {}
    checked = source.get("detail_checked") or {}
    cutoff = (datetime.fromisoformat(now()) - timedelta(hours=24)).isoformat(
        timespec="microseconds"
    )
    source.pop("collection_error", None)
    source.pop("candidate_capped", None)
    source.pop("result_capped", None)
    filters = config.get("filters") or {}
    detail_checks = source["detail_checks"] = {}

    def matches(title, place, flags=None):
        # flags: the board's remote flag and workplace type, which a Remote filter reads.
        return matches_filters(
            {"title": str(title or ""), "location": str(place or ""), "metadata": flags or {}},
            filters,
        )

    def select(rows, title, place, flags=lambda row: {}):
        # An empty first answer of a board that had jobs is confirmed by the next run.
        source["listing_empty"] = not rows
        # How many jobs of what the board listed match: "Fetched N of M" while a check runs.
        source["listed"] = checkpoint["listed"] = sum(
            bool(matches(title(row), place(row), flags(row))) for row in rows
        )
        if len(rows) > max_candidates:
            source["candidate_capped"] = True
        matching = [
            row for row in rows[:max_candidates] if matches(title(row), place(row), flags(row))
        ]
        if len(matching) > maximum:
            source["result_capped"] = True
        return matching[:maximum]

    def ordered(rows, identity):
        # List first, then refresh the oldest complete descriptions.
        # This rotates across the entire bounded board, including later pages.
        return sorted(rows, key=lambda row: checked.get(identity(row), ""))

    def get(url, *, body=None):
        try:
            return json.loads(response(url, body=body))
        except (ValueError, UnicodeError) as error:
            cache.pop(json.dumps([url, body], sort_keys=True), None)
            save()
            # Often an error or maintenance page during an outage: tried again later.
            raise DomainError(
                503,
                "source_unavailable",
                f"{kind} answered with a page that is not JSON; it is tried again later.",
            ) from error

    def detail(key, url, *, body=None, decode=None):
        if listing_only or (not preview and key in known and checked.get(key, "") > cutoff):
            return {}
        request_key = json.dumps([url, body], sort_keys=True)
        load = (lambda: decode(url)) if decode else (lambda: get(url, body=body))
        if request_key in cache:
            return load()
        if attempts.get(key, 0) >= 3:
            unavailable.add(key)
            return {}
        if source.get("collection_error"):
            pending.add(key)
            return {}
        detail_requests[key] = request_key
        try:
            result = load()
        except DomainError as error:
            status = (error.details or {}).get("http_status")
            if not isinstance(error, ProviderDeferred) and status in (404, 410):
                attempts[key] = 3
                unavailable.add(key)
            else:
                source["collection_error"] = error
                pending.add(key)
            save()
            return {}
        attempts[key] = attempts.get(key, 0) + 1
        detail_checks[key] = now()
        save()
        return result

    def add(row, identity, title, url, place="", posting="", **metadata):
        if not identity or len(items) >= maximum or not matches(title, place, metadata):
            return
        key = f"{kind}:{board or config.get('host', '')}:{identity}"
        previous = known.get(key, {}) if isinstance(known, dict) else {}
        if metadata.get("job_type"):
            # The board's current type replaces the types normalized from an earlier one.
            previous = {
                name: value
                for name, value in previous.items()
                if name not in ("job_types", "job_type_raw")
            }
        posting = text(str(posting or ""))
        if not any(character.isalnum() for character in posting):
            posting = ""
        if not posting and key in known:
            posting = source["known_posting"](key) if source.get("known_posting") else ""
        if not posting and key in attempts and key not in pending:
            if attempts[key] < 3:
                pending.add(key)
                # An empty detail response is retried in a later bounded batch.
                cache.pop(detail_requests.get(key), None)
            else:
                unavailable.add(key)
        metadata = {
            **previous,
            **{key: value for key, value in metadata.items() if value is not None and value != ""},
        }
        if not posting and key in known:
            unavailable.discard(key)
            metadata["description_complete"] = previous.get("description_complete", True)
        elif not posting:
            if key not in pending:
                unavailable.add(key)
            metadata["description_complete"] = False
            metadata["description_status"] = "pending" if key in pending else "unavailable"
        elif len(posting) > 200000:
            unavailable.add(key)
            metadata["description_complete"] = False
            metadata["description_status"] = "truncated"
        elif posting:
            unavailable.discard(key)
            metadata["description_complete"] = True
            metadata["description_status"] = "complete"
        items.append(
            {
                "source_key": key,
                "title": str(title or "Untitled role")[:400],
                "company": str(metadata.pop("company", name) or name)[:300],
                "location": str(place or "")[:500],
                "url": str(url or ""),
                "posting": posting[:200000],
                "metadata": {
                    **({"source": kind} if kind != "greenhouse" else {}),
                    "ats": kind,
                    "board": board,
                    "external_id": str(identity),
                    **metadata,
                },
                "raw": row,
            }
        )
        if on_item is not None:
            on_item(items[-1])

    slug = quote(board, safe="")
    if kind == "greenhouse":
        base = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        # One listing carries every description. A board too large for it falls back to
        # the plain listing and one detail request a job.
        try:
            rows = records(get(base + "?content=true"), "jobs")
        except DomainError as error:
            if error.code != "source_too_large":
                raise
            rows = records(get(base), "jobs")
        # A listing's location is often a work mode ("Hybrid"); its cities are its offices.
        offices = (
            {}
            if listing_only
            else get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/offices")
        )
        cities = {}
        for office in (offices.get("offices") if isinstance(offices, dict) else None) or []:
            for department in office.get("departments") or []:
                for job in department.get("jobs") or []:
                    cities.setdefault(job.get("id"), []).append(office)

        def place(row):
            # A region office ("EMEA") says less than its listed child office ("London").
            mine = cities.get(row.get("id"), [])
            parents = {office.get("parent_id") for office in mine}
            return places(
                location(row.get("location")),
                *(
                    location(office.get("location")) or office.get("name")
                    for office in mine
                    if office.get("id") not in parents
                ),
            )

        rows = select(rows, lambda row: row.get("title"), place)
        for row in ordered(rows, lambda row: f"{kind}:{board}:{row.get('id')}"):
            identity = row.get("id")
            full = row
            if not any(character.isalnum() for character in text(str(row.get("content") or ""))):
                # Only a row the listing gave no text costs a detail request.
                full = detail(
                    f"{kind}:{board}:{identity}", base + "/" + quote(str(identity), safe="")
                )
            add(
                {**row, **full},
                identity,
                row.get("title"),
                row.get("absolute_url"),
                place(row),
                full.get("content", ""),
                departments=[
                    item.get("name") for item in full.get("departments") or [] if item.get("name")
                ],
                published_at=row.get("first_published"),
            )
    elif kind == "recruitee":
        payload = get(f"https://{board}.recruitee.com/api/offers/")

        def place(row):
            return places(
                row.get("location")
                or ", ".join(str(row[key]) for key in ("city", "country") if row.get(key)),
                *(
                    location({key: item.get(key) for key in ("city", "state", "country")})
                    for item in row.get("locations") or []
                    if isinstance(item, dict)
                ),
            )

        def flags(row):
            return {
                "remote": row.get("remote"),
                "workplace_type": "hybrid" if row.get("hybrid") else None,
            }

        for row in select(records(payload, "offers"), lambda row: row.get("title"), place, flags):
            add(
                row,
                row.get("id"),
                row.get("title"),
                row.get("careers_url") or row.get("careers_apply_url"),
                place(row),
                "\n\n".join(filter(None, (row.get("description"), row.get("requirements")))),
                **flags(row),
                job_type=row.get("employment_type_code"),
                published_at=row.get("published_at"),
            )
    elif kind == "personio":
        base = f"https://{board}.jobs.personio.de"
        # Without a language: ?language=en empties positions written only in German.
        root = xml(response(base + "/xml"))
        if root.tag != "workzag-jobs":
            raise DomainError(
                502, "source_format", "Personio did not return its public positions feed."
            )

        def place(row):
            return places(
                row.findtext("office"),
                *(office.text for office in row.findall("additionalOffices/office")),
            )

        for row in select(root.findall("position"), lambda row: row.findtext("name"), place):

            def value(tag, row=row):
                return (row.findtext(tag) or "").strip()

            description = "\n\n".join(
                "\n".join(filter(None, (part.findtext("name"), part.findtext("value"))))
                for part in row.findall("jobDescriptions/jobDescription")
            )
            add(
                {child.tag: child.text for child in row},
                value("id"),
                value("name"),
                base + "/job/" + value("id"),
                place(row),
                description,
                # employmentType first: "intern" says more than its "full-time" schedule.
                job_type=[part for part in (value("employmentType"), value("schedule")) if part],
                published_at=value("createdAt"),
            )
    elif kind == "workable":
        payload = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")
        for row in select(
            records(payload, "jobs"),
            lambda row: row.get("title"),
            location,
            lambda row: {"remote": row.get("telecommuting")},
        ):
            add(
                row,
                row.get("shortcode"),
                row.get("title"),
                row.get("url") or row.get("shortlink"),
                location(row),
                row.get("description"),
                remote=row.get("telecommuting"),
                job_type=row.get("employment_type"),
                published_at=row.get("published_on"),
            )
    elif kind == "breezy":
        payload = get(f"https://{board}.breezy.hr/json?full=true")
        for row in select(
            records(payload), lambda row: row.get("name"), lambda row: location(row.get("location"))
        ):
            place = row.get("location") or {}
            add(
                row,
                row.get("id"),
                row.get("name"),
                row.get("url"),
                location(place),
                remote=place.get("is_remote"),
                job_type=(row.get("type") or {}).get("name"),
                published_at=row.get("published_date"),
                description_available=False,
            )
    elif kind == "bamboohr":
        base = f"https://{board}.bamboohr.com"

        def address(row):
            # Both are dicts, often one of null values; the detail's names the country.
            for value in (row.get("location"), row.get("atsLocation")):
                value = {key: item for key, item in (value or {}).items() if item}
                if value:
                    return {**value, "country": value.get("country") or value.get("addressCountry")}
            return {}

        def flags(row):
            # locationType: "0" on site, "1" remote, "2" hybrid.
            mode = {"0": "onsite", "1": "remote", "2": "hybrid"}.get(str(row.get("locationType")))
            return {
                "remote": row.get("isRemote") or mode == "remote" or None,
                "workplace_type": mode,
            }

        for row in ordered(
            select(
                records(get(base + "/careers/list"), "result"),
                lambda row: row.get("jobOpeningName"),
                # The listing names no country: a country filter waits for the detail.
                lambda row: location(address(row)) if address(row).get("country") else "",
                flags,
            ),
            lambda row: f"{kind}:{board}:{row.get('id')}",
        ):
            identity = row.get("id")
            key = f"{kind}:{board}:{identity}"
            full = (detail(key, f"{base}/careers/{identity}/detail").get("result") or {}).get(
                "jobOpening"
            ) or {}
            country = address(full).get("country") or (
                (known.get(key) or {}).get("country") if isinstance(known, dict) else None
            )
            add(
                {**row, **full},
                identity,
                row.get("jobOpeningName"),
                full.get("jobOpeningShareUrl") or f"{base}/careers/{identity}",
                location({**address(row), **address(full), "country": country}),
                full.get("description"),
                **flags({**row, **full}),
                country=country,
                job_type=row.get("employmentStatusLabel"),
                published_at=full.get("datePosted"),
            )
    elif kind == "rippling":
        base = f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
        # The board lists a role once per location: one row per role, every location.
        roles = {}
        for row in records(get(base)):
            label = (row.get("workLocation") or {}).get("label")
            role = roles.setdefault(row.get("uuid"), {**row, "workLocations": []})
            role["workLocations"].append(label)
        for row in ordered(
            select(
                list(roles.values()),
                lambda row: row.get("name"),
                lambda row: places(*row["workLocations"]),
            ),
            lambda row: f"{kind}:{board}:{row.get('uuid')}",
        ):
            identity = row.get("uuid")
            full = detail(f"{kind}:{board}:{identity}", base + "/" + quote(str(identity), safe=""))
            description = full.get("description") or ""
            if isinstance(description, dict):
                description = "\n\n".join(str(part) for part in description.values() if part)
            add(
                {**row, **full},
                identity,
                row.get("name"),
                row.get("url"),
                places(*row["workLocations"]),
                description,
                job_type=(full.get("employmentType") or {}).get("label"),
                published_at=full.get("createdOn"),
            )
    elif kind == "smartrecruiters":
        base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        listed, total = [], None
        try:
            for offset in range(0, 100 if preview else max_candidates, 100):
                payload = get(base + "?" + urlencode({"limit": 100, "offset": offset}))
                rows = records(payload, "content")
                if isinstance(payload.get("totalFound"), int):
                    total = payload["totalFound"]
                listed.extend(rows)
                if len(rows) < 100 or (total is not None and offset + 100 >= total):
                    break
            else:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error

        def place(row):
            # fullLocation names the country; location's country is an ISO code ("de").
            value = row.get("location") or {}
            return value.get("fullLocation") or location(value)

        def flags(row):
            value = row.get("location") or {}
            return {
                "remote": value.get("remote"),
                "workplace_type": "hybrid" if value.get("hybrid") else None,
            }

        for row in ordered(
            select(listed, lambda row: row.get("name"), place, flags),
            lambda row: f"{kind}:{board}:{row.get('id')}",
        ):
            identity = row.get("id")
            # Construct the vendor endpoint rather than following arbitrary ref URLs.
            full = detail(f"{kind}:{board}:{identity}", base + "/" + quote(str(identity), safe=""))
            sections = (full.get("jobAd") or {}).get("sections") or {}
            posting = "\n\n".join(
                str((sections.get(key) or {}).get("text") or "")
                for key in (
                    "companyDescription",
                    "jobDescription",
                    "qualifications",
                    "additionalInformation",
                )
            )
            add(
                {**row, **full},
                identity,
                row.get("name"),
                f"https://jobs.smartrecruiters.com/{slug}/{identity}",
                place(row),
                posting,
                **flags(row),
                job_type=(row.get("typeOfEmployment") or {}).get("label"),
                published_at=row.get("releasedDate"),
            )
    elif kind == "workday":
        host, site = board.split("/", 1)
        tenant = host.split(".")[0]
        api, public = f"https://{host}/wday/cxs/{tenant}/{site}", f"https://{host}/{site}"
        listed, paths, total = [], set(), None
        try:
            for offset in range(0, 20 if preview else max_candidates, 20):
                payload = get(
                    api + "/jobs",
                    body={
                        "appliedFacets": config.get("facets") or {},
                        "limit": 20,
                        "offset": offset,
                        "searchText": "",
                    },
                )
                rows = records(payload, "jobPostings")
                # Only the first page states the total; past the end Workday repeats page one.
                if total is None and isinstance(payload.get("total"), int):
                    total = payload["total"]
                fresh = [row for row in rows if row.get("externalPath") not in paths]
                paths.update(row.get("externalPath") for row in fresh)
                listed.extend(fresh)
                if len(rows) < 20 or not fresh or (total is not None and offset + 20 >= total):
                    break
            else:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error

        def listed_place(row):
            # "2 Locations" names none of them: the detail's locations are matched instead.
            place = str(row.get("locationsText") or "")
            return "" if re.fullmatch(r"\d+ Locations", place) else place

        for row in ordered(
            select(listed, lambda row: row.get("title"), listed_place),
            lambda row: f"{kind}:{board}:{row.get('externalPath')}",
        ):
            path = row.get("externalPath") or ""
            if not path.startswith("/job/") or ".." in path:
                continue
            key = f"{kind}:{board}:{path}"
            full = detail(key, api + path).get("jobPostingInfo") or {}
            located = places(full.get("location"), *(full.get("additionalLocations") or []))
            # A detail read in the last day is skipped: its locations come from the archive.
            previous = known.get(key, {}) if isinstance(known, dict) else {}
            located = located or previous.get("locations") or ""
            add(
                {"listing": row, "detail": full},
                path,
                row.get("title"),
                full.get("externalUrl") or public + path,
                located or listed_place(row),
                full.get("jobDescription"),
                job_type=full.get("timeType"),
                published_at=full.get("startDate"),
                locations=located,
            )
    elif kind == "oracle":
        host, site = board.split("/", 1)
        base = f"https://{host}/hcmRestApi/resources/latest"
        # An unknown site answers with the default site's jobs: check that it exists.
        get(base + "/recruitingCESites/" + quote(site, safe="") + "?onlyData=true")
        listed, total = [], None
        try:
            for offset in range(0, 50 if preview else max_candidates, 50):
                payload = get(
                    base
                    + "/recruitingCEJobRequisitions?"
                    + urlencode(
                        {
                            "onlyData": "true",
                            "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
                            "finder": f"findReqs;siteNumber={site},limit=50,offset={offset}",
                        }
                    )
                )
                envelopes = records(payload, "items")
                rows = records(envelopes[0], "requisitionList") if envelopes else []
                if envelopes and isinstance(envelopes[0].get("TotalJobsCount"), int):
                    total = envelopes[0]["TotalJobsCount"]
                listed.extend(rows)
                if len(rows) < 50 or (total is not None and offset + 50 >= total):
                    break
            else:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error

        def place(row):
            return places(
                row.get("PrimaryLocation"),
                *(
                    item.get("Name")
                    for item in row.get("secondaryLocations") or []
                    if isinstance(item, dict)
                ),
            )

        for row in ordered(
            select(listed, lambda row: row.get("Title"), place),
            lambda row: f"{kind}:{board}:{row.get('Id')}",
        ):
            identity = row.get("Id")
            full = detail(
                f"{kind}:{board}:{identity}",
                base
                + "/recruitingCEJobRequisitionDetails?"
                + urlencode(
                    {
                        "onlyData": "true",
                        "expand": "all",
                        "finder": f'ById;Id="{identity}",siteNumber={site}',
                    }
                ),
            )
            full = (full.get("items") or [{}])[0]
            add(
                {**row, **full},
                identity,
                row.get("Title"),
                f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{identity}",
                place(row),
                "\n\n".join(
                    str(full.get(key) or "")
                    for key in (
                        "ExternalDescriptionStr",
                        "ExternalResponsibilitiesStr",
                        "ExternalQualificationsStr",
                    )
                ),
                job_type=full.get("JobSchedule"),
                published_at=row.get("PostedDate"),
            )
    elif kind == "joincom":
        base = f"https://join.com/companies/{slug}"

        def state(url):
            page = response(url).decode("utf-8", errors="replace")
            match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.DOTALL)
            if not match:
                raise DomainError(
                    502,
                    "source_format",
                    "join.com embedded job data was unavailable; its page shape may have changed.",
                )
            try:
                page_props = json.loads(match.group(1))["props"]["pageProps"]
                result = (
                    page_props["initialState"]
                    if "initialState" in page_props
                    else page_props["pageData"]
                )
                if not isinstance(result, dict):
                    raise TypeError()
                return result
            except (ValueError, KeyError, TypeError) as error:
                raise DomainError(
                    502, "source_format", "join.com returned unexpected embedded job data."
                ) from error

        # Five jobs a page; pages can overlap, so a job is kept once.
        listed, seen = [], set()
        try:
            page, count = 1, 1
            while page <= count and len(listed) < max_candidates:
                jobs = state(base + (f"?page={page}" if page > 1 else "")).get("jobs") or {}
                for row in records(jobs, "items"):
                    if row.get("id") not in seen:
                        seen.add(row.get("id"))
                        listed.append(row)
                pages = (jobs.get("pagination") or {}).get("pageCount")
                count = 1 if preview or not isinstance(pages, int) else pages
                page += 1
            if page <= count:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error

        def place(row):
            # The listing's English names: the detail's are localized ("Deutschland").
            city = row.get("city") or {}
            return ", ".join(
                str(city[key]) for key in ("cityName", "regionName", "countryName") if city.get(key)
            )

        for row in ordered(
            select(listed, lambda row: row.get("title"), place),
            lambda row: f"{kind}:{board}:{row.get('id')}",
        ):
            identity = row.get("id")
            path = row.get("idParam")
            url = base + "/" + quote(path, safe="-") if path else ""
            full = {}
            key = f"{kind}:{board}:{identity}"
            if url:
                full = detail(key, url, decode=state).get("job") or {}
            merged = {**row, **full}
            employment = merged.get("employmentType") or {}
            add(
                merged,
                identity,
                merged.get("title"),
                url,
                place(row),
                "\n\n".join(
                    str(merged.get(key) or "")
                    for key in ("intro", "tasks", "requirements", "benefits", "description")
                ),
                remote=merged.get("workplaceType") == "REMOTE",
                workplace_type=str(merged.get("workplaceType") or "").casefold() or None,
                job_type=employment.get("googleType") or employment.get("name"),
                published_at=merged.get("createdAt"),
            )
    else:
        raise DomainError(422, "unsupported_source", "This company source type is unsupported.")
    checkpoint["pending_details"] = len(pending)
    checkpoint["unavailable_descriptions"] = len(unavailable)
    checkpoint["complete"] = not pending and not source.get("collection_error")
    if checkpoint["complete"]:
        checkpoint.pop("responses", None)
        checkpoint.pop("detail_attempts", None)
        checkpoint.pop("detail_requests", None)
    if source.get("on_checkpoint") and not preview:
        source["on_checkpoint"](checkpoint)
    return items
