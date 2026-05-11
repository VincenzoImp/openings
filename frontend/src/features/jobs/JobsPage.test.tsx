import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { JobListResponse, JobRecord } from "../../api/types";
import { JobsPage } from "./JobsPage";

vi.mock("../../api/client", () => ({
  blacklistJobs: vi.fn(),
  listJobs: vi.fn(),
  setApplied: vi.fn(),
  setBookmarked: vi.fn()
}));

import {
  blacklistJobs,
  listJobs,
  setApplied,
  setBookmarked
} from "../../api/client";

const baseJobs: JobRecord[] = [
  {
    job_id: "job-1",
    title: "Backend Engineer",
    company: "Acme Corp",
    location: "Remote",
    job_url: "https://example.com/backend",
    site: "linkedin",
    job_type: "fulltime",
    is_remote: true,
    job_level: null,
    description: "Build Python APIs and data pipelines.",
    date_posted: null,
    min_amount: null,
    max_amount: null,
    currency: null,
    company_url: null,
    first_seen: "2026-05-01T10:00:00",
    last_seen: "2026-05-02T10:00:00",
    relevance_score: 44,
    applied: false,
    bookmarked: false
  },
  {
    job_id: "job-2",
    title: "Frontend Developer",
    company: "Widget Inc",
    location: "New York",
    job_url: "https://example.com/frontend",
    site: "indeed",
    job_type: "contract",
    is_remote: false,
    job_level: null,
    description: "Own React dashboards.",
    date_posted: null,
    min_amount: null,
    max_amount: null,
    currency: null,
    company_url: null,
    first_seen: "2026-05-01T11:00:00",
    last_seen: "2026-05-02T11:00:00",
    relevance_score: 31,
    applied: false,
    bookmarked: true
  }
];

function response(items = baseJobs): JobListResponse {
  return {
    items,
    total: items.length,
    limit: 50,
    offset: 0
  };
}

function renderJobsPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <JobsPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.mocked(listJobs).mockResolvedValue(response());
  vi.mocked(setBookmarked).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_id: "job-1",
    bookmarked: true,
    applied: null,
    message: null
  });
  vi.mocked(setApplied).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_id: "job-1",
    bookmarked: null,
    applied: true,
    message: null
  });
  vi.mocked(blacklistJobs).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_id: null,
    bookmarked: null,
    applied: null,
    message: null
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

test("renders rows from the jobs API", async () => {
  renderJobsPage();

  expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
  expect(screen.getByText("Frontend Developer")).toBeInTheDocument();
  expect(screen.getByText("2 jobs")).toBeInTheDocument();
});

test("filter controls update the list query", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.change(screen.getByLabelText("Search jobs"), {
    target: { value: "backend" }
  });
  fireEvent.change(screen.getByLabelText("Minimum score"), {
    target: { value: "35" }
  });
  fireEvent.change(screen.getByLabelText("Site"), {
    target: { value: "linkedin" }
  });
  fireEvent.change(screen.getByLabelText("Status"), {
    target: { value: "bookmarked" }
  });

  await waitFor(() => {
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        bookmarked: true,
        min_score: 35,
        site: "linkedin",
        text: "backend"
      })
    );
  });
});

test("bookmark action sends an explicit boolean", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Save Backend Engineer" }));

  await waitFor(() => expect(setBookmarked).toHaveBeenCalledWith("job-1", true));
});

test("applied action sends an explicit boolean", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Mark Backend Engineer applied" }));

  await waitFor(() => expect(setApplied).toHaveBeenCalledWith("job-1", true));
});

test("selected blacklist action sends selected job ids", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("checkbox", { name: "Select Backend Engineer" }));
  fireEvent.click(screen.getByRole("button", { name: "Blacklist selected" }));

  await waitFor(() => expect(blacklistJobs).toHaveBeenCalledWith(["job-1"]));
});

test("exports the current rows as CSV", async () => {
  const createObjectUrl = vi.fn(() => "blob:jobs");
  const revokeObjectUrl = vi.fn();
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => undefined);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createObjectUrl
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: revokeObjectUrl
  });

  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

  expect(createObjectUrl).toHaveBeenCalledTimes(1);
  expect(click).toHaveBeenCalledTimes(1);
  expect(revokeObjectUrl).toHaveBeenCalledWith("blob:jobs");
});

test("opening a row shows the detail panel", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Open Backend Engineer details" }));

  expect(screen.getByText("Build Python APIs and data pipelines.")).toBeInTheDocument();
});
