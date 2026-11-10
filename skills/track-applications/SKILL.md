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

## Read the pipeline

List applications by stage with complete pagination. For each Draft, read its
current CV and letter leaves, files and review state, and its job posting. Classify:

- **ready**: both current leaves have checked PDFs, exact sources and approved review;
- **incomplete**: a document, file or review step is missing;
- **blocked**: an employer requirement or open question needs the owner;
- **stale**: the frozen context predates a relevant Profile, Career or template
  change, or the posting changed after preparation;
- **expired**: the posting is closed or past its deadline.

Check stale and expired cases against current records before reporting them.

## Prioritize Drafts

Order ready Drafts for the owner: live deadlines first, then fit with the Profile
decision policy, then posting age. Give one line per Draft with the reason.
Do not invent deadlines; mark unknown ones as unknown.

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
as changes to the Profile policy. Report using the shared
[run report](../openings-workspace/references/run-report.md).
