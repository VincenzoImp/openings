# Dashboard Console Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a professional Job Search Console with parity across dashboard, REST API, and MCP tools.

**Architecture:** Add capabilities to the shared application/database layer first, then expose them through REST and MCP adapters. Rebuild the dashboard around server-backed filters, HeroUI primitives, contextual bulk actions, blacklist management, and an inspector-driven triage workflow.

**Tech Stack:** Python 3.11, FastAPI, FastMCP, SQLite, React 19, HeroUI, Tailwind v4, TanStack Query, TanStack Table/Virtual, Vitest, pytest, Docker.

---

## File Structure

- Modify `src/job_search_tool/database.py`: SQL-backed filters, facets, blacklist listing, unblacklist, permanent delete, export query support.
- Modify `src/job_search_tool/application/models.py`: query/command result contracts and blacklist/facet/export models.
- Modify `src/job_search_tool/application/jobs.py`: shared command/query capability layer.
- Modify `src/job_search_tool/web/api.py`: REST parity endpoints.
- Modify `src/job_search_tool/web/mcp.py`: MCP parity tools.
- Modify `tests/test_database.py`, `tests/test_application_jobs.py`, `tests/test_web_api.py`, `tests/test_web_mcp.py`: backend TDD coverage.
- Modify `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts`: typed API client.
- Split frontend into focused files under `frontend/src/features/jobs/`: filters, table, inspector, bulk actions, blacklist, cleanup helpers.
- Modify `frontend/src/App.tsx`: navigation shell and views.
- Modify frontend feature tests for job triage, blacklist, cleanup, and API parity flows.
- Add `tests/test_docker_e2e.py` or scripted smoke coverage only if it can run reliably in CI/local without making the normal suite dependent on Docker availability.

## Task 1: Backend Database Capabilities

**Files:**
- Modify: `src/job_search_tool/database.py`
- Test: `tests/test_database.py`

- [ ] Add failing tests for `query_jobs` filters: location, salary min/max, date bounds, job type, multi-site, sort by company/title/salary.
- [ ] Add failing tests for `list_blacklisted_jobs`, `unblacklist_jobs`, `delete_jobs`, `purge_blacklist`, and `get_facets`.
- [ ] Implement the minimal SQL and dataclasses needed to pass those tests.
- [ ] Run `./.venv/bin/pytest tests/test_database.py -q`.
- [ ] Commit: `feat: expand database job operations`.

## Task 2: Shared Application Layer

**Files:**
- Modify: `src/job_search_tool/application/models.py`
- Modify: `src/job_search_tool/application/jobs.py`
- Test: `tests/test_application_jobs.py`

- [ ] Add failing tests for bulk bookmarked/applied commands over multiple IDs.
- [ ] Add failing tests for blacklist/unblacklist/delete command envelopes.
- [ ] Add failing tests for facets and blacklist list queries.
- [ ] Implement shared service methods without FastAPI/MCP concerns.
- [ ] Run `./.venv/bin/pytest tests/test_application_jobs.py -q`.
- [ ] Commit: `feat: add shared job console capabilities`.

## Task 3: REST API Parity

**Files:**
- Modify: `src/job_search_tool/web/api.py`
- Modify: `tests/test_web_api.py`

- [ ] Add failing tests for new list filters and sort parameters.
- [ ] Add failing tests for `/api/jobs/facets`.
- [ ] Add failing tests for bulk bookmark/applied/delete endpoints.
- [ ] Add failing tests for blacklist list/remove/purge endpoints.
- [ ] Add failing tests for export selected/filtered jobs.
- [ ] Implement REST adapters as thin wrappers over `JobApplicationService`.
- [ ] Run `./.venv/bin/pytest tests/test_web_api.py -q`.
- [ ] Commit: `feat: expose job console rest api`.

## Task 4: MCP Parity

**Files:**
- Modify: `src/job_search_tool/web/mcp.py`
- Modify: `tests/test_web_mcp.py`

- [ ] Add failing test that tool registry includes every REST-equivalent command.
- [ ] Add failing tests for `list_blacklisted_jobs`, `unblacklist_jobs`, `delete_jobs`, `get_facets`, and export.
- [ ] Implement tools as thin wrappers over `JobApplicationService`.
- [ ] Run `./.venv/bin/pytest tests/test_web_mcp.py -q`.
- [ ] Commit: `feat: expose job console mcp tools`.

