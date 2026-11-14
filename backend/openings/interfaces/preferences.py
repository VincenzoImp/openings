"""Operations of Preferences and the workspace settings."""

from ..preferences import PreferencesUpdate, Section, SettingsUpdate
from ..responses import Preferences, PreferenceSection, Settings
from .operation import WRITE, WS, operation


@operation("GET /preferences", tags=["preferences"])
def preferences_get(ws: WS) -> Preferences:
    """Read the owner's Preferences and settings.

    In the owner's words: looking_for, ruled_out, facts, writing (scope all, cv or letter)
    and working_with_me, each versioned; and no_reply_days and spoken_languages. Nothing
    acts automatically.
    """
    return ws.preferences.get_preferences()


@operation("PUT /preferences/{section}", access=WRITE, tags=["preferences"])
def preferences_update(ws: WS, section: Section, body: PreferencesUpdate) -> PreferenceSection:
    """Replace a Preferences section.

    The whole list of items with the section's version (on a conflict read again and merge).
    Keep the owner's wording; change only what the owner asked or confirmed.
    """
    return ws.preferences.update_preferences(section, body)


@operation("PATCH /settings", access=WRITE, tags=["preferences"])
def settings_update(ws: WS, body: SettingsUpdate) -> Settings:
    """Change the no-reply period or the spoken languages.

    no_reply_days (1-365) or spoken_languages (ISO 639-1 codes, used by
    hide_unspoken_required), with the settings' version.
    """
    return ws.preferences.update_settings(body)
