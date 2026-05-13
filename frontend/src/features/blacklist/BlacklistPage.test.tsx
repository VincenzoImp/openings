import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { BlacklistPage } from "./BlacklistPage";

vi.mock("../../api/client", () => ({
  listBlacklistedJobs: vi.fn(),
  purgeBlacklist: vi.fn(),
  unblacklistJobs: vi.fn()
}));

import { listBlacklistedJobs, purgeBlacklist, unblacklistJobs } from "../../api/client";

function renderBlacklistPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false }
    }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <BlacklistPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.mocked(listBlacklistedJobs).mockResolvedValue({
    items: [
      {
        blacklisted_at: "2026-05-10T10:00:00",
        company: "Acme Corp",
        job_id: "job-1",
        location: "Remote",
        title: "Backend Engineer"
      }
    ],
    limit: 100,
    offset: 0,
    total: 1
  });
  vi.mocked(unblacklistJobs).mockResolvedValue({
    affected_count: 1,
    applied: null,
    bookmarked: null,
    job_ids: ["job-1"],
    message: null,
    success: true
  });
  vi.mocked(purgeBlacklist).mockResolvedValue({
    affected_count: 1,
    applied: null,
    bookmarked: null,
    job_ids: [],
    message: null,
    success: true
  });
});

test("lists and filters blacklist entries", async () => {
  renderBlacklistPage();

  expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Search blacklist"), {
    target: { value: "acme" }
  });

  await waitFor(() => {
    expect(listBlacklistedJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({ text: "acme" })
    );
  });

  fireEvent.change(screen.getByLabelText("Blacklist company"), {
    target: { value: "Acme Corp" }
  });
  fireEvent.change(screen.getByLabelText("Blacklist location"), {
    target: { value: "Remote" }
  });

  await waitFor(() => {
    expect(listBlacklistedJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({ company: "Acme Corp", location: "Remote", text: "acme" })
    );
  });
});

test("blacklist pagination requests the next server page", async () => {
  vi.mocked(listBlacklistedJobs).mockResolvedValue({
    items: [
      {
        blacklisted_at: "2026-05-10T10:00:00",
        company: "Acme Corp",
        job_id: "job-1",
        location: "Remote",
        title: "Backend Engineer"
      }
    ],
    limit: 100,
    offset: 0,
    total: 220
  });

  renderBlacklistPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Next blacklist page" }));

  await waitFor(() => {
    expect(listBlacklistedJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 100, offset: 100 })
    );
  });
});

test("unblacklists selected entries and can purge the blacklist", async () => {
  renderBlacklistPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("checkbox", { name: "Select Backend Engineer" }));
  fireEvent.click(screen.getByRole("button", { name: "Unblacklist selected" }));
  fireEvent.click(screen.getByRole("button", { name: "Purge all" }));

  await waitFor(() => expect(unblacklistJobs).toHaveBeenCalledWith(["job-1"]));
  expect(screen.getByRole("heading", { name: "Purge blacklist entries?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm purge blacklist" }));

  await waitFor(() => expect(purgeBlacklist).toHaveBeenCalledWith(undefined));
});
