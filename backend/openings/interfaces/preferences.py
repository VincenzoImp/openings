"""Operations of Preferences and the workspace settings."""

from ..preferences import PreferencesUpdate, Section, SettingsUpdate
from ..responses import Preferences, PreferenceSection, Settings
from .operation import WRITE, WS, operation


@operation("GET /preferences", tags=["preferences"], mcp="workspace_context")
def preferences_get(ws: WS) -> Preferences:
    """Read the owner's Preferences and settings.

    The five sections with their versions, no_reply_days and spoken_languages.
    """
    return ws.preferences.get_preferences()


@operation("PUT /preferences/{section}", access=WRITE, tags=["preferences"])
def preferences_update(ws: WS, section: Section, body: PreferencesUpdate) -> PreferenceSection:
    """Replace one Preferences section's items, only when the owner asked.

    looking_for, ruled_out, facts, writing (scope all, cv, letter) or working_with_me, with
    its version. Keep the owner's wording.
    """
    return ws.preferences.update_preferences(section, body)


@operation("PATCH /settings", access=WRITE, tags=["preferences"])
def settings_update(ws: WS, body: SettingsUpdate) -> Settings:
    """Change no_reply_days (1-365) or spoken_languages, with the settings' version.

    spoken_languages are ISO 639-1 codes; jobs_list hide_unspoken_required uses them.
    """
    return ws.preferences.update_settings(body)
