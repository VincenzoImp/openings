"""Company feeds and persisted collection tasks.

``DiscoveryService`` (service.py) is composed of sources.py, runs.py and
tasks.py over the shared provider gate. models.py holds the typed inputs,
resolution.py turns a URL or configuration into a source, feeds.py reads
postings and network.py is the public-address policy behind every request.
"""

from .models import (
    CollectionWrite,
    Filters,
    RSSConfig,
    RunOverrides,
    SourceBulk,
    SourceConfigure,
    SourceCreate,
    SourceKind,
    SourcePatch,
    SourcePreview,
    SourceRun,
    SourceVersion,
)
from .service import DiscoveryService

__all__ = [
    "CollectionWrite",
    "DiscoveryService",
    "Filters",
    "RSSConfig",
    "RunOverrides",
    "SourceBulk",
    "SourceConfigure",
    "SourceCreate",
    "SourceKind",
    "SourcePatch",
    "SourcePreview",
    "SourceRun",
    "SourceVersion",
]
