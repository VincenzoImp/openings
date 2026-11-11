---
name: prepare-interview
description: Prepare the owner for an interview on an Openings application - role analysis, evidence-backed stories, likely questions, gaps and questions to ask - kept as private notes on that application.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Prepare interview

Use this workflow when the owner asks to prepare for an interview or a recruiter
call. It writes preparation notes; it never contacts the employer or changes the
application stage unless the owner reports a new stage.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport and notes,
and [Career claims](../career-claims/SKILL.md) for evidence-led wording.

## Run and questions

Open a run before the first write: `runs_start` with `workflow: "prepare-interview"` and the scope; writes made
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

## Read the application as sent

Read the job posting, the application's current CV and letter leaves (the versions
the employer saw), their frozen context, the application note and events, the
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
5. **Logistics**: availability, work authorization and other dated Profile facts
   the owner may be asked about, as recorded, without inferring rights.
6. **Questions to ask**: specific to the team, product and role.

Use public company information only from sources the owner can verify; cite them.

## Save and report

Save the preparation as a note on the application, so it stays with that attempt.
Report the note ID and any open questions for the owner, using the shared
[run report](../openings-workspace/references/run-report.md).
