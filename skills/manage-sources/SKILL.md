---
name: manage-sources
description: Review and tune Openings collection sources by measuring what each source contributes to kept jobs and applications, then add, tune or retire searches, monitored companies, filters and schedules as standing work under the operating mandate.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Manage sources

Use this workflow to keep collection effective: measure quality, add or tune
searches, add companies worth monitoring, and reduce noise among New jobs. It is standing
work under the [operating mandate](../openings-workspace/references/operating-mandate.md). Never change sources as a side
effect of triage or preparation; record each change and its reason.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, source
schemas, provider limits and optimistic versions. Read the current Profile and
the owner's Preferences (`preferences_get`), above all What I'm looking for and
What I rule out: they define what a useful job is. Keep no personal search
criteria in this skill.

## Run and questions

Open a run before the first write: `runs_start` with `workflow: "manage-sources"` and the scope; writes made
with this token then attach to the run. First read the owner's answers given
since the previous run (`questions_list` with `answered_since`) and act on them.
Then read the owner's open requests (`requests_list` with `state: "open"`): take
the ones in this workflow's scope (`requests_take`), do the work, and report on
each with `requests_complete` and a short result, or `requests_decline` and the
reason. Leave requests for other workflows open. A request never authorises
submitting an application, contacting an employer or recording Applied.
Ask each new question as a record tied to its job, application or Career entry
(`questions_ask`), not only in chat. Close the run with `runs_finish` and the
stored [run report](../openings-workspace/references/run-report.md).

## Measure before changing

For each source, read its configuration, schedule, last runs and errors. Measure
yield with `sources_yield` (REST `GET /collection/yield`) over a stated
period (`since`, `until`): per source and per search, the jobs it collected
first, still to review, shortlisted, applied to, answered by an employer
(replies, interviews, offers), dismissed by an agent, the owner or other, likely duplicates and postings no longer listed; searches are also
split by job board (`providers`). Each job counts once, for the source that
found it first, so a search whose jobs are mostly `likely_duplicates` of other
sources adds little. `kept_rate` is withheld below `min_sample` collected jobs:
do not judge a small source on it. Separate history from the current filters:
jobs collected before a filter change do not describe it, so set `since` to the
change when you re-measure.

Dismissals were made by agents applying the Preferences, so a high dismissal
rate measures collected text outside them, not the owner's taste. A source
whose jobs mostly require languages the owner does not speak (`jobs_list` with
`hide_unspoken_required` reports the count) is better narrowed by place or
language, so that collection stops paying for them. Applications
the owner closed without applying are not preference evidence either: postings
close or become unfeasible. Derive every filter from the Preferences and Career
records, and use dismissed titles only to find recurring clear mismatches
(unrelated domains, sales, roles the owner rules out). Check each candidate term
against shortlisted jobs so a filter never removes work the owner is looking for.

## Tune

Prefer the narrowest change that removes a measured, recurring mismatch:

- a more specific query or location for keyword searches;
- excluded title terms (whole words) for recurring unrelated roles, when the
  service supports them, checked against the shortlisted sample;
- include-only title terms for company boards with many unrelated departments;
- a company board source for an employer that appears repeatedly among shortlisted jobs,
  or that the Profile and Career evidence make a strong target.

Read the current source schemas before writing; a source's service is fixed after
creation. Preserve omitted configuration and use expected versions. Use a run
override or preview to test a change before saving it when the service allows.
Do not disable a source only because its yield is low when it is cheap and
targeted. Excluding a term removes jobs before any agent reads them, so prefer
terms with no ambiguous technical use and leave borderline titles to triage.

## Report

List each changed source with before/after configuration and the yield that
justified it (period, collected, shortlisted, applied, replies). Use the shared
[run report](../openings-workspace/references/run-report.md). Re-measure after
the next collection cycles before tuning the same source again.
