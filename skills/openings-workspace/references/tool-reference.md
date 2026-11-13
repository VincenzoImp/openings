# Tool-level reference

Step-by-step MCP/REST sequences behind the workflow skills: [Prepare Shortlist](../../prepare-shortlist/SKILL.md) for documents, [Manage sources](../../manage-sources/SKILL.md) for collection.

## Documents

1. Find and read the job with `jobs_list` and `jobs_get`. Before ingesting a
   URL, `jobs_resolve` reports any existing record and its attempts without
   writing; `jobs_duplicates` lists candidate copies of the same vacancy with a
   `confidence`, `tier` and `reasons` (`min_confidence` defaults to 0.5). A job's `application`
   summary identifies an open attempt or the latest closed one. Use
   `applications_list` with `value.job_id` for the full history. Continue an open
   attempt, or create Draft with `applications_create` and an idempotency key.
   Starting retains saved interest and removes the job from the pending Shortlist queue. A separate later attempt requires the
   previous one to be closed. Retain the attempt ID for subsequent writes.
2. Read profile, the policy (`policy_get`), detailed career entries, approved
   claims with their typed selection fields, selected templates and writing
   instructions. Summary lists help discovery; fetch the full records
   before writing. Ask for missing facts and keep qualifications accurate.
3. Call `contexts_create` with the application, selected templates
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
   ownership and citing `claim_ids` and `knowledge_ids`; a CV or letter takes no
   `content`. Reserve its `.tex` source upload with `files_reserve_upload`: safe
   relative name, exact size, media type and optional SHA-256. Then reserve the
   PDF with `source_sha256` set to the source's SHA-256. Transfer raw bytes
   using the returned HTTP method, URL and headers; verify the stored files and
   read the revision's derived `text`. Binary bodies do not belong in MCP
   arguments.
7. An answers document archives a revision. Update the application's live
   `answers` separately with `applications_update`, current `expected_version`
   and question IDs. Leave progress and review state unchanged unless requested.

A PDF does not record submission. A changed source needs a new revision using
`previous_id` and its own source and PDF; `documents_compare` shows what changed. Approved revisions reject uploads. Attachment
changes increment versions: reread and review current files before approval.
Prepare a new context when updated source knowledge is needed.

Application list/detail `preparation` counts describe current revision leaves and
their own PDFs/review state; they are not a submission or quality guarantee. Read
the exact document/files before review. Context summaries include frozen labels
and evidence/claim counts for discovery. Select claims only from selected entries;
omitting selections uses defaults, while explicit empty evidence/claim lists
include none. Updating questions preserves compatible live answers; incompatible
answers reject the update unless deliberately changed or removed in `answers`.

## Policy

`policy_get` returns the four sections (`decision`, `eligibility`, `writing`,
`facts`) with their versions and items, and the signals a decision rule may
name; `policy_get({"section": "writing"})` returns one section. Every write
takes the current version of the section as `expected_version` and answers with
the section as it is afterwards; a stale version is `409 conflict` with
`details.current_version`.

- `policy_add(section, value)`: `label`, `statement`, optional `value` (text, a
  number, true/false or a short list; `value_type: "date"` for a date), `note`,
  `scope` (`writing` only) and `rule` (`decision` only). Use an
  `idempotency_key` for retries.
- `policy_update(item_id, value)`: omitted fields stay; `value`, `scope` and
  `rule` accept null. `policy_move(item_id, {expected_version, section,
  target_version})` moves an item to another section.
  `policy_reorder(section, {expected_version, item_ids})` takes every id of the
  section in the new order. `policy_remove(item_id, expected_version)` deletes.
