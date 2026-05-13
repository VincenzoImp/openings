import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  blacklistJobs,
  deleteJobs,
  deleteJobsBelowScore,
  exportJobs,
  getDashboardAuthStatus,
  getFacets,
  listBlacklistedJobs,
  listJobs,
  purgeBlacklist,
  setApplied,
  setBookmarked,
  setDashboardToken,
  unblacklistJobs
} from "./client";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(body),
    text: vi.fn().mockResolvedValue(JSON.stringify(body))
  } as unknown as Response;
}

beforeEach(() => {
  const storage = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    clear: vi.fn(() => storage.clear()),
    getItem: vi.fn((key: string) => storage.get(key) ?? null),
    removeItem: vi.fn((key: string) => storage.delete(key)),
    setItem: vi.fn((key: string, value: string) => storage.set(key, value))
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      jsonResponse({
        items: [],
        limit: 20,
        offset: 0,
        total: 0
      })
    )
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("includes the saved dashboard token on API requests", async () => {
  setDashboardToken("secret-token");

  await listJobs();

  const [, init] = vi.mocked(fetch).mock.calls[0];
  expect(init?.headers).toMatchObject({
    "X-Job-Search-Token": "secret-token"
  });
});

test("fetches dashboard auth status from the public API route", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ token_required: true }));

  await expect(getDashboardAuthStatus()).resolves.toEqual({ token_required: true });
  expect(fetch).toHaveBeenCalledWith(
    "/api/dashboard/auth",
    expect.objectContaining({
      headers: expect.objectContaining({
        "Content-Type": "application/json"
      })
    })
  );
});

test("serializes array query parameters for server-backed filters", async () => {
  await listJobs({
    sites: ["indeed", "linkedin"],
    job_types: ["fulltime"],
    location: "remote",
    min_salary: 120000,
    sort: "salary"
  });

  expect(fetch).toHaveBeenCalledWith(
    "/api/jobs?sites=indeed&sites=linkedin&job_types=fulltime&location=remote&min_salary=120000&sort=salary",
    expect.any(Object)
  );
});

test("sends bulk command request bodies with the dashboard token", async () => {
  setDashboardToken("secret-token");

  await setBookmarked(["job-1", "job-2"], true);
  await setApplied(["job-1"], false);
  await blacklistJobs(["job-3"]);
  await deleteJobs(["job-4"]);

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/jobs/bookmark",
    expect.objectContaining({
      body: JSON.stringify({ job_ids: ["job-1", "job-2"], bookmarked: true }),
      headers: expect.objectContaining({ "X-Job-Search-Token": "secret-token" }),
      method: "POST"
    })
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/jobs/applied",
    expect.objectContaining({
      body: JSON.stringify({ job_ids: ["job-1"], applied: false }),
      method: "POST"
    })
  );
  expect(fetch).toHaveBeenNthCalledWith(
    3,
    "/api/blacklist",
    expect.objectContaining({
      body: JSON.stringify({ job_ids: ["job-3"] }),
      method: "POST"
    })
  );
  expect(fetch).toHaveBeenNthCalledWith(
    4,
    "/api/jobs/delete",
    expect.objectContaining({
      body: JSON.stringify({ job_ids: ["job-4"] }),
      method: "POST"
    })
  );
});

test("covers facets blacklist cleanup and export endpoints", async () => {
  vi.mocked(fetch).mockResolvedValue(
    jsonResponse({
      items: [],
      limit: 100,
      offset: 0,
      total: 0
    })
  );

  await getFacets();
  await listBlacklistedJobs({ text: "acme" });
  await unblacklistJobs(["job-1"]);
  await purgeBlacklist(30);
  await deleteJobsBelowScore(20);

  vi.mocked(fetch).mockResolvedValueOnce({
    blob: vi.fn().mockResolvedValue(new Blob(["id,title"])),
    ok: true,
    status: 200,
    text: vi.fn().mockResolvedValue("")
  } as unknown as Response);
  await exportJobs({ format: "csv", job_ids: ["job-1"] });

  expect(fetch).toHaveBeenNthCalledWith(1, "/api/jobs/facets", expect.any(Object));
  expect(fetch).toHaveBeenNthCalledWith(2, "/api/blacklist?text=acme", expect.any(Object));
  expect(fetch).toHaveBeenNthCalledWith(
    3,
    "/api/blacklist/remove",
    expect.objectContaining({ body: JSON.stringify({ job_ids: ["job-1"] }) })
  );
  expect(fetch).toHaveBeenNthCalledWith(
    4,
    "/api/blacklist/purge",
    expect.objectContaining({ body: JSON.stringify({ older_than_days: 30 }) })
  );
  expect(fetch).toHaveBeenNthCalledWith(
    5,
    "/api/cleanup/delete-below-score",
    expect.objectContaining({ body: JSON.stringify({ score: 20 }) })
  );
  expect(fetch).toHaveBeenNthCalledWith(
    6,
    "/api/export/jobs",
    expect.objectContaining({
      body: JSON.stringify({ job_ids: ["job-1"], format: "csv" }),
      method: "POST"
    })
  );
});
