"""Hacker News "Who is hiring?": the latest monthly thread's top-level comments as jobs.

Two requests through the shared gate, both to the HN Algolia API: the newest
threads of the whoishiring account, then the chosen thread with its comments.
Each top-level comment is one job, identified by its comment id; replies are
skipped. By convention the first line reads "Company | Role | Place | ...".
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, Field

from ..errors import DomainError
from .company import places

API = "https://hn.algolia.com/api/v1"
THREADS = API + "/search_by_date?tags=story,author_whoishiring&hitsPerPage=20"
TITLE = re.compile(r"ask hn: who is hiring\?", re.IGNORECASE)
ROLE = re.compile(
    r"\b(engineer|engineering|developer|programmer|designer|scientist|analyst|architect|"
    r"manager|lead|head|director|researcher|founding|cto|vp|sre|devops|recruiter|"
    r"consultant|specialist|administrator|writer|marketer|marketing|sales|product|"
    r"intern|staff|principal|senior|junior|ops|operations|support|account|"
    r"full[- ]?stack|front[- ]?end|back[- ]?end|ml|ai|data|security|qa)s?\b",
    re.IGNORECASE,
)
LINK = re.compile(r"https?://|www\.|^[\w-]+(\.[\w-]+)+(/\S*)?$", re.IGNORECASE)
PAY = re.compile(r"[$€£¥]|\b\d+\s*[kK]\b|\bsalary\b|\bequity\b", re.IGNORECASE)
# Employment terms, read word by word: one alternation repeated over the whole
# part would backtrack exponentially on text such as "contractororor".
TERM_WORDS = frozenset(
    [
        "fulltime",
        "parttime",
        "full",
        "part",
        "time",
        "contract",
        "contractor",
        "freelance",
        "intern",
        "internship",
        "permanent",
        "and",
        "or",
    ]
)
TERM_SPLIT = re.compile(r"[,/&+\s-]+")


def _is_terms(part):
    words = [word for word in TERM_SPLIT.split(part.lower()) if word]
    return bool(words) and all(word in TERM_WORDS for word in words)


WORKPLACE = re.compile(r"\b(remote|on[- ]?site|in[- ]office|hybrid)\b", re.IGNORECASE)


class HNHiringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_results: int = Field(default=1000, ge=1, le=2000)


def _json(fetch, url):
    try:
        return json.loads(fetch(url))
    except (ValueError, UnicodeError) as error:
        raise DomainError(
            503,
            "source_unavailable",
            "The HN Algolia API answered with a page that is not JSON; it is tried again later.",
        ) from error


def latest_thread(fetch) -> dict:
    """The newest "Ask HN: Who is hiring?" story of the whoishiring account."""
    hits = (_json(fetch, THREADS) or {}).get("hits") or []
    threads = [
        hit
        for hit in hits
        if isinstance(hit, dict)
        and TITLE.match(str(hit.get("title") or ""))
        and hit.get("objectID")
    ]
    if not threads:
        raise DomainError(
            503, "source_unavailable", "No Who is hiring thread was found; it is tried again later."
        )
    return max(threads, key=lambda hit: hit.get("created_at_i") or 0)


def first_line(text: str) -> dict:
    """Company, title, place and terms from "Company | Role | Place | REMOTE | $150k"."""
    line = text.split("\n", 1)[0]
    parts = [part.strip() for part in line.split("|") if part.strip()]
    company = re.sub(r"\s*\((https?://)?[\w.-]+\.[a-z]{2,}[^)]*\)$", "", parts[0]) if parts else ""
    title, rest, pay, terms, workplace = "", [], [], [], []
    for part in parts[1:]:
        if LINK.search(part) and " " not in part.strip():
            continue
        if PAY.search(part):
            pay.append(part)
        elif _is_terms(part):
            terms.append(part)
        elif not WORKPLACE.sub("", part).strip(" ,/&()-"):
            workplace.append(part)
        elif not title and ROLE.search(part):
            title = part
        else:
            rest.append(part)
    if not title and rest:
        title = rest.pop(0)
    remote = any(re.search(r"\bremote\b", part, re.IGNORECASE) for part in workplace + rest)
    place = places(*rest)
    if remote and "remote" not in place.casefold():
        place = places(place, "Remote") if place else "Remote"
    kind = next(
        (
            WORKPLACE.search(part).group(1).casefold()
            for part in workplace + rest
            if WORKPLACE.search(part)
        ),
        None,
    )
    return {
        "company": company[:200],
        "title": (title or "Untitled role")[:300],
        "location": place[:300],
        "salary": " · ".join(pay)[:200] or None,
        "employment_type": ", ".join(terms) or None,
        "workplace_type": "remote"
        if remote
        else ("onsite" if kind.startswith(("on", "in")) else kind)
        if kind
        else None,
    }


def collect(fetch, text, config: dict, source: dict) -> list[dict]:
    """One posting per top-level comment of the latest thread; deleted ones are skipped."""
    thread = latest_thread(fetch)
    story = _json(fetch, f"{API}/items/{int(thread['objectID'])}") or {}
    comments = [
        row
        for row in story.get("children") or []
        if isinstance(row, dict) and row.get("type", "comment") == "comment" and row.get("text")
    ]
    source["listing_empty"] = not comments
    source["listed"] = len(comments)
    source["result_capped"] = len(comments) > config.get("max_results", 1000)
    items = []
    for row in comments:
        identity = str(row.get("id") or "")
        posting = text(row["text"])
        if not identity.isdigit() or not posting:
            continue
        head = first_line(posting)
        items.append(
            {
                "source_key": f"hnhiring:{identity}",
                "title": head["title"],
                "company": head["company"],
                "location": head["location"],
                "url": f"https://news.ycombinator.com/item?id={identity}",
                "posting": posting,
                "metadata": {
                    "source": "hnhiring",
                    "external_id": identity,
                    "thread": str(thread["objectID"]),
                    "thread_title": thread.get("title"),
                    "author": row.get("author"),
                    "published_at": row.get("created_at"),
                    "salary": head["salary"],
                    "employment_type": head["employment_type"],
                    "workplace_type": head["workplace_type"],
                },
                "raw": {"id": identity, "text": row["text"]},
            }
        )
    return items
