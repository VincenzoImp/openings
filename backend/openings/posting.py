"""Shared posting completeness and source-filter rules."""

import json
import re


def posting_complete(posting, metadata, overrides):
    """Accept a source body or user correction, retaining the source's partial flag."""
    if not any(character.isalnum() for character in posting or ""):
        return False
    metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
    overrides = json.loads(overrides) if isinstance(overrides, str) else overrides
    return (metadata or {}).get("description_complete") is not False or bool(
        (overrides or {}).get("posting")
    )


def posting_complete_sql(alias="j"):
    return f"posting_complete({alias}.posting,{alias}.metadata,{alias}.overrides)"


def remote_scope(item):
    """Describe advertised location scope; unknown is not employment eligibility."""
    place = item.get("location", "").casefold()
    metadata = item.get("metadata") or {}
    if any(
        term in place
        for term in ("worldwide", "anywhere in the world", "global remote", "remote anywhere")
    ):
        return "worldwide"
    if metadata.get("remote_scope") == "worldwide":
        return "worldwide"
    if metadata.get("eligible_countries"):
        return "countries"
    if "remote" in place or metadata.get("remote") or metadata.get("is_remote"):
        remainder = re.sub(r"\b(remote|fully|work|from|home|hybrid)\b|[^\w]", "", place).strip()
        return "restricted" if remainder else "unknown"
    return "onsite" if place.strip() else "unknown"


def matches_filters(item, filters):
    titles = filters.get("titles") or []
    if titles and not any(term.casefold() in item["title"].casefold() for term in titles):
        return False
    locations = [term.casefold() for term in filters.get("locations", [])]
    place = item["location"].casefold().strip()
    if not locations or not place:
        return True
    specific = [term for term in locations if term not in ("remote", "worldwide", "anywhere")]
    if any(term in place for term in specific):
        return True
    remote_requested = any(term in locations for term in ("remote", "worldwide", "anywhere"))
    if not remote_requested:
        return False
    scope = remote_scope(item)
    if scope == "worldwide":
        return True
    countries = (item.get("metadata") or {}).get("eligible_countries") or []
    if any(term == country.casefold() for term in specific for country in countries):
        return True
    # A broad Remote token cannot widen a specific geography to US-only or EMEA.
    return not specific and ("remote" in place or scope in ("restricted", "unknown", "countries"))
