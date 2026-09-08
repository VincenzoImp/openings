import { vi } from "vitest";

import type {
  CleanupReport,
  FacetsResponse,
  JobDetail,
  JobSummary,
  RunRecord,
  SettingsSummary,
  SourceStatus,
  StatsResponse,
} from "../api/types";

/** One handler per "METHOD /path" prefix; the first match wins. */
export type Route = {
  method?: string;
  path: string | RegExp;
  reply: (request: { url: URL; init: RequestInit | undefined; body: unknown }) => unknown;
  status?: number;
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Install a fetch mock; returns the list of calls for assertions. */
export function mockApi(routes: Route[]) {
  const calls: { method: string; url: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    let body: unknown = null;
    if (typeof init?.body === "string") {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    } else if (init?.body instanceof FormData) {
      body = Object.fromEntries(init.body.entries());
    }
    calls.push({ method, url: url.pathname + url.search, body });
    for (const route of routes) {
      const methodOk = !route.method || route.method.toUpperCase() === method;
      const pathOk =
        typeof route.path === "string"
          ? url.pathname === route.path
          : route.path.test(url.pathname);
      if (methodOk && pathOk) {
        const payload = route.reply({ url, init, body });
        if (payload instanceof Response) {
          return payload;
        }
        return jsonResponse(payload, route.status ?? 200);
      }
    }
    return jsonResponse({ detail: `No mock for ${method} ${url.pathname}` }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export const ok = { success: true, affected_count: 1, job_ids: [] as string[], message: null };

export function job(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    job_id: "a".repeat(64),
    title: "Backend Engineer",
    company: "Acme",
    location: "Remote",
    source: "linkedin",
    external_id: "li-1",
    job_url: "https://example.com/jobs/1",
    job_type: "fulltime",
    is_remote: true,
    job_level: null,
    date_posted: "2026-09-07",
    min_amount: 100000,
    max_amount: 120000,
    currency: "USD",
    salary_interval: "yearly",
    company_url: "https://example.com",
    first_seen: "2026-09-07",
    last_seen: "2026-09-08",
    relevance_score: 42,
    status: "new",
    status_changed_at: null,
    postings_count: 1,
    notes_count: 0,
    attachments_count: 0,
    labels: [],
    ...overrides,
  };
}

export function jobDetail(overrides: Partial<JobDetail> = {}): JobDetail {
  const summary = job();
  return {
    ...summary,
    description: "## About\n\nPython services with **PostgreSQL**.",
    raw_json: '{"title": "Backend Engineer"}',
    explain: {
      score: 42,
      matched: [
        { category: "role", weight: 25 },
        { category: "stack", weight: 17 },
      ],
    },
    labels: ["seed"],
    postings: [
      {
        id: 1,
        job_id: summary.job_id,
        key: "linkedin:li-1",
        source: "linkedin",
        external_id: "li-1",
        url: "https://example.com/jobs/1",
        first_seen: "2026-09-07",
        last_seen: "2026-09-08",
      },
    ],
    notes: [],
    attachments: [],
    events: [
      {
        id: 1,
        job_id: summary.job_id,
        kind: "ingested",
        summary: "Ingested from linkedin",
        data: null,
        created_at: "2026-09-07T06:00:00+00:00",
      },
    ],
    ...overrides,
  };
}

export function stats(overrides: Partial<StatsResponse> = {}): StatsResponse {
  return {
    total_jobs: 12,
    by_status: {
      new: 5,
      shortlisted: 3,
      applied: 2,
      interviewing: 1,
      offer: 0,
      rejected: 1,
      withdrawn: 0,
      blacklisted: 7,
    },
    new_today: 4,
    seen_today: 9,
    avg_relevance_score: 21.5,
    blacklisted: 7,
    attachments: 3,
    notes: 4,
    ...overrides,
  };
}

export function facets(overrides: Partial<FacetsResponse> = {}): FacetsResponse {
  return {
    statuses: [{ value: "new", count: 5 }],
    sources: [
      { value: "linkedin", count: 8 },
      { value: "greenhouse", count: 4 },
    ],
    companies: [
      { value: "Acme", count: 3 },
      { value: "Beta", count: 1 },
    ],
    locations: [{ value: "Remote", count: 4 }],
    job_types: [{ value: "fulltime", count: 4 }],
    labels: [{ value: "seed", count: 1 }],
    ...overrides,
  };
}

export function source(overrides: Partial<SourceStatus> = {}): SourceStatus {
  return {
    name: "linkedin",
    kind: "jobspy",
    detail: "1 queries x 1 locations",
    enabled: true,
    active_jobs: 8,
    last_run: {
      name: "linkedin",
      tasks: 6,
      succeeded: 6,
      failed: 0,
      rows: 30,
      errors: [],
      started_at: "2026-09-08T06:00:00+00:00",
    },
    ...overrides,
  };
}

export function run(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    id: 1,
    started_at: "2026-09-08T06:00:00+00:00",
    finished_at: "2026-09-08T06:25:00+00:00",
    running: false,
    duration_seconds: 1500,
    total_found: 40,
    unique_found: 30,
    saved: 12,
    new_jobs: 4,
    notified: 2,
    success: true,
    sources: [{ name: "linkedin", tasks: 6, succeeded: 6, failed: 0, rows: 30, errors: [] }],
    errors: [],
    ...overrides,
  };
}

export function cleanup(overrides: Partial<CleanupReport> = {}): CleanupReport {
  return {
    deleted_below_score: 0,
    deleted_stale: 0,
    protected: 3,
    total_deleted: 0,
    ...overrides,
  };
}

export function settings(overrides: Partial<SettingsSummary> = {}): SettingsSummary {
  return {
    version: "0.2.0",
    profile: { name: "Test User", headline: "Engineer", target: "Backend" },
    scoring: { save_threshold: 10, notify_threshold: 45, weights: {}, keywords: {} },
    scheduler: { interval_hours: 6, run_on_startup: false },
    sources: {
      jobspy: {
        enabled: true,
        sites: ["linkedin"],
        locations: ["Zurich"],
        queries: ["backend engineer"],
        job_types: [],
        hours_old: 24,
      },
      companies: [],
      feeds: [],
      adzuna: { enabled: false },
    },
    notifications: { telegram: false },
    retention: { max_age_days: 90 },
    attachments: { max_size_mb: 25 },
    embeddings: { enabled: true, status: "ready" },
    timezone: "Europe/Zurich",
    data_dir: "/data",
    ...overrides,
  };
}

/** The read-only routes almost every view touches on mount. */
export function commonRoutes(): Route[] {
  return [
    { path: "/api/dashboard/auth", reply: () => ({ token_required: false }) },
    { path: "/api/stats", reply: () => stats() },
    { path: "/api/jobs/facets", reply: () => facets() },
    { path: "/api/labels", reply: () => [{ value: "seed", count: 1 }] },
    { path: "/api/settings", reply: () => settings() },
    { path: "/api/settings/reference", reply: () => new Response("# reference", { status: 200 }) },
    { path: "/api/sources", reply: () => [] },
    { path: "/api/runs/status", reply: () => ({ running: false, run: null, requested: false }) },
    { path: "/api/runs", reply: () => [] },
  ];
}
