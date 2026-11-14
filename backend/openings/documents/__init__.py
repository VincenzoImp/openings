"""Immutable documents and bounded SQLite file transfers.

``DocumentService`` (service.py) is composed of revisions.py (document
revisions and comparison) and files.py (owned files and scoped transfers); sources.py holds when a CV or
letter revision is complete (its PDF stored) and pairs a TeX source with its
PDF, text.py derives readable text from the source without a TeX runtime
(latex.py: what class commands print), pdf.py reads the text of a PDF-only
revision and models.py holds the inputs.
"""

from .models import (
    SOURCE_KINDS,
    DocumentCreate,
    FileSpec,
    OwnerType,
    UploadReservation,
)
from .service import DocumentService

__all__ = [
    "SOURCE_KINDS",
    "DocumentCreate",
    "DocumentService",
    "FileSpec",
    "OwnerType",
    "UploadReservation",
]
