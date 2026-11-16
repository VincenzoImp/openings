---
name: run-job-search
title: Run my job search
summary: Have new jobs triaged, the shortlist prepared to Ready and ranked, deadlines and replies checked and a short report written, on request or on a schedule.
example: Go through my new jobs and get everything Ready.
description: Run the whole Openings routine end to end - "run my job search", "empty my inbox", "get everything Ready", "do the daily run", "weekly report", "run this every morning". Checks collection, triages, prepares, ranks, watches deadlines and replies, and reports; also on a schedule in the owner's own harness.
---

# Run my job search

Read [openings](../openings/SKILL.md) first, with its "Runs without the
owner". This skill chains the others; each step follows its own skill.
Working with me says which steps the owner wants, the limits (such as how many
to prepare per run) and what needs their yes.

## 1. Check

- `workspace_context`: counts, Preferences and feedback; apply the feedback
  before anything else.
- `collection_get`: whether collection is on and which sources fail. Report
  failures; fix them only as [manage-sources](../manage-sources/SKILL.md)
  says.

## 2. Triage

Follow [triage-jobs](../triage-jobs/SKILL.md) for every new job, with a
priority on each shortlist.

## 3. Prepare

`applications_list` with needs documents, sort priority. Follow
[prepare-applications](../prepare-applications/SKILL.md) for each, up to the
run's limit. One you cannot finish keeps its state, with an unpinned note
giving the reason (key from the application, so a second run adds none).

## 4. Rank and check the queue

Follow [review-applications](../review-applications/SKILL.md): priorities,
postings that closed, employer caps, and deadlines in the next 7 days
(`applications_list` has_deadline, deadline_until).

## 5. Replies

`applications_list` with needs reply_overdue. Close them as no response only
under a standing instruction; otherwise list them. Nothing is learned from
silence.

## Report back

Five to ten lines:

- counts per step: triaged, shortlisted, dismissed, prepared, closed;
- the Ready list to apply to, best first (priority, then deadline), with
  deadlines;
- questions for the owner, each with the item it holds back;
- failures, and what stayed unchanged.

An item you could not decide stays as it was and appears in the questions.

## Weekly report

On request or on a weekly schedule, for the last 7 days:

- in: `jobs_list` with created_since and counts;
- decided: shortlisted and dismissed, the top dismissal reasons;
- sent and answered: `applications_list` applied_since; replies from
  `changes_list` kind reply_added; `stats_get` for the rates (counts when few);
- due: deadlines in the next 14 days and overdue replies;
- sources: `sources_list` counts, new failures, a source that brought nothing
  useful;
- what agents did: `changes_list` with actor agent and since;
- lessons: Preference lines proposed from the owner's corrections, as
  [maintain-career](../maintain-career/SKILL.md) says.

## Scheduled runs

The server collects on each source's schedule; the agent runs in the owner's
own harness on their machine. To set one up with the owner:

1. Pick times after collection (the sources' daily times and timezone).
2. The harness starts the client headless in the agent's folder with a short
   prompt, such as "Run my job search with the run-job-search skill": cron,
   launchd or systemd running the client's non-interactive mode, or the
   client's own local scheduled tasks. A cloud scheduler reaches the server
   only at a public URL.
3. One Agent token per scheduled agent, named for it, in the harness's
   environment; never in the prompt or a file.
4. Pre-approve only what the run needs: the Openings tools, `curl` and the TeX
   engine. Never overlap two runs of one token.
5. Record the schedule, what it may do and where the report goes as Working
   with me lines, with the owner's yes; then do one run while they watch.

A run can also take a backup kept elsewhere, as
[maintain-workspace](../maintain-workspace/SKILL.md) says. The owner's guide
to working with an agent has ready recipes.
