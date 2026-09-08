import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SystemView } from "./SystemView";
import { cleanup, mockApi, stats } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

function routes() {
  return [
    { path: "/api/stats", reply: () => stats() },
    { path: "/api/dashboard/auth", reply: () => ({ token_required: false }) },
    {
      path: "/api/distribution",
      reply: () => [
        [-40, 1],
        [0, 3],
        [40, 2],
      ],
    },
    { path: "/api/cleanup/preview", reply: () => cleanup({ deleted_stale: 2 }) },
    {
      method: "GET",
      path: "/api/blacklist",
      reply: () => ({
        items: [
          {
            job_id: "b".repeat(64),
            title: "Sales Manager",
            company: "Gamma",
            location: "Remote",
            blacklisted_at: "2026-09-01T10:00:00",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    },
    {
      method: "POST",
      path: "/api/blacklist/remove",
      reply: () => ({ success: true, affected_count: 1, job_ids: [], message: null }),
    },
    { method: "POST", path: "/api/cleanup/run", reply: () => cleanup({ total_deleted: 2 }) },
  ];
}

describe("SystemView", () => {
  it("shows statistics, the distribution and the blacklist", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<SystemView />);
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("Applied 2")).toBeInTheDocument();
    expect(await screen.findByText("Sales Manager")).toBeInTheDocument();
    expect(await screen.findByText(/would delete/)).toHaveTextContent("2 stale");

    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() =>
      expect(calls.some((call) => call.url === "/api/blacklist/remove")).toBe(true),
    );
  });

  it("confirms before running the configured cleanup", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<SystemView />);
    await screen.findByText("12");
    fireEvent.click(screen.getByRole("button", { name: "Run configured cleanup" }));
    expect(screen.getByRole("dialog", { name: "Are you sure?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/cleanup/run")).toBe(true));
  });
});
