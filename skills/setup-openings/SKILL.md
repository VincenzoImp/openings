---
name: setup-openings
description: Install, connect and onboard an Openings workspace for its owner - Docker setup, agent connection, then career record, Profile and decision policy, CV and letter templates and first searches - so the other workflow skills can run the job search.
compatibility: Requires a machine with Docker Compose v2 for installation, or an existing Openings URL; see the openings-workspace skill for connection details.
---

# Set up Openings

Use this workflow when the owner wants to start using Openings, or when a
workspace exists but is not yet ready for the routine workflows. It ends when
the workspace has a career record, a Profile policy, both templates and running
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

The owner creates an API token in **Settings** and starts the agent client with
`OPENINGS_URL`, `OPENINGS_TOKEN` and, for a private certificate authority,
`OPENINGS_CA_FILE`. Never ask for the token in the conversation. Register the MCP
server at `<origin>/mcp` with the bearer header in the client's own configuration.
Confirm with `workspace_info` and `capabilities_get`.

Suggest a small operator workspace: a directory with the client's instruction
file stating the operating mandate and linking these skills, plus ignored local
space for temporary files. Personal data stays in Openings.

## Onboard the owner

Work in this order; each step uses records the next ones need.

1. **Career record.** Ask for a current CV, LinkedIn export, publication list or
   plain description. Use `career_preview_import` before `career_import` and
   inspect every created entry. Then follow
   [Maintain Career](../maintain-career/SKILL.md): integrated descriptions, dates,
   personal versus team scope, approved claims. Ask focused questions for gaps.
2. **Profile and policy.** Ask about target roles, seniority, locations and
   remote work, work authorization, availability, languages, and hard
   exclusions. Record the owner's words in `preferences` and a structured
   `metadata.decision_policy` (include, exclude, eligibility, geography, stretch,
   uncertainty rules), each fact dated with its source.
3. **Templates.** Start from the repository `examples/resume.tex` and
   `examples/cover-letter.tex` or the owner's own documents. Build a one-page CV
   MASTER from the Career record, compile it, check the PDF, and store source,
   guidance and rules in the resume template. Do the same for the letter template.
4. **Instructions.** Store general writing guidance with `instructions_update`:
   language register, evidence rules, what never to claim.
5. **Searches.** Follow [Manage sources](../manage-sources/SKILL.md): keyword
   searches for the target roles and locations, plus company boards for
   employers that match the Profile. Preview, then enable schedules.

## Hand over

Run one [Review Inbox](../review-inbox/SKILL.md) pass and prepare one Draft with
[Prepare Shortlist](../prepare-shortlist/SKILL.md) so the owner can see a real
result. Explain the owner's part in two sentences and report with the shared
[run report](../openings-workspace/references/run-report.md), including the
open questions about their career.
