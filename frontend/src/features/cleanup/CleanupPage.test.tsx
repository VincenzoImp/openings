import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { CleanupPage } from "./CleanupPage";

vi.mock("../../api/client", () => ({
  deleteJobsBelowScore: vi.fn(),
  deleteStaleJobs: vi.fn(),
  previewCleanup: vi.fn(),
  purgeCleanupBlacklist: vi.fn(),
  runCleanup: vi.fn()
}));

import {
  deleteJobsBelowScore,
  deleteStaleJobs,
  previewCleanup,
  purgeCleanupBlacklist,
  runCleanup
} from "../../api/client";

function renderCleanupPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false }
    }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <CleanupPage />
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
  vi.mocked(deleteJobsBelowScore).mockResolvedValue({
    affected_count: 2,
    applied: null,
    bookmarked: null,
    job_ids: [],
    message: null,
    success: true
  });
  vi.mocked(deleteStaleJobs).mockResolvedValue({
    affected_count: 1,
    applied: null,
    bookmarked: null,
    job_ids: [],
    message: null,
    success: true
  });
  vi.mocked(purgeCleanupBlacklist).mockResolvedValue({
    affected_count: 5,
    applied: null,
    bookmarked: null,
    job_ids: [],
    message: null,
    success: true
  });
});

test("renders cleanup preview counts", async () => {
  renderCleanupPage();

  expect(await screen.findByText("8")).toBeInTheDocument();
  expect(screen.getByText("Below score")).toBeInTheDocument();
  expect(screen.getByText("Blacklist purge")).toBeInTheDocument();
});

test("runs configured and manual cleanup commands", async () => {
  renderCleanupPage();
  await screen.findByText("8");

  fireEvent.click(screen.getByLabelText("Confirm cleanup"));
  fireEvent.click(screen.getByRole("button", { name: "Run configured cleanup" }));

  fireEvent.change(screen.getByLabelText("Score threshold"), {
    target: { value: "30" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Delete below score" }));

  fireEvent.change(screen.getByLabelText("Stale days"), {
    target: { value: "45" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Delete stale jobs" }));

  fireEvent.change(screen.getByLabelText("Blacklist age days"), {
    target: { value: "90" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Purge aged blacklist" }));

  await waitFor(() => expect(runCleanup).toHaveBeenCalledTimes(1));
  expect(vi.mocked(deleteJobsBelowScore).mock.calls[0][0]).toBe(30);
  expect(vi.mocked(deleteStaleJobs).mock.calls[0][0]).toBe(45);
  expect(vi.mocked(purgeCleanupBlacklist).mock.calls[0][0]).toBe(90);
});
