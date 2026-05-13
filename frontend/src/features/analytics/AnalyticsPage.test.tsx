import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { AnalyticsPage } from "./AnalyticsPage";

vi.mock("../../api/client", () => ({
  getDistribution: vi.fn(),
  getFacets: vi.fn(),
  getStats: vi.fn()
}));

import { getDistribution, getFacets, getStats } from "../../api/client";

function renderAnalyticsPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AnalyticsPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.mocked(getStats).mockResolvedValue({
    applied: 2,
    avg_relevance_score: 32.5,
    blacklisted: 4,
    new_today: 3,
    seen_today: 8,
    total_jobs: 42
  });
  vi.mocked(getDistribution).mockResolvedValue([
    [0, 2],
    [20, 7],
    [40, 5]
  ]);
  vi.mocked(getFacets).mockResolvedValue({
    companies: [{ count: 5, value: "Acme Corp" }],
    job_types: [{ count: 6, value: "fulltime" }],
    locations: [{ count: 7, value: "Remote" }],
    remote: [{ count: 8, value: true }],
    sites: [{ count: 9, value: "indeed" }]
  });
});

test("renders analytics stats and score distribution", async () => {
  renderAnalyticsPage();

  expect(await screen.findByRole("heading", { name: "Analytics" })).toBeInTheDocument();
  expect(await screen.findByText("42")).toBeInTheDocument();
  expect(screen.getByText("32.5")).toBeInTheDocument();
  expect(screen.getByText("New today")).toBeInTheDocument();
  expect(screen.getByText("Blacklisted")).toBeInTheDocument();
  expect(screen.getByText("40-44")).toBeInTheDocument();
  expect(screen.getAllByText("5").length).toBeGreaterThan(0);
  expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
  expect(screen.getByText("fulltime")).toBeInTheDocument();
});
