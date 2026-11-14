---
name: maintain-career
description: Maintain the Openings Career record - integrate new owner facts into entries, keep claims deduplicated and linked to evidence, and improve the MASTER and templates and propagate changes to Shortlisted applications, as standing maintenance under the operating mandate.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Maintain Career

Use this workflow to add or correct career facts, clean up claims, and improve
the CV MASTER or letter template. It is standing work under the [operating
mandate](../openings-workspace/references/operating-mandate.md), done deliberately and never inside one application's
document preparation. Back up the workspace before a broad change.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, versions
and file transfers, and [Career claims](../career-claims/SKILL.md) for wording
and the integrated-account method.

## Run and questions

Open a run before the first write: `runs_start` with `workflow: "maintain-career"` and the scope; writes made
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

## Integrate new facts

Ask focused questions for missing facts that matter; never invent one. Put each
confirmed fact into the relevant existing passage of the entry where the work
happened. Keep dates, contribution scope, maturity and source confidence, with
provenance in metadata rather than dated appendices. Use import preview before
an import, and inspect every created or changed record.

## Preferences

The owner's preferences and facts live in Preferences (`preferences_get`), not
in Profile metadata, in the owner's own words: `looking_for` (what the owner is
looking for), `ruled_out` (what the owner rules out), `facts` (facts employers
ask about), `writing` (writing rules with scope `cv`, `letter` or `all`) and
`working_with_me` (instructions you follow). Each section has its own version.

- Record a preference or fact the owner stated with `preferences_update`: read
  the section, add the statement in the owner's words to its `items` and write
  the whole list back with the section's version. Change or remove a statement
  only when the owner asked for it or the fact changed.
- After the upgrades to 0.19, 0.23 and 0.24, statements copied from the old
  Profile metadata, preferences and target roles, the old general instructions
  and template rule statements (suffixed "(from template <name>)") sit in the
  sections; former proposals start with "(proposed by …, not confirmed)". Sort
  them with the owner: split a block into single statements,
  move a statement to its section (remove it from one, add it to the other) and
  remove what is obsolete. The Profile metadata keeps its copy until the owner
  removes it; do not delete it for them.
- Nothing in Preferences acts automatically: no job is dismissed by a
  statement. Apply them yourself when you review jobs and write documents.

Keep the Profile for who the owner is: name, contact, headline, summary and
links. Writing rules have one home, the `writing` section of Preferences
(scope `cv` or `letter` for one document); a template keeps its source, files,
guidance and typed limits.

## Claim hygiene

Compare claims within and across entries. Merge exact duplicates unless they
serve distinct template slots; correct claims that exceed their entry's evidence;
keep each claim attached to the entry where the work occurred, with source
links in metadata. `always_include` (★, in the CV unless the job gives a reason
to leave it out) is the one typed selection field; keep any other selection hint,
such as a role or a group, in metadata (0.24 moved the former `role` and `group`
fields there). New claims must follow from recorded evidence; ask the owner
for any new fact.

## MASTER and template changes

Change the canonical MASTER or a template when it makes applications stronger,
and record why. Compile and check the
full PDF and extracted text, then update the template source, rules, guidance and
assets together with the expected version.

Existing revisions never change. After the change, list Shortlisted applications
(`applications_list` with `stage: "shortlisted"`) and their current revisions
(`documents_list`), and find those whose documents use the changed Profile part,
Preferences statement, template, entry or claim (each revision names the
`claim_ids` and `knowledge_ids` it cites). Propagate the change to applications
the owner has not yet submitted when it improves them: read the live records
again, save new revisions linked with `previous_id`, check them like new work,
keep earlier revisions and report each updated application. Leave an
application unchanged when the change does not matter to it, and say so in the
report.

Report with the shared [run report](../openings-workspace/references/run-report.md),
listing every record version changed.
