import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunsView } from "./RunsView";
import { mockApi, run } from "../../test/mockApi";
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
    ]);
    renderWithProviders(<RunsView />);
    const runs = await screen.findAllByTestId("run");
    expect(runs).toHaveLength(2);
    expect(runs[0]).toHaveTextContent("ok");
    expect(runs[0]).toHaveTextContent("25m 0s");
    expect(runs[1]).toHaveTextContent("failed");
    expect(runs[1]).toHaveTextContent("3 errors");
  });

  it("explains an empty history", async () => {
    mockApi([{ path: "/api/runs", reply: () => [] }]);
    renderWithProviders(<RunsView />);
    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
  });
});
