---
name: maintain-career
description: Maintain the Openings Career record - integrate new owner facts into entries, keep claims deduplicated and linked to evidence, and improve the MASTER and templates and propagate changes to Drafts, as standing maintenance under the operating mandate.
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

## Policy

The owner's rules and facts live in the policy (`policy_get`), not in Profile
metadata: `decision` (what to shortlist and dismiss), `eligibility` (facts
employers ask about), `writing` (document rules with scope `cv`, `letter` or
`all`) and `facts` (anything else the owner confirmed). Each section has its own
version; every write sends the current version of the section it changes.

- Add a rule or fact the owner stated with `policy_add`: a short label, the
  statement in the owner's words, a typed value when there is one (a number, a
  date, a list). Your item is a proposal until the owner confirms it in the
  dashboard under **Policy**; an agent token cannot call `policy_confirm`. Say
  in the report which items wait, and ask with `questions_ask` when a decision
  depends on one.
- After the upgrade to 0.19 the `facts` section holds the old Profile metadata,
  one unconfirmed item per key (`origin.source: "profile_metadata"`), and
  `decision` holds the old `preferences` and `roles` text. Sort them with the
  owner: split a block into single statements (`policy_add`), move an item to
  its section (`policy_move`), give it a label and a typed value
  (`policy_update`), and remove what is obsolete (`policy_remove`). The Profile
  keeps its copy until the owner removes it; do not delete it for them.
- Changing the content of a confirmed item makes it a proposal again. Change
  wording only when the owner asked for it or the fact changed.
- A decision item may carry a `rule` on a collection signal. Propose it with
  `enabled` left false: only the owner enables a rule, and no rule is applied
  at collection yet.

Keep the Profile for who the owner is: name, contact, headline, summary and
links. Keep rules of one document layout in its template (`rules.statements`
beside the typed limits). Remove a rule from one place when it is moved to the
other.

## Claim hygiene

Compare claims within and across entries. Merge exact duplicates unless they
serve distinct template slots; correct claims that exceed their entry's evidence;
keep each claim attached to the entry where the work occurred, with source
links in metadata. Selection is typed, not metadata: `default_in_cv` (in the CV
unless the job gives a reason to leave it out), `role` (`core` carries the
account, `supporting` is used when the job calls for it, `bench` is kept in
reserve) and `group` (a free short name for claims that belong together). Move
selection values an earlier run wrote into metadata to these fields. New claims must follow from recorded evidence; ask the owner
for any new fact.

## MASTER and template changes

Change the canonical MASTER or a template when it makes applications stronger,
and record why. Compile and check the
full PDF and extracted text, then update the template source, rules, guidance and
assets together with the expected version.

Existing Drafts keep their frozen contexts. After the change, list stale Drafts
with `applications_staleness` (REST `GET /staleness`); each report names the
changed Profile, guidance, template, entry or claim and the affected revisions.
Contexts prepared since 0.19 also record the policy section versions they froze.
Propagate the change to Drafts the owner has not yet submitted when it improves
them: prepare a new context with the same deliberate selections, save new
revisions linked with `previous_id`, check them like new work, keep earlier
revisions and report each updated Draft. Re-run `application_staleness` to confirm
the new leaves are current. Leave a Draft stale when the change does not matter to
it, and say so in the report.

Report with the shared [run report](../openings-workspace/references/run-report.md),
listing every record version changed.
