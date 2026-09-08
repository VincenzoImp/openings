import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { commonRoutes, mockApi } from "../test/mockApi";
import { testQueryClient } from "../test/render";

function routes(tokenRequired = false) {
  return [
    { path: "/api/dashboard/auth", reply: () => ({ token_required: tokenRequired }) },
    { path: "/api/jobs", reply: () => ({ items: [], total: 0, limit: 100, offset: 0 }) },
    ...commonRoutes(),
  ];
}

describe("App", () => {
  it("renders the shell with counts and switches views from the keyboard", async () => {
    mockApi(routes());
    render(<App queryClient={testQueryClient()} />);
    expect(screen.getByRole("heading", { name: "Inbox" })).toBeInTheDocument();
    // The sidebar and the phone tab bar both exist in the DOM; CSS hides one.
    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /Inbox/ })[0]).toHaveTextContent("5"),
    );
    expect(screen.getAllByRole("link", { name: /Pipeline/ })[0]).toHaveTextContent("6");

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
    const help = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    expect(help).toBeInTheDocument();
    expect(help).toHaveTextContent("Add a posting by hand");
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).not.toBeInTheDocument(),
    );
    fireEvent.keyDown(window, { key: "n" });
    expect(screen.getByRole("dialog", { name: "Add a Posting" })).toBeInTheDocument();
  });

  it("asks for a token when the server requires one", async () => {
    mockApi(routes(true));
    render(<App queryClient={testQueryClient()} />);
    expect(await screen.findByRole("dialog", { name: "API token required" })).toBeInTheDocument();
  });

  it("toggles the theme and remembers it", async () => {
    mockApi(routes());
    render(<App queryClient={testQueryClient()} />);
    fireEvent.click(screen.getAllByRole("button", { name: "Switch to dark theme" })[0]);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("openings.theme")).toBe("dark");
    fireEvent.click(screen.getAllByRole("button", { name: "Switch to light theme" })[0]);
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("recovers from a view that throws", async () => {
    mockApi([...routes(), { path: "/api/jobs/facets", reply: () => jsonThrow() }]);
    render(<App queryClient={testQueryClient()} />);
    expect(screen.getByRole("heading", { name: "Inbox" })).toBeInTheDocument();
  });
});

function jsonThrow(): Response {
  return new Response("not json", { status: 200, headers: { "Content-Type": "text/plain" } });
}
