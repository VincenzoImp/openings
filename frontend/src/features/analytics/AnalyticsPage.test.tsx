import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { AnalyticsPage } from "./AnalyticsPage";

vi.mock("../../api/client", () => ({
  getDistribution: vi.fn(),
  getStats: vi.fn()
}));

import { getDistribution, getStats } from "../../api/client";

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
});

test("renders analytics stats and score distribution", async () => {
  renderAnalyticsPage();

  expect(await screen.findByText("42")).toBeInTheDocument();
  expect(screen.getByText("32.5")).toBeInTheDocument();
  expect(screen.getByText("40-44")).toBeInTheDocument();
  expect(screen.getByText("5")).toBeInTheDocument();
});
