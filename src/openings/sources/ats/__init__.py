"""Public postings feeds of applicant tracking systems."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Sequence

from openings.sources.ats import ashby, greenhouse, lever, smartrecruiters

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig

KnownIds = Callable[[Sequence[str]], set[str]]
"""Given external ids, the subset already stored; lets a feed skip detail fetches."""

Fetcher = Callable[
    ["CompanySourceConfig", str | None, float, KnownIds | None], list[dict[str, Any]]
]

FETCHERS: dict[str, Fetcher] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}

__all__ = ["FETCHERS", "Fetcher", "KnownIds"]
