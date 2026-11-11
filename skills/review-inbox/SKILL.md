---
name: review-inbox
description: Review or clear the Openings Inbox by reading full jobs against current Profile and Career evidence, then shortlist credible opportunities or dismiss confirmed mismatches; runs routinely under the operating mandate.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Review Inbox

Use this workflow to review, classify and clear Inbox jobs, as routine work under
the [operating mandate](../openings-workspace/references/operating-mandate.md). A run the owner asked only to inspect is
read-only. Triage does not prepare applications, change application stages or
change collection.

Read [Openings workspace](../openings-workspace/SKILL.md) for connection, schemas,
versions and the shared API reference. Read the current Profile/preferences,
general guidance and the full current Career record, then its relevant evidence before decisions. Those live data
own the selection criteria; keep no personal criteria in this skill.

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

Count the requested Inbox and snapshot all its IDs through complete pagination
before mutations. Keep a small task log of IDs, decisions, unresolved facts and
successful writes. Server state is authoritative on every resume.

Read each full job with its current version. A list preview is not a complete
posting. Check existing application state and the actual scope of the request.
Read Career descriptions when a title, duty or requirement is ambiguous.

## Decide from the current policy

Assess actual responsibilities, essential requirements, preferred tools and
supported transfer. Use the Profile preferences and any structured decision
policy recorded in Profile metadata; they own the criteria and flexibility.
Explain the fit or mismatch with specific facts, not a keyword score.
Missing evidence does not establish that a skill or experience is absent.

Shortlist or dismiss only when the evidence supports the decision. If a plausible
role depends on a specific unresolved fact, leave it in Inbox, ask the question
on that job (`questions_ask`) and continue the other jobs. Do not manufacture certainty to empty a queue.

## Write and resume safely

Use the current triage operation and expected version. Inspect each bulk item;
partial success is not a completed batch. On conflict, read the job again and
preserve a concurrent decision. On an uncertain response, read server state
before retrying. Record successful IDs so reruns do not repeat completed work.

Do not move existing pursued jobs or application attempts outside the requested
scope. Saved interest and application stages are different. Do not dismiss a job
to remove it from another pipeline view.

Reconcile the initial cohort, successful changes, unresolved jobs and new arrivals.
Use a fresh Inbox query at the end. Report actual saved/dismissed counts, remaining
IDs with reasons, failures and any arrivals outside the reviewed cohort, using
the shared [run report](../openings-workspace/references/run-report.md). When the
same kind of clear mismatch recurs from one source, mention it for
[Manage sources](../manage-sources/SKILL.md) instead of changing sources here.
Only call the Inbox empty when the final queue check establishes it.

## Duplicate awareness

Before saving candidates, and when a posting appears repeated, use the shared
[vacancy identity check](../openings-workspace/references/job-deduplication.md).
Check existing applications across records. Similar titles alone do not prove a
duplicate. Report uncertain identity; resolve verified duplicates only within
the requested cleanup scope, preserving application and document history.
