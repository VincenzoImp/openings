"""Public postings feeds of applicant tracking systems."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Sequence

from openings.sources.ats import (
    ashby,
    bamboohr,
    greenhouse,
    joincom,
    lever,
    rippling,
    smartrecruiters,
    workable,
    workday,
)

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
    "workday": workday.fetch,
    "joincom": joincom.fetch,
    "workable": workable.fetch,
    "rippling": rippling.fetch,
    "bamboohr": bamboohr.fetch,
}

__all__ = ["FETCHERS", "Fetcher", "KnownIds"]
