"""Bounded clients for public company ATS boards.

These adapters read public JSON/XML or embedded page data. They do not execute
JavaScript, traverse arbitrary pages or import user-provided Python code.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from pydantic import BaseModel, ConfigDict, Field

from ..errors import DomainError
from ..common import now
from ..posting import matches_filters


class BoardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    board: str = Field(min_length=1, max_length=250)
    region: str = "global"
    max_results: int = Field(default=100, ge=1, le=2000)
    max_details: int = Field(default=10, ge=0, le=25)
    max_candidates: int = Field(default=2000, ge=20, le=10000)


def xml(body):
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise DomainError(422, "source_format", "XML entity declarations are unsupported.")
    try:
        return ET.fromstring(body)
    except ET.ParseError as error:
        raise DomainError(
            502,
            "source_format",
            "The source did not return a valid XML feed. Check that its public feed is enabled.",
        ) from error


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
    max_details = min(config.get("max_details", 10), 3 if preview else 25)
    details = 0
    items = []
    checkpoint = source.get("checkpoint", {}) if not preview else {}
    cache = checkpoint.setdefault("responses", {})
    attempts = checkpoint.setdefault("detail_attempts", {})
    detail_requests = checkpoint.setdefault("detail_requests", {})
    pending = set()
    unavailable = set()
    max_candidates = min(config.get("max_candidates", 2000), 3 if preview else 10000)

    def save():
        checkpoint["complete"] = False
        checkpoint["pending_details"] = len(pending)
        if source.get("on_checkpoint") and not preview:
            source["on_checkpoint"](checkpoint)

    def response(url, *, body=None):
        key = json.dumps([url, body], sort_keys=True)
        if key not in cache:
            cache[key] = (
                request(url) if body is None else request(url, method="POST", body=body)
            ).decode("utf-8")
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

    def matches(title, place):
        return matches_filters({"title": str(title or ""), "location": str(place or "")}, filters)

    def select(rows, title, place):
        if len(rows) > max_candidates:
            source["candidate_capped"] = True
        matching = [row for row in rows[:max_candidates] if matches(title(row), place(row))]
        if len(matching) > maximum:
            source["result_capped"] = True
        return matching[:maximum]

    def ordered(rows, identity):
        # List first, then spend the existing detail budget on the oldest checks.
        # This rotates across the entire bounded board, including later pages.
        return sorted(rows, key=lambda row: checked.get(identity(row), ""))

    def get(url, *, body=None):
        try:
            return json.loads(response(url, body=body))
        except (ValueError, UnicodeError) as error:
            raise DomainError(
                502,
                "source_format",
                f"{kind} returned invalid JSON; its public endpoint may have changed.",
            ) from error

    def detail(key, url, *, body=None):
        nonlocal details
        if not preview and key in known and checked.get(key, "") > cutoff:
            return {}
        request_key = json.dumps([url, body], sort_keys=True)
        if request_key in cache:
            return get(url, body=body)
        if max_details == 0 or attempts.get(key, 0) >= 3:
            unavailable.add(key)
            return {}
        if source.get("collection_error") or details >= max_details:
            pending.add(key)
            return {}
        details += 1
        detail_requests[key] = request_key
        result = get(url, body=body)
        attempts[key] = attempts.get(key, 0) + 1
        detail_checks[key] = now()
        save()
        return result

    def add(row, identity, title, url, place="", posting="", **metadata):
        if not identity or len(items) >= maximum or not matches(title, place):
            return
        key = f"{kind}:{board or config.get('host', '')}:{identity}"
        previous = known.get(key, {}) if isinstance(known, dict) else {}
        posting = text(str(posting or ""))
        if not posting and key in known:
            posting = (source.get("known_postings") or {}).get(key, "")
        if not posting and key in attempts and key not in pending:
            if attempts[key] < 3 and max_details:
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
            metadata["description_complete"] = previous.get("description_complete", True)
        elif not posting:
            metadata["description_complete"] = False
            metadata["description_status"] = "pending" if key in pending else "unavailable"
        elif len(posting) > 200000:
            metadata["description_complete"] = False
        elif posting:
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
        rows = records(get(base), "jobs")
        rows = select(rows, lambda row: row.get("title"), lambda row: location(row.get("location")))
        for row in ordered(rows, lambda row: f"{kind}:{board}:{row.get('id')}"):
            identity = row.get("id")
            full = detail(f"{kind}:{board}:{identity}", base + "/" + quote(str(identity), safe=""))
            add(
                {**row, **full},
                identity,
                row.get("title"),
                row.get("absolute_url"),
                location(row.get("location")),
                full.get("content", ""),
                departments=row.get("departments", []),
            )
    elif kind == "recruitee":
        payload = get(f"https://{board}.recruitee.com/api/offers/")
        for row in select(
            records(payload, "offers"),
            lambda row: row.get("title"),
            lambda row: (
                row.get("location")
                or ", ".join(str(row[key]) for key in ("city", "country") if row.get(key))
            ),
        ):
            add(
                row,
                row.get("id"),
                row.get("title"),
                row.get("careers_url") or row.get("careers_apply_url"),
                row.get("location")
                or ", ".join(str(row[key]) for key in ("city", "country") if row.get(key)),
                "\n\n".join(filter(None, (row.get("description"), row.get("requirements")))),
                remote=row.get("remote"),
                job_type=row.get("employment_type_code"),
                published_at=row.get("published_at"),
            )
    elif kind == "personio":
        base = f"https://{board}.jobs.personio.de"
        root = xml(response(base + "/xml?language=en"))
        if root.tag != "workzag-jobs":
            raise DomainError(
                502, "source_format", "Personio did not return its public positions feed."
            )
        for row in select(
            root.findall("position"),
            lambda row: row.findtext("name"),
            lambda row: row.findtext("office"),
        ):

            def value(tag):
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
                value("office"),
                description,
                job_type=value("schedule"),
                published_at=value("createdAt"),
            )
    elif kind == "workable":
        payload = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")
        for row in select(records(payload, "jobs"), lambda row: row.get("title"), location):
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
        for row in ordered(
            select(
                records(get(base + "/careers/list"), "result"),
                lambda row: row.get("jobOpeningName"),
                lambda row: location(row.get("location") or row.get("atsLocation")),
            ),
            lambda row: f"{kind}:{board}:{row.get('id')}",
        ):
            identity = row.get("id")
            full = (
                detail(f"{kind}:{board}:{identity}", f"{base}/careers/{identity}/detail").get(
                    "result"
                )
                or {}
            ).get("jobOpening") or {}
            add(
                {**row, **full},
                identity,
                row.get("jobOpeningName"),
                full.get("jobOpeningShareUrl") or f"{base}/careers/{identity}",
                location(row.get("location") or row.get("atsLocation")),
                full.get("description"),
                remote=row.get("isRemote"),
                job_type=row.get("employmentStatusLabel"),
                published_at=full.get("datePosted"),
            )
    elif kind == "rippling":
        base = f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
        for row in ordered(
            select(
                records(get(base)),
                lambda row: row.get("name"),
                lambda row: (row.get("workLocation") or {}).get("label"),
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
                (row.get("workLocation") or {}).get("label"),
                description,
                published_at=full.get("createdOn"),
            )
    elif kind == "smartrecruiters":
        base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        listed = []
        try:
            for offset in range(0, 100 if preview else max_candidates, 100):
                rows = records(
                    get(base + "?" + urlencode({"limit": 100, "offset": offset})),
                    "content",
                )
                listed.extend(rows)
                if len(rows) < 100:
                    break
            else:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error
        for row in ordered(
            select(listed, lambda row: row.get("name"), lambda row: location(row.get("location"))),
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
                location(row.get("location")),
                posting,
                job_type=(row.get("typeOfEmployment") or {}).get("label"),
                published_at=row.get("releasedDate"),
            )
    elif kind == "workday":
        host, site = board.split("/", 1)
        tenant = host.split(".")[0]
        api, public = f"https://{host}/wday/cxs/{tenant}/{site}", f"https://{host}/{site}"
        listed = []
        try:
            for offset in range(0, 20 if preview else max_candidates, 20):
                rows = records(
                    get(
                        api + "/jobs",
                        body={
                            "appliedFacets": {},
                            "limit": 20,
                            "offset": offset,
                            "searchText": "",
                        },
                    ),
                    "jobPostings",
                )
                listed.extend(rows)
                if len(rows) < 20:
                    break
            else:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error
        for row in ordered(
            select(listed, lambda row: row.get("title"), lambda row: row.get("locationsText")),
            lambda row: f"{kind}:{board}:{row.get('externalPath')}",
        ):
            path = row.get("externalPath") or ""
            if not path.startswith("/job/") or ".." in path:
                continue
            full = detail(f"{kind}:{board}:{path}", api + path).get("jobPostingInfo") or {}
            add(
                {"listing": row, "detail": full},
                path,
                row.get("title"),
                full.get("externalUrl") or public + path,
                full.get("location") or row.get("locationsText"),
                full.get("jobDescription"),
                job_type=full.get("timeType"),
                published_at=full.get("startDate"),
            )
    elif kind == "oracle":
        host, site = board.split("/", 1)
        base = f"https://{host}/hcmRestApi/resources/latest"
        listed = []
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
                listed.extend(rows)
                if len(rows) < 50:
                    break
            else:
                source["candidate_capped"] = True
        except DomainError as error:
            if not listed:
                raise
            source["collection_error"] = error
        for row in ordered(
            select(listed, lambda row: row.get("Title"), lambda row: row.get("PrimaryLocation")),
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
                row.get("PrimaryLocation"),
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
            match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
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
                    raise ValueError()
                return result
            except (ValueError, KeyError, TypeError) as error:
                raise DomainError(
                    502, "source_format", "join.com returned unexpected embedded job data."
                ) from error

        for row in ordered(
            select(
                records(state(base).get("jobs"), "items"),
                lambda row: row.get("title"),
                lambda row: ", ".join(
                    str((row.get("city") or {})[key])
                    for key in ("cityName", "regionName", "countryName")
                    if (row.get("city") or {}).get(key)
                ),
            ),
            lambda row: f"{kind}:{board}:{row.get('id')}",
        ):
            identity = row.get("id")
            path = row.get("idParam")
            url = base + "/" + quote(path, safe="-") if path else ""
            full = {}
            key = f"{kind}:{board}:{identity}"
            if url and (preview or key not in known or checked.get(key, "") <= cutoff):
                if key in attempts and json.dumps([url, None], sort_keys=True) in cache:
                    full = state(url).get("job") or {}
                elif details < max_details and attempts.get(key, 0) < 3:
                    details += 1
                    detail_requests[key] = json.dumps([url, None], sort_keys=True)
                    full = state(url).get("job") or {}
                    attempts[key] = attempts.get(key, 0) + 1
                    detail_checks[key] = now()
                    save()
                elif max_details and attempts.get(key, 0) < 3:
                    pending.add(key)
                else:
                    unavailable.add(key)
            merged = {**row, **full}
            city = merged.get("city") or {}
            add(
                merged,
                identity,
                merged.get("title"),
                url,
                ", ".join(
                    str(city[key])
                    for key in ("cityName", "regionName", "countryName")
                    if city.get(key)
                ),
                "\n\n".join(
                    str(merged.get(key) or "")
                    for key in ("intro", "tasks", "requirements", "benefits", "description")
                ),
                remote=merged.get("workplaceType") == "REMOTE",
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
