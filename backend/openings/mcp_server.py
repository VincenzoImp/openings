"""MCP server that matches REST threading and error contracts."""

import json
import sqlite3

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import (
    ResourceError,
    ResourceNotFoundError,
    ToolError,
    UnexpectedResourceError,
)
from pydantic import ValidationError

from .actors import batch
from .errors import DomainError


def validation_details(error: ValidationError):
    return [
        {"field": list(e["loc"]), "message": e["msg"], "type": e["type"]}
        for e in error.errors(include_url=False, include_context=False)
    ]


def structured_error(error: BaseException) -> DomainError | None:
    if isinstance(error, DomainError):
        return error
    if isinstance(error, ValidationError):
        return DomainError(
            422, "validation", "Some fields need attention.", validation_details(error)
        )
    if isinstance(error, sqlite3.IntegrityError):
        return DomainError(409, "constraint", "This change conflicts with existing workspace data.")
    return None


def error_text(domain: DomainError) -> str:
    body = {
        "code": domain.code,
        "status": domain.status,
        "message": domain.message,
        "details": domain.details,
    }
    return json.dumps({"error": body}, default=str)


# Tools removed in 0.24, with what replaces each, for an agent that still calls them.
_PREFERENCES = "Removed in 0.24: the policy became Preferences. Use preferences_get and preferences_update (one whole section at a time); the no-reply period and spoken languages are settings_update."
REMOVED_TOOLS = {
    "policy_get": _PREFERENCES,
    "policy_add": _PREFERENCES,
    "policy_update": _PREFERENCES,
    "policy_move": _PREFERENCES,
    "policy_remove": _PREFERENCES,
    "policy_reorder": _PREFERENCES,
    "policy_confirm": _PREFERENCES,
    "policy_rule_preview": "Removed in 0.24 with the automatic rules: nothing is dismissed automatically. Filter jobs_list (signal, requires, hide_unspoken_required) and dismiss with jobs_bulk.",
    "instructions_get": "Removed in 0.24: general instructions are Writing rules in Preferences (preferences_get, section writing).",
    "instructions_update": "Removed in 0.24: general instructions are Writing rules in Preferences (preferences_update, section writing).",
    # #211 secondary features trimmed.
    "insights_get": "Removed in 0.24: Insights became Stats. Use stats_get (period 90d, 12m or all).",
    "overview_get": "Removed in 0.24: use stats_get for sent applications, replies and the funnel, and jobs_list (include_counts) or applications_list for current counts.",
    "sources_yield": "Removed in 0.24: sources_list returns counts per source (found, shortlisted, applied, replied); stats_get gives replies by source.",
}
# #215: frozen contexts and staleness.
_CONTEXTS = "Removed in 0.24 with frozen contexts: read the live records instead (applications_get, jobs_get, profile_get, knowledge_list, claims_list, templates_list, preferences_get) and cite claim_ids and knowledge_ids in documents_create."
REMOVED_TOOLS |= {
    "contexts_create": _CONTEXTS,
    "contexts_get": _CONTEXTS,
    "contexts_list": _CONTEXTS,
    "staleness_get": "Removed in 0.24: documents are no longer compared with changed inputs. Read the application's revisions with documents_list and replace one with documents_create (previous_id).",
    "staleness_list": "Removed in 0.24: documents are no longer compared with changed inputs. List applications with applications_list and their revisions with documents_list.",
}

# #209: the agent-collaboration layer.
_RUNS = "Removed in 0.24 with agent runs: report what you did in the chat. Your changes carry your token's actor label and one batch_id per tool call (events_list)."
_QUESTIONS = "Removed in 0.24 with questions for the owner: ask the owner in the chat. Keep a lasting answer as a note on the job or application (notes_create) or in Preferences (preferences_update, section facts)."
_REQUESTS = "Removed in 0.24 with requests for the agent: the owner asks in the chat. Keep what was agreed as a note on the job or application (notes_create)."
_SKILL_NOTES = "Removed in 0.24 with skill local notes: skills are served as shipped. The owner's standing instructions are Preferences, section working_with_me (preferences_get, preferences_update)."
REMOVED_TOOLS.update(
    {
        **dict.fromkeys(
            ("runs_list", "runs_start", "runs_get", "runs_update", "runs_finish"), _RUNS
        ),
        **dict.fromkeys(
            (
                "questions_list",
                "questions_ask",
                "questions_get",
                "questions_answer",
                "questions_withdraw",
            ),
            _QUESTIONS,
        ),
        **dict.fromkeys(
            (
                "requests_list",
                "requests_create",
                "requests_get",
                "requests_take",
                "requests_complete",
                "requests_decline",
                "requests_withdraw",
            ),
            _REQUESTS,
        ),
        **dict.fromkeys(("skill_notes_get", "skill_notes_update"), _SKILL_NOTES),
    }
)


class OpeningsMCP(MCPServer):
    """Return REST-shaped error bodies; the SDK runs sync tools in worker threads."""

    async def call_tool(self, name, arguments, context=None):
        try:
            if name in REMOVED_TOOLS and self._tool_manager.get_tool(name) is None:
                raise DomainError(404, "tool_removed", REMOVED_TOOLS[name], {"tool": name})
            self._refuse_unknown_arguments(name, arguments)
            # Every change of one tool call shares one batch id.
            with batch():
                return await super().call_tool(name, arguments, context)
        except DomainError as error:
            raise ToolError(error_text(error)) from error
        except ToolError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            raise ToolError(error_text(domain)) from error.__cause__

    def _refuse_unknown_arguments(self, name, arguments):
        """An argument the tool does not take is refused, never ignored.

        Lists take their filters inside ``value``; a filter passed beside it would
        otherwise be dropped silently and the list returned unfiltered.
        """
        tool = self._tool_manager.get_tool(name)
        if tool is None or not arguments:
            return
        unknown = sorted(set(arguments) - set(tool.parameters.get("properties", {})))
        if unknown:
            raise DomainError(
                422,
                "validation",
                "Some fields need attention.",
                [
                    {
                        "field": [field],
                        "message": "This tool takes no such argument; pass filters, "
                        "options and a write's fields inside value.",
                        "type": "extra_forbidden",
                    }
                    for field in unknown
                ],
            )

    async def read_resource(self, uri, context=None):
        try:
            return await super().read_resource(uri, context)
        except UnexpectedResourceError as error:
            domain = structured_error(error.__cause__)
            if domain is None:
                raise
            kind = ResourceNotFoundError if domain.status == 404 else ResourceError
            raise kind(domain.message) from error.__cause__
