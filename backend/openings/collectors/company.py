"""Narrow clients for public ATS boards and two explicit regional searches.

These adapters read public JSON/XML or embedded page data. They do not execute
JavaScript, traverse arbitrary pages or import user-provided Python code.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

from pydantic import BaseModel, ConfigDict, Field

from ..errors import DomainError


class BoardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    board: str = Field(min_length=1, max_length=250)
    region: str = "global"
    max_results: int = Field(default=100, ge=1, le=2000)
    max_details: int = Field(default=10, ge=0, le=25)


class JobCloudConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=300)
    location: str = Field(default="", max_length=300)
    host: str = Field(default="jobs.ch", pattern=r"^(jobs\.ch|jobup\.ch)$")
    results_wanted: int = Field(default=20, ge=1, le=40)
    max_details: int = Field(default=10, ge=0, le=25)


class AdzunaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=300)
    location: str = Field(default="", max_length=300)
    country: str = Field(default="gb", pattern=r"^[a-z]{2}$")
    app_id: str = Field(min_length=1, max_length=300)
    app_key: str = Field(min_length=1, max_length=1000)
    results_wanted: int = Field(default=20, ge=1, le=50)
    max_days_old: int = Field(default=7, ge=1, le=365)


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
    known = known or set()

    def get(url, *, body=None):
        try:
            return json.loads(request(url, method="POST" if body is not None else "GET", body=body))
        except (ValueError, UnicodeError) as error:
            raise DomainError(
                502,
                "source_format",
                f"{kind} returned invalid JSON; its public endpoint may have changed.",
            ) from error

    def detail(key, url, *, body=None):
        nonlocal details
        if key in known or details >= max_details:
            return {}
        details += 1
        return get(url, body=body)

    def add(row, identity, title, url, place="", posting="", **metadata):
        if not identity or len(items) >= maximum:
            return
        key = f"{kind}:{board or config.get('host', '')}:{identity}"
        previous = known.get(key, {}) if isinstance(known, dict) else {}
        metadata = {
            **previous,
            **{key: value for key, value in metadata.items() if value is not None and value != ""},
        }
        items.append(
            {
                "source_key": key,
                "title": str(title or "Untitled role")[:400],
                "company": str(metadata.pop("company", name) or name)[:300],
                "location": str(place or "")[:500],
                "url": str(url or ""),
                "posting": text(str(posting or ""))[:200000],
                "metadata": {
                    "source": kind,
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
    if kind == "recruitee":
        payload = get(f"https://{board}.recruitee.com/api/offers/")
        for row in records(payload, "offers")[:maximum]:
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
        root = xml(request(base + "/xml?language=en"))
        if root.tag != "workzag-jobs":
            raise DomainError(
                502, "source_format", "Personio did not return its public positions feed."
            )
        for row in root.findall("position")[:maximum]:

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
        for row in records(payload, "jobs")[:maximum]:
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
        for row in records(payload)[:maximum]:
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
        for row in records(get(base + "/careers/list"), "result")[:maximum]:
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
        for row in records(get(base))[:maximum]:
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
        for offset in range(0, min(maximum, 500), 100):
            rows = records(
                get(base + "?" + urlencode({"limit": min(maximum, 100), "offset": offset})),
                "content",
            )
            for row in rows[: maximum - len(items)]:
                identity = row.get("id")
                # Construct the vendor endpoint rather than following arbitrary ref URLs.
                full = detail(
                    f"{kind}:{board}:{identity}", base + "/" + quote(str(identity), safe="")
                )
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
            if len(rows) < min(maximum, 100):
                break
    elif kind == "workday":
        host, site = board.split("/", 1)
        tenant = host.split(".")[0]
        api, public = f"https://{host}/wday/cxs/{tenant}/{site}", f"https://{host}/{site}"
        for offset in range(0, min(maximum, 200), 20):
            rows = records(
                get(
                    api + "/jobs",
                    body={
                        "appliedFacets": {},
                        "limit": min(maximum, 20),
                        "offset": offset,
                        "searchText": "",
                    },
                ),
                "jobPostings",
            )
            for row in rows[: maximum - len(items)]:
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
            if len(rows) < min(maximum, 20):
                break
    elif kind == "oracle":
        host, site = board.split("/", 1)
        base = f"https://{host}/hcmRestApi/resources/latest"
        for offset in range(0, min(maximum, 200), 50):
            payload = get(
                base
                + "/recruitingCEJobRequisitions?"
                + urlencode(
                    {
                        "onlyData": "true",
                        "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
                        "finder": f"findReqs;siteNumber={site},limit={min(maximum, 50)},offset={offset}",
                    }
                )
            )
            envelopes = records(payload, "items")
            rows = records(envelopes[0], "requisitionList") if envelopes else []
            for row in rows[: maximum - len(items)]:
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
            if len(rows) < min(maximum, 50):
                break
    elif kind == "joincom":
        base = f"https://join.com/companies/{slug}"

        def state(url):
            page = request(url).decode("utf-8", errors="replace")
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

        for row in records(state(base).get("jobs"), "items")[:maximum]:
            identity = row.get("id")
            path = row.get("idParam")
            url = base + "/" + quote(path, safe="-") if path else ""
            full = {}
            if url and f"{kind}:{board}:{identity}" not in known and details < max_details:
                details += 1
                full = state(url).get("job") or {}
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
    elif kind == "jobcloud":
        host = config["host"]
        for page in range(1, 3):
            count = min(maximum - len(items), 20)
            if count <= 0:
                break
            rows = records(
                get(
                    f"https://{host}/api/v1/public/search?"
                    + urlencode(
                        {
                            "query": config["query"],
                            "location": config["location"],
                            "rows": count,
                            "page": page,
                        }
                    )
                ),
                "documents",
            )
            for row in rows[:count]:
                identity = row.get("job_id")
                full = detail(
                    f"{kind}:{host}:{identity}",
                    f"https://{host}/api/v1/public/search/job/" + quote(str(identity), safe=""),
                )
                links = row.get("_links") or {}
                url = next(
                    (
                        (links.get(key) or {}).get("href")
                        for key in ("detail_en", "detail_de", "detail_fr", "detail_it")
                        if (links.get(key) or {}).get("href")
                    ),
                    "",
                )
                add(
                    {"listing": row, "detail": full},
                    identity,
                    row.get("title"),
                    url
                    or (
                        f"https://{host}/en/vacancies/detail/{row['slug']}/"
                        if row.get("slug")
                        else ""
                    ),
                    row.get("place"),
                    full.get("job_content") or full.get("content") or row.get("preview"),
                    company=row.get("company_name"),
                    published_at=row.get("publication_date"),
                    languages=row.get("language_skills"),
                    description_complete=bool(full.get("job_content") or full.get("content")),
                )
            if len(rows) < count:
                break
    elif kind == "adzuna":
        params = {
            "app_id": config["app_id"],
            "app_key": config["app_key"],
            "what": config["query"],
            "where": config["location"],
            "results_per_page": maximum,
            "max_days_old": config["max_days_old"],
        }
        payload = get(
            f"https://api.adzuna.com/v1/api/jobs/{config['country']}/search/1?" + urlencode(params)
        )
        for row in records(payload, "results")[:maximum]:
            add(
                row,
                row.get("id"),
                row.get("title"),
                row.get("redirect_url"),
                (row.get("location") or {}).get("display_name"),
                row.get("description"),
                company=(row.get("company") or {}).get("display_name"),
                published_at=row.get("created"),
                description_complete=False,
                salary={"min_amount": row.get("salary_min"), "max_amount": row.get("salary_max")},
            )
    else:
        raise DomainError(422, "unsupported_source", "This company source type is unsupported.")
    return items
