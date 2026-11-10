---
name: manage-sources
description: Review and tune Openings collection sources by measuring what each source contributes to kept jobs and applications, then add, tune or retire searches, monitored companies, filters and schedules as standing work under the operating mandate.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Manage sources

Use this workflow to keep collection effective: measure quality, add or tune
searches, add companies worth monitoring, and reduce Inbox noise. It is standing
work under the [operating mandate](../openings-workspace/references/operating-mandate.md). Never change sources as a side
effect of triage or preparation; record each change and its reason.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, source
schemas, provider limits and optimistic versions. Read the current Profile and
its decision policy: they define what a useful job is. Keep no personal search
criteria in this skill.

## Measure before changing

For each source, read its configuration, schedule, last runs and errors. Measure
yield from server data over a stated period: jobs collected, saved, dismissed,
still in Inbox, and jobs that reached an application. Separate history from the
current filters: jobs collected before a filter change do not describe it.

Dismissals were made by agents applying the Profile policy, so a high dismissal
rate measures collected text outside that policy, not the owner's taste. Drafts
the owner closed without applying are not preference evidence either: postings
close or become unfeasible. Derive every filter from the Profile and Career
records, and use dismissed titles only to find recurring clear mismatches
(unrelated domains, sales, roles the policy excludes). Check each candidate term
against saved jobs so a filter never removes work the policy includes.

## Tune

Prefer the narrowest change that removes a measured, recurring mismatch:

- a more specific query or location for keyword searches;
- excluded title terms (whole words) for recurring unrelated roles, when the
  service supports them, checked against the saved sample;
- include-only title terms for company boards with many unrelated departments;
- a company board source for an employer that appears repeatedly among saved jobs,
  or that the Profile and Career evidence make a strong target.

Read the current source schemas before writing; a source's service is fixed after
creation. Preserve omitted configuration and use expected versions. Use a run
override or preview to test a change before saving it when the service allows.
Do not disable a source only because its yield is low when it is cheap and
targeted. Excluding a term removes jobs before any agent reads them, so prefer
terms with no ambiguous technical use and leave borderline titles to triage.

## Report

List each changed source with before/after configuration and the measurement that
justified it. Use the shared
[run report](../openings-workspace/references/run-report.md). Re-measure after
the next collection cycles before tuning the same source again.
