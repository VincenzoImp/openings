import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { getDashboardAuthStatus, listJobs, setDashboardToken } from "./client";

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
