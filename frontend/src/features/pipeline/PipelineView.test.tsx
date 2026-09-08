import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PipelineView } from "./PipelineView";
import { commonRoutes, job, mockApi, ok } from "../../test/mockApi";
import type { Route } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

const SHORTLISTED = job({ job_id: "1".repeat(64), status: "shortlisted" });
const APPLIED = job({
  job_id: "2".repeat(64),
  title: "Data Engineer",
  status: "applied",
  status_changed_at: "2026-09-07T10:00:00+00:00",
});

function routes(items = [SHORTLISTED, APPLIED]): Route[] {
  return [
    {
      method: "GET",
      path: "/api/jobs",
      reply: () => ({ items, total: items.length, limit: 100, offset: 0 }),
    },
    { method: "POST", path: "/api/jobs/status", reply: () => ok },
    ...commonRoutes(),
  ];
}

describe("PipelineView", () => {
  it("groups jobs by status and moves the selected one forward with ]", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<PipelineView />);
    const shortlisted = await screen.findByTestId("column-shortlisted");
    await waitFor(() =>
      expect(within(shortlisted).getAllByTestId("pipeline-card")).toHaveLength(1),
    );
    expect(
      within(screen.getByTestId("column-applied")).getByText("Data Engineer"),
    ).toBeInTheDocument();
    expect(calls[0].url).toContain("statuses=shortlisted&statuses=applied");
    expect(screen.queryByTestId("column-rejected")).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "]" });
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    expect(calls.find((call) => call.url === "/api/jobs/status")?.body).toEqual({
      job_ids: [SHORTLISTED.job_id],
      status: "applied",
      note: null,
    });
  });

  it("accepts drops from another column", async () => {
    const { calls } = mockApi(routes([SHORTLISTED]));
    renderWithProviders(<PipelineView />);
    await screen.findByTestId("pipeline-card");
    const dataTransfer = { getData: () => SHORTLISTED.job_id, setData: () => {} };
    fireEvent.drop(screen.getByTestId("column-interviewing"), { dataTransfer });
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    expect(calls.find((call) => call.url === "/api/jobs/status")?.body).toMatchObject({
      status: "interviewing",
    });
  });

  it("moves a card from its menu and shows closed columns on demand", async () => {
    const { calls } = mockApi(routes([SHORTLISTED]));
    renderWithProviders(<PipelineView />);
    await screen.findByTestId("pipeline-card");
    fireEvent.click(screen.getByRole("button", { name: "Card actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Move to Offer" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    expect(calls.find((call) => call.url === "/api/jobs/status")?.body).toMatchObject({
      status: "offer",
    });

    fireEvent.click(screen.getByRole("checkbox", { name: "Show closed" }));
    expect(await screen.findByTestId("column-rejected")).toBeInTheDocument();
    expect(window.location.search).toContain("closed=1");
  });
});