## Task 5: Frontend API Client

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`

- [ ] Add failing tests for bulk command request bodies and token propagation.
- [ ] Add failing tests for facets, blacklist, delete, export, and cleanup command methods.
- [ ] Implement typed client methods and request helpers.
- [ ] Run `npm --prefix frontend run test -- client.test.ts`.
- [ ] Commit: `feat: add dashboard console api client`.

## Task 6: Dashboard Shell And Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] Add failing tests for navigation to Jobs, Saved, Applied, Blacklist, Cleanup, Analytics.
- [ ] Implement HeroUI/Tailwind shell with stable sidebar/top responsive navigation.
- [ ] Run `npm --prefix frontend run test -- App.test.tsx`.
- [ ] Commit: `feat: add console navigation shell`.

## Task 7: Jobs Triage View

**Files:**
- Split/modify: `frontend/src/features/jobs/JobsPage.tsx`
- Create focused modules under `frontend/src/features/jobs/`
- Test: `frontend/src/features/jobs/JobsPage.test.tsx`

- [ ] Add failing tests for advanced filters updating server params.
- [ ] Add failing tests for selected-row bulk action bar.
- [ ] Add failing tests for inspector rendering full metadata and quick actions.
- [ ] Add failing tests for export selected/filtered.
- [ ] Implement with HeroUI controls and Tailwind layout; avoid custom component primitives.
- [ ] Run `npm --prefix frontend run test -- JobsPage.test.tsx`.
- [ ] Commit: `feat: rebuild jobs triage console`.

## Task 8: Blacklist And Cleanup Views

**Files:**
- Create/modify frontend views for blacklist and cleanup.
- Test frontend feature tests.

- [ ] Add failing tests for blacklist listing, selection, unblacklist, purge.
- [ ] Add failing tests for cleanup preview and explicit cleanup actions.
- [ ] Implement views using HeroUI table/cards/modals.
- [ ] Run relevant frontend tests.
- [ ] Commit: `feat: add blacklist and cleanup console views`.

## Task 9: Analytics Improvements

**Files:**
- Modify: `frontend/src/features/analytics/AnalyticsPage.tsx`
- Backend may use facets/stat endpoints from previous tasks.

- [ ] Add tests for source/company/location/job-type summary rendering.
- [ ] Implement dense analytics cards and simple bar summaries with Tailwind only.
- [ ] Run analytics tests.
- [ ] Commit: `feat: expand dashboard analytics`.

## Task 10: Docker E2E Smoke

**Files:**
- Add: `tests/test_docker_e2e.py` or `scripts/smoke-dashboard-console.sh`
- Update docs if needed.

- [ ] Build local image.
- [ ] Start container with seeded data and token.
- [ ] Verify REST auth, list, filter, bulk action, blacklist, delete, cleanup, export.
- [ ] Verify MCP initialize/list-tools/call-tools for representative tools.
- [ ] Verify dashboard HTML and static assets load.
- [ ] Run Playwright or browser-level smoke if existing dependencies support it; otherwise keep it as documented manual/local smoke.
- [ ] Commit: `test: add dashboard console docker smoke`.

## Task 11: Final Verification And Release Prep

- [ ] Run `./.venv/bin/pytest -q`.
- [ ] Run `uv run mypy src/job_search_tool --ignore-missing-imports`.
- [ ] Run `uv run pre-commit run --all-files`.
- [ ] Run `npm --prefix frontend run quality`.
- [ ] Run `npm --prefix frontend audit --audit-level=moderate`.
- [ ] Run `docker compose config`.
- [ ] Run `docker build -t job-search-tool:dashboard-console .`.
- [ ] Update `CHANGELOG.md` and version if release-ready.
- [ ] Push branch and open PR.

## Coverage Review

The spec requirements map to this plan as follows:

- Capability parity: Tasks 1-4.
- Dashboard triage and design: Tasks 5-9.
- Blacklist vs permanent delete separation: Tasks 1-4 and 8.
- Component library/Tailwind constraint: Tasks 6-9.
- Docker E2E verification: Task 10.
- Release hygiene: Task 11.
