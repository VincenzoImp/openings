"""What 0.24 removed or renamed, with what replaces it, for a script or agent that still calls it.

``ROUTES``: a removed REST route answers ``410 Gone`` with
``{"error": {"code": "removed", "message", "details": {"use": <replacement>}}}``.

``TOOLS``: every MCP tool of 0.23 that is not a tool of 0.24, by name. Calling one
answers ``{"error": {"code": "renamed" | "removed" | "owner_only", "message",
"details": {"tool", "use"}}}``: ``renamed`` names the tool that does its work now,
``removed`` the feature that went and what to do instead, ``owner_only`` an operation
the owner does in the dashboard. Both tables go in the 0.25.0 release.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Removed:
    message: str
    use: str
    routes: tuple[str, ...] = ()


ROUTES = (
    Removed(
        "Removed in 0.24: the policy became Preferences, read in workspace_context and "
        "written one section at a time; the no-reply period and spoken languages are settings.",
        "GET /workspace/context, PUT /preferences/{section}, PATCH /settings",
        (
            "GET /policy",
            "GET /policy/{section}",
            "POST /policy/{section}/items",
            "POST /policy/{section}/reorder",
            "PATCH /policy/items/{item_id}",
            "DELETE /policy/items/{item_id}",
            "POST /policy/items/{item_id}/confirm",
            "POST /policy/items/{item_id}/move",
            "GET /instructions",
            "PATCH /instructions",
        ),
    ),
    Removed(
        "Removed in 0.24 with the automatic rules: nothing is dismissed automatically. Filter "
        "jobs (signal, requires, hide_unspoken_required) and triage them in a batch.",
        "GET /jobs, POST /jobs/triage",
        ("POST /policy/rules/preview",),
    ),
    Removed(
        "Removed in 0.24: Insights became Stats; current counts are in workspace_context.",
        "GET /stats, GET /workspace/context",
        ("GET /insights", "GET /overview"),
    ),
    Removed(
        "Removed in 0.24: sources list their counts (found, shortlisted, applied, replied).",
        "GET /sources",
        ("GET /collection/yield",),
    ),
    Removed(
        "Removed in 0.24 with frozen contexts and staleness: read the live records and cite "
        "highlight_ids and career_ids when creating a revision.",
        "GET /workspace/context, GET /applications/batch, POST /documents",
        (
            "GET /contexts",
            "POST /contexts",
            "GET /contexts/{context_id}",
            "GET /staleness",
            "GET /applications/{application_id}/staleness",
        ),
    ),
    Removed(
        "Removed in 0.24 with agent runs, questions and requests: the owner and the agent talk "
        "in the agent's chat. Every change carries its actor and batch_id (GET /changes); keep "
        "lasting answers as notes or in Preferences.",
        "GET /changes, POST /jobs/{job_id}/notes",
        (
            "GET /runs",
            "POST /runs",
            "GET /runs/{run_id}",
            "PATCH /runs/{run_id}",
            "POST /runs/{run_id}/finish",
            "GET /questions",
            "POST /questions",
            "GET /questions/{question_id}",
            "POST /questions/{question_id}/answer",
            "POST /questions/{question_id}/withdraw",
            "GET /requests",
            "POST /requests",
            "GET /requests/{request_id}",
            "POST /requests/{request_id}/take",
            "POST /requests/{request_id}/complete",
            "POST /requests/{request_id}/decline",
            "POST /requests/{request_id}/withdraw",
        ),
    ),
    Removed(
        "Removed in 0.24 with skill local notes: the owner's standing instructions are "
        "Preferences, section working_with_me.",
        "PUT /preferences/working_with_me",
        ("GET /skills/{name}/notes", "PUT /skills/{name}/notes"),
    ),
    Removed(
        "Removed in 0.24: Ready is computed, and a CV or letter revision is complete once its "
        "PDF is stored.",
        "GET /applications/batch",
        ("POST /applications/{application_id}/ready", "POST /documents/{document_id}/review"),
    ),
    Removed(
        "Removed in 0.24: an employer reply is recorded, corrected or removed with an "
        "application update (reply, reply_fix) and read with the application (replies).",
        "PATCH /applications/batch",
        (
            "GET /applications/{application_id}/responses",
            "POST /applications/{application_id}/responses",
            "PATCH /responses/{response_id}",
            "DELETE /responses/{response_id}",
        ),
    ),
    Removed(
        "Removed in 0.24: one change log serves every record; filter it by job_id, "
        "application_id, subject, actor or batch_id.",
        "GET /changes",
        ("GET /events", "GET /applications/{application_id}/events"),
    ),
)


@dataclass(frozen=True)
class Gone:
    code: str  # renamed, removed or owner_only
    use: str
    hint: str


def _renamed(use, hint=""):
    return Gone("renamed", use, hint)


def _removed(use, hint):
    return Gone("removed", use, hint)


_OWNER = "The owner does this in the dashboard; it is not an MCP tool."
_CHAT = "Talk to the owner in your chat; keep a lasting answer as a note or in Preferences."
_IMPORT = "The owner imports files in the dashboard; read the CV yourself and save the entries."

TOOLS = {
    "applications_bulk": _renamed("applications_update", "stage and outcome per item"),
    "applications_history": _renamed("changes_list", "with application_id"),
    "applications_ready": _removed("applications_get", "Ready is computed."),
    "capabilities_get": _removed("workspace_context", "tools/list lists the tools."),
    "career_import": Gone("owner_only", "career_save", _IMPORT),
    "career_preview_import": Gone("owner_only", "career_save", _IMPORT),
    "claims_create": _renamed("highlights_save"),
    "claims_delete": _renamed("highlights_delete"),
    "claims_get": _renamed("career_get", "highlights come with their entry"),
    "claims_list": _renamed("career_get", "highlights come with their entry"),
    "claims_update": _renamed("highlights_save", "highlight_id with expected_version"),
    "collection_runs_cancel": _renamed("collection_update", "cancel"),
    "collection_runs_get": _renamed("sources_get", "recent_runs"),
    "collection_runs_list": _renamed("sources_get", "recent_runs"),
    "contexts_create": _removed(
        "workspace_context", "Frozen contexts are gone: read the live records."
    ),
    "contexts_get": _removed(
        "workspace_context", "Frozen contexts are gone: read the live records."
    ),
    "contexts_list": _removed(
        "workspace_context", "Frozen contexts are gone: read the live records."
    ),
    "documents_compare": _renamed("documents_get", "compare_to"),
    "documents_list": _renamed("applications_get", "documents"),
    "documents_review": _removed("documents_get", "A revision is complete once its PDF is stored."),
    "events_list": _renamed("changes_list"),
    "files_get": _renamed(
        "files_download", "file lists come with career_get, templates_get, documents_get"
    ),
    "files_list": _renamed(
        "career_get", "file lists come with career_get, templates_get, documents_get"
    ),
    "files_reserve_download": _renamed("files_download"),
    "files_reserve_upload": _renamed("files_upload"),
    "insights_get": _renamed("stats_get"),
    "instructions_get": _renamed("workspace_context", "Preferences writing"),
    "instructions_update": _renamed("preferences_update", "section writing"),
    "jobs_bulk": _renamed("jobs_triage", "items [{job_id, to, reason}]; forget is jobs_delete"),
    "jobs_distinct": _renamed("jobs_link", "decision different"),
    "jobs_duplicates": _renamed("jobs_list", "signal likely_duplicate"),
    "jobs_merge": _renamed("jobs_link", "decision same"),
    "jobs_resolve": _renamed("jobs_list", "url"),
    "knowledge_create": _renamed("career_save"),
    "knowledge_delete": _renamed("career_delete"),
    "knowledge_get": _renamed("career_get"),
    "knowledge_list": _renamed("career_get", "or the career summary in workspace_context"),
    "knowledge_update": _renamed("career_save", "career_id with expected_version"),
    "notes_get": _renamed("jobs_get", "notes come with jobs_get and applications_get"),
    "notes_list": _renamed("jobs_get", "notes come with jobs_get and applications_get"),
    "notes_pin": _renamed("notes_update", "pinned"),
    "overview_get": _renamed("workspace_context", "counts"),
    "owner_password_update": Gone("owner_only", "", _OWNER),
    "policy_add": _renamed("preferences_update", "the whole section's items"),
    "policy_confirm": _removed("preferences_update", "Preferences need no confirmation."),
    "policy_get": _renamed("workspace_context", "preferences"),
    "policy_move": _renamed("preferences_update", "the whole section's items"),
    "policy_remove": _renamed("preferences_update", "the whole section's items"),
    "policy_reorder": _renamed("preferences_update", "the whole section's items"),
    "policy_rule_preview": _removed("jobs_list", "Nothing is dismissed automatically."),
    "policy_update": _renamed("preferences_update", "the whole section's items"),
    "profile_get": _renamed("workspace_context", "profile"),
    "providers_list": _renamed("collection_get", "include providers"),
    "providers_update": _renamed("collection_update", "providers"),
    "questions_answer": _removed("notes_create", _CHAT),
    "questions_ask": _removed("notes_create", _CHAT),
    "questions_get": _removed("notes_create", _CHAT),
    "questions_list": _removed("notes_create", _CHAT),
    "questions_withdraw": _removed("notes_create", _CHAT),
    "requests_complete": _removed("notes_create", _CHAT),
    "requests_create": _removed("notes_create", _CHAT),
    "requests_decline": _removed("notes_create", _CHAT),
    "requests_get": _removed("notes_create", _CHAT),
    "requests_list": _removed("notes_create", _CHAT),
    "requests_take": _removed("notes_create", _CHAT),
    "requests_withdraw": _removed("notes_create", _CHAT),
    "responses_create": _renamed("applications_update", "reply"),
    "responses_delete": _renamed("applications_update", "reply_fix with delete"),
    "responses_list": _renamed("applications_get", "replies"),
    "responses_update": _renamed("applications_update", "reply_fix"),
    "runs_finish": _removed("changes_list", "Report what you did in the chat."),
    "runs_get": _removed("changes_list", "Report what you did in the chat."),
    "runs_list": _removed("changes_list", "Report what you did in the chat."),
    "runs_start": _removed("changes_list", "Report what you did in the chat."),
    "runs_update": _removed("changes_list", "Report what you did in the chat."),
    "skill_notes_get": _removed(
        "workspace_context", "The owner's instructions are Preferences working_with_me."
    ),
    "skill_notes_update": _removed(
        "preferences_update", "The owner's instructions are Preferences working_with_me."
    ),
    "skills_list": _renamed("skills_get", "without name"),
    "sources_bulk": _renamed("sources_save", "enabled per item; sources_run, sources_delete"),
    "sources_create": _renamed("sources_save"),
    "sources_preview": _renamed("sources_run", "preview true"),
    "sources_schemas": _renamed("collection_get", "include kinds"),
    "sources_update": _renamed("sources_save", "source_id with expected_version"),
    "sources_yield": _renamed("sources_list", "counts"),
    "staleness_get": _removed(
        "applications_get", "Documents are no longer compared with changed inputs."
    ),
    "staleness_list": _removed(
        "applications_list", "Documents are no longer compared with changed inputs."
    ),
    "tasks_cancel": _renamed("collection_update", "cancel"),
    "tasks_get": _renamed("collection_get", "include fetches"),
    "tasks_list": _renamed("collection_get", "include fetches"),
    "tasks_retry": _renamed("collection_update", "retry"),
    "templates_create": _renamed("templates_save"),
    "templates_list": _renamed("workspace_context", "templates"),
    "templates_update": _renamed("templates_save", "template_id with expected_version"),
    "timeline_get": _renamed("changes_list", "notes come with jobs_get and applications_get"),
    "tokens_create": Gone("owner_only", "", _OWNER),
    "tokens_list": Gone("owner_only", "", _OWNER),
    "tokens_revoke": Gone("owner_only", "", _OWNER),
    "workspace_export": Gone("owner_only", "workspace_backup", _OWNER),
    "workspace_info": _renamed("workspace_context", "workspace"),
    "workspace_restore": Gone("owner_only", "", _OWNER),
}


def tool_message(name, gone: Gone):
    """The sentence an agent reads for a 0.23 tool name."""
    if gone.code == "renamed":
        text = f"{name} was replaced in 0.24: use {gone.use}"
        return text + (f" ({gone.hint})." if gone.hint else ".")
    if gone.code == "owner_only":
        return f"{name} is owner-only. {gone.hint}"
    return f"{name} was removed in 0.24. {gone.hint} Use {gone.use}."
