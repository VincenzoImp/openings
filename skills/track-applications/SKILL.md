---
name: track-applications
title: Track your applications
summary: Tell your agent what happened - a reply, an interview, a rejection - and see what is waiting on you or an employer.
example: Northstar Labs replied, they want an interview on Monday.
description: Record and review the progress of Openings applications - "X replied", "I applied to Y", "I got rejected by Z", "track my applications", "what's waiting?", "close the ones that never answered". Records only what the owner reports.
---

# Track your applications

Read [openings](../openings/SKILL.md) first. You record what the owner tells
you; you never learn an outcome from silence and never contact anyone.

## Find the application

Search `applications_list` by company or title. When more than one matches,
or the job has a Closed attempt and an open one, ask which. A job with no
application yet: start one with `applications_create` only when the owner
says they applied to it.

## Record what happened

Use `applications_update`; the date is the one the owner gives, today
otherwise.

- **"I applied"**: set Applied with the day they sent it.
- **A reply** (interview invitation, offer, rejection, or anything else such
  as a request for references): record it as a reply with a short note in the
  owner's words. A reply moves the stage by itself; do not set the stage too.
- **A mistake in a recorded reply**: correct or delete that reply.
- **"I won't pursue it"**: close it as not pursued. An employer's rejection is
  a reply, not this.
- Details worth keeping (interviewer names, next steps) go in a note on the
  application.

## What's waiting

Read `workspace_context` counts, then `applications_list`:

- **Waiting on the owner**: Ready applications, deadlines first; Shortlisted
  ones blocked by a requirement only they can resolve.
- **Waiting on employers**: Applied and Interview, with days since sending and
  the last reply.
- **Overdue**: Applied with no reply past the no-reply period.

Close overdue ones as no response only when the owner asks, or Working with
me says to. Otherwise list them and ask. Never close an Interview or Offer as
no response.

For "how is it going", `stats_get` gives reply and interview rates; with only
a few applications give counts, not percentages.

## Report back

In chat: what you recorded, with the stage each application is now in; what
waits on the owner, deadlines first; overdue applications and the question
whether to close them.
