# Vacancy identity and duplicate preflight

Read full postings and existing application attempts before creating a Draft.
Check candidate duplicates across job IDs, not just within actionable queues:
application idempotency protects one job ID, not two records for the same vacancy.

## Establish identity

Openings ingestion reuses exact identities: a verified source key, normalized
source URL, or a recognized Greenhouse, Lever or Ashby posting key. It does not
merge near-duplicates. Two read-only operations find candidates without writing:

- `jobs_resolve({value: {url?, source_key?}})` or `GET /jobs/resolve?url=…`
  looks up a URL or source key before ingestion. It returns every matching job
  with `matched_by`, triage and all application attempts. `identity_conflict:
  true` means several records already share that identity: merge before ingesting.
- `jobs_duplicates({value: {queue?, job_id?, match_location?, limit, offset}})` or
  `GET /jobs/duplicates` returns paginated candidate groups. A group joins jobs
  with the same normalized company and title (legal suffixes and markers such as
  `(m/f/d)` ignored; optionally the same location) or identical posting text.
  Each group lists its `signals`, `identical_postings`, `open_application_ids`,
  `merge_blocked` and a `reference_id` (open attempt, then any attempt, then
  saved, then oldest). Items carry triage, attempts, `posting_hash` and advisory
  `similarity` to the reference. `queue` keeps groups with at least one member in
  that queue; `job_id` returns the group containing that job.

These are review signals, not identity. The same vacancy often arrives from
LinkedIn, Indeed, Glassdoor and the employer's ATS with the same text and
different IDs; a shared template can also produce identical text for different
requisitions.

Compare employer and requisition ID first, then the actual apply destination,
full duties, location, level and posting details. Follow a source link only when
needed to resolve identity. Title similarity alone is insufficient. Different
requisitions, levels or locations can be separate vacancies even with similar text.
A shared generic careers page is not a unique application URL.

URL normalization removes fragments, trailing slashes and known tracking fields
(`utm_*`, `gclid`, `fbclid`, `ref`, `source`), and sorts remaining query fields.
Preserve other query parameters: they can identify the requisition. Do not invent
an identity from an unverified source key or strip every query string.

## Resolve confirmed duplicates within the requested task

Prefer a canonical record with the relevant existing application or submitted
history over a newly collected copy. Check all attempts, their stages and files.
If both records carry important history, retain it and resolve ownership before
continuing. Repeated collection alone does not authorize another application.
An Applied, Interview or Offer attempt is not a new preparation request. Resume
an intended Draft; start no later attempt after Closed without explicit scope.

The supported merge is `job_merge(job_id, value: {target_id, expected_version,
target_version})` or `POST /jobs/{source_id}/merge` with the same body. Read both
versions immediately before it. The source is merged into the chosen target;
source identities, postings, applications, events, notes and owned files move to
the target. The source job ID is removed. Frozen document contexts are not rewritten.
The target keeps its own title, posting fields and triage; the merge does not
choose the best description or interest state. Queued or running tasks for both
records are cancelled. Record the surviving ID and re-read its actual application
and queue state before continuing.

Merge rejects more than one active application with 409. Do not close, delete or
change an application's stage to make the merge pass. Report that conflict and
skip new preparation for the duplicate group until resolved. Never use job forget
or delete an application to remove a duplicate.

If identity is uncertain, report both IDs and the reason; do not merge or dismiss
on similarity alone. A supported job note (`note_add`, body plus optional
application_id) can record the candidate canonical ID without inventing a metadata
field. If an explicitly authorized cleanup uses dismissal instead of merge for a
confirmed duplicate, note the canonical ID and reason first; preserve all history.
Do not dismiss a job merely because its Draft has left actionable Shortlist.

## Batch and rerun

Build a stable cohort with `jobs_duplicates` (for example `queue: "shortlist"`
before preparation, or `queue: "inbox"` before triage) and verify each group.
Build a verified canonical-ID map before mutations. Skip a
losing record after a confirmed merge and reuse the target's existing Draft or
completed work. Re-read server state on rerun; notes and retained applications
can recover the relationship without a local file. Reconcile candidate groups,
merges, conflicts and unresolved identities at the end. A readiness audit only
checks these operations; it does not merge, dismiss or prepare real jobs.
