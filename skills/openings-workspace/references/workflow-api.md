# Workflow API semantics

Use the current MCP schemas or REST OpenAPI for exact inputs. REST paths below
are relative to the configured `/api/v1` origin. This reference contains shared
mechanics, not personal selection or writing policy.

## Queues and applications

- `GET /jobs?queue=inbox&limit=200&offset=0` and `jobs_search(value)` list a
  compact preview. `job_get` / `GET /jobs/{id}` supplies the full posting.
  Filter value lists (`facets`) appear only with `include_facets: true`.
- `job_triage(job_id, value)` / `POST /jobs/{id}/triage` takes `triage` and
  `expected_version`, and with `dismissed` an optional `reason` (at most 500
  characters) the owner reads beside the dismissal; `jobs_bulk` takes the same
  `reason` for its `dismissed` action. Values are `inbox`, `saved` and
  `dismissed`, not `draft`. Restoring a dismissed job clears its dismissal.
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
  `idempotency_key`. It freezes job, Profile, the policy sections with their
  versions, guidance, evidence, claims, templates and selected source-file bytes. Same key/request reuses the context; changed
  input with the same key conflicts. Omitted selections use current defaults.
- A context is a fixed input snapshot. Compare versions and relevant content
  before reusing it. Prepare a new context when different inputs are needed.
- `documents_create` / `POST /documents` takes application/context IDs,
  `kind: resume | cover_letter | answers | other`, `title`, optional `note`,
  `claim_ids`, `knowledge_ids` and `previous_id`. A CV or letter (`resume`,
  `cover_letter`) takes no `content` (`422 content_not_accepted`): it is the
  `.tex` source and PDF uploaded next. Form answers keep structured `content`.
  A retry with the same fields returns the same revision (a CV or letter only
  while it is still an empty draft). Changed output needs the proper parent.
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
  derived from sources. Pass `summary: false`, or read `documents_get`, for text,
  content and file entries.
- Ready is a stored step of a Draft, set with `application_ready(application_id,
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

- `responses_add(application_id, value)` / `POST /applications/{id}/responses`
  records an owner-reported answer (`kind`, `date`, `note`,
  `idempotency_key`) without moving the stage. `responses_update` /
  `PATCH /responses/{id}` and `responses_remove` / `DELETE /responses/{id}` take
  the response's `expected_version`; `responses_list` /
  `GET /applications/{id}/responses` reads them.
- `application_update` moving a sent application to Interview or Offer, or
  closing it as `rejected`, records the response itself (`response_date`,
  `response_note`); `outcome: "no_response"` with `concluded_on` closes a sent
  application that never got an answer.
- `applications_list(value: {no_reply_due: true})` /
  `GET /applications?no_reply_due=true` lists the Applied applications past the
  no-reply period; `insights_get` / `GET /insights` reads the rates.

## Runs and questions

- `runs_start(value)` / `POST /runs` takes `workflow`, `scope`, optional
  `supersede` and `idempotency_key`, and needs an API token: a dashboard session
  has no runs (`403 run_actor`). One open run per token: `409 run_open` carries
  the open run in `details.run`.
- `runs_update(run_id, value)` / `PATCH /runs/{id}` and
  `runs_finish(run_id, value)` / `POST /runs/{id}/finish` take the run's
  `expected_version` and work only for the token that opened the run
  (`403 run_owner`) while it is open (`409 run_closed`).
- `runs_get` / `GET /runs/{id}` and `runs_list` / `GET /runs` are open to every
  caller. `change_counts` is derived from the recorded changes; a finished or
  superseded run keeps the counts it had when it ended.
- `questions_ask(value)` / `POST /questions`, `questions_list(value)` /
  `GET /questions`, `questions_get` / `GET /questions/{id}`,
  `questions_answer(question_id, value)` / `POST /questions/{id}/answer` and
  `questions_withdraw(question_id, value)` / `POST /questions/{id}/withdraw`.
  An answer needs text or one of the listed choices; answering again corrects
  the answer and renews `answered_at`. Answering needs owner authority: an agent
  token gets `403 forbidden`. Only an open question can be withdrawn.
- `events_list(value)` / `GET /events` reads the attributed change log.

## Requests for the agent

- `requests_list(value)` / `GET /requests` and `requests_get` /
  `GET /requests/{id}` are open to every caller. Read `state: "open"` at the
  start of a run; `workspace_info` reports the count as `open_requests`.
- `requests_take(request_id, value)` / `POST /requests/{id}/take`,
  `requests_complete` / `POST /requests/{id}/complete` (`result`) and
  `requests_decline` / `POST /requests/{id}/decline` (`reason`) take the
  request's `expected_version` and need an API token (`403 request_actor`).
  Taking needs an open request (`409 request_taken`, `409 request_closed`);
  completing and declining work from open or taken. The token's open run is
  recorded on the request; without an open run the request is still handled.
- `requests_create(value)` / `POST /requests` and `requests_withdraw` /
  `POST /requests/{id}/withdraw` are the owner's (`403 forbidden` for an agent
  token).
- A request never authorises what the operating mandate forbids.

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
