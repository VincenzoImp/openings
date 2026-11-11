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

The owner creates an **Agent** token in **Settings → Agent access** and starts
the agent client with `OPENINGS_URL`, `OPENINGS_TOKEN` and, for a private
certificate authority, `OPENINGS_CA_FILE`. Recommend an agent token, not an owner
token: it runs every workflow and cannot change the owner password, manage
tokens, restore a backup or answer a question for the owner. `workspace_info`
reports the kind in `actor.token_kind`; when it is `owner`, tell the owner that
an agent token is enough. Never ask for the token in the conversation. Register the MCP
server at `<origin>/mcp` with the bearer header in the client's own configuration.
Confirm with `workspace_info` and `capabilities_get`.

Suggest an operator workspace: copy the repository's
`examples/operator-workspace/`, run its `sync.py --url <origin>`, and start the
client through its `launch.py`. It states the operating mandate, generates MCP
configuration for common clients and keeps personal data out of Git.

Check the agent's own machine for `pdflatex` (and `pdftotext`/`pdfinfo` for
checks). Openings does not compile documents. If they are missing, propose a
user-level TeX distribution such as TinyTeX, install it with the owner's
agreement, and report PDF preparation as blocked until a compiler works.

## Run and questions

Once the connection works, open a run: `runs_start` with `workflow: "setup-openings"` and the scope; writes made
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

## Onboard the owner

To try the workflow before sharing personal data, import the repository's
synthetic `examples/career.json`, add the items of `examples/policy.json` and use
`examples/resume.tex` and `examples/cover-letter.tex`; replace them with the
owner's records afterwards.

Work in this order; each step uses records the next ones need.

1. **Career record.** Ask for a current CV, LinkedIn export, publication list or
   plain description. Use `career_preview_import` before `career_import` and
   inspect every created entry. Then follow
   [Maintain Career](../maintain-career/SKILL.md): integrated descriptions, dates,
   personal versus team scope, approved claims. Ask focused questions for gaps.
2. **Profile and policy.** Fill the Profile's typed fields (name, contact,
   headline, summary, links). Ask about target roles, seniority, locations and
   remote work, work authorization, availability, languages, hard exclusions
   and how documents should read. Record each answer as one policy item in the
   owner's words (`policy_add`): rules for shortlisting and dismissing in
   `decision`, facts employers ask about in `eligibility`, document rules in
   `writing` with a scope, anything else in `facts`. Your items are proposals:
   ask the owner to open **Policy** in the dashboard and confirm them, and do
   not rely on an unconfirmed item. In a workspace upgraded from an earlier
   version, sort the copied items first as
   [Maintain Career](../maintain-career/SKILL.md) describes.
3. **Templates.** Start from the repository `examples/resume.tex` and
   `examples/cover-letter.tex` or the owner's own documents. Build a one-page CV
   MASTER from the Career record, compile it, check the PDF, and store source,
   guidance and rules in the resume template. Do the same for the letter template.
4. **Instructions.** Store general writing guidance with `instructions_update`:
   language register, evidence rules, what never to claim.
5. **Searches.** Follow [Manage sources](../manage-sources/SKILL.md): keyword
   searches for the target roles and locations, plus company boards for
   employers that match the policy. Preview, then enable schedules.

## Hand over

Run one [Review Inbox](../review-inbox/SKILL.md) pass and prepare one Draft with
[Prepare Shortlist](../prepare-shortlist/SKILL.md) so the owner can see a real
result. Explain the owner's part in two sentences and report with the shared
[run report](../openings-workspace/references/run-report.md), including the
open questions about their career.
