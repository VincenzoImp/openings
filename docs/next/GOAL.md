# Openings 0.5.0 delivery handoff

## Entry point and status

The user-authorized final integration is complete on `codex/openings-next`,
[PR 52](https://github.com/VincenzoImp/openings/pull/52). Start at README.md,
STATE.json, CONTRACTS.md and OPERATIONS.md. PLAN.md maps the completed phases;
WORKLOG.md and evidence/ retain findings and validation. Do not restart the rewrite
or interpret historical baseline probes as the current candidate.

The persistent implementation goal completes at delivery. No implementation task
remains. The owner may review the PR; main merge, version tag, image publication
and production deployment have not been performed or authorized by this handoff.
Version 0.5.0 deliberately precedes stable API/data-format compatibility guarantees.
The REST namespace `/api/v1` is independent of the package version.

## Delivered scope

Broad saved searches with pinned JobSpy 1.4.1 plus selected company ATS/feed
monitoring; typed SQLite configuration, per-HTTP provider budgets/cooldowns,
schedules/global pause, diagnostics/tasks and independent collection/inference.
Dashboard, REST and MCP cover 84 logical operations through shared services.
Bootstrap, deployment and binary HTTP transport differences are explicit.

One portable SQLite database stores profile/evidence/claims, multiple LaTeX
packages/assets/rules, writing instructions, jobs, independent application attempts,
notes/history, frozen contexts and exact document/file revisions. External agents
read context, generate documents and compile TeX externally, then upload artifacts.
Optional local/remote Laya/SystemOne classification is advisory. Profile/config
edits mark scores outdated; explicit batches control rescoring. There is no
empirical fallback, internal generation/chat/TeX, semantic/OpenSearch, default
browser crawler, email/calendar, portal submission or old-database importer.

All shipped material is English; examples/data are synthetic. The dashboard has
responsive layouts, dirty-form protection, compact server-filtered pagination,
bulk actions, useful deep links, Kanban, document review and a recorded funnel.

## Verification and workspace

55 backend cases, 103 practical browser checks plus 14 local-preview checks pass.
Native amd64/arm64 CI verifies builds/startup and installed package hashes. Actual
Codex+skill+DockerMCP+Tectonic round trip verifies two one-page PDFs and four exact
PDF/source transfers. Combined Linux ARM 2 CPU / 4 GiB / no swap acquisition/inference
passes 17 checks: 1885 tokens untruncated, 2.904 GiB conservative peak, no OOM, core
responsive. Exact image IDs and measured qualifications are in evidence/.

Task worktrees/branches and temporary Linux verification tools/VM/model volumes
were removed. Original Openings/Dossier references and main are unchanged.
The retained http://127.0.0.1:18800 demo uses only ignored synthetic data at
`data/development.sqlite`; scoring is off and example collection sources paused.
Developer uv/Node/browser tools remain available for future work.
