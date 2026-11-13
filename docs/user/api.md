# REST API

Base path: **`/api/v1`**. The running server exposes interactive reference at
`/api/docs` and schemas at `/api/openapi.json`; those schemas are authoritative
for fields. All normal data operations require an owner session or bearer token.

Create a token in **Settings** and store it outside source control. A token is
an **owner** token (full access) or an **agent** token, which is refused with
`403 forbidden` for the owner password, token management, restore, answering
a question and writing or withdrawing a request (see
[token kinds](agents.md#token-kinds)). `POST /tokens` takes
`{"name": "...", "kind": "agent"}`; `kind` defaults to `agent`. Tokens can be
revoked independently. Browser session writes also need
the `X-CSRF-Token` returned by `/auth/session`; scripts use bearer auth instead.
`POST /auth/logout` revokes every browser session (all signed-in browsers must
sign in again); API/MCP tokens stay valid.

```bash
export OPENINGS_URL=http://127.0.0.1:8080
# Set OPENINGS_TOKEN to the token shown once in Settings.
curl --fail "$OPENINGS_URL/api/v1/jobs?triage=new&limit=50" \
  -H "Authorization: Bearer $OPENINGS_TOKEN"

curl --fail "$OPENINGS_URL/api/v1/jobs" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"title":"Backend engineer","company":"Example Co","posting":"Build Python APIs."}'
```

A URL-only job uses `{"url":"https://…"}` and attempts public page extraction.
Paste the posting when extraction cannot obtain the complete text.

## Operations

| Area | Routes under `/api/v1` |
|---|---|
| Archive | `GET/POST /jobs`, `GET /jobs/resolve`, `GET /jobs/duplicates`, `POST /jobs/bulk`, `GET/PATCH/DELETE /jobs/{id}`, `POST /jobs/{id}/triage`, `/merge`, `/distinct`, `GET/POST /jobs/{id}/notes` |
| Notes and timelines | `GET/PATCH/DELETE /notes/{id}`, `POST /notes/{id}/pin` plus job-owned list/create routes; `GET /jobs/{id}/timeline`, `GET /applications/{id}/timeline` |
| Applications | `GET/POST /applications`, `POST /applications/bulk`, `GET/PATCH/DELETE /applications/{id}`, `GET /applications/{id}/events`, `GET /applications/{id}/staleness`, `GET /staleness` |
| Employer replies | `PATCH /applications/{id}` with `reply`; `GET /insights` |
| Career | `GET/PATCH /career/profile`, CRUD `/career/knowledge` and `/career/claims`, `POST /career/import/preview` then `/career/import` |
| Preferences | `GET /preferences`, `PUT /preferences/{section}`, `PATCH /settings` |
| Templates | CRUD `/templates` |
| Collection | `GET/PATCH /collection`, `GET /providers`, `PATCH /providers/{id}`, CRUD `/sources`, `/sources/schemas`, preview/run, `/sources/bulk`, `/collection/runs` and `GET /collection/yield` |
| Tasks | `GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel` or `/retry` |
| Documents | `GET/POST /contexts`, `GET /contexts/{id}`, `GET/POST /documents`, `GET/DELETE /documents/{id}`, `GET /documents/{id}/comparison` |
| Files | `GET /files`, `GET/DELETE /files/{id}`, `GET /files/{id}/content`, `POST /files/uploads`, `POST /files/{id}/download` |
| Agent activity | `GET /events`; `GET/POST /runs`, `GET/PATCH /runs/{id}`, `POST /runs/{id}/finish`; `GET/POST /questions`, `GET /questions/{id}`, `POST /questions/{id}/answer`, `POST /questions/{id}/withdraw`; `GET/POST /requests`, `GET /requests/{id}`, `POST /requests/{id}/take`, `/complete`, `/decline`, `/withdraw` |
| Skills | `GET /skills`, `GET /skills/{name}`, `GET /skills/{name}/files/{path}`, `GET/PUT /skills/{name}/notes` |
| Operations | `GET /workspace`, `/capabilities`, `/overview`, `/export`, `/backup`; `POST /backup/restore`; `/tokens`; `POST /auth/password` |

Paged list routes take bounded `limit` and `offset` and return `items`, `total`,
`limit` and `offset`. `GET /jobs/{id}/notes`, `/providers`, `/skills` and `/tokens` are bounded by one job, one application or
the installation and return every item with `total`. Job rows include `application_count` and a compact `application`
summary with `id`, `status`, `outcome` and `version`: the open attempt, otherwise
the latest closed attempt, or null. Read detail records for full postings,
questions or answers. `GET /jobs` returns filter value lists in `facets` only
with `include_facets=true` (up to 200 matching companies, locations, sources and
job types each).

Lists return summaries by default and take `summary=false` for full records:

| List | Default `summary=true` | Added by `summary=false` |
|---|---|---|
| `GET /career/knowledge` | Entry fields, bounded `narrative_preview` and `claim_preview`, claim and file counts | `narrative` and `metadata` |
| `GET /career/claims` | Claim fields, the typed selection fields, a bounded `text_preview` and the entry's title and organization | Full `text` and `metadata` |
| `GET /templates` | Name, kind, default flag, version and `file_count` | `tex`, `guidance` and `rules` |
| `GET /documents` | Revision metadata, `revision_number`, `file_count`, `complete` | Readable `text` and `text_from`, form `content`, evidence ids and `files` |
| `GET /sources` | Source settings, outcome/counts, `last_diagnostic_count`, compact `last_run` | `last_diagnostics`, full `last_run` with `source_snapshot` and task payloads/results |
| `GET /collection/runs` | Run state, counts, timing, compact `tasks` (`id`, `kind`, `provider`, `state`, `attempts`, `error`, `next_run_at`, `updated_at`) | `source_snapshot` and full task payloads/results |

`GET /sources/{id}` and `GET /collection/runs/{id}` always return the full record.
Context lists never return payloads: with `summary=true` (the default) they
include frozen job/template labels, evidence/claim counts, a bounded
`note_preview` and file/document counts, and with `summary=false` only the id,
application, signature and time. Files contain metadata only.
Versioned changes include the last read `expected_version`, and every delete
names it as a query parameter, for example
`DELETE /notes/{id}?expected_version=3`; a delete without it is refused with
`422 validation`. A file never changes: its `version` is always 1. Every create accepts an
`idempotency_key`: a retry with the same key and request returns the record the
first request created; the same key with another request returns
`409 conflict`.

Job mutations return the compact job summary used by list rows (with
`posting_preview`, without `posting`, `postings` or `overrides`):
`POST /jobs/{id}/triage` and `PATCH /jobs/{id}`. `PATCH /applications/{id}`
embeds the same compact `job`. The new `version`, `triage` and `application`
fields stay present; read `GET /jobs/{id}` for the full posting.
Application list/detail records include `preparation`: per-kind counts of current
revision leaves (`revisions`) and of complete ones, their PDF stored
(`complete`). A new revision inherits no files. These counts do not certify
content quality or submission. `stale_inputs` lists the input kinds (`profile`, `preferences`,
`template`, `knowledge`, `claim`) that changed after the contexts
of the current leaves were frozen; it is empty when they are current.
`stale_changes` holds the first three changes of the staleness report and
`stale_changes_total` their number.
A version conflict returns HTTP 409 with the stored version, for example
`{"error":{"code":"conflict","message":"…","details":{"current_version":4}}}`;
reload before editing again. This includes settings records (profile,
Preferences sections, settings, collection switch) and per-item errors from
`/jobs/bulk` and `/sources/bulk`. MCP tool errors carry the same `code`, `status`,
`message` and `details` as a JSON `{"error":{…}}` text result, including field
lists for `validation` errors.

To shortlist use `{"expected_version":3,"triage":"shortlisted"}`: it starts the
job's application in stage Shortlisted when it has no open one. `new` returns a
job to review and `dismissed` remembers it outside active review. Leaving
`shortlisted` deletes the application its shortlist started while it is still
empty; otherwise it is refused with 409 `application_has_work`, whose
`details.work` names what exists (for example `documents`, `notes`, `replies`).
Closing an application never changes the job's triage.
A dismissal takes an optional `reason` (at most 500 characters), as does the
`dismissed` action of `POST /jobs/bulk`. Every job read carries `dismissal`
(null unless dismissed): `at`, `by` (the actor), `category` (`agent`, `owner`
or `other`) and `reason`. Restoring a job clears it. Nothing dismisses a job
automatically.

### Ingest signals

Every job carries `signals`, computed without a model when it is collected or
its title or posting changes:

```json
{"computed": true, "language": "de", "language_confidence": 0.93,
 "required": [["de"], ["en", "fr"]], "welcome": ["it"],
 "duplicate_checked": true,
 "duplicate": {"job_id": "EARLIER_JOB_ID", "confidence": 0.91, "tier": "high"},
 "no_longer_listed": false, "unlisted_at": null}
```

`language` is the language the posting is written in (ISO 639-1, or null when
the text is too short or mixed). `required` lists groups of required languages:
one language of a group is enough, so the example needs German and English or
French. `welcome` lists languages described as a plus. `duplicate` names an
earlier job this one likely repeats, from the medium tier up; it is a review
signal and nothing is merged. `POST /jobs/{id}/distinct` with
`{"other_id": "EARLIER_JOB_ID"}` records two different vacancies: the signal
goes and is not computed again for that pair. `no_longer_listed` is set when a full
run of a company board no longer lists the posting (`unlisted_at`), and cleared
when the board lists it again. Signals label and filter jobs; they never
dismiss one. `computed: false` marks a job whose signals are still being computed.

`GET /jobs` filters on them: `signal=likely_duplicate|no_longer_listed|language_required|pending`,
`posting_language=de`, `posting_language_not=en`, `requires=de` (codes or names
such as `German`), `dismissed_by=agent|owner|other` and `sort=dismissed` (most
recently dismissed first). `hide_unspoken_required=true` leaves out jobs whose
required languages are outside the `spoken_languages` setting (a job is left
out when one required group has no spoken language); with `true` or `false`
the response adds `unspoken_required`: `spoken_languages`, the `count` of such
jobs under the other filters and whether they are `hidden`. `include_counts=true` adds
`counts`: jobs of each triage (`all`, `new`, `shortlisted`, `dismissed`) and
`dismissed_by`, for the same filters.

Whether a company board still lists a posting is `signals.no_longer_listed`.

`GET /collection/yield?since=2026-08-01&until=&min_sample=10` returns, per
source (`items`, with `source_id`, `name`, `kind`, `providers` for searches) and
in `total`: `collected`, `to_review`, `shortlisted`, `applied`, `responded`,
`interviews`, `offers`, `dismissed`, `dismissed_by` (`agent`, `owner`,
`other`), `likely_duplicates`, `no_longer_listed` and
`kept_rate` (shortlisted over collected; `null` with `withheld:
"too_few_collected"` below `min_sample`). Each job counts once, for the source that collected it first and
by the time it was added; jobs added by hand or by a removed source have a row
with `source_id: null`.

`POST /applications` starts an application in stage Shortlisted and shortlists
its job; shortlisting the job starts one too. Application stages are
`shortlisted`, `applied`, `interview`, `offer` and `closed`. `GET /jobs?triage=`
takes `new`, `shortlisted`, `dismissed` or `active` (not dismissed); omitting it
searches the full archive. Filters apply before totals, facets and pagination.
Each job permits one
non-Closed attempt. A conflicting creation or reopening returns 409
`application_in_progress` with the active `application_id`; use that attempt or
close it before starting another. Use `idempotency_key` for retries of one creation.
`GET /applications?job_id=JOB_ID` lists the exact job's attempts with pagination.

Ready is computed, never stored: an application is `ready` when it is
Shortlisted, every kind in its `required_documents` (`cv`, `letter`; both by
default, set at creation and editable with `PATCH`) has a current complete
revision, and no blocking requirement is unresolved. Reads and rows return
`ready` and `missing` (for example `["letter", "requirement:REQ_ID"]`).
`stage=shortlisted|ready|applied|interview|offer|closed` filters by stage
(`ready` is the Shortlisted ones that are Ready), and `needs=documents` lists
the Shortlisted ones missing a required document. `stage_counts` include
`ready`, and the overview returns `ready`. `sort=deadline` or `sort=priority`
lists planned attempts first. Rows include `priority`, `deadline`,
`open_requirements` and `blocking_requirements`; the full `requirements` list
is on the single read.
`applied_since` and `applied_until` filter by the time an application was
recorded as applied: `stage=applied&applied_until=2026-10-12` lists the ones
still waiting for a reply since that day. `needs=reply_overdue` lists the
Applied applications without a reply sent longer ago than the no-reply period.
Every list returns `no_reply`: the period in `days`, its `source` (`settings`,
the `no_reply_days` setting, or `default`, 30 days) and how many applications
are `due`. Each row has its `last_reply` (`id`, `kind`, `date`, `count`) and
`concluded_on`.
Create and `PATCH` accept `required_documents`, `priority` (1 highest to 5),
`deadline` (`YYYY-MM-DD`) and `requirements`, a list of
`{id, kind, text, blocking, resolved, note}`.
A requirements patch replaces the whole list; keep existing `id` values. `null`
clears `priority` or `deadline`.

Application changes use `PATCH /applications/{id}` and its `expected_version`.
Mark applied is `{"status": "applied"}`: `applied_at` defaults to now and stays
editable. It is the owner's act; an agent records it only when the owner says
the application was sent. `{"status": "shortlisted"}` undoes it while the
application has no reply, clearing `applied_at`.
Entering Closed requires an explicit outcome: `accepted`, `rejected` (by the
employer), `not_pursued` (stopped by you) or `no_response` (no answer within the
no-reply period; only for a sent application, with `concluded_on`, today by
default). Closing as no reply is always manual, one by one or with
`POST /applications/bulk`; nothing closes automatically.

### Employer replies and insights

A reply records what an employer did about a sent application: `kind`
(`interview`, `rejection`, `offer` or `other`), the `date` it arrived (not in
the future, today by default) and a `note`. `reply` on `PATCH` records it and
moves the stage in the same change: `interview` to Interview (from Applied),
`offer` to Offer, `rejection` closes the application as `rejected`, and `other`
leaves the stage. Do not send `status`, `outcome` or `concluded_on` with it
(422 `reply_stage`).

```json
PATCH /applications/APPLICATION_ID
{"expected_version": 6, "reply": {"kind": "interview", "date": "2026-11-06"}}
```

A reply is refused with 409 `application_not_sent` for an application never
sent, and with 409 `reply_exists` (`details.reply_id`) for a second one of a
kind (other than `other`) on a day. `{"reply": {"id": "REPLY_ID", "date":
"2026-11-05"}}` corrects `kind`, `date` or `note`, and `{"reply": {"id":
"REPLY_ID", "remove": true}}` removes one; neither moves the stage. The
application read lists its `replies` and `last_reply`.

`GET /insights` reports how employers answered the sent applications: `sent`,
`responded`, `interviews` (an interview or offer reply), `offers`,
`rejections`, `no_reply`, `waiting`, the `response_rate`, `interview_rate` and
`offer_rate`, and the `median_days_to_response` (first reply day minus the
`applied_at` day), overall and in `groups` by `role_family`, `seniority`,
`location`, `source_kind`, `source` and `month` applied, plus a
`time_to_response` table. A rate is `null` with `withheld: "too_few_sent"` when
fewer than `min_sample` applications (default 5, 1 to 100) were sent; a median
needs as many dated answers. `applied_since` and `applied_until` narrow the
sample. Shortlisted applications and attempts closed without being sent are
counted in `excluded` (`shortlisted`, `closed_unsent`), never in a rate. Role family and seniority come from the job title
(see [Applications](applications.md#insights)).
Updating `questions` without `answers` preserves compatible existing answers.
Incompatible answers reject the update atomically; explicitly update or remove
only the affected answer when that is intended.

Deletion requires the current `expected_version` query parameter:

```text
DELETE /jobs/JOB_ID?expected_version=3
DELETE /applications/APPLICATION_ID?expected_version=2
```

Forgetting a job removes its identities, documents and application history.
Deleting an application removes that attempt and its contexts/documents/files,
while preserving the job and other attempts; deleting a job's last application
returns the job to `new`. Frozen contexts and complete revisions retain their
content; create a new revision/context for changed input.

The authenticated `/capabilities` list gives the version, the schema, the
caller's `token_kind` and, for each operation, its MCP `name`, its main REST
`method` and `path` (relative to `api_base`) and `access: "owner"` when an agent
token may not call it. OpenAPI and MCP `tools/list` are the full contract. Lists
support server filters; `/jobs/bulk`, `/applications/bulk` and `/sources/bulk`
accept at most 200 versioned items and return per-item outcomes. Application `stage_counts` span all matching
attempts, independent of pagination. Overview accepts `since`/`until` for the
submitted-attempt cohort. Career nonnullable PATCH fields reject explicit null:
omit unchanged fields, or clear text/lists/objects with empty values. Entry dates
are nullable; `dates: null` clears them. See [Career](career.md) for structured
headers, partial dates, skills, ordering and the typed selection fields of a
claim (`default_in_cv`, `role`, `group`), and [Preferences](preferences.md)
for what the owner is looking for, rules out, states as facts and wants in
documents. Template `rules` hold the typed limits (`max_pages`, `max_bullets`,
`max_bullet_chars`) and free keys such as `engine` or `date_format`; writing
rules belong in Preferences, and `rules.statements` is refused.

## Notes and the timeline

A note belongs to a job, or to one of its applications when `application_id` is
given. It records its `author` and, for a token with an open run, that `run`.
`pinned: true` pins it on creation; `POST /notes/{id}/pin` with
`{"expected_version": N, "pinned": true}` pins an existing note and `false`
unpins it. A job and an application each have at most one pinned note: pinning
another one unpins it, with a `note_unpinned` change naming the replacement.

```bash
# A pinned note on an application: its standing guidance.
curl -sS -X POST "$OPENINGS_URL/api/v1/jobs/$JOB/notes" -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "Lead with the platform work.", "application_id": "'"$APPLICATION"'", "pinned": true}'
# The application's notes and changes with its job's, notes and replies only.
curl -sS "$OPENINGS_URL/api/v1/applications/$APPLICATION/timeline?kinds=note&kinds=reply&limit=50" \
  -H "Authorization: Bearer $OPENINGS_TOKEN"
```

`GET /jobs/{id}/timeline` lists the notes and recorded changes of a job and of
all its applications; `GET /applications/{id}/timeline` those of one
application and of its job, not of the job's other applications. Pinned notes
come first, then everything newest first. Each entry has `type` (`note` or
`event`), `kind` (`note`, `event`, or `reply` for an employer reply
recorded, corrected or removed), `scope` (`{"type": "job" | "application",
"id"}`), `actor`, `run` and either `note` (`body`, `version`, `updated_at`,
`pinned`, `pinned_at`) or `event` (`kind`, `payload`, `subject`).
Event payloads hold identifiers, field names and versions, never text; adding
or editing a note is shown by the note itself. Filters: `kinds`, `who` (`owner`
for the dashboard or an owner token, `agent`, `system`, `unknown`), `scope`
(`job` or `application`), `since` and `until`; `counts` gives the entries of
each kind for the other filters; `limit` (at most 200) and `offset` page.
`timeline_get` returns the same entries over MCP.

An application's standing guidance is its pinned note. `GET
/applications/{id}` returns `pinned_note` (the note record, or null); write it
with the notes routes above. `q` on the application list searches the pinned
notes. A frozen context carries the pinned note as `application.note` and
`instructions.application_note`. An application has no `note` field since 0.23:
sending one is refused with `422 validation`.

## Runs, questions and the change log

Each write records its actor: `owner` for the dashboard session, `token` with the
token's id, name and `token_kind` (`owner` or `agent`), or `system`. History entries (`GET /applications/{id}/events`,
`GET /events`, the overview activity) return `actor`, `run_id` and `subject`;
notes return `author` and `run`. Entries from before version 0.17 have
`actor.kind = "unknown"`. A source refresh is an entry only when it changed the
title, company, location or posting text (`job_refreshed`, with the field names);
the `posting_updated` kind of earlier releases no longer exists.

`GET /workspace` and `workspace_info` return `schema_version` (the database
schema of this release) and `storage`: `database_bytes`,
`free_bytes` on the data volume, `restore_limit_bytes` (the largest backup a
restore accepts now), `restore_limit_configured_bytes` (the optional
`OPENINGS_MAX_RESTORE_MB` bound, or null), `retention_days` and
`kept_runs_per_source` ([retention](operations.md#retention)).

Runs need an API token; a dashboard session gets `403 run_actor`.

```bash
# Open a run; later writes with this token are attached to it.
curl -sS -X POST "$OPENINGS_URL/api/v1/runs" -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow": "review-inbox", "scope": "New jobs: 14", "idempotency_key": "review-2026-03-02"}'

# Ask the owner a question about a job.
curl -sS -X POST "$OPENINGS_URL/api/v1/questions" -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Is a hybrid schedule acceptable?", "why": "Two office days are required.",
       "subject_type": "job", "subject_id": "JOB_ID", "choices": ["Yes", "No"]}'

# Close the run with its report (expected_version from the run).
curl -sS -X POST "$OPENINGS_URL/api/v1/runs/RUN_ID/finish" -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expected_version": 1, "summary": "Reviewed 14 jobs.", "changes": "Shortlisted 3, dismissed 9.",
       "not_done": [{"item": "Two postings", "reason": "On-call duty is not stated."}],
       "checks": [{"check": "Final query of New jobs"}, {"check": "Salary ranges", "verified": false}],
       "limits": "Nothing was submitted.", "method": ""}'

# Answers given since a time, oldest first.
curl -sS "$OPENINGS_URL/api/v1/questions?answered_since=2026-03-01T08:00:00Z" \
  -H "Authorization: Bearer $OPENINGS_TOKEN"
```

A second `POST /runs` for a token with an open run returns `409 run_open` with
that run in `error.details.run`, unless `supersede` is true. `PATCH /runs/{id}`
stores a progress `note`. `GET /runs/{id}?changes_limit=50&changes_offset=0`
returns the report, the questions asked and the changes made; `GET /runs` filters
by `status`, `workflow`, `token_id`, `started_since`, `started_until` and
`active_since` (last activity at or after a time: a start, a change or the end).
Each listed run carries `summary` and `method`, the report's account of what the
workflow lacked (empty when none), which the owner may turn into the skill's
[local notes](#skills-and-local-notes).
`GET /questions` filters by `state`, `subject_type`, `subject_id`, `run_id` and
`answered_since`; answer and withdraw take `expected_version`, and answering
needs owner authority (an agent token gets `403 forbidden`). `GET /events`
filters by `run_id`, `job_id`, `application_id`, `subject_type`, `subject_id`,
`actor`, `token_id`, `kind`, `since` and `until`; `subject_types` (repeat the
parameter) takes several kinds of record at once. A change, a question and a
request carry `run_workflow`, the workflow of their run, beside `run_id`.

A question keeps its text, state and a `subject.label` after its job,
application or Career entry is deleted. Deleting an application or forgetting a
job removes that record's own history and leaves one attributed entry.

## Requests for the agent

The owner writes a request; an agent reads it at the start of its next run.

```bash
# The owner (session or owner token) writes a request about a job.
curl -sS -X POST "$OPENINGS_URL/api/v1/requests" -H "Authorization: Bearer $OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Prepare this one too.", "subject_type": "job", "subject_id": "JOB_ID"}'

# The agent reads the open requests, takes one and reports the result.
curl -sS "$OPENINGS_URL/api/v1/requests?state=open" -H "Authorization: Bearer $OPENINGS_TOKEN"
curl -sS -X POST "$OPENINGS_URL/api/v1/requests/REQUEST_ID/take" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" -H "Content-Type: application/json" \
  -d '{"expected_version": 1}'
curl -sS -X POST "$OPENINGS_URL/api/v1/requests/REQUEST_ID/complete" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" -H "Content-Type: application/json" \
  -d '{"expected_version": 2, "result": "CV and letter uploaded; the application is Ready."}'
```

States are `open`, `taken`, `done`, `declined` and `withdrawn`. `take` needs an
open request (`409 request_taken` with the taker's `run_id`, or
`409 request_closed`); `complete` (`result`) and `decline` (`reason`) work from
`open` or `taken`. These three need an API token (`403 request_actor` for a
dashboard session) and record the token's open run on the request, when it has
one. `POST /requests` (`text`, optional `subject_type` and `subject_id`,
`idempotency_key`) and `withdraw` need owner authority. `GET /requests` filters
by `state`, `subject_type`, `subject_id`, `run_id` and `updated_since`.
`GET /workspace` returns `open_requests`, and `GET /runs/{id}` the requests the
run handled. A request keeps its text, state and `subject.label` after its
subject is deleted, and follows a job through a merge.

## Skills and local notes

`GET /skills` lists the shipped skills: `name`, `description`, `files`,
`file_details` (`path`, `bytes` and the first heading as `title` for each file)
and `local_notes` (`version`, `updated_at`, `updated_by`, `length`, or null).
`GET /skills/{name}` reads `SKILL.md`, `GET /skills/{name}/files/{path}` a
reference file. Skills ship with the server and are never edited by a workspace.

A workspace adds **local notes** to a skill instead: at most 2,000 characters,
appended to the served `SKILL.md` (over REST, `skills_get` and the MCP prompt
alike) after a rule, under `## Local notes for this workspace`, with the
version, the day and who wrote them. `?local_notes=false` returns the shipped
text alone; reference files are served as shipped. The response's
`local_notes` describes the current notes without their text.

```bash
# Read the notes with their earlier versions, newest first (version 0: none yet).
curl -sS "$OPENINGS_URL/api/v1/skills/review-inbox/notes" -H "Authorization: Bearer $OPENINGS_TOKEN"

# Replace them, naming the version they replace; empty text clears them.
curl -sS -X PUT "$OPENINGS_URL/api/v1/skills/review-inbox/notes" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" -H "Content-Type: application/json" \
  -d '{"expected_version": 0, "text": "Leave every job at Northstar Labs for the owner."}'
```

The notes return `skill`, `text`, `version`, `max_length`, `updated_at`,
`updated_by`, `versions` (up to 50, each with `version`, `text`, `created_at`
and `created_by`) and `versions_total`. A stale `expected_version` returns
`409 conflict` with `details.current_version`; the same text again is no
change. Each save is a new version with a `skill_notes_updated` change (subject
`skill`). The dashboard session, owner tokens and agent tokens may write notes:
an agent records a lasting method gap of this workspace, and the owner sees who
wrote each version and restores any of them. Personal criteria belong to
[Preferences](preferences.md).

## Identity and duplicates

Both reads are side-effect free; neither fetches a page nor merges records.

```text
GET /jobs/resolve?url=https://jobs.example.test/123&source_key=linkedin:42
GET /jobs/duplicates?triage=shortlisted&limit=20&offset=0
GET /jobs/duplicates?job_id=JOB_ID
GET /jobs/duplicates?min_confidence=0.85
```

`/jobs/resolve` normalizes the URL as ingestion does and returns `items` (job
summaries with `matched_by`, triage and every attempt in `applications`),
`identities` and `identity_conflict`. `/jobs/duplicates` returns candidate
`items` groups, most confident first, with a `total` group count: `job_ids`,
`confidence` (0 to 1), `tier` (`high`, `medium` or `low`), `reasons` (`matched`
and `conflicts` signal names), `signals` (the matched names), `identical_postings`,
`reference_id`, `open_application_ids` and `merge_blocked`, plus per-job
`posting_hash`, advisory `similarity` and the job's own `confidence` and `reasons`
against the reference record. `min_confidence` (default `0.5`) is the lowest
group confidence returned: `0.85` keeps the high tier, `0` adds records that
share only a company and title. The response repeats `min_confidence` and the
`tiers` thresholds. Add `match_location=true` to require agreeing locations.
Signals come from requisition IDs, apply links and ATS posting IDs, posting text,
company, title and location; the
[vacancy identity reference](../../skills/openings-workspace/references/job-deduplication.md)
lists them. Verify a group, then merge with `POST /jobs/{source_id}/merge`;
nothing is merged automatically.

`POST /applications/bulk` closes, reopens or deletes selected attempts:

```json
{"action": "close", "outcome": "not_pursued",
 "items": [{"id": "APPLICATION_ID", "expected_version": 3}]}
```

`reopen` takes `status` (`shortlisted`, `applied`, `interview` or `offer`) and only
applies to Closed attempts; `delete` takes neither field. Closing with
`no_response` applies only to sent attempts; list them first with
`GET /applications?needs=reply_overdue`. Each result item has `ok` and either
`result` or `error`.

## Collection recipes

Read `GET /sources/schemas` for typed defaults and applicable configuration fields.
Each adapter exposes its description mode and `automatic_collection` capability,
and accepts its applicable options. Description retrieval is automatic.
A source's service is fixed after creation. Read its current `version` before a
PATCH, run or DELETE; include it as `expected_version` (a query parameter for
DELETE). A 409 means the source changed since it was read.

A one-off run leaves saved settings unchanged:

```bash
curl --fail "$OPENINGS_URL/api/v1/sources/SOURCE_ID/run" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"expected_version":3,"overrides":{"hours_old":168,"results_wanted":50}}'
```

The returned run groups provider tasks and freezes the effective source settings.
Read `/collection/runs/{id}` for cumulative counts and waiting/processing time;
`POST /collection/runs/{id}/cancel` stops it. Later source edits affect new runs.
Only candidates with usable posting text enter the archive. Pending descriptions
remain in the run checkpoint and appear separately in progress.

Provider policy is shared across every source and manual request. Read
`GET /providers`, then `PATCH /providers/{id}` with the current `expected_version`
and either `enabled` or `min_interval_seconds` (default 5). Recent request counts
are informational; actual provider cooldowns remain effective after edits.

For a shared schedule, send a compatible bulk patch:

```json
{
  "action": "configure",
  "items": [{"id": "SOURCE_ID", "expected_version": 3}],
  "patch": {
    "schedule": {"kind": "daily", "times": ["08:00", "16:00"], "timezone": "Europe/Berlin"}
  }
}
```

`POST /sources/bulk` returns per-source outcomes. Omitted configuration keys remain
unchanged. Omitted filter keys are preserved; an explicit empty list clears that
filter. `schedule` replaces the whole schedule variant. Inspect failures before
retrying. [Collection](sources.md) defines the
settings, defaults, run counters and request pacing.

## Document and byte flow

1. `POST /contexts` with `application_id` and optional `template_id`/`template_ids`,
   evidence/claim IDs, note and `idempotency_key`. The context freezes the selected
   profile, evidence, Preferences, template guidance, questions and template
   assets.
2. `POST /documents` with `application_id`, `context_id`, `kind`, `title`, the
   evidence it uses (`claim_ids`, `knowledge_ids`) and an optional `note`. Kinds:
   `cv`, `letter`, `answers`, `other`. A CV or letter is a required PDF and an
   optional `.tex` source and takes no `content` (`422 content_not_accepted`):
   give `pdf` (`name`, `size`, optional `sha256`) and optionally the source
   inline as `source` (UTF-8, at most 256 KB) or as `source_file` (`name`,
   `size`, optional `sha256`). Form answers and `other` keep structured
   `content`. Use `previous_id` for a new revision. New revisions inherit no old
   PDF/files.
3. The response's `uploads` holds one-shot grants: `pdf`, and `source` for a
   `source_file`. Send the source first, then the PDF; the PDF grant already
   names the source's SHA-256. `POST /files/uploads` still reserves other
   uploads with `owner_type`, `owner_id`, relative `name`, `media_type`, exact
   `size` in bytes and optional hex `sha256`. File owners are `knowledge`,
   `template`, `document` or `job`; frozen context assets are read-only.
4. Resolve each returned relative `url` against the workspace origin and send raw
   bytes with its returned `method` and `headers`. This scoped transfer needs no
   owner bearer token. SHA-256 is always computed server-side. Files are limited
   to 20 MiB; grants expire after ten minutes.
5. A CV or letter revision is incomplete until its PDF is stored, then complete
   and immutable (`409 revision_complete` for any further file); a change is a
   new revision with `previous_id`. Only complete revisions count toward Ready.
   Read the document and its files to verify them.

### Source, PDF and readable text

A CV or letter revision has one PDF and at most one `.tex` source (a file is a
source by a `.tex`/`.ltx` name or a TeX media type). With a source, the PDF
reservation names the source it was built from; a PDF-only revision has no
source hash:

```json
{"owner_type": "document", "owner_id": "DOCUMENT_ID", "name": "cv.pdf",
 "media_type": "application/pdf", "size": 48213, "source_sha256": "SHA256_OF_CV_TEX"}
```

| Refusal | When |
|---|---|
| `422 source_sha256_required` | A PDF without `source_sha256` for a revision with a source |
| `409 source_required` | The PDF names a source the revision does not have yet |
| `409 source_mismatch` | `source_sha256` is not the revision's source |
| `409 source_exists`, `409 pdf_exists` | A second source or PDF; create a new revision |
| `422 source_encoding` | A source that is not UTF-8 |
| `422 pdf_media_type` | A `.pdf` sent with another media type |

The file record returns `source_sha256` (null for every other file and for PDFs
uploaded before 0.22). When there is a source the server derives the revision's
`text` from it (`text_from: "tex"`), as a reader sees it in the PDF: the document body with macros the source
defines expanded; the personal data, entries, openings and closings of moderncv,
`letter` and `scrlttr2` printed where the class prints them; link text without
the address; comments, settings and markup removed; accents composed; and the
breaks TeX makes (paragraphs, `\\`, items, headings) kept as lines. An unknown
command contributes the text of its arguments. No TeX runtime is used. Without
a source, the text is extracted from the PDF with a pure-Python reader
(`text_from: "pdf"`); when extraction fails the revision has no text and is
still complete. The text is for search and comparison; the PDF is the document.
`GET /documents/{id}` returns `complete`, `text`, `text_from`, `source_sha256`, `claim_ids`,
`knowledge_ids`, `note`, `files` and `legacy_content` (the content a CV or
letter stored before 0.22, read-only, else null); form answers also return
`content`. `GET /documents?q=` searches titles, notes and the readable text.

`GET /documents/{id}/comparison` (MCP `documents_compare`) compares a revision's
text with the revision it replaces, or with `other_id` of the same application,
line by line: `lines` of `{"change": "same" | "added" | "removed", "text"}`,
the `added` and `removed` counts, and `text.document`/`text.other`, false for a
side without text (a CV or letter whose text could not be read). Form answers compare their
content as `path: value` lines.

### Stale contexts

A context prepared since 0.24 contains `preferences`: each section with its
`version` and `items`. Earlier contexts are unchanged.

Contexts record the inputs they froze: each selected template, Career entry and
claim with its version, and a short hash of each Profile part, each Preferences
statement and the content of each template, entry and claim.
`GET /applications/{id}/staleness` compares them with the current records for
each current revision leaf and returns `stale`, `inputs`, `changes` and
per-document status (`current`, `stale` or `no_context`) with that document's
`changes` and `comparison`.

Only what documents use is compared:

- **Profile:** the parts `name`, `headline`, `contact` (email, phone, location),
  `links` and `summary`. `metadata` is frozen too but never makes a document
  stale: rules and facts belong in Preferences. (Contexts frozen before 0.23
  also hold the Profile's `preferences` and `roles`; they are not compared.)
- **Preferences:** the statements of `facts` and `writing`, by content (text
  and scope). The other sections and the order of statements are not compared.
  A writing rule scoped to `cv` concerns the CV only, one scoped to `letter`
  the letter only.
- **Templates, entries and claims:** by the content documents
  use: a template's kind, source, guidance and rules; an
  entry's kind, title, organization, dates, skills and narrative; a claim's text
  and entry. A new version that only changes a name, a position, the default
  flag, a claim's selection fields (`default_in_cv`, `role`, `group`) or
  free-form `metadata` keeps documents current, and so does a change undone. A
  claim that is no longer approved still counts. Entries and claims the context
  did not freeze are ignored.
- Text is compared with its runs of whitespace made single spaces, except a
  template's source.

A change has `input` (`profile`, `preferences`, `template`, `knowledge` or
`claim`), `id` (the Profile part, `<section>:<hash>` for a statement, or the
record), `label`, `state`, `frozen_version` and `current_version`; a
Preferences change also has its `section`, its label is the statement's text
and its versions are the section's. States: `changed`, `deleted` and
`unapproved` for records; `added` and `removed` for statements (an edited
statement is removed and added).

`comparison` says what a document's context allowed: `profile` is `parts`, or
`whole` when the frozen payload could not be read part by part (`id` is then
null and the Profile version is compared); `preferences` is `items`, or
`not_frozen` for a context prepared before 0.24, which is not compared for it.

`GET /staleness` lists such reports across applications: `status` defaults to
`shortlisted` (`all` for every stage), `stale_only` defaults to `true`,
with `limit`/`offset`. These reads never change a context. To refresh an
application, prepare a new context and save new revisions linked with `previous_id`.

For direct downloads, authenticated `GET /files/{id}/content` supports PDF/image
preview. External agents can reserve a scoped download via `POST /files/{id}/download`.
Transfer URLs contain no secret; keep the returned headers private. The returned
file metadata records exact bytes and ownership.

Structured evidence references and supported bullet/answer limits are validated
against the frozen context. PDF page targets and factual accuracy still require
external/human review. Archiving an `answers` document does not change the live
application answers: update `PATCH /applications/{id}` explicitly for that.