- With an agent token an added or changed item has `confirmed: false`.
  `policy_confirm` and `enabled: true` on a rule are the owner's (`403
  forbidden`).
- A decision `rule` is `{signal, condition: {operator, value}, action}` on
  `language_required` (`in`/`not_in` a list of languages, by name or code),
  `posting_language` (`in`/`not_in`), `likely_duplicate` (`at_least` a
  confidence) or `no_longer_listed` (`is` true). While enabled and confirmed it
  acts once on each job nobody has reviewed, when the signal arrives: at
  collection, and for `no_longer_listed` when a board stops listing the posting.
  `dismiss` dismisses the job as the system, naming the rule in
  `dismissal.rule`; `flag` records it in `signals.rules`. Jobs the owner adds
  in the dashboard are never dismissed by a rule. `policy_rule_preview({rule})`
  counts the jobs waiting in the Inbox a rule would match now, without acting:
  measure a rule before proposing it.

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
snapshot. Pass `value.summary: false`, or read `sources_get` / `collection_runs_get`,
for diagnostics and full task records.
`collection_runs_cancel` stops one run. Automatic collection pause preserves
source settings and stops future enqueueing; queued/current runs need explicit
cancellation. Previews, manual and scheduled work share provider request spacing
and durable server cooldowns. `providers_update` accepts enable/pause and request
interval. Let cooldowns expire before retrying.

Description retrieval is automatic. Candidates awaiting text stay in the run
checkpoint; only usable automatic postings enter the archive. Inspect pending,
unavailable and failed results before calling a collection complete.

`sources_yield({since?, until?, min_sample?})` reports, per source and per
search, what the jobs it first collected became: collected, to review,
shortlisted, applied, employer responses, dismissed (by rule, agent, owner or
other, and by rule), likely duplicates and postings no longer listed, with
searches split by job board. Use it to tune sources (manage-sources).

Every job has `signals` computed at collection without a model: `language`,
the languages it states as `required` (groups, one of a group suffices) or
`welcome`, a likely `duplicate` of an earlier job with its confidence, and
`no_longer_listed` (a company board stopped listing it; `unlisted_at` on the
observation). `jobs_list` filters by `signal`, `posting_language`,
`posting_language_not`, `requires`, `dismissed_by` and `rule_id`, and
`include_counts` returns the size of each queue. A dismissed job has
`dismissal`: who, when, why (`reason`) and the rule, if one dismissed it.
`jobs_distinct(job_id, {other_id})` records that a flagged likely duplicate is a
different vacancy. Whether a board still lists a posting is
`signals.no_longer_listed`.

Use `jobs_list` with `value.queue="inbox"` to review new jobs and
`jobs_triage` / `jobs_bulk` to save or dismiss selected versioned jobs. Read full
postings and the user's career/preferences to make a qualitative selection.
`value.queue="shortlist"` returns saved jobs with no application attempts, with
server-side totals and pagination. Draft (`draft`, shown as Preparing) removes a
job from that queue. Applied, Interview, Offer and Closed history never returns
it to Inbox or Shortlist. `triage` remains the independent interest flag;
`queue="applications"` finds jobs with any attempt, including dismissed ones. Dismiss remembers the job during future collection. Forget deletes
job-owned history, documents, files and identities when permanent removal is
intended. `jobs_delete` requires `job_id` and the current `expected_version`.

Applications progress through Preparing (`draft`) / Applied / Interview / Offer / Closed.
Closing requires an explicit outcome. Creation or reopening cannot introduce a
second open attempt; use the application identified by a conflict. Deleting an
attempt preserves its job and other attempts; `applications_delete` requires
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

`applications_ready(application_id, value)` takes the application's current
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
`ready_since` and `ready_until`, and returns `ready_count`. `applied_since` and
`applied_until` filter by the time an application was recorded as applied;
`ready: false` with `status: "draft"` lists Preparing applications not marked
ready.

## Employer responses, no reply and insights

`responses_list(application_id)`, `responses_create(application_id, value)`,
`responses_update(response_id, value)` and `responses_delete(response_id,
expected_version)` manage an application's employer answers. A response has
`kind` (`rejection`, `interview`, `offer`, `other`), `date` (not in the future;
today when omitted), `note`, `estimated`, `origin` (`manual`, `stage`,
`upgrade`), who created and updated it, and `version`. Adding takes an
`idempotency_key`; one per kind and day (except `other`) returns
`409 response_exists` with `details.response_id`, and a Draft never sent returns
`409 application_not_sent`. Adding never moves the stage; removing never moves
it back. `applications_get` returns `responses` and `last_response`; list rows
carry `last_response`.

`applications_update` records the matching response when it moves a sent
application: to `interview` from Preparing or Applied, to `offer` from an
earlier stage, or to `closed` with `outcome: "rejected"` (accepting without an
offer on record also records one). Closing a Draft never sent as rejected
records nothing.
It takes `response_date` (default today) and `response_note`; a duplicate is not
added. Closing with `outcome: "no_response"` needs a sent application and takes
`concluded_on` (default today). `applications_list` with `no_reply_due: true`
lists Applied applications sent before the no-reply cutoff; every list result
has `no_reply` with `days`, `source` (`policy` or `default`), `item_id`,
`confirmed` and `due`. The period comes from the Policy decision item labelled
"No reply" (its first number of days), else 30.

`insights_get(value)` / `GET /insights` takes `min_sample` (1-100, default 5),
`applied_since` and `applied_until`. It returns `overall` (sent, responded,
interviews, offers, rejections, no reply, waiting, the three rates,
`median_days_to_response`, `timed`, `undated`), `time_to_response` buckets,
`groups` (`role_family`, `seniority`, `location`, `source_kind`, `source`,
`month`) and `excluded` (`preparing`, `closed_unsent`). A rate or median below
the sample is `null` with `withheld`.

## Requests for the agent

`requests_list` filters by `state` (`open`, `taken`, `done`, `declined`,
`withdrawn`), `subject_type`/`subject_id`, `run_id` and `updated_since` (written
or changed at or after a time, oldest first). Each request has `text`, an
optional `subject` shaped like a question's, `created_by`, `taken_by`, `run_id`
(the run that handled it), `result` and `resolved_by`. `requests_take` moves an
open request to `taken` for the calling token and records its open run;
`409 request_taken` names the run of another taker. `requests_complete` takes
`result` and `requests_decline` takes `reason`; both work on an open or taken
request, need its current `expected_version` and an API token
(`403 request_actor` for a dashboard session). `requests_create` (`text`,
optional subject, `idempotency_key`) and `requests_withdraw` need owner
authority: an agent token gets `403 forbidden`. A finished or withdrawn request
returns `409 request_closed`. A request outlives its subject like a question
does, and `runs_get` lists the requests a run handled.

## Runs, questions and the change log

`runs_start` opens a run for the calling token (`workflow`, `scope`, optional
`idempotency_key`); the token's later writes attach to it without any extra
argument. A second start returns `run_open` with the open run in
`details.run`; `supersede: true` marks that run interrupted and starts a new
one. `runs_update` stores a progress `note`; `runs_finish` closes the run with
`summary`, `changes`, `not_done`, `checks`, `limits` and `method`, both with the
run's current `expected_version`. `runs_get` returns the report, the questions
asked and a page of the changes made (`value.changes_limit`,
`value.changes_offset`);
`runs_list` filters by `status` (`open`, `finished`, `interrupted`), `workflow`,
`token_id`, start time and `active_since` (last activity at or after a time). An open run without a write or note for two hours is
reported as `interrupted`; it stays open, and a later write revives it.
Each listed run carries its report's `summary` and `method`.

`skills_get(name)` returns `SKILL.md` with this workspace's local notes appended
under `## Local notes for this workspace` (`value.local_notes: false` for the shipped
text alone); reference files are served as shipped. `skill_notes_get(name)`
returns `text`, `version` (0 when none), the author and up to 50 earlier
versions. `skill_notes_update(name, {"expected_version": N, "text": "..."})`
replaces the whole notes (at most 2,000 characters; empty clears them); a stale
version returns `409 conflict` with `details.current_version`. An agent token may
write notes; every version names its author and the owner can restore any.

