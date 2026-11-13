"""CareerService: default settings and change records, composed with each Career area."""

from __future__ import annotations

from .claims import ClaimOperations
from .entries import EntryOperations
from .imports import ImportOperations
from .models import DEFAULT_GUIDANCE, DEFAULT_PROFILE
from .profile import ProfileOperations
from .records import _setting, _write_setting
from .templates import TemplateOperations


class CareerService(
    ProfileOperations, EntryOperations, ClaimOperations, TemplateOperations, ImportOperations
):
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        with self.db.transaction() as conn:
            for key, default in [
                ("profile", DEFAULT_PROFILE),
                ("instructions", {"general": DEFAULT_GUIDANCE}),
            ]:
                if not _setting(conn, key, None)["version"]:
                    _write_setting(conn, key, default, 1)

    def _record(self, conn, event, subject_type, subject_id, /, **payload):
        """Leave an attributed record of a change: identifiers, field names and versions only."""
        self.workspace.event(event, payload=payload, conn=conn, subject=(subject_type, subject_id))
