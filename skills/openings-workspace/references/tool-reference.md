# Tool-level reference

Step-by-step MCP/REST sequences behind the workflow skills: [Prepare Shortlist](../../prepare-shortlist/SKILL.md) for documents, [Manage sources](../../manage-sources/SKILL.md) for collection.

## Documents

1. Find and read the job with `jobs_search` and `job_get`. Before ingesting a
   URL, `jobs_resolve` reports any existing record and its attempts without
   writing; `jobs_duplicates` lists candidate copies of the same vacancy. Its `application`
   summary identifies an open attempt or the latest closed one. Use
   `applications_list` with `value.job_id` for the full history. Continue an open
   attempt, or create Draft with `application_create` and an idempotency key.
   Starting retains saved interest and removes the job from the pending Shortlist queue. A separate later attempt requires the
   previous one to be closed. Retain the attempt ID for subsequent writes.
2. Read profile, detailed career entries, approved claims, selected templates and
   writing instructions. Summary lists help discovery; fetch the full records
   before writing. Ask for missing facts and keep qualifications accurate.
3. Call `application_prepare_context` with the application, selected templates
   and relevant evidence/claims. Omitted selections use available defaults. Use
   an idempotency key for retries. Retain the context ID/signature and read its
   frozen payload or returned `openings://contexts/...` resource.
4. Write CV, letter and answers from that snapshot. Approved claims provide
   reusable wording; detailed evidence can support accurate new wording. Follow
   general, template and application instructions and answer limits.
5. Download frozen assets through `files_reserve_download`, resolving relative
   URLs against the workspace origin. Compile externally and check page count,
   extracted text and layout. If a compiler is unavailable, save the sources and
   report the missing PDF.
6. Create draft revisions with `documents_create`, keeping application/context
   ownership. Structured bullets can cite `evidence_ids` and `claim_ids`. Reserve
   each PDF/source upload with `files_reserve_upload`: safe relative name, exact
   size, media type and optional SHA-256. Transfer raw bytes using the returned
   HTTP method, URL and headers; verify the stored files. Binary bodies do not
   belong in MCP arguments.
7. An answers document archives a revision. Update the application's live
   `answers` separately with `application_update`, current `expected_version`
   and question IDs. Leave progress and review state unchanged unless requested.

A PDF does not record submission. Changed content needs a new revision using
`previous_id` and its own files. Approved revisions reject uploads. Attachment
changes increment versions: reread and review current files before approval.
Prepare a new context when updated source knowledge is needed.

Application list/detail `preparation` counts describe current revision leaves and
their own PDFs/review state; they are not a submission or quality guarantee. Read
the exact document/files before review. Context summaries include frozen labels
and evidence/claim counts for discovery. Select claims only from selected entries;
omitting selections uses defaults, while explicit empty evidence/claim lists
include none. Updating questions preserves compatible live answers; incompatible
answers reject the update unless deliberately changed or removed in `answers`.

## Manage collection and the archive

Read `sources_schemas` for supported adapters, defaults and limits. Store one
query/location per search. Read the current source and include `expected_version`
for updates, runs and deletion; source service is fixed after creation. For a
one-off backfill use run overrides, leaving saved settings unchanged. Compatible
bulk configuration preserves omitted config and filter keys; an empty filter list
clears it. A schedule replaces the whole schedule variant. Inspect each source's
outcome.

Runs freeze source settings at enqueue time. Use `collection_runs_list` and
`collection_runs_get` to distinguish progress, provider waits and failure.
`sources_list` and `collection_runs_list` return compact rows by default: a
`last_diagnostic_count` instead of diagnostics, and task stubs (state, provider,
attempts, error, next run) without payloads/results or the frozen source
snapshot. Pass `summary: false`, or read `sources_get` / `collection_runs_get`,
for diagnostics and full task records.
`collection_runs_cancel` stops one run. Automatic collection pause preserves
source settings and stops future enqueueing; queued/current runs need explicit
cancellation. Previews, manual and scheduled work share provider request spacing
and durable server cooldowns. `providers_update` accepts enable/pause and request
interval. Let cooldowns expire before retrying.

Description retrieval is automatic. Candidates awaiting text stay in the run
checkpoint; only usable automatic postings enter the archive. Inspect pending,
unavailable and failed results before calling a collection complete.

Use `jobs_search` with `value.queue="inbox"` to review new jobs and
`job_triage` / `jobs_bulk` to save or dismiss selected versioned jobs. Read full
postings and the user's career/preferences to make a qualitative selection.
`value.queue="shortlist"` returns saved jobs with no application attempts, with
server-side totals and pagination. Draft (`draft`, shown as Preparing) removes a
job from that queue. Applied, Interview, Offer and Closed history never returns
it to Inbox or Shortlist. `triage` remains the independent interest flag;
`queue="applications"` finds jobs with any attempt, including dismissed ones. Dismiss remembers the job during future collection. Forget deletes
job-owned history, documents, files and identities when permanent removal is
intended. `job_forget` requires `job_id` and the current `expected_version`.

