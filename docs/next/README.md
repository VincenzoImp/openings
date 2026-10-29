# Openings 0.5.0 integration

Openings is a fresh Python/FastAPI, React and SQLite implementation on
`codex/openings-next`. The final user-approved integration adds broad saved searches,
company feeds, shared provider budgets and logical Dashboard/REST/MCP parity.
[PR 52](https://github.com/VincenzoImp/openings/pull/52) is the review entry point.
Final integration is complete. [STATE.json](STATE.json), [GOAL.md](GOAL.md) and
[evidence](evidence/) record the verified candidate and retained limitations;
publication/deployment remain separate owner actions.

The app stores career evidence, claims, templates/assets/instructions, jobs,
application attempts, frozen contexts and exact document/file revisions in one
portable SQLite database. External agents generate documents and compile TeX.
Optional local or remote scoring is classification only. Target deployment is
Docker with 2 CPU cores / 4 GiB combined, including the optional local scorer.

## Read in order

1. [Product scope and switches](PRODUCT.md)
2. [Workflow and data rules](DESIGN.md)
3. [Optional scoring and external agents](AI.md)
4. [Final integration contracts](CONTRACTS.md) and [operation matrix](OPERATIONS.md)
5. [Execution plan](PLAN.md), [handoff state](STATE.json) and [current findings](WORKLOG.md)
6. [Measured feasibility](FEASIBILITY.md) and [research decisions](RESEARCH.md)

## Current boundaries

- One shared domain implementation, paginated summaries and separate detail reads.
- Explicit saved query/location searches plus selected company ATS/feed sources;
  previews, manual runs and schedules share persisted per-HTTP provider limits.
- Inbox / Saved / Dismissed job triage; independent application attempts and history.
  Forget deletes job-owned data and permits later rediscovery.
- Profile/rubric/model changes mark scores outdated; mass rescoring stays explicit.
- External document generation/compilation, frozen evidence and exact file ownership.
  No internal chat/generative endpoint, server TeX, portal submission or email/calendar.
- No legacy importer or compatibility layer. Version 0.5.0 precedes stable public
  API and data-format guarantees; `/api/v1` is an independent route namespace.
- English shipped material and synthetic public examples only; user content may
  use another language. No production deployment, image publication or main merge.

The repository [agent skill](../../skills/openings-workspace/SKILL.md) is optional
workflow guidance. MCP is usable without it. Actual external Codex/Tectonic and
Linux measurements are recorded under `evidence/`, with dates and limitations.
The browser-only [design preview](preview/index.html) and `experiments/next` are
historical references; the production dashboard is `frontend/`.
