# Openings development

Read `docs/next/README.md`, `STATE.json`, `PRODUCT.md`, `PLAN.md` and `GOAL.md`
inside `docs/next` before implementation. STATE.json identifies the current task
and whether production execution has been authorized. Do not mistake experiments
or the dashboard preview for production code.

Complete the user-authorized final integration for Openings0.5.0. Read CONTRACTS.md and the current operation matrix; the prior rewrite is the baseline. No legacy compatibility/importer,
internal generative AI, server TeX, email/calendar, or unplanned features. Ship
English material and synthetic examples only. Dashboard/REST/MCP share services.

The user authorizes an orchestrator with focused subagents in isolated worktrees
when work is independent. Assign file ownership; integrate shared contracts
first. Use a few substantial commits and practical integration checks. Update
handoff state and record unresolved defects after meaningful work batches. Keep
temporary worktrees/branches clean. Respect the user's explicit start signal.
