# Workflow API semantics

Use the current MCP schemas or REST OpenAPI for exact inputs. REST paths below
are relative to the configured `/api/v1` origin. This reference contains shared
mechanics, not personal selection or writing rules.

## Names and arguments

- Every tool is named `<resource>_<verb>` (`jobs_get`, `applications_update`,
  `profile_get`). Its arguments are the record ids a REST path names, flat;
  `expected_version` of a delete, flat; and one `value`: the REST body of a
  write, or the filters, `limit`, `offset` and options of a read.
- Lists return summaries with `items`, `total`, `limit` and `offset`; pass
  `value.summary: false` or read the single record for full content.
- Every delete names the record's `expected_version`. Every create accepts an
  `idempotency_key`: a retry with the same key and request returns the record
  the first request created; the key with another request is `409 conflict`.

## Queues and applications

- `GET /jobs?queue=inbox&limit=200&offset=0` and `jobs_list(value)` list a
  compact preview. `jobs_get` / `GET /jobs/{id}` supplies the full posting.
  Filter value lists (`facets`) appear only with `include_facets: true`.
- `jobs_triage(job_id, value)` / `POST /jobs/{id}/triage` takes `triage` and
  `expected_version`, and with `dismissed` an optional `reason` (at most 500
  characters) the owner reads beside the dismissal; `jobs_bulk` takes the same
  `reason` for its `dismissed` action. Values are `inbox`, `saved` and
  `dismissed`, not `draft`. Restoring a dismissed job clears its dismissal.
  It returns the compact job summary with the new `version`, not the posting.
  `jobs_update` and `applications_update` also return compact jobs.
- A 409 version conflict carries `details.current_version`; read the record
  again before retrying so concurrent edits are preserved.
- Actionable `queue=shortlist` means saved with no application attempt. Raw
  `triage=saved` also includes jobs with open or closed attempts.
- Snapshot the queue's IDs before mutating it, or repeatedly process offset zero.
  Advancing offsets over a shrinking queue can skip jobs.
- `applications_list` / `GET /applications?job_id={id}` resolves attempts.
  `applications_create` / `POST /applications` creates Draft and retains saved
  job interest. Application existence removes the job from actionable Shortlist.
- Application creation supports an `idempotency_key`. A repeat key for the same
  job returns the existing attempt without changing its fields. A conflicting open attempt returns409 with its ID;
  a key reused for another job also conflicts. Resume the intended open attempt.
  Starting a later attempt after Closed requires the actual task's authority.

## Contexts and documents

- `contexts_create` / `POST /contexts` takes `application_id`,
  explicit `template_ids`, optional `knowledge_ids`, `claim_ids`, `note` and
  `idempotency_key`. It freezes job, Profile, the Preferences sections with
  their versions (`preferences`), template guidance, evidence, claims, templates and selected source-file bytes,
  and the application's pinned note as `instructions.application_note`, followed
  by this request's `note`. Same key/request reuses the context; changed
  input with the same key conflicts. Omitted selections use current defaults.
- A context is a fixed input snapshot. Compare versions and relevant content
  before reusing it. Prepare a new context when different inputs are needed.
- `documents_create` / `POST /documents` takes application/context IDs,
  `kind: resume | cover_letter | answers | other`, `title`, optional `note`,
  `claim_ids`, `knowledge_ids` and `previous_id`. A CV or letter (`resume`,
  `cover_letter`) takes no `content` (`422 content_not_accepted`): it is the
  `.tex` source and PDF uploaded next. Form answers keep structured `content`.
  A retry with the same fields, or the same `idempotency_key`, returns the same
  revision (without a key, a CV or letter only while it is still an empty
  draft). Changed output needs the proper parent.
  Child revisions inherit neither files nor approval.
- Cite the evidence a revision uses: `claim_ids` of reused approved claims,
  `knowledge_ids` of the Career entries behind new wording. Include them in the
  context. Unknown frozen evidence/claim IDs are rejected; entailment is not
  checked.
- `documents_get` returns a CV or letter's `text`, derived from its source
  without a TeX runtime, `source_sha256`, the cited ids, `note`, its files and,
  for revisions saved before 0.22, the read-only `legacy_content`.
  `documents_compare(document_id, other_id?)` /
  `GET /documents/{id}/comparison` compares the text with the revision it
  replaces (or `other_id`) line by line: `lines` of `same`, `added`, `removed`.

