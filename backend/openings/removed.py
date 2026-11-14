"""What 0.24 removed, with what replaces it, for a script or agent that still calls it.

One table serves both interfaces: a removed REST route answers ``410 Gone`` with
``{"error": {"code": "removed", "message", "details": {"use": ...}}}`` and a
removed MCP tool answers ``tool_removed`` with the same message. Both go away
after 0.24.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Removed:
    message: str
    use: str
    tools: tuple[str, ...] = ()
    routes: tuple[str, ...] = ()


REMOVED = (
    Removed(
        "Removed in 0.24: the policy became Preferences. Use preferences_get and preferences_update (one whole section at a time); the no-reply period and spoken languages are settings_update.",
        "GET /preferences, PUT /preferences/{section}, PATCH /settings",
        (
            "policy_get",
            "policy_add",
            "policy_update",
            "policy_move",
            "policy_remove",
            "policy_reorder",
            "policy_confirm",
        ),
        (
            "GET /policy",
            "GET /policy/{section}",
            "POST /policy/{section}/items",
            "POST /policy/{section}/reorder",
            "PATCH /policy/items/{item_id}",
            "DELETE /policy/items/{item_id}",
            "POST /policy/items/{item_id}/confirm",
            "POST /policy/items/{item_id}/move",
        ),
    ),
    Removed(
        "Removed in 0.24 with the automatic rules: nothing is dismissed automatically. Filter jobs_list (signal, requires, hide_unspoken_required) and dismiss with jobs_bulk.",
        "GET /jobs, POST /jobs/bulk",
        ("policy_rule_preview",),
        ("POST /policy/rules/preview",),
    ),
    Removed(
        "Removed in 0.24: general instructions are Writing rules in Preferences (preferences_get and preferences_update, section writing).",
        "GET /preferences, PUT /preferences/writing",
        ("instructions_get", "instructions_update"),
        ("GET /instructions", "PATCH /instructions"),
    ),
    Removed(
        "Removed in 0.24: Insights became Stats. Use stats_get (period 90d, 12m or all).",
        "GET /stats",
        ("insights_get",),
        ("GET /insights",),
    ),
    Removed(
        "Removed in 0.24: use stats_get for sent applications, replies and the funnel, and jobs_list (include_counts) or applications_list for current counts.",
        "GET /stats, GET /jobs?include_counts=true, GET /applications",
        ("overview_get",),
        ("GET /overview",),
    ),
    Removed(
        "Removed in 0.24: sources_list returns counts per source (found, shortlisted, applied, replied); stats_get gives replies by source.",
        "GET /sources, GET /stats",
        ("sources_yield",),
        ("GET /collection/yield",),
    ),
    Removed(
        "Removed in 0.24 with frozen contexts: read the live records instead (applications_get, jobs_get, profile_get, knowledge_list, claims_list, templates_list, preferences_get) and cite claim_ids and knowledge_ids in documents_create.",
        "GET /applications/{application_id}, POST /documents",
        ("contexts_create", "contexts_get", "contexts_list"),
        ("GET /contexts", "POST /contexts", "GET /contexts/{context_id}"),
    ),
    Removed(
        "Removed in 0.24: documents are no longer compared with changed inputs. Read the application's revisions with documents_list and replace one with documents_create (previous_id).",
        "GET /documents?application_id=..., POST /documents",
        ("staleness_get", "staleness_list"),
        ("GET /staleness", "GET /applications/{application_id}/staleness"),
    ),
    Removed(
        "Removed in 0.24 with agent runs: report what you did in the chat. Your changes carry your token's actor label and one batch_id per tool call (events_list).",
        "GET /events",
        ("runs_list", "runs_start", "runs_get", "runs_update", "runs_finish"),
        (
            "GET /runs",
            "POST /runs",
            "GET /runs/{run_id}",
            "PATCH /runs/{run_id}",
            "POST /runs/{run_id}/finish",
        ),
    ),
    Removed(
        "Removed in 0.24 with questions for the owner: ask the owner in the chat. Keep a lasting answer as a note on the job or application (notes_create) or in Preferences (preferences_update, section facts).",
        "POST /jobs/{job_id}/notes, PUT /preferences/facts",
        (
            "questions_list",
            "questions_ask",
            "questions_get",
            "questions_answer",
            "questions_withdraw",
        ),
        (
            "GET /questions",
            "POST /questions",
            "GET /questions/{question_id}",
            "POST /questions/{question_id}/answer",
            "POST /questions/{question_id}/withdraw",
        ),
    ),
    Removed(
        "Removed in 0.24 with requests for the agent: the owner asks in the chat. Keep what was agreed as a note on the job or application (notes_create).",
        "POST /jobs/{job_id}/notes",
        (
            "requests_list",
            "requests_create",
            "requests_get",
            "requests_take",
            "requests_complete",
            "requests_decline",
            "requests_withdraw",
        ),
        (
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
        "Removed in 0.24 with skill local notes: skills are served as shipped. The owner's standing instructions are Preferences, section working_with_me (preferences_get, preferences_update).",
        "GET /preferences, PUT /preferences/working_with_me",
        ("skill_notes_get", "skill_notes_update"),
        ("GET /skills/{name}/notes", "PUT /skills/{name}/notes"),
    ),
    Removed(
        "Removed in 0.24: Ready is computed (Shortlisted, every required document complete, no open blocking requirement); read it on applications_get and applications_list.",
        "GET /applications/{application_id}",
        ("applications_ready",),
        ("POST /applications/{application_id}/ready",),
    ),
    Removed(
        "Removed in 0.24 with per-document approval: a CV or letter revision is complete once its PDF is stored.",
        "GET /documents/{document_id}",
        ("documents_review",),
        ("POST /documents/{document_id}/review",),
    ),
    Removed(
        "Removed in 0.24: an employer reply is recorded, corrected or removed with applications_update (reply) and read on applications_get (replies).",
        "PATCH /applications/{application_id}, GET /applications/{application_id}",
        ("responses_list", "responses_create", "responses_update", "responses_delete"),
        (
            "GET /applications/{application_id}/responses",
            "POST /applications/{application_id}/responses",
            "PATCH /responses/{response_id}",
            "DELETE /responses/{response_id}",
        ),
    ),
)

REMOVED_TOOLS = {tool: item.message for item in REMOVED for tool in item.tools}
