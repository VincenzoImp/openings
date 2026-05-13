import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import { getDashboardAuthStatus, getDashboardToken, setDashboardToken } from "./api/client";

vi.mock("./api/client", () => ({
  getDashboardAuthStatus: vi.fn(),
  getDashboardToken: vi.fn(),
  setDashboardToken: vi.fn()
}));

vi.mock("./features/jobs/JobsPage", () => ({
  JobsPage: ({ preset }: { preset?: string }) => <div>{preset ?? "all"} jobs view</div>
}));

vi.mock("./features/analytics/AnalyticsPage", () => ({
  AnalyticsPage: () => <div>Analytics view</div>
}));

vi.mock("./features/blacklist/BlacklistPage", () => ({
  BlacklistPage: () => <div>Blacklist view</div>
}));

vi.mock("./features/cleanup/CleanupPage", () => ({
  CleanupPage: () => <div>Cleanup view</div>
}));

beforeEach(() => {
  vi.mocked(getDashboardAuthStatus).mockResolvedValue({ token_required: false });
  vi.mocked(getDashboardToken).mockReturnValue(null);
  vi.mocked(setDashboardToken).mockReturnValue(undefined);
});

test("renders the dashboard shell", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Job Search" })).toBeInTheDocument();
  expect(await screen.findByRole("navigation")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Jobs" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Saved" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Applied" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Blacklist" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cleanup" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analytics" })).toBeInTheDocument();
});

test("navigates between console workspaces", async () => {
  render(<App />);

  expect(await screen.findByText("all jobs view")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Saved" }));
  expect(screen.getByText("saved jobs view")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Applied" }));
  expect(screen.getByText("applied jobs view")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Blacklist" }));
  expect(screen.getByText("Blacklist view")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Cleanup" }));
  expect(screen.getByText("Cleanup view")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Analytics" }));
  expect(screen.getByText("Analytics view")).toBeInTheDocument();
});

test("shows a token gate when the API requires dashboard authentication", async () => {
  vi.mocked(getDashboardAuthStatus).mockResolvedValue({ token_required: true });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "API token required" })).toBeInTheDocument();
  expect(screen.getByLabelText("API token")).toBeInTheDocument();
});
