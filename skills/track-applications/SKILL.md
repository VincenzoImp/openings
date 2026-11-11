---
name: track-applications
description: Review the Openings application pipeline - Draft readiness and priority, stale or expired postings, follow-ups and recorded outcomes - and record owner-reported progress without submitting anything.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Track applications

Use this workflow to keep the pipeline in order: what to apply to next, which
Drafts need work, and progress the owner reports. A status request is read-only.
The owner submits applications, contacts employers and records Applied; this
workflow records a stage or outcome only when the owner reports that fact.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, schemas,
application history and versions. Keep application progress separate from job
interest.

## Run and questions

Open a run before the first write: `runs_start` with `workflow: "track-applications"` and the scope; writes made
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

## Read the pipeline

List applications by stage with complete pagination. Each row has a
`readiness` from the current revision leaves and requirements: `none` (no
documents), `missing_pdf` (a current CV or letter lacks its PDF), `unreviewed`,
`blocked` (an unresolved blocking requirement), `reviewed` (every check passes,
not marked ready) or `ready` (the stored step: marked ready with `ready_at` and
`ready_by`, and every check still passes); filter with `readiness` to find each
group. Read the ready queue with `readiness: "ready"` and `sort: "ready"`
(longest waiting first); the list's `ready_count` is its size. Readiness does not
check content, sources or staleness. For each Draft, read its current CV and
letter leaves, files and review state, its `requirements` and its job posting.
Classify:

- **ready**: marked ready, and both current leaves still have checked PDFs, exact
  sources and approved review;
- **reviewed, not marked**: the checks pass but nobody judged the Draft complete;
  report it, and mark it ready (`application_ready`) only after the full
  [Prepare Shortlist](../prepare-shortlist/SKILL.md) readiness checks;
- **incomplete**: a document, file or review step is missing;
- **blocked**: an employer requirement or open question needs the owner;
- **stale**: the frozen context predates a relevant Profile, Career or template
  change (`applications_staleness` lists these with the changed inputs), or the
  posting changed after preparation;
- **expired**: the posting is closed or past its deadline.

Check stale and expired cases against current records before reporting them.
A ready Draft that is stale or expired stays in the owner's queue until someone
acts: report it first, and clear the mark (`application_ready` with
`ready: false`) when the owner should not apply with the current documents.
An `application_ready_cleared` event in `application_history` gives the reason a
Draft left the queue.

## Prioritize Drafts

Order ready Drafts for the owner: live deadlines first, then fit with the
policy's decision items, then posting age. `sort: "deadline"` and `sort: "priority"` list
dated or prioritized attempts first, combined with `readiness: "ready"`. Give one line per Draft with the reason.
Do not invent deadlines; mark unknown ones as unknown. Record a deadline the
posting or owner states, and an owner-agreed `priority`, on the application.

## Follow-ups and outcomes

For Applied and Interview stages, report the time since the last recorded event
and postings that disappeared. Suggest follow-ups; never send them.

When the owner reports a submission, interview, offer, rejection or withdrawal,
record it with the current operation and expected version, with the date the
owner gives. Use Closed with `not_pursued` only for the owner's or an authorized
decision not to continue, never for an employer rejection.

## Patterns

When enough outcomes exist, summarize employer responses (interview, offer,
rejection, no reply) by role type, seniority, location and source, with counts.
Do not read Drafts the owner closed without applying as preferences: the owner
applies to every feasible prepared Draft, and closures record feasibility. Present patterns as observations for the owner to weigh, not
as changes to the policy. Report using the shared
[run report](../openings-workspace/references/run-report.md).
