import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SystemView } from "./SystemView";
import { getToken } from "../../api/client";
import { cleanup, commonRoutes, job, mockApi, ok } from "../../test/mockApi";
import type { Route } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

function routes(): Route[] {
  return [
    {
      path: "/api/distribution",
      reply: () => [
        [-40, 1],
        [0, 3],
        [40, 2],
      ],
    },
    { path: "/api/cleanup/preview", reply: () => cleanup({ deleted_stale: 2, total_deleted: 2 }) },
    {
      method: "GET",
      path: "/api/blacklist",
      reply: () => ({
        items: [
          job({
            job_id: "b".repeat(64),
            title: "Sales Manager",
            company: "Gamma",
            status: "blacklisted",
            status_changed_at: "2026-09-01T10:00:00+00:00",
          }),
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    },
    { method: "POST", path: "/api/blacklist/remove", reply: () => ok },
    { method: "POST", path: "/api/cleanup/run", reply: () => cleanup({ total_deleted: 2 }) },
    {
      method: "POST",
      path: "/api/cleanup/delete-below-score",
      reply: () => ({ ...ok, affected_count: 3 }),
    },
    {
      path: "/api/export/jobs",
      reply: () => new Response("a,b\n", { status: 200, headers: { "Content-Type": "text/csv" } }),
    },
    ...commonRoutes(),
  ];
}

describe("SystemView", () => {
  it("shows statistics, the distribution, settings and the blacklist", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<SystemView />);
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("Applied 2")).toBeInTheDocument();
    expect(await screen.findByText("Sales Manager")).toBeInTheDocument();
    expect(await screen.findByText(/would delete/)).toHaveTextContent("2 stale");
    expect(await screen.findByText("Europe/Zurich")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Restore/ }));
    await waitFor(() =>
      expect(calls.some((call) => call.url === "/api/blacklist/remove")).toBe(true),
    );
  });

  it("confirms with counts before running the configured cleanup", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<SystemView />);
    await screen.findByText("12");
    fireEvent.click(screen.getByRole("button", { name: "Run configured cleanup…" }));
    const dialog = await screen.findByRole("dialog", { name: "Run the configured cleanup?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete 2" }));
    await waitFor(() => expect(calls.some((call) => call.url === "/api/cleanup/run")).toBe(true));
  });

  it("dry-runs a score deletion before asking", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<SystemView />);
    await screen.findByText("12");
    fireEvent.change(screen.getByLabelText("Delete new jobs below score"), {
      target: { value: "5" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Delete…" })[0]);
    const dialog = await screen.findByRole("dialog", { name: "Delete new jobs below score 5?" });
    expect(calls.find((call) => call.url === "/api/cleanup/delete-below-score")?.body).toEqual({
      score: 5,
      dry_run: true,
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete 3" }));
    await waitFor(() =>
      expect(calls.filter((call) => call.url === "/api/cleanup/delete-below-score")).toHaveLength(
        2,
      ),
    );
    expect(calls.filter((call) => call.url === "/api/cleanup/delete-below-score")[1].body).toEqual({
      score: 5,
      dry_run: false,
    });
  });

  it("switches the theme, exports and stores the token", async () => {
    const { calls } = mockApi(routes());
    renderWithProviders(<SystemView />);
    await screen.findByText("12");
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");

    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    await waitFor(() =>
      expect(calls.some((call) => call.url.startsWith("/api/export/jobs?"))).toBe(true),
    );
    expect(calls.find((call) => call.url.startsWith("/api/export/jobs?"))?.url).toContain(
      "statuses=applied&limit=0&format=csv",
    );

    fireEvent.change(screen.getByLabelText("API token"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(getToken()).toBe("secret");
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(getToken()).toBeNull();
  });
});