`questions_ask` takes `question`, `why`, optional `subject_type` (`job`,
`application`, `knowledge`) with `subject_id`, optional `choices` and an
`idempotency_key`. `questions_list` filters by `state` (`open`, `answered`,
`withdrawn`), subject, `run_id` and `answered_since`, which returns answers
given at or after a time, oldest first. `questions_answer` and
`questions_withdraw` take the question's current `expected_version`;
`questions_answer` needs owner authority and returns `403 forbidden` to an agent
token. A question
outlives its subject: after the job, application or entry is deleted,
`subject.id` is null, `subject.deleted` is true and `subject.label` keeps the
name.

`events_list` reads the change log, newest first, by `run_id`, `job_id`,
`application_id`, `subject_type`/`subject_id`, `actor` (`owner`, `token`,
`system`, `unknown`), `kind` or time; `subject_types` takes several kinds of
record at once. Every entry carries `actor` (for a token, with `token_kind`
`owner` or `agent`), `run_id` with `run_workflow`, and `subject`; `applications_history` returns the same fields. Changes recorded
before version 0.17 have the actor `unknown (before 0.17)`. Payloads hold
identifiers, changed field names and versions, never record content. Deleting an
application or forgetting a job removes that record's own history and leaves one
`application_deleted` or `job_forgotten` entry. For one job or application,
`timeline_get` (below) lists the same changes with its notes.

