import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { JobListResponse, JobRecord } from "../../api/types";
import { JobsPage } from "./JobsPage";

vi.mock("../../api/client", () => ({
  blacklistJobs: vi.fn(),
  deleteJobs: vi.fn(),
  exportJobs: vi.fn(),
  getFacets: vi.fn(),
  listJobs: vi.fn(),
  setApplied: vi.fn(),
  setBookmarked: vi.fn()
}));

import {
  blacklistJobs,
  deleteJobs,
  exportJobs,
  getFacets,
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

function response(
  items = baseJobs,
  overrides: Partial<Omit<JobListResponse, "items">> = {}
): JobListResponse {
  return {
    items,
    total: overrides.total ?? items.length,
    limit: overrides.limit ?? 50,
    offset: overrides.offset ?? 0
  };
}

function renderJobsPage(): RenderResult & { queryClient: QueryClient } {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <JobsPage />
    </QueryClientProvider>
  );
  return { ...result, queryClient };
}

beforeEach(() => {
  vi.mocked(listJobs).mockResolvedValue(response());
  vi.mocked(getFacets).mockResolvedValue({
    companies: [{ count: 1, value: "Acme Corp" }],
    job_types: [{ count: 1, value: "fulltime" }],
    locations: [{ count: 1, value: "Remote" }],
    remote: [
      { count: 1, value: true },
      { count: 1, value: false }
    ],
    sites: [
      { count: 1, value: "linkedin" },
      { count: 1, value: "indeed" }
    ]
  });
  vi.mocked(setBookmarked).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_ids: ["job-1"],
    bookmarked: true,
    applied: null,
    message: null
  });
  vi.mocked(setApplied).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_ids: ["job-1"],
    bookmarked: null,
    applied: true,
    message: null
  });
  vi.mocked(blacklistJobs).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_ids: ["job-1"],
    bookmarked: null,
    applied: null,
    message: null
  });
  vi.mocked(deleteJobs).mockResolvedValue({
    success: true,
    affected_count: 1,
    job_ids: ["job-1"],
    bookmarked: null,
    applied: null,
    message: null
  });
  vi.mocked(exportJobs).mockResolvedValue(new Blob(["id,title"]));
});

afterEach(() => {
  vi.clearAllMocks();
});

test("renders rows from the jobs API", async () => {
  renderJobsPage();

  expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
  expect(screen.getByText("Frontend Developer")).toBeInTheDocument();
  expect(screen.getByText(/2 active records/)).toBeInTheDocument();
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
  fireEvent.change(screen.getByLabelText("Location"), {
    target: { value: "remote" }
  });
  fireEvent.change(screen.getByLabelText("Job type"), {
    target: { value: "fulltime" }
  });
  fireEvent.change(screen.getByLabelText("Status"), {
    target: { value: "bookmarked" }
  });
  fireEvent.change(screen.getByLabelText("Sort"), {
    target: { value: "salary" }
  });

  await waitFor(() => {
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        bookmarked: true,
        job_types: ["fulltime"],
        location: "remote",
        min_score: 35,
        sites: ["linkedin"],
        sort: "salary",
        text: "backend"
      })
    );
  });
});

test("open status excludes saved and applied jobs", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.change(screen.getByLabelText("Status"), {
    target: { value: "open" }
  });

  await waitFor(() => {
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        applied: false,
        bookmarked: false
      })
    );
  });
});

test("next page requests the next server offset", async () => {
  vi.mocked(listJobs).mockResolvedValue(response(baseJobs, { limit: 100, total: 220 }));

  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Next page" }));

  await waitFor(() => {
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        limit: 100,
        offset: 100
      })
    );
  });
});

test("changing filters clears selected job ids", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("checkbox", { name: "Select Backend Engineer" }));
  expect(screen.getByRole("button", { name: "Blacklist selected" })).not.toBeDisabled();

  fireEvent.change(screen.getByLabelText("Site"), {
    target: { value: "linkedin" }
  });

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Blacklist selected" })).toBeDisabled();
  });
});

test("bookmark action sends an explicit boolean", async () => {
  const { queryClient } = renderJobsPage();
  const invalidate = vi.spyOn(queryClient, "invalidateQueries");
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Save Backend Engineer" }));

  await waitFor(() => expect(setBookmarked).toHaveBeenCalledWith(["job-1"], true));
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["jobs"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["stats"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["distribution"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["cleanup-preview"] });
});

test("applied action sends an explicit boolean", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Mark Backend Engineer applied" }));

  await waitFor(() => expect(setApplied).toHaveBeenCalledWith(["job-1"], true));
});

test("selected blacklist action sends selected job ids", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("checkbox", { name: "Select Backend Engineer" }));
  fireEvent.click(screen.getByRole("button", { name: "Blacklist selected" }));

  await waitFor(() => expect(blacklistJobs).toHaveBeenCalledWith(["job-1"]));
});

test("bulk actions can save apply export delete and blacklist selected jobs", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("checkbox", { name: "Select Backend Engineer" }));
  fireEvent.click(screen.getByRole("button", { name: "Save selected" }));
  fireEvent.click(screen.getByRole("button", { name: "Mark applied" }));
  fireEvent.click(screen.getByRole("button", { name: "Export selected" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete selected" }));
  fireEvent.click(screen.getByRole("button", { name: "Blacklist selected" }));

  await waitFor(() => expect(setBookmarked).toHaveBeenCalledWith(["job-1"], true));
  expect(setApplied).toHaveBeenCalledWith(["job-1"], true);
  expect(exportJobs).toHaveBeenCalledWith({ format: "csv", job_ids: ["job-1"] });
  expect(deleteJobs).toHaveBeenCalledWith(["job-1"]);
  expect(blacklistJobs).toHaveBeenCalledWith(["job-1"]);
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

  fireEvent.click(screen.getByRole("button", { name: "Export filtered" }));

  await waitFor(() => expect(exportJobs).toHaveBeenCalledWith(expect.objectContaining({ format: "csv" })));
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

test("changing filters clears the detail panel", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Open Backend Engineer details" }));
  expect(screen.getByText("Build Python APIs and data pipelines.")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Site"), {
    target: { value: "linkedin" }
  });

  await waitFor(() => {
    expect(screen.queryByText("Build Python APIs and data pipelines.")).not.toBeInTheDocument();
  });
});
