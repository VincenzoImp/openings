---
name: setup-openings
title: Set up Openings
summary: Get Openings installed and connected, then onboard your Career, Preferences, templates and first searches.
example: Set up Openings for me and import my CV.
description: Install, connect and onboard an Openings workspace for its owner - Docker setup, agent connection, then career record, Profile and Preferences, CV and letter templates and first searches - so the other workflow skills can run the job search.
compatibility: Requires a machine with Docker Compose v2 for installation, or an existing Openings URL; see the openings-workspace skill for connection details.
---

# Set up Openings

Use this workflow when the owner wants to start using Openings, or when a
workspace exists but is not yet ready for the routine workflows. It ends when
the workspace has a career record, a Profile, Preferences, both templates and running
sources, and the owner knows their own part: apply to Drafts and mark them
Applied or close them.

Read [Openings workspace](../openings-workspace/SKILL.md) for connection and
versions, and the [operating mandate](../openings-workspace/references/operating-mandate.md).

## Install

Skip this section when the owner already has a reachable Openings URL.

1. Check Docker with Compose v2 on the target machine. Follow the repository's
   `docs/user/getting-started.md`: clone, `cp .env.example .env`, pull the pinned
   images and start with `docker compose up -d --no-build`.
2. For access from another device, set `OPENINGS_BIND`, `OPENINGS_PORT` and
   `OPENINGS_PUBLIC_URL` as that guide describes. Recommend HTTPS through a
   trusted reverse proxy across untrusted networks.
3. Check `docker compose ps` and `curl --fail <origin>/health`.
4. The owner chooses the owner password in the dashboard, or sets
   `OPENINGS_PASSWORD` in `.env` before the first start. Never choose, print or
   store the password yourself.

## Connect

The owner creates an **Agent** token in the dashboard's setup guide, which a new
workspace opens on, or in **Settings → Agent access**, and starts
the agent client with `OPENINGS_URL`, `OPENINGS_TOKEN` and, for a private
certificate authority, `OPENINGS_CA_FILE`. Recommend an agent token, not an owner
token: it runs every workflow and cannot change the owner password, manage
tokens or restore a backup. `workspace_info` reports the token in `actor`
(`owner` or `agent:<token name>`); when it is `owner`, tell the owner that
an agent token is enough. Never ask for the token in the conversation. Register the MCP
server at `<origin>/mcp` with the bearer header in the client's own configuration.
Confirm with `workspace_info`.

Suggest an operator workspace: copy the repository's
`examples/operator-workspace/`, run its `sync.py --url <origin>`, and start the
client through its `launch.py`. It states the operating mandate, generates MCP
configuration for common clients and keeps personal data out of Git.

Check the agent's own machine for `pdflatex` (and `pdftotext`/`pdfinfo` for
checks). Openings does not compile documents. If they are missing, propose a
user-level TeX distribution such as TinyTeX, install it with the owner's
agreement, and report PDF preparation as blocked until a compiler works.

## Questions and report

Ask the owner in the chat when a missing fact matters, and never record an
answer the owner did not give. Report what you did in the chat.

## Onboard the owner

To try the workflow before sharing personal data, import the repository's
synthetic `examples/career.json`, add the sections and settings of `examples/preferences.json` and use
`examples/resume.tex` and `examples/cover-letter.tex`; replace them with the
owner's records afterwards.

Work in this order; each step uses records the next ones need.

1. **Career record.** Ask for a current CV, LinkedIn export, publication list or
   plain description. Use `career_preview_import` before `career_import` and
   inspect every created entry. Then follow
   [Maintain Career](../maintain-career/SKILL.md): integrated descriptions, dates,
   personal versus team scope, approved claims. Ask focused questions for gaps.
2. **Profile and Preferences.** Fill the Profile's typed fields (name, contact,
   headline, summary, links). Ask about target roles, seniority, locations and
   remote work, work authorization, availability, languages, hard exclusions,
   how documents should read and how the owner wants you to work. Record each
   answer as one statement in the owner's words (`preferences_update`, which
   replaces a whole section with its version): what the owner wants in
   `looking_for`, hard exclusions in `ruled_out`, facts employers ask about in
   `facts`, document rules in `writing` with a scope, instructions for you in
   `working_with_me`. Set the spoken languages and, when the owner gives one,
   the no-reply period with `settings_update`. Tell the owner they can review
   and edit everything under **Preferences** in the dashboard. In a workspace
   upgraded from an earlier version, sort the copied statements first as
   [Maintain Career](../maintain-career/SKILL.md) describes.
3. **Templates.** Start from the repository `examples/resume.tex` and
   `examples/cover-letter.tex` or the owner's own documents. Build a one-page CV
   MASTER from the Career record, compile it, check the PDF, and store source,
   guidance and rules in the resume template. Do the same for the letter template.
4. **Writing rules.** Store general writing guidance as Writing rules with scope
   `all` (`preferences_update` on `writing`): language register, evidence
   rules, what never to claim.
5. **Searches.** Follow [Manage sources](../manage-sources/SKILL.md): keyword
   searches for the target roles and locations, plus company boards for
   employers that match the owner's Preferences. Preview, then enable schedules.

## Hand over

Run one [Review Inbox](../review-inbox/SKILL.md) pass and prepare one Draft with
[Prepare Shortlist](../prepare-shortlist/SKILL.md) so the owner can see a real
result. Explain the owner's part in two sentences and report what you did in the chat,
including the open questions about their career.
