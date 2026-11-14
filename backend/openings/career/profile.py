"""The Profile, one versioned setting."""

from __future__ import annotations

from .. import events
from ..errors import conflict
from .models import DEFAULT_PROFILE, ProfileUpdate
from .records import _setting, _write_setting, values


class ProfileOperations:
    """Reading and updating the Profile."""

    def get_profile(self) -> dict:
        """Read the current single-user profile and version."""
        setting = self.workspace.get_settings("profile", DEFAULT_PROFILE)
        return {**DEFAULT_PROFILE, **setting["data"], "version": setting["version"]}

    def _apply_profile(self, conn, data, expected):
        setting = _setting(conn, "profile", DEFAULT_PROFILE)
        if setting["version"] != expected:
            conflict(details={"current_version": setting["version"], "id": "profile"})
        previous = {**DEFAULT_PROFILE, **setting["data"]}
        merged = {**previous, **data}
        if previous != merged:
            _write_setting(conn, "profile", merged, expected + 1)
            events.record(
                conn,
                "profile_updated",
                ("profile", "profile"),
                {
                    "fields": sorted(key for key in merged if previous.get(key) != merged[key]),
                    "version": expected + 1,
                },
            )

    def update_profile(self, value: ProfileUpdate) -> dict:
        """Edit current profile with optimistic version checking."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            self._apply_profile(conn, data, expected)
        return self.get_profile()
