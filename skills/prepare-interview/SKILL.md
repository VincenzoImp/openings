---
name: prepare-interview
title: Prepare for an interview
summary: Get role analysis, evidence-backed stories, likely questions and questions to ask, saved on the application.
example: I have an interview next week for the backend role, help me prepare.
description: Prepare the owner for an interview on an Openings application - role analysis, evidence-backed stories, likely questions, gaps and questions to ask - kept as private notes on that application.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Prepare interview

Use this workflow when the owner asks to prepare for an interview or a recruiter
call. It writes preparation notes; it never contacts the employer or changes the
application stage unless the owner reports a new stage.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport and notes,
and [Career claims](../career-claims/SKILL.md) for evidence-led wording.

## Questions and report

Ask the owner in the chat when a missing fact matters, and never record an
answer the owner did not give. Report what you did in the chat.

## Read the application as sent

Read the job posting, the application's current CV and letter leaves (the versions
the employer saw) with the claims and Career entries they cite, the application's timeline
(`timeline_get` with `application_id`: its pinned note, other notes and events,
with its job's), the
current Profile and the relevant Career entries. Ask the owner for the interview
format, interviewers and stage when they are unknown and matter.

## Prepare

1. **Role needs**: the three to five main needs of the role, from the posting.
2. **Stories**: for each need, one or two examples from Career evidence: situation,
   the owner's own work, a technical choice and its result. Keep personal and team
   work distinct and match what the CV and letter already state.
3. **Likely questions**: technical, behavioural and motivation questions, with
   short answer outlines that point to the stories.
4. **Gaps**: requirements without supporting evidence, with an honest bridge from
   transferable work. Do not present a gap as experience.
5. **Logistics**: availability, work authorization and other Facts about me
   in the owner's Preferences that the owner may be asked about,
   as recorded, without inferring rights.
6. **Questions to ask**: specific to the team, product and role.

Use public company information only from sources the owner can verify; cite them.

## Save and report

Save the preparation as a note on the application (`notes_create` with
`application_id`), so it stays with that attempt. Do not pin it: the pinned note
is the owner's standing guidance.
Report the note ID and any open questions for the owner in the chat.
