import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { DatabasePage } from "./DatabasePage";

vi.mock("../../api/client", () => ({
  previewCleanup: vi.fn(),
  runCleanup: vi.fn()
}));

import { previewCleanup, runCleanup } from "../../api/client";

function renderDatabasePage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false }
    }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <DatabasePage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.mocked(previewCleanup).mockResolvedValue({
    deleted_below_score: 2,
    deleted_stale: 1,
    protected_applied: 4,
    protected_bookmarked: 3,
    purged_blacklist: 5,
    total_deleted: 8
  });
  vi.mocked(runCleanup).mockResolvedValue({
    deleted_below_score: 2,
    deleted_stale: 1,
    protected_applied: 4,
    protected_bookmarked: 3,
    purged_blacklist: 5,
    total_deleted: 8
  });
});

test("renders cleanup preview counts", async () => {
  renderDatabasePage();

  expect(await screen.findByText("8")).toBeInTheDocument();
  expect(screen.getByText("Below score")).toBeInTheDocument();
  expect(screen.getByText("Blacklist purge")).toBeInTheDocument();
});

test("runs cleanup only after explicit confirmation", async () => {
  renderDatabasePage();
  await screen.findByText("8");

  fireEvent.click(screen.getByRole("button", { name: "Run cleanup" }));
  expect(runCleanup).not.toHaveBeenCalled();

  fireEvent.click(screen.getByLabelText("Confirm cleanup"));
  fireEvent.click(screen.getByRole("button", { name: "Run cleanup" }));

  await waitFor(() => expect(runCleanup).toHaveBeenCalledTimes(1));
});
