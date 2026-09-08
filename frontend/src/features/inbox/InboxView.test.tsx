import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InboxView } from "./InboxView";
import { commonRoutes, job, mockApi, ok } from "../../test/mockApi";
import type { Route } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

const FIRST = job({ job_id: "1".repeat(64), title: "Backend Engineer", relevance_score: 42 });
const SECOND = job({
  job_id: "2".repeat(64),
  title: "Data Engineer",
  company: "Beta",
  relevance_score: 10,
  first_seen: "2026-08-01",
  labels: ["seed"],
});

function routes(items = [FIRST, SECOND]): Route[] {
  return [
    {
      method: "GET",
      path: "/api/jobs",
      reply: () => ({ items, total: items.length, limit: 100, offset: 0 }),
    },
    { method: "POST", path: "/api/jobs/status", reply: () => ok },
    { method: "POST", path: "/api/blacklist", reply: () => ok },
    { method: "POST", path: "/api/jobs/labels", reply: () => ok },
    {
      method: "GET",
      path: "/api/jobs/search/semantic",
      reply: () => [{ ...FIRST, similarity: 0.9 }],
    },
    ...commonRoutes(),
  ];
}

describe("InboxView", () => {
  it("lists new jobs, marks the ones since the last visit and moves the cursor", async () => {
    localStorage.setItem("openings.inbox.visited-at", "2026-09-01T00:00:00.000Z");
    const { calls } = mockApi(routes());
    renderWithProviders(<InboxView />);
    const rows = await screen.findAllByTestId("job-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("1 since last visit")).toBeInTheDocument();
    expect(screen.getByText("seed")).toBeInTheDocument();
    const list = calls.find((call) => call.url.startsWith("/api/jobs?"));
    expect(list?.url).toContain("statuses=new");
    expect(list?.url).toContain("limit=100");

    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() =>
      expect(screen.getAllByTestId("job-row")[1]).toHaveAttribute("aria-current", "true"),
    );

    fireEvent.keyDown(window, { key: "s" });
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    const status = calls.find((call) => call.url === "/api/jobs/status");
    expect(status?.body).toEqual({ job_ids: [SECOND.job_id], status: "shortlisted", note: null });
  });

  it("asks before blacklisting and opens the job page on Enter", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<InboxView />);
    await screen.findAllByTestId("job-row");

    fireEvent.keyDown(window, { key: "x" });
    const dialog = await screen.findByRole("dialog", { name: "Blacklist this posting?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Blacklist" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/blacklist")).toBe(true));
    expect(calls.find((call) => call.url === "/api/blacklist")?.body).toEqual({
      job_ids: [FIRST.job_id],
      note: null,
    });

    fireEvent.keyDown(window, { key: "Enter" });
    expect(window.location.search).toContain(`job=${FIRST.job_id}`);
  });

  it("ignores shortcuts while typing in the search box", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<InboxView />);
    await screen.findAllByTestId("job-row");
    const search = screen.getByRole("textbox", { name: "Search" });
    fireEvent.keyDown(window, { key: "/" });
    expect(search).toHaveFocus();
    fireEvent.keyDown(search, { key: "s" });
    expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(false);
  });

  it("selects several jobs and applies a bulk action", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<InboxView />);
    await screen.findAllByTestId("job-row");

    fireEvent.keyDown(window, { key: " " });
    expect(await screen.findByText("1 selected")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "*" });
    expect(await screen.findByText("2 selected")).toBeInTheDocument();

    const toolbar = screen.getByRole("toolbar", { name: "Bulk actions" });
    fireEvent.click(within(toolbar).getByRole("button", { name: "Mark applied" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    expect(calls.find((call) => call.url === "/api/jobs/status")?.body).toMatchObject({
      job_ids: [FIRST.job_id, SECOND.job_id],
      status: "applied",
    });

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByText("2 selected")).not.toBeInTheDocument());
  });

  it("runs a semantic search when the query starts with ~", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<InboxView />);
    await screen.findAllByTestId("job-row");
    fireEvent.change(screen.getByRole("textbox", { name: "Search" }), {
      target: { value: "~python backend" },
    });
    await waitFor(() =>
      expect(calls.some((call) => call.url.startsWith("/api/jobs/search/semantic?"))).toBe(true),
    );
    expect(calls.find((call) => call.url.startsWith("/api/jobs/search/semantic?"))?.url).toContain(
      "q=python+backend",
    );
    expect(await screen.findByText("1 semantic matches")).toBeInTheDocument();
  });

  it("distinguishes an empty inbox from a search without results", async () => {
    mockApi(routes([]));
    renderWithProviders(<InboxView />);
    expect(await screen.findByText("Nothing new")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Search" }), {
      target: { value: "nothing" },
    });
    expect(await screen.findByText("No postings match")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear search and filters" }));
    expect(await screen.findByText("Nothing new")).toBeInTheDocument();
  });

  it("keeps filters in the URL", async () => {
    const { calls } = mockApi(routes());
    window.history.replaceState(null, "", "?view=inbox&sources=greenhouse&min_score=20");
    renderWithProviders(<InboxView />);
    await screen.findAllByTestId("job-row");
    const list = calls.find((call) => call.url.startsWith("/api/jobs?"));
    expect(list?.url).toContain("sources=greenhouse");
    expect(list?.url).toContain("min_score=20");
    expect(screen.getByRole("button", { name: /Filters/ })).toHaveTextContent("2");
  });
});
