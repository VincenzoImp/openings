# REST API

Base path: `/api/v1`. The server describes every operation, field and error: read
`/api/docs` (interactive) and `/api/openapi.json` (the schema) on your own
installation. They are the reference; this page covers only what they do not.
Without a server, `uv run python -m openings.openapi` prints the schema.

The dashboard, REST and MCP use the same operations. `operationId` in OpenAPI is
the MCP tool name, and `x-openings-access: owner` marks the owner-only routes,
which are not MCP tools. `GET /api/v1/capabilities` (authenticated) lists each
operation's MCP name, route and access.

## Authentication

Create a token in **Settings › API & agents** and keep it outside source control.
Send it as `Authorization: Bearer <token>`. Revoke it independently of any other.

| Kind | Can do |
|---|---|
| `agent` (the default) | Everything except owner-only operations |
| `owner` | Everything, like your dashboard session |

An agent token is refused with `403 forbidden` for the owner password, API tokens,
restore, the records export, the career import and kept backups. `POST /tokens`
takes `{"name": "...", "kind": "agent"}`. Browser sessions are for the dashboard:
their writes need the `X-CSRF-Token` from `GET /auth/session`; scripts use a token.

```bash
export OPENINGS_URL=http://127.0.0.1:8080
export OPENINGS_TOKEN=...   # shown once in Settings
curl --fail "$OPENINGS_URL/api/v1/jobs?triage=new&limit=50" \
  -H "Authorization: Bearer $OPENINGS_TOKEN"

curl --fail "$OPENINGS_URL/api/v1/jobs" \
  -H "Authorization: Bearer $OPENINGS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"title":"Backend engineer","company":"Example Co","posting":"Build Python APIs."}'
```

## Lists and summaries

A paged list takes `limit` and `offset` and returns `items`, `total`, `limit` and
`offset`. Lists return summaries (previews, counts) by default; read one record, or
pass `summary=false`, for full text.

## Versions and idempotency

Every record that can change has a `version`. A change names the version you read
as `expected_version`, and every permanent delete does too, as a query parameter:
`DELETE /notes/{id}?expected_version=3`. A stale version fails with `409 conflict`
and `details.current_version`; read again and apply your change to the new record.
Files never change: their version is always 1.

Every create accepts an `idempotency_key` (up to 200 characters). A retry with the
same key and request returns the record the first one created; the same key with a
different request returns `409 conflict`.

## Errors

Every error has one shape, the `Error` model:

```json
{"error": {"code": "conflict", "status": 409, "message": "...", "details": {"current_version": 4, "id": "..."}}}
```

`code` is stable; `message` is for people. MCP tool errors carry the same body as
text. Common codes:

| Status | Code | Meaning |
|---|---|---|
| 401 | `unauthorized` | No or invalid token |
| 403 | `forbidden` | The token's kind may not do this |
| 404 | `not_found` | No such record |
| 409 | `conflict` | A stale version; see `details.current_version` |
| 409 | `application_in_progress` | The job already has an open application (`details.application_id`) |
| 409 | `application_has_work` | The shortlist cannot be undone: the application holds work (`details.work`) |
| 409 | `revision_complete` | A complete revision takes no more files |
| 413 | `file_size`, `backup_size` | Too large |
| 422 | `validation` | Invalid fields; `details` lists them |

Others name a specific rule, for example `application_not_sent` or `reply_exists`.

## Batches

Operations that change many records take `items` and apply each on its own: there
is no transaction across items. A call returns one `BatchResult`:

```json
{"batch_id": "b_...", "total": 2, "succeeded": 1, "failed": 1,
 "items": [{"index": 0, "ok": true, "id": "...", "version": 5},
           {"index": 1, "ok": false, "error": {"code": "conflict", "status": 409, "message": "..."}}]}
```

Check every item's `ok`. A batch read takes `ids` and returns `items` and the ids
it did not find. Each batch operation states its item limit in OpenAPI (for
example 200 jobs to triage). Every change one call writes shares its `batch_id`,
which `GET /changes` can filter on. Triage, stage changes and replies take no
version: they are reversible and guarded by rules, and a conflict names the rule.

## Upload a PDF

MCP and JSON carry no file bytes, so a file goes up in two steps:

1. Create the record that owns it. `POST /documents` with `kind` (`cv` or
   `letter`), `application_id`, the `career_ids` and `highlight_ids` it uses and
   `pdf: {name, size}`, and optionally the TeX source inline as `source` (up to 256
   KB) or as `source_file`. `POST /files/uploads` does the same for a career,
   template or job file. The result has `uploads`, one grant per file, each with an
   absolute `url`, `headers` and a ready `curl` line.
2. `PUT` the exact bytes to the grant's `url` with its headers (`X-Transfer-Token`;
   no bearer token). When `uploads` has a source grant too, send the source first. With a source, the
   PDF's request names its SHA-256, and a PDF built from another source is
   refused.

```bash
curl -fsS -X PUT -H 'X-Transfer-Token: ...' --data-binary @'cv.pdf' \
  'http://127.0.0.1:8080/api/v1/transfers'
```

A grant works once and expires after ten minutes; files are limited to 20 MiB. The
revision is complete when its PDF is stored, and a complete revision never changes.
A download works the same way: `POST /files/{id}/download` returns a grant to `GET`.

The origin of the grant's `url` and `curl` line is `OPENINGS_PUBLIC_URL` (else the origin
the request reached), so it must be reachable from the machine that runs it.
