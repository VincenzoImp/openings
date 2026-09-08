import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { facets, mockApi, stats } from "../test/mockApi";
import { testQueryClient } from "../test/render";

function routes(tokenRequired = false) {
  return [
    { path: "/api/dashboard/auth", reply: () => ({ token_required: tokenRequired }) },
    { path: "/api/stats", reply: () => stats() },
    { path: "/api/jobs/facets", reply: () => facets() },
    { path: "/api/jobs", reply: () => ({ items: [], total: 0, limit: 500, offset: 0 }) },
    { path: "/api/runs", reply: () => [] },
    { path: "/api/sources", reply: () => [] },
  ];
}

describe("App", () => {
  it("renders the shell with counts and switches views from the keyboard", async () => {
    mockApi(routes());
    render(<App queryClient={testQueryClient()} />);
    expect(screen.getByRole("heading", { name: "Inbox" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: /Inbox/ })).toHaveTextContent("5"));
    expect(screen.getByRole("link", { name: /Pipeline/ })).toHaveTextContent("7");

    fireEvent.keyDown(window, { key: "2" });
    expect(await screen.findByRole("heading", { name: "Pipeline" })).toBeInTheDocument();
    expect(window.location.search).toBe("?view=pipeline");

    fireEvent.keyDown(window, { key: "4" });
    expect(await screen.findByRole("heading", { name: "Runs" })).toBeInTheDocument();
  });

  it("opens the shortcut help and the add-job dialog", async () => {
    mockApi(routes());
    render(<App queryClient={testQueryClient()} />);
    fireEvent.keyDown(window, { key: "?" });
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).not.toBeInTheDocument(),
    );
    fireEvent.keyDown(window, { key: "n" });
    expect(screen.getByRole("dialog", { name: "Add a posting" })).toBeInTheDocument();
  });

  it("asks for a token when the server requires one", async () => {
    mockApi(routes(true));
    render(<App queryClient={testQueryClient()} />);
    expect(await screen.findByRole("dialog", { name: "API token required" })).toBeInTheDocument();
  });
});
