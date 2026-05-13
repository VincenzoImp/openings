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
  searchSimilarJobs: vi.fn(),
  setApplied: vi.fn(),
  setBookmarked: vi.fn()
}));

import {
  blacklistJobs,
  deleteJobs,
  exportJobs,
  getFacets,
  listJobs,
  searchSimilarJobs,
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
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:jobs")
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn()
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
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
  vi.mocked(searchSimilarJobs).mockResolvedValue([
    {
      company: "Acme Corp",
      job_id: "job-1",
      job_url: "https://example.com/backend",
      location: "Remote",
      relevance_score: 44,
      similarity: 0.91,
      site: "linkedin",
      title: "Backend Engineer"
    }
  ]);
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
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
  fireEvent.click(screen.getByRole("button", { name: /More filters/ }));
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
  fireEvent.change(screen.getByLabelText("First seen from"), {
    target: { value: "2026-05-01" }
  });
  fireEvent.change(screen.getByLabelText("Last seen to"), {
    target: { value: "2026-05-09" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Saved" }));
  fireEvent.change(screen.getByLabelText("Sort"), {
    target: { value: "salary" }
  });

  await waitFor(() => {
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        bookmarked: true,
        first_seen_from: "2026-05-01",
        job_types: ["fulltime"],
        last_seen_to: "2026-05-09",
        location: "remote",
        min_score: 35,
        sites: ["linkedin"],
        sort: "salary",
        text: "backend"
      })
    );
  });
});

test("page size is sent to the jobs API", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.change(screen.getByLabelText("Page size"), {
    target: { value: "50" }
  });

  await waitFor(() => {
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        limit: 50,
        offset: 0
      })
    );
  });
});

test("open status excludes saved and applied jobs", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Open" }));

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

  fireEvent.click(screen.getByRole("button", { name: /More filters/ }));
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

  expect(blacklistJobs).not.toHaveBeenCalled();
  expect(screen.getByRole("heading", { name: "Blacklist selected jobs?" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Confirm blacklist" }));

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
  expect(screen.getByRole("heading", { name: "Delete selected jobs permanently?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));

  await waitFor(() => expect(setBookmarked).toHaveBeenCalledWith(["job-1"], true));
  expect(setApplied).toHaveBeenCalledWith(["job-1"], true);
  expect(exportJobs).toHaveBeenCalledWith({ format: "csv", job_ids: ["job-1"] });
  expect(deleteJobs).toHaveBeenCalledWith(["job-1"]);
});

test("row actions can blacklist and delete one job", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Blacklist Backend Engineer" }));
  expect(screen.getByRole("heading", { name: "Blacklist Backend Engineer?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm blacklist" }));
  await waitFor(() => expect(blacklistJobs).toHaveBeenCalledWith(["job-1"]));

  fireEvent.click(screen.getByRole("button", { name: "Delete Backend Engineer" }));
  expect(screen.getByRole("heading", { name: "Delete Backend Engineer permanently?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await waitFor(() => expect(deleteJobs).toHaveBeenCalledWith(["job-1"]));
});

test("reset filters returns the job query to the default console state", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.change(screen.getByLabelText("Search jobs"), {
    target: { value: "backend" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Saved" }));
  fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));

  await waitFor(() => {
    expect(screen.getByLabelText("Search jobs")).toHaveValue("");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  });
  expect(listJobs).toHaveBeenCalledWith(
    expect.objectContaining({
      limit: 100,
      offset: 0,
      sort: "score"
    })
  );
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

test("exports filtered jobs as JSON when selected", async () => {
  const createObjectUrl = vi.fn(() => "blob:jobs");
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createObjectUrl
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn()
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.change(screen.getByLabelText("Export format"), {
    target: { value: "json" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Export filtered" }));

  await waitFor(() => expect(exportJobs).toHaveBeenCalledWith(expect.objectContaining({ format: "json" })));
});

test("semantic search returns matching jobs without replacing the main list", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.change(screen.getByLabelText("Semantic search"), {
    target: { value: "python backend platform" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Search similar jobs" }));

  await waitFor(() =>
    expect(searchSimilarJobs).toHaveBeenCalledWith(
      {
        min_score: undefined,
        n_results: 10,
        q: "python backend platform",
        site: undefined
      },
      expect.any(Object)
    )
  );
  expect(await screen.findByText(/91% match/)).toBeInTheDocument();
});

test("opening a row shows the detail panel", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Open Backend Engineer details" }));

  expect(screen.getByText("Build Python APIs and data pipelines.")).toBeInTheDocument();
});

test("detail panel can permanently delete the open job", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Open Backend Engineer details" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete job" }));
  expect(screen.getByRole("heading", { name: "Delete Backend Engineer permanently?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));

  await waitFor(() => expect(deleteJobs).toHaveBeenCalledWith(["job-1"]));
});

test("changing filters clears the detail panel", async () => {
  renderJobsPage();
  await screen.findByText("Backend Engineer");

  fireEvent.click(screen.getByRole("button", { name: "Open Backend Engineer details" }));
  expect(screen.getByText("Build Python APIs and data pipelines.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /More filters/ }));
  fireEvent.change(screen.getByLabelText("Site"), {
    target: { value: "linkedin" }
  });

  await waitFor(() => {
    expect(screen.queryByText("Build Python APIs and data pipelines.")).not.toBeInTheDocument();
  });
});
