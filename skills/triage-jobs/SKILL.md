---
name: triage-jobs
title: Go through new jobs
summary: Have your new jobs read against your Preferences and experience, then shortlisted or dismissed with a reason.
example: Empty my inbox using my criteria, and filter it really well.
description: Triage the Openings inbox of new jobs by the owner's Preferences and Career - "empty my inbox", "go through new jobs", "filter the inbox", "anything good today?". Shortlists clear fits, dismisses confirmed mismatches with a reason, resolves duplicates and asks about the rest.
---

# Go through new jobs

Read [openings](../openings/SKILL.md) first. Triage only: shortlisting starts
an application, but documents are
[prepare-applications](../prepare-applications/SKILL.md) work.

## 1. Know the criteria

Call `workspace_context`. Before reading any job, write down for yourself:

- **Dealbreakers** from What I rule out and Facts about me (work permit,
  places, languages, seniority, domains);
- **Must-haves and pluses** from What I'm looking for, and what the Career
  record shows the owner has done;
- **Lessons** from `feedback`: a restored dismissal means that reason was too
  strict, a closed application from your shortlist means that kind of job is
  not wanted;
- **Rules** from Working with me, such as asking before large dismissals.

Missing evidence of a skill is not proof the owner lacks it. Read a career
entry in full (`career_get`) when a decision turns on it.

## 2. Take the cohort

List the new jobs with `jobs_list`, with counts, and page through all of them
before writing, so your cohort does not move while you work. Note how many
there are and what the signals say (required languages, no longer listed,
likely duplicates).

## 3. Clear whole kinds of mismatch

Use the `jobs_list` filters to find groups that likely fail a dealbreaker: a
required language the owner does not speak, postings no longer listed, a ruled
out title or place. A signal is a lead, never a verdict: read each posting
(`jobs_get`, 20 at a time) and dismiss only when the text confirms it. A
posting written in another language does not by itself require it.

## 4. Read the rest

Read every remaining posting in full, 20 at a time, and decide each:

- **Shortlist**: it meets the must-haves, breaks no dealbreaker, and the
  owner's record makes a credible case. Be strict: the owner will get a CV and
  letter for each one.
- **Dismiss**: a concrete dealbreaker or a clear mismatch with what they want,
  stated in the posting. The reason is one sentence the owner reads beside the
  job: the fact and their preference, as in "Requires fluent German; you
  speak English and Italian" or "Sales role; you rule out non-engineering
  jobs".
- **Leave in the inbox and ask**: a plausible fit that depends on a fact you do
  not have, or a borderline case. Group these into a few questions.

Never decide from the title alone, and never dismiss to empty the list. A
posting without its full text cannot be judged: leave it and say so.

## 5. Write in batches

Send the decisions with `jobs_triage`, up to 200 at a time, and check every
item; a failed one stays where it was, so fix the cause or mention it. When
Working with me sets a limit, show the owner a sample first.

## 6. Duplicates

For each job you shortlist, and each likely duplicate, check the vacancy:

- The same vacancy: same employer and requisition or apply link, or the same
  title, place and duties in nearly the same text.
- Different: another requisition, level, city or team, or a reopened round
  months later. Same company and title alone prove nothing.

With `jobs_link`, merge a confirmed copy into the record that has the
application or history, or mark the pair different so the flag stops. When
unsure, leave both and ask.

## 7. Check the result

List the inbox again with counts. Call it empty only when that read says so;
mention jobs that arrived meanwhile.

## Report back

In chat: shortlisted, dismissed and left counts; the shortlisted jobs by title
and company with one line of fit each; the most common dismissal reasons; your
questions for the jobs left; anything a source keeps sending that
[manage-sources](../manage-sources/SKILL.md) could filter. Offer to prepare
the new shortlist.
