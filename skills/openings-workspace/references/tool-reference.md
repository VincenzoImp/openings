# Tool-level reference

Step-by-step MCP/REST sequences behind the workflow skills: [Prepare Shortlist](../../prepare-shortlist/SKILL.md) for documents, [Manage sources](../../manage-sources/SKILL.md) for collection.

## Documents

1. Find and read the job with `jobs_list` and `jobs_get`. Before ingesting a
   URL, `jobs_resolve` reports any existing record and its attempts without
   writing; `jobs_duplicates` lists candidate copies of the same vacancy with a
   `confidence`, `tier` and `reasons` (`min_confidence` defaults to 0.5). A job's `application`
   summary identifies an open attempt or the latest closed one. Use
   `applications_list` with `value.job_id` for the full history. Continue an open
   attempt (shortlisting a job starts one in stage Shortlisted), or start one
   with `applications_create` and an idempotency key, which also shortlists the
   job. A separate later attempt requires the previous one to be closed. Retain the attempt ID for subsequent writes.
2. Read the live records: `applications_get` (with its `pinned_note`),
   `jobs_get`, `profile_get`, `preferences_get`, detailed Career entries
   (`knowledge_list`), approved claims with their typed selection fields
   (`claims_list`) and the selected templates (`templates_list`,
   `templates_get`). Summary lists help discovery; fetch the full records
   before writing. Ask for missing facts and keep qualifications accurate.
3. Select the templates, entries and claims the documents will use. Select
   claims only from selected entries.
4. Write CV, letter and answers from those records. Approved claims provide
   reusable wording; detailed evidence can support accurate new wording. Follow
   the Writing rules and facts, template guidance, the pinned note and answer
   limits.
5. Download template assets through `files_reserve_download`, resolving relative
   URLs against the workspace origin. Compile externally and check page count,
   extracted text and layout. If a compiler is unavailable, report the missing
   PDF: a revision without its PDF stays incomplete.
6. Create the revision with `documents_create` once its PDF has passed the
   checks, keeping application ownership and citing `claim_ids` and
   `knowledge_ids`. A CV or letter takes no `content`: give `pdf` (safe relative
   name, exact size, optional SHA-256) and, optionally, the TeX source inline as
   `source` or as `source_file`. PUT the raw bytes to each returned `uploads`
   grant with its headers, the source first; verify the stored files and read
   the revision's `text` and `text_from`. Binary bodies do not belong in MCP
   arguments.
7. An answers document archives a revision. Update the application's live
   `answers` separately with `applications_update`, current `expected_version`
   and question IDs. Leave progress unchanged unless requested.

A PDF does not record submission. A revision is complete and immutable once its
PDF is stored; a change needs a new revision using `previous_id` and its own
files; `documents_compare` shows what changed. Read the records again when
updated source knowledge is needed.

Application list/detail `preparation` counts describe current revision leaves
and how many are complete; with `ready` and `missing` they are not a submission
or quality guarantee. Read the exact document/files before relying on them. Updating questions preserves compatible live answers; incompatible
answers reject the update unless deliberately changed or removed in `answers`.

## Preferences

