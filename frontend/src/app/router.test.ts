import { describe, expect, it } from "vitest";

import { navigate, parseRoute, routeHref } from "./router";

describe("router", () => {
  it("parses the view and job from the query string", () => {
    expect(parseRoute("")).toEqual({ view: "inbox", jobId: null });
    expect(parseRoute("?view=runs")).toEqual({ view: "runs", jobId: null });
    expect(parseRoute("?view=bogus&job=abc")).toEqual({ view: "inbox", jobId: "abc" });
  });

  it("builds hrefs relative to the current route", () => {
    const current = { view: "pipeline" as const, jobId: "abc" };
    expect(routeHref({ jobId: null }, current)).toBe("?view=pipeline");
    expect(routeHref({ view: "runs" }, current)).toBe("?view=runs&job=abc");
  });

  it("navigate pushes history and keeps the view when opening a job", () => {
    navigate({ view: "companies" });
    expect(window.location.search).toBe("?view=companies");
    navigate({ jobId: "abc" });
    expect(window.location.search).toBe("?view=companies&job=abc");
  });
});
