"""Career imports: a preview, then entries and an optional Profile in one transaction."""

from __future__ import annotations

import json

from pydantic import ValidationError

from ..common import now
from ..errors import DomainError
from .models import DEFAULT_PROFILE, CareerImport, EntryCreate, ImportPreview, ProfileUpdate
from .records import values


class ImportOperations:
    """Previewing and applying a career import."""

    def preview_import(self, value: ImportPreview) -> dict:
        """Preview JSON or plain-text career import without modifying stored information."""
        try:
            data = json.loads(value.text)
        except json.JSONDecodeError:
            item = EntryCreate(kind="other", title=value.title, narrative=value.text)
            return {
                "entries": [item.model_dump()],
                "warnings": ["Text is preserved as one narrative. Review before importing."],
            }
        if isinstance(data, list):
            data = {"entries": data}
        elif isinstance(data, dict) and "title" in data and "entries" not in data:
            data = {"entries": [data]}
        elif (
            isinstance(data, dict)
            and "entries" not in data
            and "profile" not in data
            and any(key in DEFAULT_PROFILE for key in data)
        ):
            data = {"profile": data}
        if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
            raise DomainError(
                422,
                "import_format",
                "Use a profile object, a JSON array of career entries, or an object with profile and entries.",
            )
        try:
            items = [
                EntryCreate.model_validate(item).model_dump() for item in data.get("entries", [])
            ]
            result = {"entries": items}
            if data.get("profile") is not None:
                if not isinstance(data["profile"], dict):
                    raise DomainError(422, "import_format", "The profile must be a JSON object.")
                patch = ProfileUpdate.model_validate(
                    {**data["profile"], "expected_version": self.get_profile()["version"]}
                )
                result["profile"] = patch.model_dump(
                    exclude_unset=True, exclude={"expected_version"}
                )
                result["expected_profile_version"] = patch.expected_version
        except ValidationError as error:
            raise DomainError(
                422,
                "import_validation",
                "The import contains invalid career fields.",
                error.errors(include_context=False),
            ) from error
        result["warnings"] = [
            f"Field '{key}' is not imported; edit it explicitly in the workspace."
            for key in data
            if key not in {"entries", "profile"}
        ]
        if result.get("profile"):
            result["warnings"].append(
                "The previewed profile fields will replace those current fields only after confirmation."
            )
        return result

    def import_entries(self, value: CareerImport) -> dict:
        """Confirm a previewed career import: append narratives and optionally apply explicitly versioned profile fields."""
        profile_data = None
        if value.profile is not None:
            if value.expected_profile_version is None:
                raise DomainError(
                    422,
                    "profile_version",
                    "Confirm the profile version shown in the import preview.",
                )
            try:
                patch = ProfileUpdate.model_validate(
                    {**value.profile, "expected_version": value.expected_profile_version}
                )
                profile_data = values(patch)
                profile_data.pop("expected_version")
            except ValidationError as error:
                raise DomainError(
                    422,
                    "import_validation",
                    "The import contains invalid profile fields.",
                    error.errors(include_context=False),
                ) from error
        timestamp = now()
        identifiers = []
        with self.db.transaction() as conn:
            if profile_data is not None:
                self._apply_profile(conn, profile_data, value.expected_profile_version)
            for item in value.entries:
                identifiers.append(self._insert_entry(conn, item, timestamp))
        return {
            "profile": self.get_profile(),
            "items": [self.get_entry(record_id) for record_id in identifiers],
            "total": len(identifiers),
        }
