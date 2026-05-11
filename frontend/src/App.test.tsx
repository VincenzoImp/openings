import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import { getDashboardAuthStatus, getDashboardToken, setDashboardToken } from "./api/client";

vi.mock("./api/client", () => ({
  getDashboardAuthStatus: vi.fn(),
  getDashboardToken: vi.fn(),
  setDashboardToken: vi.fn()
}));

vi.mock("./features/jobs/JobsPage", () => ({
  JobsPage: () => <div>Jobs view</div>
}));

vi.mock("./features/analytics/AnalyticsPage", () => ({
  AnalyticsPage: () => <div>Analytics view</div>
}));

vi.mock("./features/database/DatabasePage", () => ({
  DatabasePage: () => <div>Database view</div>
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
});

test("shows a token gate when the API requires dashboard authentication", async () => {
  vi.mocked(getDashboardAuthStatus).mockResolvedValue({ token_required: true });

  render(<App />);

  expect(await screen.findByRole("heading", { name: "API token required" })).toBeInTheDocument();
  expect(screen.getByLabelText("API token")).toBeInTheDocument();
});