## Transfers and completed Drafts

- `files_reserve_upload` / `POST /files/uploads` takes owner type/ID, name,
  media type, size and optional SHA-256. Transfer bytes through the returned
  upload instruction, then verify the stored file. The server checks size,
  digest and a PDF header, not full PDF validity or layout.
- A CV or letter revision has one `.tex` source (UTF-8) and one PDF. Upload the
  source first; the PDF reservation names `source_sha256`, the source's
  SHA-256. Without it: `422 source_required`; before the source:
  `409 source_required`; another source: `409 source_mismatch`; a second source
  or PDF: `409 source_exists` / `pdf_exists`.
- `documents_review` / `POST /documents/{id}/review` takes `expected_version`
  and `review_state: approved`. A CV or letter needs its source
  (`409 source_required`) and its PDF (`409 pdf_required`). Uploads change the
  document version; read it again before review. Approval does not parse the PDF
  or establish human approval.
- `documents_list` / `GET /documents` returns compact rows by default (file
  counts, no text, content or files); `q` searches titles, notes and the text
  derived from sources. Pass `value.summary: false`, or read `documents_get`, for
  text, content and file entries. `documents_delete(document_id,
  expected_version)` removes a draft revision and its files for good.
- Ready is a stored step of a Draft, set with `applications_ready(application_id,
  value)` / `POST /applications/{id}/ready` (`expected_version`, `ready`). The
  agent's assessment comes first: the intended current CV and CL leaf revisions,
  valid final PDFs and sources, complete content/layout checks and approved
  document review states. The server then checks files, review states and
  blocking requirements and refuses with `409 application_not_ready` and
  `details.check`. `readiness` is `ready` only for a marked Draft whose checks
  still pass, and `reviewed` when they pass without the mark.
- A new revision or context, a deleted revision, a file added to a current
  revision, an unresolved blocking requirement or leaving Draft clears the mark
  and changes the application version; mark it again after the rework is checked.
- The UI projects current leaves as Needs PDF, PDF to review or Approved PDF.
  A newer incomplete leaf is not covered by an approved parent. Resolve ambiguous
  branches rather than selecting an arbitrary ancestor.
- Keep application state Draft. The owner submits online and records Applied.
  Missing output or a failed check remains incomplete; do not delete the attempt
  or dismiss the job to conceal a preparation failure.

## Employer responses

- `responses_create(application_id, value)` / `POST /applications/{id}/responses`
  records an owner-reported answer (`kind`, `date`, `note`,
  `idempotency_key`) without moving the stage. `responses_update` /
  `PATCH /responses/{id}` and `responses_delete` / `DELETE /responses/{id}` take
  the response's `expected_version`; `responses_list` /
  `GET /applications/{id}/responses` reads them.
- `applications_update` moving a sent application to Interview or Offer, or
  closing it as `rejected`, records the response itself (`response_date`,
  `response_note`); `outcome: "no_response"` with `concluded_on` closes a sent
  application that never got an answer.
- `applications_list(value: {no_reply_due: true})` /
  `GET /applications?no_reply_due=true` lists the Applied applications past the
  no-reply period; `insights_get` / `GET /insights` reads the rates.

## The change log

- `events_list(value)` / `GET /events` reads the attributed change log. Each
  change carries an `actor` label and the `batch_id` of the REST request or MCP
  tool call that wrote it.
- Report what you did in the chat.

## Recover preparation from the database

Use `applications_list(value: {status: "draft", limit: 200, offset: 0})` or
`GET /applications?status=draft&limit=200&offset=0`, then paginate the stable
read-only result. The field is `status`, not `stage`. Add `readiness`
(`none`, `missing_pdf`, `unreviewed`, `blocked`, `reviewed`, `ready`) to resume only
incomplete or blocked Drafts, and `sort: "deadline"` to keep deadline order. Read each relevant
application and its document revisions, contexts and files before resuming.
A local checkpoint is optional. A compatible complete Draft needs no new work.

Application idempotency matches the key and job, not the whole payload. A repeat
key for the same job reuses the attempt without changing existing fields; inspect
them before continuing. Context idempotency checks the request content.