## Notes and the timeline

A note belongs to a job, or to one application of that job when written with
`application_id`: `notes_create(job_id, {"body": "...", "application_id": ...})`.
It records its author and the open run. `pinned: true` pins it; a job and an
application each have one pinned note, listed first, and pinning another unpins
it (`notes_pin(note_id, {"expected_version": N, "pinned": true|false})`). The
application's pinned note is the owner's standing guidance for that application:
read it first, leave it to the owner, and write your own findings as ordinary
notes. `notes_update` edits a body with its version; `notes_delete(note_id,
expected_version)` removes a note for good and leaves a `note_deleted` event.

`timeline_get` reads one list of notes and recorded changes: `job_id` for a job
with all of its applications, or `application_id` for one application with its
job's entries. Each entry has `type` (`note` or `event`), `kind` (`note`,
`event`, or `response` for an employer response recorded, corrected or
removed), `scope` (`job` or `application`), `actor`, `run` and either `note`
(`body`, `version`, `pinned`, `origin`) or `event` (`kind`, a text-free
`payload`, `subject`). Pinned notes come first, then newest first. Filter with
`kinds`, `who` (`owner`, `agent`, `system`, `unknown`), `scope`, `since` and
`until`; `counts` gives the entries of each kind for the other filters; page
with `limit` and `offset`. REST serves the same entries at
`GET /jobs/{id}/timeline` and `GET /applications/{id}/timeline`.

An application's standing guidance is its pinned note: `applications_get`
returns it as `pinned_note`; write it with `notes_create` (`application_id`,
`pinned: true`), `notes_update` and `notes_pin`. A frozen context carries the
pinned note as `application.note` and `instructions.application_note`.

## Scripting and transfers

Read `/api/openapi.json` for REST inputs under `/api/v1`. An MCP tool takes the
record ids of its REST path and the `expected_version` of a delete as flat
arguments and everything else in one `value` (the REST body or query string);
discover the exact schemas. Use optimistic versions on every write and delete,
and an idempotency key on every create you may retry. Omit unchanged PATCH fields; clear text/lists/objects with empty
values. Career dates also accept null to clear them.

`workspace_export` returns readable JSON without file bytes. Scoped
`workspace_backup` and `workspace_restore` move a portable SQLite snapshot
when requested. Restore replaces workspace data while retaining destination
authentication, recent provider request history and later cooldowns.
`workspace_restore`, `tokens_list`, `tokens_create`, `tokens_revoke`,
`owner_password_update`, `requests_create` and `requests_withdraw` need owner authority: an agent token gets
`403 forbidden`. A backup downloaded with an agent token omits the owner
password hash, the session secret and the API tokens, and still restores
completely. Keep transfer
headers, credentials and personal data out of logs and repository examples.
