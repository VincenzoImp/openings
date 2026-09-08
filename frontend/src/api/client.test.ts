import { describe, expect, it, vi } from "vitest";

import { ApiError, TOKEN_HEADER, TOKEN_INVALID_EVENT, api, buildQuery, setToken } from "./client";
import { jsonResponse, mockApi } from "../test/mockApi";

describe("buildQuery", () => {
  it("repeats array keys and drops empty values", () => {
    expect(
      buildQuery({ status: ["new", "applied"], text: "", limit: 5, remote: true, x: null }),
    ).toBe("?status=new&status=applied&limit=5&remote=true");
    expect(buildQuery({})).toBe("");
    expect(buildQuery(undefined)).toBe("");
  });
});

describe("api", () => {
  it("sends the stored token and JSON bodies", async () => {
    setToken("secret");
    const { fetchMock } = mockApi([
      {
        method: "POST",
        path: "/api/jobs/status",
        reply: () => ({ success: true, affected_count: 1, job_ids: ["x"], message: null }),
      },
    ]);
    const result = await api.setStatus(["x"], "applied", "sent");
    expect(result.affected_count).toBe(1);
    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>)[TOKEN_HEADER]).toBe("secret");
    expect(JSON.parse(init?.body as string)).toEqual({
      job_ids: ["x"],
      status: "applied",
      note: "sent",
    });
  });

  it("raises ApiError with the server detail and signals invalid tokens", async () => {
    mockApi([{ path: "/api/stats", reply: () => jsonResponse({ detail: "nope" }, 401) }]);
    const listener = vi.fn();
    window.addEventListener(TOKEN_INVALID_EVENT, listener);
    await expect(api.stats()).rejects.toMatchObject({ status: 401, message: "nope" });
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(TOKEN_INVALID_EVENT, listener);
  });

  it("uploads attachments as multipart form data", async () => {
    const { fetchMock } = mockApi([
      {
        method: "POST",
        path: /\/api\/jobs\/[^/]+\/attachments$/,
        reply: () => ({ id: 1, filename: "cv.pdf" }),
      },
    ]);
    const file = new File(["%PDF"], "cv.pdf", { type: "application/pdf" });
    await api.uploadAttachment("abc", file, "cv", "v1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/jobs/abc/attachments");
    const form = init?.body as FormData;
    expect(form.get("kind")).toBe("cv");
    expect(form.get("note")).toBe("v1");
    expect((form.get("file") as File).name).toBe("cv.pdf");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("builds list URLs from params", async () => {
    const { calls } = mockApi([
      { path: "/api/jobs", reply: () => ({ items: [], total: 0, limit: 50, offset: 0 }) },
    ]);
    await api.listJobs({ status: ["new"], min_score: 10, sort: "date" });
    expect(calls[0].url).toBe("/api/jobs?status=new&min_score=10&sort=date");
  });

  it("is an ApiError instance", () => {
    expect(new ApiError(500, "x")).toBeInstanceOf(Error);
  });
});
