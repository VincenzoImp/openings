---
name: manage-sources
title: Manage job sources
summary: Have searches, company boards and feeds added, previewed, tuned or paused so new jobs fit what you want.
example: Follow Northstar Labs' job board and add a search for data engineer jobs in Zurich.
description: Add, tune, pause and review Openings job sources - "add a search for...", "follow company X", "why so much noise from Y?", "which sources work?". Previews every new source before saving and measures sources by what they bring.
---

# Manage job sources

Read [openings](../openings/SKILL.md) first and call `workspace_context`:
What I'm looking for and What I rule out define a useful job.

## Add a source

1. `collection_get` with the source kinds: what each kind needs (a search
   query and place, a company's board, a feed URL). For a company, find its
   careers page and use its board kind when one matches; otherwise a search.
2. Preview it with `sources_run`: nothing is stored. Read the sample against
   the Preferences: how many would the owner want? Narrow the query, place or
   title filters until most are relevant, without excluding jobs they want.
3. Save it with `sources_save`, enabled, on a daily schedule unless the owner
   says otherwise. Add several in one batch and check every item.
4. Run it once with `sources_run` when the owner wants results now.

One query and one place per search; split "Zurich or Basel" into two.

## Tune a noisy source

1. `sources_list` gives each source's counts: found, shortlisted, applied,
   replied. Judge a source only after it has found enough jobs.
2. Read why its jobs were dismissed: `jobs_list` of dismissed jobs, narrowed
   to its site or company, shows each dismissal reason. A recurring, clear
   mismatch (another field, a ruled out title or language) is worth a filter;
   a varied mix is triage's job.
3. Prefer the narrowest fix: a more specific query or place, or excluded
   title words checked against the shortlisted jobs so none would be lost.
   Preview the change before saving.
4. Pause a source that brings nothing useful; delete one only when the owner
   asks.

## Failures

`collection_get` lists failing sources and `sources_get` their recent errors.
Provider limits and cooldowns are protective: wait them out rather than
raising them. Retry a failed fetch with `collection_update` once the cause is
fixed. Turn collection off only when the owner asks.

## Report back

In chat: each source added, changed or paused, with what its preview or
counts showed; failures and their causes; what you suggest next, such as a
company worth following.
