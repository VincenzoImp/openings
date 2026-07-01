import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import { getDashboardAuthStatus, getDashboardToken, setDashboardToken } from "./api/client";

vi.mock("./api/client", () => ({
  getDashboardAuthStatus: vi.fn(),
  getDashboardToken: vi.fn(),
  setDashboardToken: vi.fn(),
}));

vi.mock("./features/jobs/JobsPage", () => ({
  JobsPage: () => <div>jobs view</div>,
}));

vi.mock("./features/analytics/AnalyticsPage", () => ({
  AnalyticsPage: () => <div>Analytics view</div>,
}));

vi.mock("./features/blacklist/BlacklistPage", () => ({
  BlacklistPage: () => <div>Blacklist view</div>,
}));

vi.mock("./features/cleanup/CleanupPage", () => ({
  CleanupPage: () => <div>Cleanup view</div>,
}));

beforeEach(() => {
  window.history.pushState(null, "", "/");
  vi.mocked(getDashboardAuthStatus).mockResolvedValue({ token_required: false });
  vi.mocked(getDashboardToken).mockReturnValue(null);
  vi.mocked(setDashboardToken).mockReturnValue(undefined);
});

test("renders the dashboard shell", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Job Search" })).toBeInTheDocument();
  expect(await screen.findByRole("navigation")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Jobs" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Saved" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Applied" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Blacklist" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cleanup" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analytics" })).toBeInTheDocument();
});

test("navigates between console workspaces", async () => {
  render(<App />);

  expect(await screen.findByText("jobs view")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Blacklist" }));
  expect(screen.getByText("Blacklist view")).toBeInTheDocument();
  expect(window.location.search).toBe("?view=blacklist");

  fireEvent.click(screen.getByRole("button", { name: "Cleanup" }));
  expect(screen.getByText("Cleanup view")).toBeInTheDocument();
  expect(window.location.search).toBe("?view=cleanup");

  fireEvent.click(screen.getByRole("button", { name: "Analytics" }));
  expect(screen.getByText("Analytics view")).toBeInTheDocument();
  expect(window.location.search).toBe("?view=analytics");
});

test("opens the workspace requested by the URL", async () => {
  window.history.pushState(null, "", "/?view=analytics");

  render(<App />);

  expect(await screen.findByText("Analytics view")).toBeInTheDocument();
});

test("shows a token gate when the API requires dashboard authentication", async () => {
  vi.mocked(getDashboardAuthStatus).mockResolvedValue({ token_required: true });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "API token required" })).toBeInTheDocument();
  expect(screen.getByLabelText("API token")).toBeInTheDocument();
});
