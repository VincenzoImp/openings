---
name: prepare-interview
title: Prepare for an interview
summary: Your agent saves an interview brief on the application, with stories from your record and likely questions, then a debrief after the interview.
example: I have an interview with Northstar Labs on Monday, help me prepare.
description: Prepare the owner for an interview or recruiter call on an Openings application, and follow it up, as in "prepare me for the interview with X", "here is how the interview went". Builds a brief from the posting, what the employer received and the career entries, and saves it as a note.
---

# Prepare for an interview

Read [openings](../openings/SKILL.md) first.

## Read

- The application with `applications_get`: its replies, notes, form answers
  and the CV and letter the employer received (`documents_get` for their text).
- The posting with `jobs_get`.
- `workspace_context` with the full career; `career_get` for the entries the
  documents cite.

Ask for the format, the interviewers and the stage when they matter and are
unknown. When the owner reports the invitation itself, record it as
[track-applications](../track-applications/SKILL.md) describes.

## Brief

1. **What they need**: the three to five main needs of the role.
2. **Stories**: for each need, one or two examples from the record: the
   situation, what the owner did, a choice they made, the result. Match what
   the CV, letter and answers already say; keep personal and team work apart.
3. **Likely questions**: technical, behavioral and motivation, each with a
   short outline that points to a story.
4. **Weak spots**: requirements the record does not cover, with an honest
   bridge from related work. Never coach the owner to claim experience they
   do not have.
5. **Logistics**: availability, notice and work permit from Facts about me;
   the posting's pay band, if any, beside the owner's salary policy.
6. **Questions to ask**: specific to the team, product and role.

Use public information about the company only from sources the owner can
check, with links.

## Save

Give the brief in chat, then save it as a note on the application. Pin it only
when the owner asks, since the pinned note is their guidance.

## After the interview

Save the owner's debrief as a note: questions asked, names, next steps. Draft
a short thank-you for them to send, if they want one. Record the next round or
an offer as a reply.

## Report back

The brief itself, the questions you need answered, and that the note is saved
on the application.
