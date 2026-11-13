---
name: track-applications
description: Review the Openings application pipeline - Draft readiness and priority, stale or expired postings, follow-ups, employer responses, no-reply closures and outcome insights - and record owner-reported progress without submitting anything.
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
  report it, and mark it ready (`applications_ready`) only after the full
  [Prepare Shortlist](../prepare-shortlist/SKILL.md) readiness checks;
- **incomplete**: a document, file or review step is missing;
- **blocked**: an employer requirement or open question needs the owner;
- **stale**: the frozen context predates a change to a part its documents use:
  the Profile header or summary, a Facts about me or Writing rules statement, a
  template or Career (`staleness_list` names each changed part), or the
  posting changed after preparation;
- **expired**: the posting is closed or past its deadline.

Check stale and expired cases against current records before reporting them.
A ready Draft that is stale or expired stays in the owner's queue until someone
acts: report it first, and clear the mark (`applications_ready` with
`ready: false`) when the owner should not apply with the current documents.
An `application_ready_cleared` event in the application's timeline
(`timeline_get` with `application_id`) gives the reason a Draft left the queue.
The timeline also holds the application's notes and its job's; read the pinned
note first, it is the owner's standing guidance for that application.

## Prioritize Drafts

Order ready Drafts for the owner: live deadlines first, then fit with
What I'm looking for in the owner's Preferences, then posting age. `sort: "deadline"` and `sort: "priority"` list
dated or prioritized attempts first, combined with `readiness: "ready"`. Give one line per Draft with the reason.
Do not invent deadlines; mark unknown ones as unknown. Record a deadline the
posting or owner states, and an owner-agreed `priority`, on the application.

## Follow-ups and outcomes

For Applied and Interview stages, report the time since the sent date and the
last recorded response (`last_response` in the list), and postings that
disappeared. Suggest follow-ups; never send them.

Record only outcomes the owner reported: never infer one from silence, mail or a
portal. When the owner reports a submission, record Applied with `applied_at`.
When the owner reports an employer's answer, record it with the day it arrived:

- an interview, offer or rejection: `applications_update` with the stage
  (`interview`, `offer`, or `closed` with `outcome: "rejected"`), the current
  `expected_version` and `response_date`; the matching response is recorded
  with it. A second interview while already in Interview, or another answer
  such as a request for references, is `responses_create` with `kind`
  (`interview` or `other`), `date`, a short `note` and an `idempotency_key`;
- a mistaken record: `responses_update` or `responses_delete` with the
  response's `expected_version`.

Use Closed with `not_pursued` only for the owner's or an authorized decision not
to continue, never for an employer rejection.

## No reply

`applications_list` with `no_reply_due: true` lists Applied applications sent
longer ago than the no-reply period; the result's `no_reply` gives the period's
`days` and its `source` (`settings`, the owner's `no_reply_days`, or
`default`, 30 days). Report them with their sent dates and propose
closing them as no reply. Close them (`applications_update` or
`applications_bulk` with `outcome: "no_response"` and `concluded_on`, today
when omitted) only when the owner asks or Working with me in the owner's
Preferences says to; otherwise ask with one `questions_ask` that lists them. Never close an
Interview or Offer as no reply.

## Patterns

Read `insights_get` for employer answers: response, interview and offer rates,
the median days to a first answer, and groups by role family, seniority,
location, source kind, named source and month. A group below `min_sample`
(default 5) has `withheld` instead of a rate: report its counts, never a rate
computed from them, and do not lower `min_sample` to make a point. Drafts never
sent are counted apart in `excluded`; dismissed jobs never had an application.
Do not read Drafts the owner closed without applying as preferences: the owner
applies to every feasible prepared Draft, and closures record feasibility.
Present patterns as observations for the owner to weigh, not as changes to
the Preferences. Report using the shared
[run report](../openings-workspace/references/run-report.md).
