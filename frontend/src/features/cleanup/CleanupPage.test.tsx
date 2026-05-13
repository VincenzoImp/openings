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
  expect(runCleanup).not.toHaveBeenCalled();
  expect(screen.getByRole("heading", { name: "Run configured cleanup?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm configured cleanup" }));
  await waitFor(() => expect(runCleanup).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(screen.getByRole("button", { name: "Delete below score" })).not.toBeDisabled());

  fireEvent.change(screen.getByLabelText("Score threshold"), {
    target: { value: "30" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Delete below score" }));
  expect(screen.getByRole("heading", { name: "Delete jobs below score?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete below score" }));
  await waitFor(() =>
    expect(screen.queryByRole("heading", { name: "Delete jobs below score?" })).not.toBeInTheDocument()
  );
  await waitFor(() => expect(screen.getByRole("button", { name: "Delete stale jobs" })).not.toBeDisabled());

  fireEvent.change(screen.getByLabelText("Stale days"), {
    target: { value: "45" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Delete stale jobs" }));
  expect(screen.getByRole("heading", { name: "Delete stale jobs?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete stale jobs" }));
  await waitFor(() =>
    expect(screen.queryByRole("heading", { name: "Delete stale jobs?" })).not.toBeInTheDocument()
  );
  await waitFor(() => expect(screen.getByRole("button", { name: "Purge aged blacklist" })).not.toBeDisabled());

  fireEvent.change(screen.getByLabelText("Blacklist age days"), {
    target: { value: "90" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Purge aged blacklist" }));
  expect(screen.getByRole("heading", { name: "Purge aged blacklist entries?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm purge blacklist" }));

  expect(vi.mocked(deleteJobsBelowScore).mock.calls[0][0]).toBe(30);
  expect(vi.mocked(deleteStaleJobs).mock.calls[0][0]).toBe(45);
  await waitFor(() => expect(vi.mocked(purgeCleanupBlacklist).mock.calls[0]?.[0]).toBe(90));
  expect(vi.mocked(purgeCleanupBlacklist).mock.calls[0][0]).toBe(90);
});

test("disables manual cleanup commands when numeric input is invalid", async () => {
  renderCleanupPage();
  await screen.findByText("8");

  fireEvent.change(screen.getByLabelText("Score threshold"), {
    target: { value: "" }
  });
  fireEvent.change(screen.getByLabelText("Stale days"), {
    target: { value: "0" }
  });
  fireEvent.change(screen.getByLabelText("Blacklist age days"), {
    target: { value: "-3" }
  });

  expect(screen.getByRole("button", { name: "Delete below score" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Delete stale jobs" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Purge aged blacklist" })).toBeDisabled();
});
