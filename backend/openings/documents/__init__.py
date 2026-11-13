"""Frozen application context, immutable documents and bounded SQLite file transfers.

``DocumentService`` (service.py) is composed of contexts.py (frozen contexts
and their staleness), revisions.py (document revisions, review and comparison)
and files.py (owned files and scoped transfers); sources.py pairs a CV or
letter revision's .tex source with its PDF, text.py derives readable text from
the source without a TeX runtime (latex.py: what class commands print),
upgrade.py is the schema 13 step and
models.py holds the inputs.
"""

from .models import (
    SOURCE_KINDS,
    ContextCreate,
    DocumentCreate,
    OwnerType,
    ReviewUpdate,
    StalenessStage,
    UploadReservation,
)
from .service import DocumentService

__all__ = [
    "SOURCE_KINDS",
    "ContextCreate",
    "DocumentCreate",
    "DocumentService",
    "OwnerType",
    "ReviewUpdate",
    "StalenessStage",
    "UploadReservation",
]
