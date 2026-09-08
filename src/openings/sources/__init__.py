"""Ingestion sources.

Every source returns rows in the canonical shape defined in
:mod:`openings.sources.base`; scoring, deduplication, blacklist exclusion,
persistence and notification are shared downstream.
"""

from openings.sources.base import CANONICAL_COLUMNS, SourceResult, frame_from_records
from openings.sources.collect import CollectResult, collect_all

__all__ = [
    "CANONICAL_COLUMNS",
    "CollectResult",
    "SourceResult",
    "collect_all",
    "frame_from_records",
]
