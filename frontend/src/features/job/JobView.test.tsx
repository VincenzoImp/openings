import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JobView } from "./JobView";
import { jobDetail, mockApi } from "../../test/mockApi";
import type { Route } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

const DETAIL = jobDetail();

function routes(): Route[] {
  return [
    { method: "GET", path: `/api/jobs/${DETAIL.job_id}`, reply: () => DETAIL },
    {
      method: "POST",
      path: "/api/jobs/status",
      reply: () => ({ success: true, affected_count: 1, job_ids: [], message: null }),
    },
    {
      method: "POST",
      path: `/api/jobs/${DETAIL.job_id}/notes`,
      reply: ({ body }) => ({
        id: 7,
        job_id: DETAIL.job_id,
        created_at: "2026-09-08T10:00:00",
        title: null,
        ...(body as object),
      }),
    },
  ];
}

describe("JobView", () => {
  it("shows the posting with its score breakdown and changes status", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    expect(await screen.findByRole("heading", { name: "Backend Engineer" })).toBeInTheDocument();
    expect(screen.getByText("role")).toBeInTheDocument();
    expect(screen.getByText("+25")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), {
      target: { value: "applied" },
    });
    await waitFor(() => expect(calls.some((call) => call.url === "/api/jobs/status")).toBe(true));
    expect(calls.find((call) => call.url === "/api/jobs/status")?.body).toEqual({
      job_ids: [DETAIL.job_id],
      status: "applied",
      note: null,
    });
  });

  it("records form answers and notes in the Application tab", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    await screen.findByRole("heading", { name: "Backend Engineer" });
    fireEvent.click(screen.getByRole("tab", { name: /Application/ }));

    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), {
      target: { value: "Why us?" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Answer" }), {
      target: { value: "Because." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save answer" }));
    await waitFor(() =>
      expect(calls.some((call) => call.url.endsWith("/notes") && call.method === "POST")).toBe(
        true,
      ),
    );
    expect(calls.find((call) => call.url.endsWith("/notes"))?.body).toEqual({
      kind: "qa",
      title: "Why us?",
      body: "Because.",
    });
  });

  it("lists the timeline in the Activity tab and goes back on Escape", async () => {
    mockApi(routes());
    window.history.replaceState(null, "", `?view=inbox&job=${DETAIL.job_id}`);
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    await screen.findByRole("heading", { name: "Backend Engineer" });
    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(screen.getByText("Ingested from linkedin")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(window.location.search).toBe("?view=inbox");
  });
});
