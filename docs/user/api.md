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
curl --fail "$OPENINGS_URL/api/v1/jobs?triage=inbox&limit=50" \
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
| Collection | `GET/PATCH /collection`, `GET /providers`, `PATCH /providers/{id}`, CRUD `/sources`, preview/run and `/sources/bulk` |
| Scoring/tasks | `GET/PATCH /scoring`, `POST /scoring/test`, `/scoring/rescore`, `GET /scoring/context/{job_id}`, `GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel` or `/retry` |
| Documents | `GET/POST /contexts`, `GET /contexts/{id}`, `GET/POST /documents`, `GET/DELETE /documents/{id}`, `POST /documents/{id}/review` |
| Files | `GET /files`, `GET/DELETE /files/{id}`, `GET /files/{id}/content`, `POST /files/uploads`, `POST /files/{id}/download` |
| Operations | `GET /workspace`, `/capabilities`, `/overview`, `/export`, `/backup`; `POST /backup/restore`; `/tokens`; `POST /auth/password` |

List routes return `{items,total}` and accept bounded `limit`/`offset` where
applicable. Job/application rows are compact: request a detail record before using
full posting, questions or answers. Career/claims/templates/documents offer
`summary=true` for bounded previews/counts without narratives, metadata, TeX or
structured content. Context lists never return payloads; files contain metadata only.
Versioned changes include the last read `expected_version`.
A conflict returns HTTP 409; reload before editing again. A typical error is
`{"error":{"code":"conflict","message":"…","details":null}}`.

For triage use `{"expected_version":3,"triage":"saved"}`. Application status
changes use `PATCH /applications/{id}` with its version and a status/outcome.
`DELETE /jobs/{id}` means permanent Forget, including its documents/history.
`DELETE /applications/{id}` removes one attempt and its contexts/documents/files
while preserving the job and other attempts. Frozen contexts and approved revisions
have no mutable content interface; create a new revision/context as appropriate.

The authenticated `/capabilities` inventory maps all logical operations to REST,
MCP and dashboard locations, with explicit bootstrap/transport exceptions. Lists
support server filters; `/jobs/bulk` and `/sources/bulk` accept at most 200 versioned
items and return per-item outcomes. Application `stage_counts` span all matching
attempts, independent of pagination. Overview accepts `since`/`until` for the
submitted-attempt cohort. Career nonnullable PATCH fields reject explicit null:
omit unchanged fields, or clear text/lists/objects with empty values.

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
5. Review `POST /documents/{id}/review` with `{"review_state":"approved"}`.
   Approved revisions reject added files. Changed content belongs in a new revision.

For direct downloads, authenticated `GET /files/{id}/content` supports PDF/image
preview. External agents can reserve a scoped download via `POST /files/{id}/download`.
Transfer URLs contain no secret; keep the returned headers private. The returned
file metadata records exact bytes and ownership.

Structured evidence references and supported bullet/answer limits are validated
against the frozen context. PDF page targets and factual accuracy still require
external/human review. Archiving an `answers` document does not change the live
application answers: update `PATCH /applications/{id}` explicitly for that.
