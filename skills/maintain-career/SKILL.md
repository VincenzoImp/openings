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

## Integrate new facts

Ask focused questions for missing facts that matter; never invent one. Put each
confirmed fact into the relevant existing passage of the entry where the work
happened. Keep dates, contribution scope, maturity and source confidence, with
provenance in metadata rather than dated appendices. Use import preview before
an import, and inspect every created or changed record.

Keep the Profile for career direction, preferences, dated personal facts and a
decision policy. Keep document rules in templates. Remove a rule from one place
when it is moved to the other.

## Claim hygiene

Compare claims within and across entries. Merge exact duplicates unless they
serve distinct template slots; correct claims that exceed their entry's evidence;
keep each claim attached to the entry where the work occurred, with source
links in metadata. New claims must follow from recorded evidence; ask the owner
for any new fact.

## MASTER and template changes

Change the canonical MASTER or a template when it makes applications stronger,
and record why. Compile and check the
full PDF and extracted text, then update the template source, rules, guidance and
assets together with the expected version.

Existing Drafts keep their frozen contexts. After the change, list stale Drafts
with `applications_staleness` (REST `GET /staleness`); each report names the
changed Profile, guidance, template, entry or claim and the affected revisions.
Propagate the change to Drafts the owner has not yet submitted when it improves
them: prepare a new context with the same deliberate selections, save new
revisions linked with `previous_id`, check them like new work, keep earlier
revisions and report each updated Draft. Re-run `application_staleness` to confirm
the new leaves are current. Leave a Draft stale when the change does not matter to
it, and say so in the report.

Report with the shared [run report](../openings-workspace/references/run-report.md),
listing every record version changed.
