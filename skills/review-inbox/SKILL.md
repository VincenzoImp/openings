---
name: review-inbox
title: Review new jobs
summary: Have new jobs read against your Preferences and Career, then shortlisted or dismissed with a reason.
example: Go through my new jobs and shortlist the good ones.
description: Review or clear the Openings New jobs (to review) by reading full jobs against current Profile and Career evidence, then shortlist credible opportunities or dismiss confirmed mismatches; runs routinely under the operating mandate.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Review new jobs

Use this workflow to review, classify and clear New jobs (`triage: "new"`, to
review), as routine work under
the [operating mandate](../openings-workspace/references/operating-mandate.md). A run the owner asked only to inspect is
read-only. Shortlisting a job starts its application in stage Shortlisted; triage
does not prepare documents, change later application stages or change
collection.

Read [Openings workspace](../openings-workspace/SKILL.md) for connection, schemas,
versions and the shared API reference. Read the owner's Preferences
(`preferences_get`): `looking_for` and `ruled_out` decide what to shortlist and
dismiss, `facts` holds what employers ask about, `working_with_me` how the
owner wants you to work, and `settings.spoken_languages` the languages the
owner speaks. Read the Profile and the full current Career record, then its relevant evidence before
decisions. Those live data own the selection criteria; keep no personal criteria
in this skill.

## Questions and report

Ask the owner in the chat when a missing fact matters, and never record an
answer the owner did not give. Report what you did in the chat.

## Establish and read the cohort

Count the requested New jobs and snapshot all their IDs through complete pagination
before mutations. Keep a small task log of IDs, decisions, unresolved facts and
successful writes. Server state is authoritative on every resume.

Read each full job with its current version. A list preview is not a complete
posting. Check existing application state and the actual scope of the request.
Read Career descriptions when a title, duty or requirement is ambiguous.

## Use the ingest signals

Every job carries `signals`, computed when it was collected and without a model:
the posting's `language`, the languages it states as `required` (groups: one
language of a group is enough) or `welcome`, a likely `duplicate` of an earlier
job with its confidence, and `no_longer_listed` when a company board stopped
listing it. `computed: false` means a job from before 0.21 whose signals are
still being computed; read the posting instead. Use them to order and to find
evidence quickly, not as verdicts:

- A required language outside the owner's spoken languages is strong evidence
  of a mismatch; confirm it in the posting text before dismissing, because the
  detector reads phrases such as "fluent German" and may miss or misread an
  unusual wording. A posting written in another language without a stated
  requirement is not a requirement.
- A likely duplicate is a candidate, never a fact: compare with the earlier job
  (`jobs_get` on `signals.duplicate.job_id`) as the
  [vacancy identity check](../openings-workspace/references/job-deduplication.md)
  says. Merge only a verified duplicate (`jobs_merge`); mark a different vacancy
  with `jobs_distinct` so the signal does not return.
- A posting no longer listed by its board has probably closed: dismiss it with
  that reason unless the owner is already pursuing it.

Filter the cohort with `jobs_list` (`signal`, `requires`, `posting_language`,
`posting_language_not`, `hide_unspoken_required`) to handle a whole kind of
mismatch together. Nothing dismisses a job automatically: every dismissal is
yours or the owner's.

## Decide from the current Preferences

Assess actual responsibilities, essential requirements, preferred tools and
supported transfer. Use What I'm looking for, What I rule out and Facts about
me; they own the criteria and flexibility, and you apply them yourself. A
statement that starts "(proposed by …, not confirmed)" was copied by the 0.24
upgrade from an unconfirmed item: treat it as a hint, and ask the owner when a
decision depends on it.
Explain the fit or mismatch with specific facts, not a keyword score.
Missing evidence does not establish that a skill or experience is absent.

Shortlist or dismiss only when the evidence supports the decision. If a plausible
role depends on a specific unresolved fact, leave it in New, ask the owner in the
chat and continue the other jobs. Do not manufacture certainty to empty the list.

## Write and resume safely

Use the current triage operation and expected version. Give every dismissal a
short `reason` (`jobs_triage` or `jobs_bulk`) in the owner's terms, such as
"Requires German (C1); you speak English and Italian": the owner reads
it beside the dismissal and can restore the job. Inspect each bulk item;
partial success is not a completed batch. On conflict, read the job again and
preserve a concurrent decision. On an uncertain response, read server state
before retrying. Record successful IDs so reruns do not repeat completed work.

Do not move existing pursued jobs or application attempts outside the requested
scope. Moving a shortlisted job back to New or dismissing it deletes its
application only while that is still empty; otherwise the server refuses with
`application_has_work`, and the application must be closed deliberately instead.
Do not dismiss a job to remove it from another pipeline view.

Reconcile the initial cohort, successful changes, unresolved jobs and new arrivals.
Use a fresh `triage: "new"` query at the end. Report actual shortlisted/dismissed counts, remaining
IDs with reasons, failures and any arrivals outside the reviewed cohort, in the
chat. When the
same kind of clear mismatch recurs from one source, mention it for
[Manage sources](../manage-sources/SKILL.md) instead of changing sources here.
Only call New empty when the final check establishes it.

## Duplicate awareness

Before shortlisting candidates, and when a posting appears repeated, use the shared
[vacancy identity check](../openings-workspace/references/job-deduplication.md).
Check existing applications across records. Similar titles alone do not prove a
duplicate. Report uncertain identity; resolve verified duplicates only within
the requested cleanup scope, preserving application and document history.
