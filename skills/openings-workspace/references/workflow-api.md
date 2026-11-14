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

## Triage and applications

- `GET /jobs?triage=new&limit=200&offset=0` and `jobs_list(value)` list a
  compact preview. `jobs_get` / `GET /jobs/{id}` supplies the full posting.
  Filter value lists (`facets`) appear only with `include_facets: true`.
- `jobs_triage(job_id, value)` / `POST /jobs/{id}/triage` takes `triage` and
  `expected_version`, and with `dismissed` an optional `reason` (at most 500
  characters) the owner reads beside the dismissal; `jobs_bulk` takes the same
  `reason` for its `dismissed` action. Values are `new`, `shortlisted` and
  `dismissed`. Restoring a dismissed job clears its dismissal.
  It returns the compact job summary with the new `version`, not the posting.
  `jobs_update` and `applications_update` also return compact jobs.
- A 409 version conflict carries `details.current_version`; read the record
  again before retrying so concurrent edits are preserved.
- `triage: "shortlisted"` starts the job's application in stage Shortlisted
  when it has no open one. Moving a shortlisted job back to `new` or `dismissed`
  deletes that application only while it is empty (no documents, notes,
  replies, requirements or answers); otherwise `409 application_has_work` with
  `details.work` naming what exists. Closing an application never changes the
  job's triage; deleting a job's last application returns it to `new`.
- Snapshot the list's IDs before mutating it, or repeatedly process offset zero.
  Advancing offsets over a shrinking list can skip jobs.
- `applications_list` / `GET /applications?job_id={id}` resolves attempts.
  `applications_create` / `POST /applications` starts an application in stage
  Shortlisted and shortlists its job; `required_documents` (a subset of `cv`,
  `letter`, both by default) names what Ready needs and stays editable with
  `applications_update`.
- Application creation supports an `idempotency_key`. A repeat key for the same
  job returns the existing attempt without changing its fields. A conflicting open attempt returns409 with its ID;
  a key reused for another job also conflicts. Resume the intended open attempt.
  Starting a later attempt after Closed requires the actual task's authority.

## Inputs and documents

- Documents are written from the live records: `applications_get` (with
  `pinned_note`), `jobs_get`, `profile_get`, `knowledge_list`, `claims_list`,
  `templates_list`/`templates_get` and `preferences_get`. Read them again before
  a new revision when inputs may have changed.
- `documents_create` / `POST /documents` takes `application_id`,
  `kind: cv | letter | answers | other`, `title`, optional `note`,
  `claim_ids`, `knowledge_ids` and `previous_id`. A CV or letter takes no
  `content` (`422 content_not_accepted`): it is a required PDF
  (`pdf: {name, size, sha256?}`) and an optional TeX source, inline as `source`
  (UTF-8, at most 256 KB) or uploaded as `source_file`. The result's `uploads`
  holds one-shot grants (`pdf`, and `source` for `source_file`). Form answers
  keep structured `content`. A retry with the same fields, or the same
  `idempotency_key`, returns the same revision. Changed output needs the proper
  parent; child revisions inherit no files.
- Cite the evidence a revision uses: `claim_ids` of reused approved claims,
  `knowledge_ids` of the Career entries behind new wording. Unapproved claims
  (`unapproved_claim`) and unknown entries (`unknown_evidence`) are rejected;
  entailment is not checked.
- `documents_get` returns a CV or letter's `complete`, its `text` and
  `text_from` (`tex`: derived from the source without a TeX runtime; `pdf`:
  extracted from the PDF when there is no source; no text when extraction
  fails), `source_sha256`, the cited ids, `note` and its files.
  `documents_compare(document_id, other_id?)` /
  `GET /documents/{id}/comparison` compares the text with the revision it
  replaces (or `other_id`) line by line: `lines` of `same`, `added`, `removed`.

## Transfers and complete revisions

- `files_reserve_upload` / `POST /files/uploads` takes owner type/ID, name,
  media type, size and optional SHA-256. Transfer bytes through the returned
  upload instruction, then verify the stored file. The server checks size,
  digest and a PDF header, not full PDF validity or layout.
- PUT the exact bytes to each grant's `url` with its headers, the source
  first. A CV or letter revision is incomplete until its PDF is stored, then
  complete and immutable (`409 revision_complete`); a change is a new revision
  with `previous_id`. With a source, the PDF must name `source_sha256`, the
  source's SHA-256 (`422 source_sha256_required`); before the source:
  `409 source_required`; another source: `409 source_mismatch`; a second source
  or PDF: `409 source_exists` / `pdf_exists`. A PDF-only revision has no
  source hash.
- `documents_list` / `GET /documents` returns compact rows by default (file
  counts and `complete`, no text, content or files); `q` searches titles, notes
  and readable text. Pass `value.summary: false`, or read `documents_get`, for
  text, content and file entries. `documents_delete(document_id,
  expected_version)` removes a revision and its files for good.
- Ready is computed, never stored or marked: an application is `ready` when it
  is Shortlisted, every kind in `required_documents` has a current complete
  revision and no blocking requirement is unresolved. Reads and lists return
  `ready` and `missing` (for example `["letter", "requirement:<id>"]`). Ready
  checks files, not content: finish the agent's own content and PDF checks
  before uploading the PDF. A newer incomplete leaf is not covered by a
  complete parent. Resolve ambiguous branches rather than selecting an
  arbitrary ancestor.
- Keep the application Shortlisted. Mark applied (`status: "applied"`) is the
  owner's act: the owner submits online and records it.
  Missing output or a failed check remains incomplete; do not delete the attempt
  or dismiss the job to conceal a preparation failure.

## Employer replies

- `applications_update` / `PATCH /applications/{id}` with
  `reply: {kind, date?, note?}` records an owner-reported reply to a sent
  application (kinds `interview`, `rejection`, `offer`, `other`; `date` defaults
  to today) and moves the stage in the same change: `interview` to Interview,
  `offer` to Offer, `rejection` closes as `rejected`, `other` leaves it. Do not
  pass `status` with it. `reply: {id, kind?, date?, note?}` corrects one and
  `reply: {id, remove: true}` removes one; corrections never move the stage.
  `applications_get` lists `replies` and `last_reply`.
- `applications_list(value: {needs: "reply_overdue"})` /
  `GET /applications?needs=reply_overdue` lists the Applied applications without
  a reply past the no-reply period. Closing one as `outcome: "no_response"` (with
  `concluded_on`) is manual, single or with `applications_bulk`; nothing closes
  automatically. `insights_get` / `GET /insights` reads the rates.

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

Use `applications_list(value: {stage: "shortlisted", limit: 200, offset: 0})` or
`GET /applications?stage=shortlisted&limit=200&offset=0`, then paginate the
stable read-only result. `needs: "documents"` keeps the ones missing a required
document, `stage: "ready"` the Ready ones, and `sort: "deadline"` keeps deadline
order; each row's `missing` names what is left. Read each relevant application
and its document revisions, contexts and files before resuming. A local
checkpoint is optional. A Ready application whose documents pass the agent's
checks needs no new work.

Application idempotency matches the key and job, not the whole payload. A repeat
key for the same job reuses the attempt without changing existing fields; inspect
them before continuing. Context idempotency checks the request content.
