---
name: track-applications
description: Review the Openings application pipeline - what is Ready and its priority, expired postings, follow-ups, employer replies, no-reply closures and stats - and record owner-reported progress without submitting anything.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Track applications

Use this workflow to keep the pipeline in order: what to apply to next, which
Shortlisted applications need work, and progress the owner reports. A status request is read-only.
The owner submits applications, contacts employers and records Applied; this
workflow records a stage or outcome only when the owner reports that fact.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, schemas,
application history and versions. Closing an application never changes its
job's triage.

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

List applications by stage with complete pagination; `stage_counts` gives the
size of each stage, `ready` included. Ready is computed: a Shortlisted
application is `ready` when every document in its `required_documents` has a
current complete revision (its PDF stored) and no blocking requirement is
unresolved; otherwise `missing` names what is left (`cv`, `letter`,
`requirement:<id>`). Read the Ready ones with `stage: "ready"` and the ones
missing a document with `needs: "documents"`. Ready does not check content,
sources or later changes to the records. For each Shortlisted application, read its current CV and
letter leaves and files, its `requirements` and its job posting. Classify:

- **ready**: Ready, and the current leaves still pass the
  [Prepare Shortlist](../prepare-shortlist/SKILL.md) checks;
- **incomplete**: a required document or its PDF is missing;
- **blocked**: an employer requirement or open question needs the owner;
- **expired**: the posting is closed or past its deadline.

Check expired cases against current records before reporting them.
A Ready application that is expired stays Ready until someone acts:
report it first, so the owner does not apply with the current documents by
mistake. The application's timeline (`timeline_get` with `application_id`)
holds its notes and its job's; read the pinned note first, it is the owner's
standing guidance for that application.

## Prioritize Ready applications

Order Ready applications for the owner: live deadlines first, then fit with
What I'm looking for in the owner's Preferences, then posting age. `sort: "deadline"` and `sort: "priority"` list
dated or prioritized attempts first, combined with `stage: "ready"`. Give one line per application with the reason.
Do not invent deadlines; mark unknown ones as unknown. Record a deadline the
posting or owner states, and an owner-agreed `priority`, on the application.

## Follow-ups and outcomes

For Applied and Interview stages, report the time since the sent date and the
last recorded reply (`last_reply` in the list), and postings that
disappeared. Suggest follow-ups; never send them.

Record only outcomes the owner reported: never infer one from silence, mail or a
portal. Mark applied is the owner's act: record `status: "applied"` (with
`applied_at`, now by default) only when the owner says they sent the
application. When the owner reports an employer's answer, record it with the
day it arrived, in one `applications_update` with the current
`expected_version`:

- a reply: `reply: {kind, date, note}` with `kind` `interview`, `offer`,
  `rejection` or `other` (such as a request for references). It moves the stage
  itself (`interview` to Interview, `offer` to Offer, `rejection` closes as
  rejected, `other` leaves it); do not pass `status` with it;
- a mistaken record: `reply: {id, kind?, date?, note?}` to correct it or
  `reply: {id, remove: true}` to remove it; a correction never moves the stage.

Use Closed with `not_pursued` only for the owner's or an authorized decision not
to continue, never for an employer rejection.

## No reply

`applications_list` with `needs: "reply_overdue"` lists Applied applications
without a reply sent longer ago than the no-reply period; the result's
`no_reply` gives the period's `days` and its `source` (`settings`, the owner's
`no_reply_days`, or `default`, 30 days). Report them with their sent dates and
propose closing them as no reply. Close them (`applications_update` or
`applications_bulk` with `outcome: "no_response"` and `concluded_on`, today
when omitted) only when the owner asks or Working with me in the owner's
Preferences says to; otherwise ask with one `questions_ask` that lists them.
Nothing closes automatically. Never close an Interview or Offer as no reply.

## Patterns

Read `stats_get` (period `90d`, `12m` or `all`) for employer replies: the
applications sent, reply and interview rates, the median days to a first reply,
the funnel and, once two sources have five sent applications each, replies by
source. With few applications report the counts, not a rate. Applications never
sent do not count; dismissed jobs never had an application. Do not read
applications the owner closed without applying as preferences: the owner applies
to every feasible prepared application, and closures record feasibility.
Present patterns as observations for the owner to weigh, not as changes to
the Preferences. Report using the shared
[run report](../openings-workspace/references/run-report.md).
