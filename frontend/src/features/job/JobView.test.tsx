import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JobView } from "./JobView";
import { commonRoutes, job, jobDetail, mockApi, ok } from "../../test/mockApi";
import type { Route } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

const DETAIL = jobDetail();

function routes(detail = DETAIL): Route[] {
  return [
    { method: "GET", path: `/api/jobs/${detail.job_id}`, reply: () => detail },
    {
      method: "PATCH",
      path: `/api/jobs/${detail.job_id}`,
      reply: ({ body }) => ({ ...detail, ...(body as object) }),
    },
    {
      method: "GET",
      path: `/api/jobs/${detail.job_id}/similar`,
      reply: () => [
        { ...job({ job_id: "3".repeat(64), title: "Platform Engineer" }), similarity: 0.8 },
      ],
    },
    { method: "POST", path: "/api/jobs/status", reply: () => ok },
    { method: "POST", path: "/api/blacklist/remove", reply: () => ok },
    {
      method: "POST",
      path: `/api/jobs/${detail.job_id}/notes`,
      reply: ({ body }) => ({
        id: 7,
        job_id: detail.job_id,
        created_at: "2026-09-08T10:00:00+00:00",
        updated_at: null,
        title: null,
        ...(body as object),
      }),
    },
    ...commonRoutes(),
  ];
}

describe("JobView", () => {
  it("shows the posting with its score breakdown, similar postings and changes status", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    expect(await screen.findByRole("heading", { name: "Backend Engineer" })).toBeInTheDocument();
    expect(screen.getByText("role")).toBeInTheDocument();
    expect(screen.getByText("+25")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(await screen.findByText("Platform Engineer")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();

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
    expect(window.location.search).toContain("tab=application");

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
    fireEvent.click(screen.getByRole("tab", { name: /Activity/ }));
    expect(screen.getByText("Ingested from linkedin")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(window.location.search).toBe("?view=inbox");
  });

  it("edits the posting from the keyboard and sends only the changed fields", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    await screen.findByRole("heading", { name: "Backend Engineer" });
    fireEvent.keyDown(window, { key: "e" });
    const dialog = await screen.findByRole("dialog", { name: "Edit Posting" });
    fireEvent.change(within(dialog).getByLabelText("Title"), {
      target: { value: "Senior Backend Engineer" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save Changes" }));
    await waitFor(() => expect(calls.some((call) => call.method === "PATCH")).toBe(true));
    expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({
      title: "Senior Backend Engineer",
    });
  });

  it("shows a blacklisted job with a Restore action", async () => {
    const { calls } = mockApi(routes(jobDetail({ status: "blacklisted" })));
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    await screen.findByRole("heading", { name: "Backend Engineer" });
    expect(screen.getByText(/Blacklisted\./)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() =>
      expect(calls.some((call) => call.url === "/api/blacklist/remove")).toBe(true),
    );
  });

  it("steps through the list it was opened from", async () => {
    const other = "9".repeat(64);
    sessionStorage.setItem("openings.last-list", JSON.stringify([DETAIL.job_id, other]));
    mockApi(routes());
    window.history.replaceState(null, "", `?view=inbox&job=${DETAIL.job_id}`);
    renderWithProviders(<JobView jobId={DETAIL.job_id} />);
    await screen.findByRole("heading", { name: "Backend Engineer" });
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "]" });
    expect(window.location.search).toContain(`job=${other}`);
  });
});
