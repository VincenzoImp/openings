# Frontend Console Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the dashboard to a professional operations-console level with parity across Dashboard, REST API, and MCP for job review, cleanup, blacklist, export, and analytics workflows.

**Architecture:** Keep the React/Vite/Tailwind/HeroUI stack, but introduce focused shared UI primitives and state helpers so pages stop duplicating custom alerts, modal behavior, pagination, and headers. Keep the unified backend as-is, adding only missing MCP/API parity where the frontend exposes existing backend capabilities.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind CSS, HeroUI, TanStack Query/Table/Virtual, FastAPI, FastMCP, Vitest/Testing Library, Playwright smoke verification.

---

### Task 1: Baseline And Shell Safety

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Create: `frontend/src/components/PageHeader.tsx`
- Create: `frontend/src/components/AlertBanner.tsx`
- Modify tests: `frontend/src/App.test.tsx`

- [ ] Run `npm --prefix frontend run quality` before changes and record baseline.
- [ ] Add URL-backed workspace routing with `?view=jobs|blacklist|cleanup|analytics`.
- [ ] Add an error boundary around the dashboard body.
- [ ] Replace repeated page title/header patterns with `PageHeader`.
- [ ] Replace repeated alert markup with `AlertBanner`.
- [ ] Add tests for URL-backed navigation and token invalidation behavior.
- [ ] Run `npm --prefix frontend run test -- App.test.tsx`.

### Task 2: Dialog And Destructive Action Safety

**Files:**
- Modify: `frontend/src/components/ConfirmDialog.tsx`
- Modify: `frontend/src/features/cleanup/CleanupPage.tsx`
- Modify tests: `frontend/src/features/cleanup/CleanupPage.test.tsx`

- [ ] Write failing tests proving Escape/cancel closes confirm dialogs and configured cleanup requires a modal confirmation.
- [ ] Replace the custom card dialog with a focusable HeroUI-backed modal surface with labelled title and description.
- [ ] Route configured cleanup through the same confirmation pattern as manual cleanup.
- [ ] Add success/status messages after cleanup operations.
- [ ] Run cleanup and dialog tests.

### Task 3: Jobs Workspace Completion

**Files:**
- Modify: `frontend/src/features/jobs/jobFilters.ts`
- Modify: `frontend/src/features/jobs/JobFiltersPanel.tsx`
- Modify: `frontend/src/features/jobs/JobActionsBar.tsx`
- Modify: `frontend/src/features/jobs/JobTable.tsx`
- Modify: `frontend/src/features/jobs/JobDetailPanel.tsx`
- Modify: `frontend/src/features/jobs/JobsPage.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Modify tests: `frontend/src/features/jobs/JobsPage.test.tsx`, `frontend/src/api/client.test.ts`

- [ ] Add tests for first/last-seen filters, CSV/JSON export choice, semantic search, row-level delete, detail delete, and page-size changes.
- [ ] Add debounced search params and URL-backed job filters/page/page size.
- [ ] Expose all REST job filters that matter operationally: score, salary, posted, first seen, last seen, source, company, location, type, remote, status.
- [ ] Add semantic search UI using `/api/jobs/search/semantic`.
- [ ] Replace row actions with a complete compact action set: save, apply, details, blacklist, delete, open job.
- [ ] Add detail panel delete and full action parity.
- [ ] Improve mobile row content so status/company/source are not lost.
- [ ] Run jobs and client tests.

### Task 4: Blacklist, Cleanup, Analytics Completion

**Files:**
- Modify: `frontend/src/features/blacklist/BlacklistPage.tsx`
- Modify: `frontend/src/features/cleanup/CleanupPage.tsx`
- Modify: `frontend/src/features/analytics/AnalyticsPage.tsx`
- Modify tests: `frontend/src/features/blacklist/BlacklistPage.test.tsx`, `frontend/src/features/cleanup/CleanupPage.test.tsx`, `frontend/src/features/analytics/AnalyticsPage.test.tsx`

- [ ] Add tests for blacklist company/location filters and pagination.
- [ ] Rework blacklist into a responsive console table/card hybrid with pagination and clear filter controls.
- [ ] Give cleanup numeric commands visible labels, contextual preview counts, success states, and consistent confirmation.
- [ ] Make analytics a navigable decision surface: page heading, blacklisted/new-today metrics, clickable source/type/score summaries that move to Jobs with filters.
- [ ] Run page-specific tests.

### Task 5: MCP/API Parity

**Files:**
- Modify: `src/job_search_tool/web/mcp.py`
- Modify tests: `tests/test_web_mcp.py`

- [ ] Add failing tests showing MCP `export_jobs` accepts the same practical filters as REST and semantic search accepts score/site constraints.
- [ ] Extend MCP `export_jobs` to accept full filter params used by dashboard.
- [ ] Extend MCP `search_similar` to accept `min_score` and `site`.
- [ ] Run `uv run pytest tests/test_web_mcp.py`.

### Task 6: Verification And Audit Loop

- [ ] Run focused tests after each task.
- [ ] Run `npm --prefix frontend run quality`.
- [ ] Run `uv run pytest tests/test_web_mcp.py`.
- [ ] Run local Playwright screenshot/DOM smoke for desktop and mobile pages.
- [ ] Review screenshots for overflow, clipped text, hidden critical actions, and inconsistent destructive actions.
- [ ] Run `git diff --check` and inspect the final diff manually.
