"""CareerService: default settings and change records, composed with each Career area."""

from __future__ import annotations

from .batches import CareerBatches
from .claims import ClaimOperations
from .entries import EntryOperations
from .imports import ImportOperations
from .models import DEFAULT_PROFILE
from .profile import ProfileOperations
from .records import _setting, _write_setting
from .templates import TemplateOperations


class CareerService(
    ProfileOperations,
    EntryOperations,
    ClaimOperations,
    TemplateOperations,
    ImportOperations,
    CareerBatches,
):
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        with self.db.transaction() as conn:
            if not _setting(conn, "profile", None)["version"]:
                _write_setting(conn, "profile", DEFAULT_PROFILE, 1)
