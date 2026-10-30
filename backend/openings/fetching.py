"""Conservative URL imports: public ATS APIs or structured JobPosting data."""

import asyncio
import json
from collections import deque
from html import unescape
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup

from .errors import DomainError


def text_content(value):
    return BeautifulSoup(unescape(str(value or "")), "html.parser").get_text("\n", strip=True)


def ats_endpoint(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if (
        host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}
        and len(parts) >= 3
        and parts[1] == "jobs"
    ):
        return (
            "greenhouse",
            f"https://boards-api.greenhouse.io/v1/boards/{quote(parts[0], safe='')}/jobs/{quote(parts[2], safe='')}",
            parts[2],
        )
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(parts) >= 2:
        api = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        return (
            "lever",
            f"https://{api}/v0/postings/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}?mode=json",
            parts[1],
        )
    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        return (
            "ashby",
            f"https://api.ashbyhq.com/posting-api/job-board/{quote(parts[0], safe='')}?includeCompensation=true",
            parts[1],
        )
    return None


def structured_posting(body):
    soup = BeautifulSoup(body, "html.parser")
    candidates = deque()
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            candidates.append(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue
    while candidates:
        node = candidates.popleft()
        if isinstance(node, list):
            candidates.extend(node)
        elif isinstance(node, dict):
            kind = node.get("@type", [])
            if (
                kind in ("JobPosting", "https://schema.org/JobPosting")
                or isinstance(kind, list)
                and "JobPosting" in kind
            ):
                description = text_content(node.get("description"))
                if not description.strip():
                    continue
                organization = node.get("hiringOrganization") or {}
                locations = node.get("jobLocation") or []
                if isinstance(locations, dict):
                    locations = [locations]
                labels = []
                for location in locations:
                    address = location.get("address", {}) if isinstance(location, dict) else {}
                    if isinstance(address, str):
                        labels.append(address)
                    elif isinstance(address, dict):
                        labels.append(
                            ", ".join(
                                str(address[key])
                                for key in ("addressLocality", "addressRegion", "addressCountry")
                                if isinstance(address.get(key), str)
                            )
                        )
                return {
                    "title": str(node.get("title") or "")[:400],
                    "company": str(organization.get("name") or "")[:300]
                    if isinstance(organization, dict)
                    else "",
                    "location": "; ".join(labels)[:500],
                    "posting": description[:200_000],
                    "metadata": {
                        "extraction": "jobposting-jsonld",
                        "date_posted": node.get("datePosted"),
                        "job_type": node.get("employmentType"),
                        "is_remote": str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE",
                    },
                }
            for key in ("@graph", "mainEntity", "itemListElement", "item"):
                if key in node:
                    candidates.append(node[key])
    return {}


def ats_posting(kind, body, job_id):
    data = json.loads(body)
    if not isinstance(data, dict):
        return {}
    if kind == "greenhouse":
        return {
            "title": data.get("title", ""),
            "location": (data.get("location") or {}).get("name", ""),
            "posting": text_content(data.get("content")),
            "metadata": {"extraction": "greenhouse-api", "source": "greenhouse"},
        }
    if kind == "lever":
        sections = [data.get("descriptionPlain") or text_content(data.get("description"))]
        sections.extend(
            str(item.get("text", "")) + "\n" + text_content(item.get("content"))
            for item in data.get("lists", [])
            if isinstance(item, dict)
        )
        sections.append(data.get("additionalPlain") or text_content(data.get("additional")))
        categories = data.get("categories") or {}
        return {
            "title": data.get("text", ""),
            "location": categories.get("location", ""),
            "posting": "\n\n".join(filter(None, sections)),
            "metadata": {
                "extraction": "lever-api",
                "source": "lever",
                "job_type": categories.get("commitment"),
                "workplace_type": data.get("workplaceType"),
            },
        }
    for job in data.get("jobs", []):
        if str(job.get("id")) == job_id:
            return {
                "title": job.get("title", ""),
                "location": job.get("location", ""),
                "posting": job.get("descriptionPlain") or text_content(job.get("descriptionHtml")),
                "metadata": {
                    "extraction": "ashby-api",
                    "source": "ashby",
                    "is_remote": job.get("isRemote"),
                    "job_type": job.get("employmentType"),
                },
            }
    return {}


async def read_posting(url, discovery):
    """Unextractable or blocked pages stay incomplete; never archive challenge HTML as a job."""
    endpoint = ats_endpoint(url)
    targets = [(endpoint[1], endpoint[0])] if endpoint else []
    targets.append((url, "manual"))
    for target, provider in targets:
        try:
            body = await asyncio.to_thread(
                discovery.fetch_bytes, target, provider_id=provider, maximum=2_000_000
            )
            result = (
                ats_posting(endpoint[0], body, endpoint[2])
                if provider != "manual"
                else structured_posting(body)
            )
            if result.get("posting", "").strip():
                for field, maximum in (
                    ("title", 400),
                    ("company", 300),
                    ("location", 500),
                    ("posting", 200_000),
                ):
                    if field in result:
                        result[field] = str(result[field] or "")[:maximum]
                return result
        except DomainError as error:
            if error.code == "provider_redirect":
                return {"metadata": {"extraction": "needs_text", "extraction_error": error.message}}
            if error.status == 429 or "budget" in error.code or "cooldown" in error.code:
                return {"metadata": {"extraction": "deferred", "extraction_error": error.message}}
        except (ValueError, TypeError, AttributeError):
            continue
    return {
        "metadata": {
            "extraction": "needs_text",
            "extraction_error": "No structured job description was available. Paste the posting text to complete this job.",
        }
    }


async def complete_input(value, discovery):
    if not value.url or value.posting:
        return value
    extracted = await read_posting(value.url, discovery)
    updates = {
        key: item
        for key, item in extracted.items()
        if key != "metadata" and not getattr(value, key)
    }
    updates["metadata"] = {**extracted.get("metadata", {}), **value.metadata}
    return value.model_copy(update=updates)
