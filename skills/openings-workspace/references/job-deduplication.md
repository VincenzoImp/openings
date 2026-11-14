# Vacancy identity and duplicate preflight

Read full postings and existing application attempts before shortlisting a job
or starting an application. Check candidate duplicates across job IDs, not just
within one triage list:
application idempotency protects one job ID, not two records for the same vacancy.

## Establish identity

Openings ingestion reuses exact identities: a verified source key, normalized
source URL, or a recognized Greenhouse, Lever or Ashby posting key. It does not
merge near-duplicates. Two read-only operations find candidates without writing:

- `jobs_resolve({value: {url?, source_key?}})` or `GET /jobs/resolve?url=…`
  looks up a URL or source key before ingestion. It returns every matching job
  with `matched_by`, triage and all application attempts. `identity_conflict:
  true` means several records already share that identity: merge before ingesting.
- `jobs_duplicates({value: {triage?, job_id?, match_location?, min_confidence?,
  limit, offset}})` or `GET /jobs/duplicates` returns paginated candidate groups,
  most confident first. Each group has a `confidence` from 0 to 1, a `tier` and
  `reasons: {matched, conflicts}`, with `signals` (the matched list),
  `identical_postings`, `open_application_ids`, `merge_blocked` and a
  `reference_id` (open attempt, then any attempt, then shortlisted, then oldest).
  Items carry triage, attempts, `posting_hash`, advisory text `similarity` and
  their own `confidence` and `reasons` against the reference. `triage` keeps
  groups with at least one member of that triage; `job_id` returns the group containing that job;
  `match_location` drops pairs whose locations do not agree.

### Confidence and reasons

`min_confidence` is the lowest group confidence returned; a group's confidence is
its weakest link.

| Tier | `min_confidence` | Typical evidence |
|---|---|---|
| `high` | `0.85` | The same apply link or ATS posting ID; a shared requisition ID with the same employer, title or text; the same company, title and location with nearly identical text. |
| `medium` | `0.5` (default) | Nearly identical text under another company name; similar text; the same company, title and location when one record has no usable text; a record that fits two different vacancies. |
| `low` | `0` | The same company and title only, or any match contradicted by location, requisition, level or text. |

Matched signals: `apply_target` (the same ATS posting ID or URL, ignoring scheme,
`www.` and tracking fields), `requisition_id` (an ID in the title or labelled in
the text, such as "Req ID", "Referenznummer", "Référence" or "Rif."),
`posting_text`, `near_identical_text`, `similar_text`, `company_title`, `company`
(legal, corporate and country suffixes ignored: "Example", "Example AG" and
"Example Switzerland" are one employer), `title`, `similar_title` and `location`.

Conflicts: `requisition_id` and `apply_target` (both records name different IDs),
`location` (different cities or countries; "Remote", a country alone or a missing
location is unknown, not a conflict), `seniority`, `posting_text` (clearly
different text), `posting_date` (published more than 60 days apart: possibly a
re-opened vacancy, which is a new hiring round and never reaches the high tier)
and `ambiguous` (the record matches two vacancies that differ from each other,
for example a copy without a requisition ID next to two requisitions).

A job collected after another that it likely repeats carries the same score as
`signals.duplicate` (`job_id`, `confidence`, `tier`, from the medium tier up),
computed once when it was collected. After checking, merge a verified
duplicate with `jobs_merge`, or record a different vacancy with
`jobs_distinct(job_id, {other_id})`: the flag goes and is not computed again.

These are review signals, not identity, and nothing is merged automatically. A
high tier is a strong suggestion; an identical advertisement reused for two
openings in different teams still looks like one vacancy. Company and title alone
never prove a duplicate. Subsidiary or brand names ("Example" and "Example Labs")
are joined only by an identifier or by text, usually in the medium tier.

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
an intended Shortlisted application; start no later attempt after Closed without explicit scope.

The supported merge is `jobs_merge(job_id, value: {target_id, expected_version,
target_version})` or `POST /jobs/{source_id}/merge` with the same body. Read both
versions immediately before it. The source is merged into the chosen target;
source identities, postings, applications, events, notes and owned files move to
the target. The source job ID is removed. Frozen document contexts are not rewritten.
The target keeps its own title, posting fields and triage; the merge does not
choose the best description or interest state. Queued or running tasks for both
records are cancelled. Record the surviving ID and re-read its actual application
and triage before continuing.

Merge rejects more than one active application with 409. Do not close, delete or
change an application's stage to make the merge pass. Report that conflict and
skip new preparation for the duplicate group until resolved. Never use job forget
or delete an application to remove a duplicate.

If identity is uncertain, report both IDs and the reason; do not merge or dismiss
on similarity alone. A supported job note (`notes_create`, body plus optional
`application_id`) can record the candidate canonical ID without inventing a metadata
field. If an explicitly authorized cleanup uses dismissal instead of merge for a
confirmed duplicate, note the canonical ID and reason first; preserve all history.
Do not dismiss a job merely to change which list shows it.

## Batch and rerun

Build a stable cohort with `jobs_duplicates` (for example `triage: "shortlisted"`
before preparation, or `triage: "new"` before triage) and verify each group.
Start with `min_confidence: 0.85`, continue with the default, and request `0`
only for an exhaustive audit: the low tier is mostly different vacancies.
Build a verified canonical-ID map before mutations. Skip a
losing record after a confirmed merge and reuse the target's existing
application or completed work. Re-read server state on rerun; notes and retained
applications can recover the relationship without a local file. Reconcile
candidate groups, merges, conflicts and unresolved identities at the end. An audit only
checks these operations; it does not merge, dismiss or prepare real jobs.