Applications progress through Preparing (`draft`) / Applied / Interview / Offer / Closed.
Closing requires an explicit outcome. Creation or reopening cannot introduce a
second open attempt; use the application identified by a conflict. Deleting an
attempt preserves its job and other attempts; `application_delete` requires
`application_id` and the current `expected_version`. Deleting the final attempt
returns a saved job to Shortlist; only use this deliberately.
`applications_bulk` applies one action to at most 200 explicit
`{id, expected_version}` items: `close` with `outcome`, `reopen` with a non-Closed
`status`, `mark_ready`, `unmark_ready` or `delete`. Each item reports `ok` with a result or an error (code,
status, message, details); reopening respects the one-open-attempt rule and only
applies to Closed attempts. Bulk forget and delete collect orphaned file bytes once
per call. To stop preparation
and preserve its documents, close it with `not_pursued`. Restore known workaround
dismissals explicitly to `saved`, using current versions: they remain in Applications
when they have attempts and do not re-enter Inbox.

## Ready

`application_ready(application_id, value)` takes the application's current
`expected_version` and `ready` (default true). Marking needs a Preparing
application whose derived checks pass; otherwise it returns
`409 application_not_ready` with `details.check`: `stage` (not Preparing),
`blocked`, `none`, `missing_pdf` or `unreviewed`. The application then reports
`readiness: "ready"`, `ready_at` and `ready_by`; marking twice changes nothing,
and `ready: false` clears the mark. Openings clears it automatically and records
an `application_ready_cleared` event with `reason`: `document_created`,
`document_deleted`, `context_prepared`, `file_uploaded`, `blocking_requirement`
or `left_preparing` (`unmarked` for an explicit clear). Every clearing changes
the application `version`: read it again before the next update.
`applications_list` reads the queue with `readiness: "ready"`, `sort: "ready"`,
`ready_since` and `ready_until`, and returns `ready_count`.

## Runs, questions and the change log

`runs_start` opens a run for the calling token (`workflow`, `scope`, optional
`idempotency_key`); the token's later writes attach to it without any extra
argument. A second start returns `run_open` with the open run in
`details.run`; `supersede: true` marks that run interrupted and starts a new
one. `runs_update` stores a progress `note`; `runs_finish` closes the run with
`summary`, `changes`, `not_done`, `checks`, `limits` and `method`, both with the
run's current `expected_version`. `runs_get` returns the report, the questions
asked and a page of the changes made (`changes_limit`, `changes_offset`);
`runs_list` filters by `status` (`open`, `finished`, `interrupted`), `workflow`,
`token_id` and start time. An open run without a write or note for two hours is
reported as `interrupted`; it stays open, and a later write revives it.

`questions_ask` takes `question`, `why`, optional `subject_type` (`job`,
`application`, `knowledge`) with `subject_id`, optional `choices` and an
`idempotency_key`. `questions_list` filters by `state` (`open`, `answered`,
`withdrawn`), subject, `run_id` and `answered_since`, which returns answers
given at or after a time, oldest first. `questions_answer` and
`questions_withdraw` take the question's current `expected_version`. A question
outlives its subject: after the job, application or entry is deleted,
`subject.id` is null, `subject.deleted` is true and `subject.label` keeps the
name.

`events_list` reads the change log, newest first, by `run_id`, `job_id`,
`application_id`, `subject_type`/`subject_id`, `actor` (`owner`, `token`,
`system`, `unknown`), `kind` or time. Every entry carries `actor`, `run_id` and
`subject`; `application_history` returns the same fields. Changes recorded
before version 0.17 have the actor `unknown (before 0.17)`. Payloads hold
identifiers, changed field names and versions, never record content. Deleting an
application or forgetting a job removes that record's own history and leaves one
`application_deleted` or `job_forgotten` entry.

## Scripting and transfers

Read `/api/openapi.json` for REST inputs under `/api/v1`. Some MCP tools wrap fields
in a `value` DTO; discover their exact schemas. Use optimistic versions and
idempotency keys. Omit unchanged PATCH fields; clear text/lists/objects with empty
values. Career dates also accept null to clear them.

`workspace_export` returns readable JSON without file bytes. Scoped
`workspace_backup` and `workspace_restore_upload` move a portable SQLite snapshot
when requested. Restore replaces workspace data while retaining destination
authentication, recent provider request history and later cooldowns. Keep transfer
headers, credentials and personal data out of logs and repository examples.
