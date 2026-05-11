# Dashboard Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web dashboard secure for local/LAN use, scalable beyond 200 jobs, and maintainable with Tailwind plus a single component system.

**Architecture:** Keep the unified FastAPI process as the backend for dashboard, REST API, and MCP. Introduce explicit browser auth support and strict CORS/origin defaults at the API boundary, then refactor the React app around typed API helpers, paginated server state, and reusable Tailwind-backed components. Preserve the existing static-asset deployment model.

**Tech Stack:** FastAPI, React 19, Vite 7, TanStack Query/Table/Virtual, Tailwind CSS v4, HeroUI React components, Vitest, pytest.

---

### Task 1: Auth And CORS Hardening

**Files:**
- Modify: `src/job_search_tool/web/api.py`
- Modify: `src/job_search_tool/web/app.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add failing tests**
  - Add a test proving `/api/dashboard/auth` exposes whether a token is required without leaking it.
  - Add a test proving browser API calls can authenticate via `X-Job-Search-Token`.
  - Add a test proving configured CORS origins are enforced instead of wildcard origins.

- [ ] **Step 2: Verify RED**
  - Run: `./.venv/bin/pytest -q tests/test_web_api.py`
  - Expected: failures for missing dashboard auth route, missing header support, or wildcard CORS.

- [ ] **Step 3: Implement**
  - Accept `Authorization: Bearer <token>` and `X-Job-Search-Token: <token>` when `JOB_SEARCH_API_TOKEN` is set.
  - Add `GET /api/dashboard/auth` returning `{ "token_required": bool }`.
  - Configure CORS from `JOB_SEARCH_WEB_ALLOWED_ORIGINS`, defaulting to localhost origins only.

- [ ] **Step 4: Verify GREEN**
  - Run: `./.venv/bin/pytest -q tests/test_web_api.py tests/test_web_static.py`

### Task 2: Frontend Auth Client

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/api/client.test.ts`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Add failing tests**
  - Test that API requests include `X-Job-Search-Token` after a token is configured.
  - Test that App shows a token gate when `/api/dashboard/auth` reports `token_required: true`.

- [ ] **Step 2: Verify RED**
  - Run: `npm --prefix frontend run test -- client App`

- [ ] **Step 3: Implement**
  - Add dashboard auth status fetcher.
  - Persist token in `localStorage` under a project-specific key.
  - Render a minimal token gate before the main shell when token is required and absent.

- [ ] **Step 4: Verify GREEN**
  - Run: `npm --prefix frontend run test -- client App`

### Task 3: Job List Scalability And Correctness

**Files:**
- Modify: `frontend/src/features/jobs/JobsPage.tsx`
- Modify: `frontend/src/features/jobs/jobQueries.ts`
- Test: `frontend/src/features/jobs/JobsPage.test.tsx`

- [ ] **Step 1: Add failing tests**
  - Test next-page navigation passes the correct offset.
  - Test changing filters clears selected IDs.
  - Test Open status excludes bookmarked and applied jobs.
  - Test successful mutations invalidate jobs, stats, distribution, and cleanup preview.

- [ ] **Step 2: Verify RED**
  - Run: `npm --prefix frontend run test -- JobsPage`

- [ ] **Step 3: Implement**
  - Replace fixed first-200 loading with page state and page controls.
  - Compute Open as `applied=false` and `bookmarked=false`.
  - Clear selected IDs on parameter changes.
  - Invalidate all dashboard data affected by mutations.
  - Disable destructive actions while pending and show mutation errors.

- [ ] **Step 4: Verify GREEN**
  - Run: `npm --prefix frontend run test -- JobsPage`

### Task 4: Tailwind And Component Library Migration

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/input.tsx`
- Modify: `frontend/src/components/ui/badge.tsx`
- Modify: `frontend/src/features/jobs/JobsPage.tsx`
- Modify: `frontend/src/features/analytics/AnalyticsPage.tsx`
- Modify: `frontend/src/features/database/DatabasePage.tsx`

- [ ] **Step 1: Install styling dependencies**
  - Add Tailwind CSS v4 Vite plugin and HeroUI React.

- [ ] **Step 2: Replace custom CSS**
  - Reduce `styles.css` to Tailwind import and small global base tokens only.
  - Rebuild shell, toolbar, panels, badges, inputs, buttons, cards, and table actions with HeroUI components plus Tailwind utilities.

- [ ] **Step 3: Verify**
  - Run: `npm --prefix frontend run quality`

### Task 5: Full Verification And Review

**Files:**
- Review full diff.

- [ ] **Step 1: Run full verification**
  - Run: `npm --prefix frontend run quality`
  - Run: `npm --prefix frontend audit --audit-level=moderate`
  - Run: `./.venv/bin/pytest -q`

- [ ] **Step 2: Manual smoke**
  - Verify `/health` and `/api/jobs` on the local demo or a fresh web server.

- [ ] **Step 3: Commit**
  - Commit with a message covering dashboard hardening and component migration.
