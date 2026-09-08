import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunsView } from "./RunsView";
import { commonRoutes, mockApi, run } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

describe("RunsView", () => {
  it("lists runs with per-source counts and errors", async () => {
    mockApi([
      {
        path: "/api/runs",
        reply: () => [
          run(),
          run({
            id: 2,
            success: false,
            errors: ["linkedin: 429"],
            sources: [
              { name: "linkedin", tasks: 6, succeeded: 4, failed: 2, rows: 10, errors: ["a", "b"] },
            ],
          }),
        ],
      },
      ...commonRoutes(),
    ]);
    renderWithProviders(<RunsView />);
    const runs = await screen.findAllByTestId("run");
    expect(runs).toHaveLength(2);
    expect(runs[0]).toHaveTextContent("ok");
    expect(runs[0]).toHaveTextContent("25m 0s");
    expect(runs[1]).toHaveTextContent("failed");
    expect(runs[1]).toHaveTextContent("3 errors");
  });

  it("explains an empty history and requests a run", async () => {
    const { calls } = mockApi([
      {
        method: "POST",
        path: "/api/runs",
        reply: () => ({ running: false, run: null, requested: true }),
      },
      ...commonRoutes(),
    ]);
    renderWithProviders(<RunsView />);
    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Run now/ }));
    await waitFor(() =>
      expect(calls.some((call) => call.method === "POST" && call.url === "/api/runs")).toBe(true),
    );
  });

  it("shows an open run as running", async () => {
    const open = run({ id: 3, finished_at: null, running: true, duration_seconds: 0 });
    mockApi([
      { path: "/api/runs/status", reply: () => ({ running: true, run: open, requested: false }) },
      { path: "/api/runs", reply: () => [open] },
      ...commonRoutes(),
    ]);
    renderWithProviders(<RunsView />);
    const runs = await screen.findAllByTestId("run");
    expect(runs[0]).toHaveTextContent("running");
    expect(await screen.findByText(/Running since/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run now/ })).toBeDisabled();
  });
});
