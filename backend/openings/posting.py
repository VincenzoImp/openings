"""Shared posting completeness and source-filter rules."""

import json


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


def matches_filters(item, filters):
    return (
        not filters.get("titles")
        or any(term.casefold() in item["title"].casefold() for term in filters["titles"])
    ) and (
        not filters.get("locations")
        or not item["location"].strip()
        or any(term.casefold() in item["location"].casefold() for term in filters["locations"])
    )
