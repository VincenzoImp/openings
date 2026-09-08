import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InboxView } from "./InboxView";
import { facets, job, mockApi } from "../../test/mockApi";
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

function routes() {
  return [
    { path: "/api/jobs/facets", reply: () => facets() },
    {
      method: "GET",
      path: "/api/jobs",
      reply: () => ({ items: [FIRST, SECOND], total: 2, limit: 500, offset: 0 }),
    },
    {
      method: "POST",
      path: "/api/jobs/status",
      reply: () => ({ success: true, affected_count: 1, job_ids: [], message: null }),
    },
    {
      method: "POST",
      path: "/api/blacklist",
      reply: () => ({ success: true, affected_count: 1, job_ids: [], message: null }),
    },
  ];
}

describe("InboxView", () => {
  it("lists new jobs, marks the ones since the last visit and moves the cursor", async () => {
    localStorage.setItem("openings.inbox.visited-at", "2026-09-01");
    const { calls } = mockApi(routes());
    renderWithProviders(<InboxView />);
    const rows = await screen.findAllByTestId("job-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("1 since last visit")).toBeInTheDocument();
    expect(screen.getByText("seed")).toBeInTheDocument();
    expect(calls[0].url).toContain("status=new");

    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() =>
      expect(screen.getAllByTestId("job-row")[1]).toHaveAttribute("aria-selected", "true"),
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
    expect(screen.getByRole("dialog", { name: "Blacklist this posting?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Blacklist" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/blacklist")).toBe(true));
    expect(calls.find((call) => call.url === "/api/blacklist")?.body).toEqual({
      job_ids: [FIRST.job_id],
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
});