`preferences_get` returns the owner's Preferences, in their own words: five
sections, `looking_for` (what I'm looking for), `ruled_out` (what I rule out),
`facts` (facts about me), `writing` (writing rules) and `working_with_me`
(instructions you follow), each with `items`, `version`, `updated_at` and
`updated_by`; and `settings` with `no_reply_days`, `spoken_languages` and their
`version`. Nothing in them acts automatically: read them and apply them.

- `preferences_update(section, {expected_version, items})` replaces the whole
  section: read it, edit the list and write it back with the version you read.
  Items are `{text}` (plain text, Markdown allowed, at most 2,000 characters,
  at most 200 per section) and, in `writing`, `{text, scope}` with scope `all`,
  `cv` or `letter`. A stale version is `409 conflict` with
  `details.current_version`: read again and merge. Keep the owner's wording;
  add or change only what the owner asked for or confirmed.
- `settings_update({expected_version, no_reply_days?, spoken_languages?})`
  changes the no-reply period (1-365 days, default 30) or the spoken languages
  (ISO 639-1 codes).
- Removed in 0.24: the former policy and instructions tools return
  `tool_removed` with a hint. General instructions and template rule statements
  are Writing rules now.

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

`sources_list` gives each source `counts`: the jobs it found (each once) and
how many were shortlisted, applied to and got a reply. Use them to tune sources
(manage-sources).

Every job has `signals` computed at collection without a model: `language`,
the languages it states as `required` (groups, one of a group suffices), a likely `duplicate` of an earlier job with its confidence, and
`no_longer_listed` (a company board stopped listing it; `unlisted_at` on the
observation). Signals are labels and filters; nothing dismisses a job
automatically. `jobs_list` filters by `signal`, `posting_language`,
`posting_language_not`, `requires` and `dismissed_by`, and
`include_counts` returns `counts`: `all`, `new`, `shortlisted`, `dismissed` and
`dismissed_by`. `hide_unspoken_required: true`
leaves out jobs whose required languages are outside the owner's
`spoken_languages`; with true or false the result has `unspoken_required`
(`spoken_languages`, `count`, `hidden`). A dismissed job has `dismissal`: who,
when, why (`reason`) and its `category` (`agent`, `owner` or `other`).
`jobs_distinct(job_id, {other_id})` records that a likely duplicate is a
different vacancy. Whether a board still lists a posting is
`signals.no_longer_listed`.

Use `jobs_list` with `value.triage="new"` to review new jobs and
`jobs_triage` / `jobs_bulk` to shortlist or dismiss selected versioned jobs. Read
full postings and the user's career/preferences to make a qualitative selection.
Shortlisting starts the job's application in stage Shortlisted when it has no
open one; `value.triage="shortlisted"` lists those jobs. Moving a job back to
`new` or `dismissed` deletes that application only while it is empty, otherwise
`409 application_has_work` with `details.work`. Closing an application never
changes the job's triage. Dismiss remembers the job during future collection. Forget deletes
job-owned history, documents, files and identities when permanent removal is
intended. `jobs_delete` requires `job_id` and the current `expected_version`.

Applications progress through Shortlisted / Applied / Interview / Offer / Closed.
Closing requires an explicit outcome. Creation or reopening cannot introduce a
second open attempt; use the application identified by a conflict. Deleting an
attempt preserves its job and other attempts; `applications_delete` requires
`application_id` and the current `expected_version`. Deleting the final attempt
returns the job to New; only use this deliberately.
`applications_bulk` applies one action to at most 200 explicit
`{id, expected_version}` items: `close` with `outcome`, `reopen` with a non-Closed
`status` or `delete`. Each item reports `ok` with a result or an error (code,
status, message, details); reopening respects the one-open-attempt rule and only
applies to Closed attempts. Bulk forget and delete collect orphaned file bytes once
per call. To stop preparation
and preserve its documents, close it with `not_pursued`. Restore known workaround
dismissals explicitly, using current versions: to `new`, or to `shortlisted`,
which starts an application when the job has no open one.

## Ready

Ready is computed, never stored or marked: an application is `ready` when it is
Shortlisted, every kind in its `required_documents` (`cv`, `letter`; both by
default, set at creation and editable with `applications_update`) has a current
complete revision, and no blocking requirement is unresolved. Reads and list
rows return `ready` and `missing` (`cv`, `letter`, `requirement:<id>`).
`applications_list` filters by `stage` (`shortlisted`, `ready`, `applied`,
`interview`, `offer`, `closed`; `ready` is the Shortlisted ones that are Ready)
and `needs` (`documents`: Shortlisted and missing a required document;
`reply_overdue`), and its `stage_counts` include `ready`. `applied_since` and
`applied_until` filter by the time an application was recorded as applied.

Mark applied is the owner's act: `applications_update` with `status: "applied"`
(`applied_at` defaults to now and stays editable) only when the owner says they
sent the application. `status: "shortlisted"` undoes it while no reply exists.

## Employer replies, no reply and stats

`applications_update` with `reply: {kind, date?, note?}` records an employer
reply the owner reported on a sent application (`409 application_not_sent`
otherwise). `kind` is `interview`, `rejection`, `offer` or `other`; `date` (not
in the future) defaults to today. The same change moves the stage: `interview`
to Interview, `offer` to Offer, `rejection` closes as `rejected`; `other` never
moves it. Do not pass `status`, `outcome` or `concluded_on` with it
(`422 reply_stage`). One reply per kind and day (except `other`) returns
`409 reply_exists` with `details.reply_id`. `reply: {id, kind?, date?, note?}`
corrects a reply and `reply: {id, remove: true}` removes one; corrections never
move the stage. `applications_get` returns `replies` and `last_reply`; list rows
carry `last_reply`.

Closing with `outcome: "no_response"` needs a sent application and takes
`concluded_on` (default today); it is always a manual act, single or with
`applications_bulk`, and nothing closes automatically.
`applications_list` with `needs: "reply_overdue"` lists Applied applications
without a reply sent before the no-reply cutoff; every list result
has `no_reply` with `days`, `source` (`settings` or `default`) and `due`. The
period comes from the setting `no_reply_days`, else 30.

`stats_get(period)` / `GET /stats` takes `period` (`90d`, `12m` or `all`). It
returns `applied`, `replied`, `reply_rate`, `interviews`, `interview_rate`,
`median_days_to_reply`, the `funnel` (applied, replied, interview, offer) and
`by_source` (replies per source, `null` unless two sources have five sent
applications each). `insights_get`, `overview_get` and `sources_yield` were
removed in 0.24 and answer `tool_removed`.

## Skills and the change log

`skills_get(name)` returns the shipped `SKILL.md`; reference files are served as
shipped. The owner's standing instructions for the agent live in Preferences ›
Working with me (`preferences_get`, section `working_with_me`).

`events_list` reads the change log, newest first, by `job_id`,
`application_id`, `subject_type`/`subject_id`, `actor` (`owner`, `agent`,
`system`, `unknown` or `agent:<token name>`), `batch_id`, `kind`, `since` and
`until`; `subject_types` takes several kinds of record at once. System changes
(collection, worker, upgrade) are left out unless `actor` is `system` or
`include_system` is true. Every entry carries `actor`, a label (`owner`,
`agent:<token name>` or `system`), `batch_id`, shared by every change of one REST
request or MCP tool call, and `subject`; `applications_history` returns the same
fields. Changes recorded before version 0.17 have a null actor. Payloads hold
identifiers, changed field names and versions, never record content. Deleting an
application or forgetting a job removes that record's own history and leaves one
`application_deleted` or `job_forgotten` entry. For one job or application,
`timeline_get` (below) lists the same changes with its notes.

## Notes and the timeline

A note belongs to a job, or to one application of that job when written with
`application_id`: `notes_create(job_id, {"body": "...", "application_id": ...})`.
It records its author as an actor label. `pinned: true` pins it; a job and an
application each have one pinned note, listed first, and pinning another unpins
it (`notes_pin(note_id, {"expected_version": N, "pinned": true|false})`). The
application's pinned note is the owner's standing guidance for that application:
read it first, leave it to the owner, and write your own findings as ordinary
notes. `notes_update` edits a body with its version; `notes_delete(note_id,
expected_version)` removes a note for good and leaves a `note_deleted` event.

`timeline_get` reads one list of notes and recorded changes: `job_id` for a job
with all of its applications, or `application_id` for one application with its
job's entries. Each entry has `type` (`note` or `event`), `kind` (`note`,
`event`, or `reply` for an employer reply recorded, corrected or
removed), `scope` (`job` or `application`), `actor`, `batch_id` and either `note`
(`body`, `version`, `pinned`) or `event` (`kind`, a text-free
`payload`, `subject`). Pinned notes come first, then newest first. Filter with
`kinds`, `who` (`owner`, `agent`, `system`, `unknown`), `scope`, `since` and
`until`; `counts` gives the entries of each kind for the other filters; page
with `limit` and `offset`. REST serves the same entries at
`GET /jobs/{id}/timeline` and `GET /applications/{id}/timeline`.

An application's standing guidance is its pinned note: `applications_get`
returns it as `pinned_note`; write it with `notes_create` (`application_id`,
`pinned: true`), `notes_update` and `notes_pin`.

## Scripting and transfers

Read `/api/openapi.json` for REST inputs under `/api/v1`. An MCP tool takes the
record ids of its REST path and the fields of the REST body or query string as
flat arguments with the same names; discover the exact schemas. Use optimistic versions on every write and delete,
and an idempotency key on every create you may retry. Omit unchanged PATCH fields; clear text/lists/objects with empty
values. Career dates also accept null to clear them.

`workspace_export` returns readable JSON without file bytes, and scoped
`workspace_backup` a portable SQLite snapshot, when requested. Restoring a
backup, API tokens and the owner password are the owner's: they are REST
routes for the dashboard or an owner token, not MCP tools. A backup downloaded with an agent token omits the owner
password hash, the session secret and the API tokens, and still restores
completely. Keep transfer
headers, credentials and personal data out of logs and repository examples.
