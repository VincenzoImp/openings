"""Career evidence, reusable claims and user-owned template packages.

``CareerService`` (service.py) is composed of profile.py (Profile and
instructions), entries.py (Career entries), claims.py, templates.py and
imports.py; models.py holds the inputs and defaults, records.py the row
helpers shared with documents.
"""

from .models import (
    DEFAULT_GUIDANCE,
    DEFAULT_PROFILE,
    CareerDates,
    CareerImport,
    ClaimCreate,
    ClaimUpdate,
    ImportPreview,
    InstructionsUpdate,
    KnowledgeCreate,
    KnowledgeUpdate,
    ProfileUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from .service import CareerService

__all__ = [
    "DEFAULT_GUIDANCE",
    "DEFAULT_PROFILE",
    "CareerDates",
    "CareerImport",
    "CareerService",
    "ClaimCreate",
    "ClaimUpdate",
    "ImportPreview",
    "InstructionsUpdate",
    "KnowledgeCreate",
    "KnowledgeUpdate",
    "ProfileUpdate",
    "TemplateCreate",
    "TemplateUpdate",
]
