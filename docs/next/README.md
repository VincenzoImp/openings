# Openings next

A fresh implementation on branch `codex/openings-next`, based on `1deea662`.
Old Openings and Dossier are references, not the new application scaffold.
Production implementation awaits the user's explicit start signal.

The app owns career knowledge, company watch, collection, optional scoring,
application tracking and documents. Dashboard serves people, REST serves scripts,
MCP serves external agents. All share one service and one portable SQLite database.

**Ship all UI, code, comments, documentation, examples and release material in
English.** Users may keep their own content in any language.

## Read in order

1. [Feature map, switches and delivery steps](PRODUCT.md)
2. [Workflow and data rules](DESIGN.md)
3. [Optional scoring and external agents](AI.md)
4. [Implementation and practical verification](PLAN.md)
5. [Measured feasibility](FEASIBILITY.md) and [research](RESEARCH.md)
6. [Handoff state](STATE.json)
7. [Self-contained execution brief](GOAL.md)
8. [Current findings and defects](WORKLOG.md)

## Current decisions

- Fresh codebase on this branch; no legacy compatibility or data importer.
- Dossier is the visual reference, including Kanban and a Sankey application funnel.
- URL/text/structured manual ingestion and scheduled company feeds share one path.
- Job triage: Inbox / Saved / Dismissed. Forget permanently removes job-owned data.
- Scoring is optional, local or remote. Profile/rubric/model edits mark results outdated without launching mass inference.
- External agents read knowledge/templates/rules, prepare documents, compile externally and upload PDF plus sources.
- No internal generative model, generation button, auto-drafting, agent login or server TeX compiler in the first release.
- Target: 2 CPU cores / 4 GiB, Docker-first, heavy scoring service optional.

The [skill draft](../../skills/openings-workspace/SKILL.md) is not installed or
validated against a production MCP server. MCP must remain usable without it.

Next task after the start signal: **M1.1**, a fresh scaffold and minimal initial schema.
`experiments/next` contains historical feasibility probes, not production modules.
Use a few invariant tests and real dashboard/API/MCP/agent walkthroughs; no
coverage target. Update PLAN.md and STATE.json after each usable increment.

Release target: **Openings 1.0**. Descriptor: **Your job search workspace**.
Scope is complete for this release; there is no planned feature-expansion phase.
The [interactive dashboard preview](preview/index.html) uses synthetic browser-only data.
