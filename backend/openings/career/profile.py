"""The Profile and the general instructions, each one versioned setting."""

from __future__ import annotations

from ..errors import conflict
from .models import DEFAULT_GUIDANCE, DEFAULT_PROFILE, InstructionsUpdate, ProfileUpdate
from .records import _setting, _write_setting, values


class ProfileOperations:
    """Reading and updating the Profile and the instructions."""

    def get_profile(self) -> dict:
        """Read the current single-user profile and version."""
        setting = self.workspace.get_settings("profile", DEFAULT_PROFILE)
        return {**DEFAULT_PROFILE, **setting["data"], "version": setting["version"]}

    def _apply_profile(self, conn, data, expected):
        setting = _setting(conn, "profile", DEFAULT_PROFILE)
        if setting["version"] != expected:
            conflict(details={"current_version": setting["version"]})
        previous = {**DEFAULT_PROFILE, **setting["data"]}
        merged = {**previous, **data}
        if previous != merged:
            _write_setting(conn, "profile", merged, expected + 1)
            self._record(
                conn,
                "profile_updated",
                "profile",
                "profile",
                fields=sorted(key for key in merged if previous.get(key) != merged[key]),
                version=expected + 1,
            )

    def update_profile(self, value: ProfileUpdate) -> dict:
        """Edit current profile with optimistic version checking."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            self._apply_profile(conn, data, expected)
        return self.get_profile()

    def get_instructions(self) -> dict:
        """Read stored general document-writing guidance and its version."""
        setting = self.workspace.get_settings("instructions", {"general": DEFAULT_GUIDANCE})
        return {
            "general": setting["data"].get("general", DEFAULT_GUIDANCE),
            "version": setting["version"],
        }

    def update_instructions(self, value: InstructionsUpdate) -> dict:
        """Save editable general CV/letter guidance; existing contexts remain unchanged."""
        with self.db.transaction() as conn:
            setting = _setting(conn, "instructions", {"general": DEFAULT_GUIDANCE})
            if value.expected_version is not None and value.expected_version != setting["version"]:
                conflict(details={"current_version": setting["version"]})
            if setting["data"] != {"general": value.general}:
                _write_setting(
                    conn, "instructions", {"general": value.general}, setting["version"] + 1
                )
                self._record(
                    conn,
                    "instructions_updated",
                    "instructions",
                    "instructions",
                    version=setting["version"] + 1,
                )
        return self.get_instructions()
