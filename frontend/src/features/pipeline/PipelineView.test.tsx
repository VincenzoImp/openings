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
const REJECTED = job({ job_id: "3".repeat(64), title: "Mobile Engineer", status: "rejected" });

function routes(items = [SHORTLISTED, APPLIED, REJECTED]): Route[] {
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
  it("shows every status column and moves the selected card forward with ]", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<PipelineView />);
    const shortlisted = await screen.findByTestId("column-shortlisted");
    await waitFor(() =>
      expect(within(shortlisted).getAllByTestId("pipeline-card")).toHaveLength(1),
    );
    expect(
      within(screen.getByTestId("column-applied")).getByText("Data Engineer"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("column-rejected")).getByText("Mobile Engineer"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("column-withdrawn")).toHaveTextContent("None closed this way yet.");
    expect(calls[0].url).toContain("statuses=shortlisted&statuses=applied");

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

  it("moves a card from its menu", async () => {
    const { calls } = mockApi(routes([SHORTLISTED]));
    renderWithProviders(<PipelineView />);
    await screen.findByTestId("pipeline-card");
    fireEvent.click(screen.getByRole("button", { name: /Actions for/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Move to Offer" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    expect(calls.find((call) => call.url === "/api/jobs/status")?.body).toMatchObject({
      status: "offer",
    });
  });
});
