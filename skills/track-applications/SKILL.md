---
name: track-applications
title: Track your applications
summary: Tell your agent what happened - a reply, an interview, a rejection - and see what is waiting on you or an employer.
example: Northstar Labs replied, they want an interview on Monday.
description: Record and review the progress of Openings applications - "X replied", "I applied to Y", "I got rejected by Z", "what's waiting?", "what's due this week?", "close the ones that never answered", "draft a follow-up", "I accepted an offer". Records what the owner reports, or what a source they named shows.
---

# Track your applications

Read [openings](../openings/SKILL.md) first and call `workspace_context`. You
record what the owner tells you; you never learn an outcome from silence and
never contact anyone.

## Find the application

Search `applications_list` by company or title (company is an exact name).
When more than one matches, or the job has a Closed attempt and an open one,
ask which. A job with no application: start one with `applications_create`
only when the owner says they applied to it.

## Record what happened

Use `applications_update`; the date is the one the owner gives, else today.

- **"I applied"**: stage applied with applied_on, the day they sent it.
- **A reply** (an interview invitation, an offer, a rejection, or other, such
  as a request for references): the reply with its kind, date and a short note
  in the owner's words. It moves the stage itself: interview moves Applied to
  Interview; offer moves Applied or Interview to Offer; rejection closes as
  rejected; other never moves; any of them reopens a close as no response.
- **A reply on an application not yet recorded as sent**: the owner's report
  says they sent it. In one call, first an item with stage applied and
  applied_on (ask the day if unknown), then an item with the reply. Items
  apply in order.
- **A mistake in a reply**: correct or delete it with reply_fix.
- **Applied by mistake**: stage shortlisted, while there is no reply.
- **"I won't pursue it"**: close as not pursued. A rejection is a reply.
- **Reopen** a Closed application with the stage it had.
- Interviewer names and next steps go in a note on the application.

## Evidence from the owner's sources

When Working with me names a source of the owner's, such as their mailbox, you
may record Applied and replies from it: the employer's own confirmation or
answer, naming this job, with its date, and a note saying where it came from.
Never from silence, from Ready, or from a message about another job.

## What's waiting

Read the counts, then `applications_list`:

- **Waiting on the owner**: Ready applications; Shortlisted ones blocked by a
  requirement only they can resolve.
- **Deadlines**: has_deadline true, deadline_until today + 7, soonest first.
  A passed deadline on a Shortlisted application: ask, or close it as not
  pursued when Working with me says to.
- **Waiting on employers**: Applied and Interview, with days since sending and
  the last reply.
- **Overdue**: needs reply_overdue. Close them as no response when the owner
  asks or Working with me says to; otherwise list them and ask. An Interview
  or Offer rarely ends in silence: ask before closing one as no response.

## Follow-ups

To chase an overdue application, draft a short follow-up from the application
and its documents and save it as an unpinned note for the owner to send. You
never send it.

## An accepted offer

Close the application as accepted. When the owner asks, close the other open
applications as not pursued, and pause the sources or turn collection off
with `collection_update`.

For "how is it going", `stats_get` gives reply and interview rates; with only
a few applications give counts, not percentages.

## Report back

What you recorded and from where, with each application's stage now; what
waits on the owner, deadlines first; overdue applications, with the question
whether to close them; follow-ups drafted.
