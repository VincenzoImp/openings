import { describe, expect, it } from "vitest";

import { navigate, parseRoute, routeHref, setParams } from "./router";

describe("router", () => {
  it("parses the view, the job and the view parameters from the query string", () => {
    expect(parseRoute("")).toMatchObject({ view: "inbox", jobId: null });
    expect(parseRoute("?view=runs")).toMatchObject({ view: "runs", jobId: null });
    const route = parseRoute("?view=bogus&job=abc&q=py&sources=a&sources=b");
    expect(route).toMatchObject({ view: "inbox", jobId: "abc" });
    expect(route.params.get("q")).toBe("py");
    expect(route.params.getAll("sources")).toEqual(["a", "b"]);
    expect(route.params.has("view")).toBe(false);
  });

  it("builds hrefs relative to the current route and keeps params within a view", () => {
    const current = parseRoute("?view=pipeline&job=abc&closed=1");
    expect(routeHref({ jobId: null }, current)).toBe("?view=pipeline&closed=1");
    expect(routeHref({ view: "runs" }, current)).toBe("?view=runs&job=abc");
    expect(routeHref({ jobId: null, params: null }, current)).toBe("?view=pipeline");
  });

  it("navigate pushes history and setParams replaces it", () => {
    navigate({ view: "companies" });
    expect(window.location.search).toBe("?view=companies");
    navigate({ jobId: "abc" });
    expect(window.location.search).toBe("?view=companies&job=abc");
    setParams({ company: "Acme", q: "" });
    expect(window.location.search).toBe("?view=companies&job=abc&company=Acme");
    setParams({ company: null, sources: ["a", "b"] });
    expect(window.location.search).toBe("?view=companies&job=abc&sources=a&sources=b");
  });
});
