# Workflow API semantics

Use the current MCP schemas or REST OpenAPI for exact inputs. REST paths below
are relative to the configured `/api/v1` origin. This reference contains shared
mechanics, not personal selection or writing policy.

## Queues and applications

- `GET /jobs?queue=inbox&limit=200&offset=0` and `jobs_search(value)` list a
  compact preview. `job_get` / `GET /jobs/{id}` supplies the full posting.
  Filter value lists (`facets`) appear only with `include_facets: true`.
- `job_triage(job_id, value)` / `POST /jobs/{id}/triage` takes `triage` and
  `expected_version`. Values are `inbox`, `saved` and `dismissed`, not `draft`.
  It returns the compact job summary with the new `version`, not the posting.
  `job_update` and `application_update` also return compact jobs.
- A 409 version conflict carries `details.current_version`; read the record
  again before retrying so concurrent edits are preserved.
- Actionable `queue=shortlist` means saved with no application attempt. Raw
  `triage=saved` also includes jobs with open or closed attempts.
- Snapshot the queue's IDs before mutating it, or repeatedly process offset zero.
  Advancing offsets over a shrinking queue can skip jobs.
- `applications_list` / `GET /applications?job_id={id}` resolves attempts.
  `application_create` / `POST /applications` creates Draft and retains saved
  job interest. Application existence removes the job from actionable Shortlist.
- Application creation supports an `idempotency_key`. A repeat key for the same
  job returns the existing attempt without changing its fields. A conflicting open attempt returns409 with its ID;
  a key reused for another job also conflicts. Resume the intended open attempt.
  Starting a later attempt after Closed requires the actual task's authority.

## Contexts and documents

- `application_prepare_context` / `POST /contexts` takes `application_id`,
  explicit `template_ids`, optional `knowledge_ids`, `claim_ids`, `note` and
  `idempotency_key`. It freezes job, Profile, guidance, evidence, claims, templates
  and selected source-file bytes. Same key/request reuses the context; changed
  input with the same key conflicts. Omitted selections use current defaults.
- A context is a fixed input snapshot. Compare versions and relevant content
  before reusing it. Prepare a new context when different inputs are needed.
- `documents_create` / `POST /documents` takes application/context IDs,
  `kind: resume | cover_letter`, `title`, `content` and optional `previous_id`.
  Exact repeated content with the same context, title and parent reuses the
  revision. Changed output needs the proper parent. Child revisions inherit
  neither PDF files nor approval.
- Example of allowed new evidence-linked wording:
  `content: {bullets: [{text: "A supported sentence", evidence_ids: [entryID]}]}`.
  Include that entry in the context. Omit `claim_ids` for a new formulation.
  Unknown frozen evidence/claim IDs are rejected; entailment is not checked.

## Transfers and completed Drafts

- `files_reserve_upload` / `POST /files/uploads` takes owner type/ID, name,
  media type, size and optional SHA-256. Transfer bytes through the returned
  upload instruction, then verify the stored file. The server checks size,
  digest and a PDF header, not full PDF validity or layout.
- `documents_review` / `POST /documents/{id}/review` takes `expected_version`
  and `review_state: approved`. Uploads change the document version; read it again
  before review. Approval does not parse the PDF or establish human approval.
- `documents_list` / `GET /documents` returns compact rows by default (file
  counts, no content or files). Pass `summary: false`, or read `documents_get`,
  for structured content and file entries.
- Draft-ready is an agent assessment, not an API state or flag. It requires the
  intended current CV and CL leaf revisions, valid final PDFs and sources,
  complete content/layout checks and approved document review states.
- The UI projects current leaves as Needs PDF, PDF to review or Approved PDF.
  A newer incomplete leaf is not covered by an approved parent. Resolve ambiguous
  branches rather than selecting an arbitrary ancestor.
- Keep application state Draft. The owner submits online and records Applied.
  Missing output or a failed check remains incomplete; do not delete the attempt
  or dismiss the job to conceal a preparation failure.

## Recover preparation from the database

Use `applications_list(value: {status: "draft", limit: 200, offset: 0})` or
`GET /applications?status=draft&limit=200&offset=0`, then paginate the stable
read-only result. The field is `status`, not `stage`. Add `readiness`
(`none`, `missing_pdf`, `unreviewed`, `blocked`, `ready`) to resume only
incomplete or blocked Drafts, and `sort: "deadline"` to keep deadline order. Read each relevant
application and its document revisions, contexts and files before resuming.
A local checkpoint is optional. A compatible complete Draft needs no new work.

Application idempotency matches the key and job, not the whole payload. A repeat
key for the same job reuses the attempt without changing existing fields; inspect
them before continuing. Context idempotency checks the request content.
