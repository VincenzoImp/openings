---
name: review-inbox
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
versions and the shared API reference. Read the owner's policy (`policy_get`):
its `decision` items are the rules for shortlisting and dismissing and its
`eligibility` items the facts employers ask about. Read the Profile, general
guidance and the full current Career record, then its relevant evidence before
decisions. Those live data own the selection criteria; keep no personal criteria
in this skill.

## Run and questions

Open a run before the first write: `runs_start` with `workflow: "review-inbox"` and the scope; writes made
with this token then attach to the run. First read the owner's answers given
since the previous run (`questions_list` with `answered_since`) and act on them.
Then read the owner's open requests (`requests_list` with `state: "open"`): take
the ones in this workflow's scope (`requests_take`), do the work, and report on
each with `requests_complete` and a short result, or `requests_decline` and the
reason. Leave requests for other workflows open. A request never authorises
submitting an application, contacting an employer or recording Applied.
Ask each new question as a record tied to its job, application or Career entry
(`questions_ask`), not only in chat. Close the run with `runs_finish` and the
stored [run report](../openings-workspace/references/run-report.md). A run asked only to inspect needs no run record.

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

- A required language outside the policy's languages is strong evidence of a
  mismatch; confirm it in the posting text before dismissing, because the
  detector reads phrases such as "fluent German" and may miss or misread an
  unusual wording. A posting written in another language without a stated
  requirement is not a requirement.
- A likely duplicate is a candidate, never a fact: compare with the earlier job
  (`jobs_get` on `signals.duplicate.job_id`) as the
  [vacancy identity check](../openings-workspace/references/job-deduplication.md)
  says. Merge only a verified duplicate (`jobs_merge`); mark a different vacancy
  with `jobs_distinct` so the flag does not return.
- A posting no longer listed by its board has probably closed: dismiss it with
  that reason unless the owner is already pursuing it.

Filter the cohort with `jobs_list` (`signal`, `requires`, `posting_language`,
`posting_language_not`) to handle a whole kind of mismatch together.

## Decide from the current policy

Assess actual responsibilities, essential requirements, preferred tools and
supported transfer. Use the policy's `decision` items and `eligibility` facts;
they own the criteria and flexibility. Rely on confirmed items (`confirmed:
true`). An unconfirmed item is your own proposal or a value copied from the old
Profile (`origin`): treat it as a hint, and ask the owner to confirm it when a
decision depends on it. A decision item may carry a `rule` on a collection
signal. While the owner keeps it enabled and confirmed, the server applies it
to new jobs as they are collected: those jobs arrive dismissed with
`dismissal.rule` naming it, or with the rule in `signals.rules` for a flag
rule. Rules never act on jobs already waiting in New, so apply the statement of
every decision item yourself, enabled or not. To suggest a rule, measure it
first with `policy_rule_preview` and propose it with `policy_add`; only the
owner enables it. Target roles and preferences are decision items of the
policy too.
Explain the fit or mismatch with specific facts, not a keyword score.
Missing evidence does not establish that a skill or experience is absent.

Shortlist or dismiss only when the evidence supports the decision. If a plausible
role depends on a specific unresolved fact, leave it in New, ask the question
on that job (`questions_ask`) and continue the other jobs. Do not manufacture certainty to empty the list.

## Write and resume safely

Use the current triage operation and expected version. Give every dismissal a
short `reason` (`jobs_triage` or `jobs_bulk`) in the owner's terms, such as
"Requires German (C1); your policy lists English and Italian": the owner reads
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
IDs with reasons, failures and any arrivals outside the reviewed cohort, using
the shared [run report](../openings-workspace/references/run-report.md). When the
same kind of clear mismatch recurs from one source, mention it for
[Manage sources](../manage-sources/SKILL.md) instead of changing sources here.
Only call New empty when the final check establishes it.

## Duplicate awareness

Before shortlisting candidates, and when a posting appears repeated, use the shared
[vacancy identity check](../openings-workspace/references/job-deduplication.md).
Check existing applications across records. Similar titles alone do not prove a
duplicate. Report uncertain identity; resolve verified duplicates only within
the requested cleanup scope, preserving application and document history.
