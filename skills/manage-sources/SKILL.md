---
name: manage-sources
title: Manage job sources
summary: Your agent adds, previews, tunes and pauses your searches, company boards and feeds so new jobs fit what you want.
example: Follow Northstar Labs' job board and add a search for data engineer jobs in Berlin.
description: Add, tune, pause and review Openings job sources, as in "add a search for...", "follow company X", "why so much noise from Y?", "which sources work?", "which companies should I follow?". Previews every change before saving and measures each source by what it brings.
---

# Manage job sources

Read [openings](../openings/SKILL.md) first and call `workspace_context`:
What I'm looking for and What I rule out define a useful job.

## Add a source

1. `collection_get` with the source kinds: the fields each needs. For a
   company, find its careers page and use its board kind when one matches;
   otherwise a search. A search takes query, location, country (required with
   Indeed or Glassdoor), providers, results_wanted (up to 50), hours_old,
   is_remote and job_type. One query and one place per search: split "Berlin
   or Munich" into two.
2. Preview it with `sources_run`: nothing is stored. Read the sample against
   the Preferences: how many would the owner want? Narrow the query, place or
   title filters until most are relevant, without excluding jobs they want.
3. Save it with `sources_save` and enabled true: a new source is saved paused
   without it. Schedule: interval (every 1,440 minutes unless the owner says)
   or daily with times and a timezone. Keep hours_old at or above the
   interval in hours (24 for a day), so nothing falls between checks. When
   the owner runs a scheduled agent, set the source times before it. Add
   several in one batch and check every item.
4. Run it once with `sources_run` when the owner wants results now.

## Tune a noisy source

1. `sources_list` gives each source's counts: found, shortlisted, applied,
   replied. Judge a source only after it has found enough jobs.
2. Read its dismissal reasons: `jobs_list` with source_id and triage
   dismissed. A recurring, clear mismatch (another field, a ruled out title or
   language) is worth a filter; a varied mix is triage's job.
3. Draft the narrowest fix: a more specific query or place, excluded title
   words, or excluded companies for agencies and aggregators that triage
   keeps dismissing. Check it against that source's shortlisted jobs, so none
   would be lost.
4. Preview the change with `sources_run`, save it with `sources_save` and the
   source's version, and tell the owner what changed and why.
5. Pause a source that brings nothing useful; delete one only when the owner
   asks.

## Companies to watch

Employers the owner shortlisted or applied to, or named, that have no board
source: find their careers page, preview its board kind and propose following
it.

## Failures

`collection_get` lists failing sources and `sources_get` their recent errors.
Provider limits and cooldowns are protective: wait them out rather than
raising or lifting them, unless the owner asks. Retry a failed fetch with
`collection_update` once the cause is fixed. Turn collection off only when the
owner asks.

## Report back

Each source added, changed or paused, with what its preview or counts showed;
failures and their causes; companies worth following.
