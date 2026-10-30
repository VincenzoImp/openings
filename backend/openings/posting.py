"""Shared posting completeness rule for archive views and scoring eligibility."""

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
