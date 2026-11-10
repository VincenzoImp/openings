# REST API

Base path: **`/api/v1`**. The running server exposes interactive reference at
`/api/docs` and schemas at `/api/openapi.json`; those schemas are authoritative
for fields. All normal data operations require an owner session or bearer token.

Create a token in **Settings** and store it outside source control. Tokens grant
owner access and can be revoked independently. Browser session writes also need
the `X-CSRF-Token` returned by `/auth/session`; scripts use bearer auth instead.

```bash
export OPENINGS_URL=http://127.0.0.1:8080
# Set OPENINGS_TOKEN to the token shown once in Settings.
curl --fail "$OPENINGS_URL/api/v1/jobs?queue=inbox&limit=50" \
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
| Archive | `GET/POST /jobs`, `POST /jobs/bulk`, `GET/PATCH/DELETE /jobs/{id}`, `POST /jobs/{id}/triage`, `/merge`, `GET/POST /jobs/{id}/notes` |
| Notes | `GET/PATCH/DELETE /notes/{id}` plus job-owned list/create routes |
| Applications | `GET/POST /applications`, `GET/PATCH/DELETE /applications/{id}`, `GET /applications/{id}/events` |
| Career | `GET/PATCH /career/profile`, CRUD `/career/knowledge` and `/career/claims`, `POST /career/import/preview` then `/career/import` |
| Templates/guidance | CRUD `/templates`, `GET/PATCH /instructions` |
| Collection | `GET/PATCH /collection`, `GET /providers`, `PATCH /providers/{id}`, CRUD `/sources`, `/sources/schemas`, preview/run, `/sources/bulk` and `/collection/runs` |
| Tasks | `GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel` or `/retry` |
| Documents | `GET/POST /contexts`, `GET /contexts/{id}`, `GET/POST /documents`, `GET/DELETE /documents/{id}`, `POST /documents/{id}/review` |
| Files | `GET /files`, `GET/DELETE /files/{id}`, `GET /files/{id}/content`, `POST /files/uploads`, `POST /files/{id}/download` |
| Operations | `GET /workspace`, `/capabilities`, `/overview`, `/export`, `/backup`; `POST /backup/restore`; `/tokens`; `POST /auth/password` |

List routes return `{items,total}` and accept bounded `limit`/`offset` where
applicable. Job rows include `application_count` and a compact `application`
summary with `id`, `status`, `outcome` and `version`: the open attempt, otherwise
the latest closed attempt, or null. Read detail records for full postings,
questions or answers. Career/claims/templates/documents offer
`summary=true` for bounded previews/counts without narratives, metadata, TeX or
structured content. Context lists never return payloads; files contain metadata only.
Versioned changes include the last read `expected_version`.
Application list/detail records include `preparation`: per-kind counts of current
revision leaves (`revisions`), leaves with their own PDF (`pdf`) and leaves with
an approved PDF (`approved`). A new revision inherits neither files nor approval.
These counts do not certify content quality, required document completeness or
submission. Context lists with `summary=true` include frozen job/template labels,
evidence/claim counts and a bounded `note_preview`, alongside file/document counts.
A version conflict returns HTTP 409 with the stored version, for example
`{"error":{"code":"conflict","message":"…","details":{"current_version":4}}}`;
reload before editing again. MCP tool errors carry the same `code`, `status`,
`message` and `details` as a JSON `{"error":{…}}` text result, including field
lists for `validation` errors.

For Shortlist use `{"expected_version":3,"triage":"saved"}`; `inbox` returns a
job without attempts to review and `dismissed` remembers it outside active review.

Creating an application retains saved interest and starts Preparing (`draft`).
Use `queue=inbox` / `shortlist` for jobs without any application attempts;
`queue=applications` includes all jobs with attempts, even Closed or dismissed.
Omitting `queue` searches the full archive. `triage=saved` remains an inclusive
interest filter. Queue predicates apply before totals, facets and pagination.
Each job permits one
non-Closed attempt. A conflicting creation or reopening returns 409
`application_in_progress` with the active `application_id`; use that attempt or
close it before starting another. Use `idempotency_key` for retries of one creation.
`GET /applications?job_id=JOB_ID` lists the exact job's attempts with pagination.
`readiness=none|missing_pdf|unreviewed|blocked|ready` filters by the derived
preparation state, and `sort=deadline` or `sort=priority` lists planned attempts
first. Rows include `priority`, `deadline`, `readiness`, `open_requirements` and
`blocking_requirements`; the full `requirements` list is on the single read.
Create and `PATCH` accept `priority` (1 highest to 5), `deadline` (`YYYY-MM-DD`)
and `requirements`, a list of `{id, kind, text, blocking, resolved, note}`.
A requirements patch replaces the whole list; keep existing `id` values. `null`
clears `priority` or `deadline`.

Application changes use `PATCH /applications/{id}` and its `expected_version`.
Entering Closed requires an explicit outcome: `accepted`, `rejected` or
`not_pursued`. Send `applied_at: null` to clear the submission date.
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
while preserving the job and other attempts. Frozen contexts and approved
revisions retain their content; create a new revision/context for changed input.

The authenticated `/capabilities` inventory maps all logical operations to REST,
MCP and dashboard locations, with explicit bootstrap/transport exceptions. Lists
support server filters; `/jobs/bulk` and `/sources/bulk` accept at most 200 versioned
items and return per-item outcomes. Application `stage_counts` span all matching
attempts, independent of pagination. Overview accepts `since`/`until` for the
submitted-attempt cohort. Career nonnullable PATCH fields reject explicit null:
omit unchanged fields, or clear text/lists/objects with empty values. Entry dates
are nullable; `dates: null` clears them. See [Career](career.md) for structured
headers, partial dates, skills and ordering.

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
   profile, evidence, instructions, questions and template assets.
2. `POST /documents` with `application_id`, `context_id`, `kind`, `title` and
   structured `content`. Kinds: `resume`, `cover_letter`, `answers`, `other`.
   Use `previous_id` for a new revision. New revisions inherit no old PDF/files.
3. Reserve `POST /files/uploads` with `owner_type`, `owner_id`, relative `name`,
   `media_type`, exact `size` in bytes and optional hex `sha256`. File owners are
   `knowledge`, `template`, `document` or `job`; frozen context assets are read-only.
4. Resolve the returned relative `url` against the workspace origin and send raw
   bytes with its returned `method` and `headers`. This scoped transfer needs no
   owner bearer token. SHA-256 is always computed server-side. Files are limited
   to 20 MiB; grants expire after ten minutes.
5. Read the document and its files, then review `POST /documents/{id}/review` with
   `{"review_state":"approved","expected_version":3}`, using the version just read.
   An attachment change invalidates that version. Reload and review the current
   files before retrying a conflict. Approved revisions reject added files.
   Changed content belongs in a new revision.

For direct downloads, authenticated `GET /files/{id}/content` supports PDF/image
preview. External agents can reserve a scoped download via `POST /files/{id}/download`.
Transfer URLs contain no secret; keep the returned headers private. The returned
file metadata records exact bytes and ownership.

Structured evidence references and supported bullet/answer limits are validated
against the frozen context. PDF page targets and factual accuracy still require
external/human review. Archiving an `answers` document does not change the live
application answers: update `PATCH /applications/{id}` explicitly for that.
