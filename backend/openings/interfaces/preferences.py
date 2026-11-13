"""REST routes and MCP tools of Preferences and the workspace settings."""

from mcp.types import ToolAnnotations

from ..preferences import PreferencesService, PreferencesUpdate, Section, SettingsUpdate
from .registry import Operation, Param, Route, Tool, bind_mcp, bind_rest

READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
REPLACE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

OPERATIONS = (
    Operation(
        "preferences.read",
        "preferences",
        "get",
        "Career and templates",
        "Read the owner's Preferences and settings",
        params=(),
        call=lambda s: s.get_preferences(),
        rest=(Route("GET", "/preferences", "preferences_get"),),
        tool=Tool(
            READ,
            "Read the owner's Preferences, in their own words: looking_for (what I'm looking for), ruled_out (what I rule out), facts (facts about me), writing (writing rules, each for all documents, the cv or the letter) and working_with_me (instructions you follow), each with its version; and the settings no_reply_days and spoken_languages. Apply them yourself: nothing here acts automatically.",
        ),
    ),
    Operation(
        "preferences.update",
        "preferences",
        "update",
        "Career and templates",
        "Replace the statements of a Preferences section",
        params=(Param("section", Section), Param("value", PreferencesUpdate)),
        call=lambda s, section, value: s.update_preferences(section, value),
        rest=(Route("PUT", "/preferences/{section}", "preferences_update"),),
        tool=Tool(
            REPLACE,
            "Replace a section's whole list of statements with the section's current version (a conflict returns details.current_version: read again and merge). Keep the owner's wording; add or change only what the owner asked for or confirmed. Items are {text} and, in writing, {text, scope: all|cv|letter}.",
        ),
    ),
    Operation(
        "settings.update",
        "settings",
        "update",
        "Career and templates",
        "Change the no-reply period or the spoken languages",
        params=(Param("value", SettingsUpdate),),
        call=lambda s, value: s.update_settings(value),
        rest=(Route("PATCH", "/settings", "settings_update"),),
        tool=Tool(
            REPLACE,
            "Change no_reply_days (1-365: when an application without an employer answer counts as no reply) or spoken_languages (ISO 639-1 codes, used by the jobs filter hide_unspoken_required), with the settings' current version.",
        ),
    ),
)


def register_api(router, preferences: PreferencesService):
    bind_rest(router, OPERATIONS, preferences)


def register_mcp(mcp, preferences: PreferencesService):
    bind_mcp(mcp, OPERATIONS, preferences)
