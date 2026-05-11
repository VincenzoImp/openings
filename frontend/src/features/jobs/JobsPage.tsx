import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Bookmark,
  Check,
  Download,
  ExternalLink,
  PanelRightOpen,
  Search,
  Trash2,
  X
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { blacklistJobs, setApplied, setBookmarked } from "../../api/client";
import type { JobRecord } from "../../api/types";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { jobsQuery } from "./jobQueries";

type StatusFilter = "all" | "bookmarked" | "applied" | "open";

const columnHelper = createColumnHelper<JobRecord>();
const columns = [
  columnHelper.accessor("relevance_score", { header: "Score" }),
  columnHelper.accessor("title", { header: "Role" }),
  columnHelper.accessor("company", { header: "Company" }),
  columnHelper.accessor("site", { header: "Site" }),
  columnHelper.display({ id: "status", header: "Status" }),
  columnHelper.display({ id: "actions", header: "Actions" })
];

function scoreTone(score: number) {
  if (score >= 40) {
    return "good";
  }
  if (score >= 25) {
    return "warning";
  }
  return "neutral";
}

function statusBadges(job: JobRecord) {
  if (job.applied) {
    return <Badge tone="good">Applied</Badge>;
  }
  if (job.bookmarked) {
    return <Badge tone="warning">Saved</Badge>;
  }
  return <Badge>Open</Badge>;
}

function csvCell(value: string | number | boolean | null) {
  return `"${String(value ?? "").replaceAll("\"", "\"\"")}"`;
}

function exportJobsCsv(jobs: JobRecord[]) {
  const columns = ["title", "company", "location", "site", "relevance_score", "applied", "bookmarked"];
  const lines = [
    columns.join(","),
    ...jobs.map((job) =>
      [
        job.title,
        job.company,
        job.location,
        job.site,
        job.relevance_score,
        job.applied,
        job.bookmarked
      ]
        .map(csvCell)
        .join(",")
    )
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "jobs.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function JobsPage() {
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [minScore, setMinScore] = useState("");
  const [site, setSite] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);

  const params = useMemo(
    () => ({
      applied: status === "applied" ? true : status === "open" ? false : undefined,
      bookmarked: status === "bookmarked" ? true : undefined,
      limit: 200,
      min_score: minScore ? Number(minScore) : undefined,
      offset: 0,
      remote: remoteOnly ? true : undefined,
      site: site || undefined,
      sort: "score" as const,
      text: text || undefined
    }),
    [minScore, remoteOnly, site, status, text]
  );

  const { data, isLoading, isError } = useQuery(jobsQuery(params));
  const jobs = data?.items ?? [];
  const table = useReactTable({
    columns,
    data: jobs,
    getCoreRowModel: getCoreRowModel()
  });
  const rows = table.getRowModel().rows;
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    estimateSize: () => 58,
    getScrollElement: () => scrollRef.current,
    overscan: 8
  });
  const virtualItems = rowVirtualizer.getVirtualItems();
  const visibleRows = virtualItems.length
    ? virtualItems.map((item) => ({ fallbackIndex: item.index, item, row: rows[item.index] }))
    : rows.map((row, index) => ({ item: null, row, fallbackIndex: index }));

  const invalidateJobs = () => queryClient.invalidateQueries({ queryKey: ["jobs"] });
  const bookmarkMutation = useMutation({
    mutationFn: (job: JobRecord) => setBookmarked(job.job_id, !job.bookmarked),
    onSuccess: invalidateJobs
  });
  const appliedMutation = useMutation({
    mutationFn: (job: JobRecord) => setApplied(job.job_id, !job.applied),
    onSuccess: invalidateJobs
  });
  const blacklistMutation = useMutation({
    mutationFn: (jobIds: string[]) => blacklistJobs(jobIds),
    onSuccess: () => {
      setSelectedIds(new Set());
      return invalidateJobs();
    }
  });

  const toggleSelected = (jobId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  };

  return (
    <section className="workspace" aria-label="Jobs">
      <div className="toolbar toolbar--stacked">
        <label className="search-field">
          <Search aria-hidden="true" size={18} />
          <Input
            aria-label="Search jobs"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Search title, company, location"
          />
        </label>
        <label className="filter-field">
          <span>Minimum score</span>
          <Input
            aria-label="Minimum score"
            min="0"
            max="100"
            type="number"
            value={minScore}
            onChange={(event) => setMinScore(event.target.value)}
          />
        </label>
        <label className="filter-field">
          <span>Site</span>
          <Input
            aria-label="Site"
            value={site}
            onChange={(event) => setSite(event.target.value)}
          />
        </label>
        <label className="filter-field">
          <span>Status</span>
          <select
            aria-label="Status"
            className="select"
            value={status}
            onChange={(event) => setStatus(event.target.value as StatusFilter)}
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="bookmarked">Saved</option>
            <option value="applied">Applied</option>
          </select>
        </label>
        <label className="toggle-field">
          <input
            checked={remoteOnly}
            onChange={(event) => setRemoteOnly(event.target.checked)}
            type="checkbox"
          />
          Remote
        </label>
        <Badge>{data?.total ?? 0} jobs</Badge>
      </div>

      <div className="bulk-bar">
        <Button disabled={jobs.length === 0} onClick={() => exportJobsCsv(jobs)}>
          <Download aria-hidden="true" size={16} />
          Export CSV
        </Button>
        <Button
          disabled={selectedIds.size === 0 || blacklistMutation.isPending}
          onClick={() => blacklistMutation.mutate([...selectedIds])}
          variant="danger"
        >
          <Trash2 aria-hidden="true" size={16} />
          Blacklist selected
        </Button>
      </div>

      <div className={selectedJob ? "job-layout job-layout--detail" : "job-layout"}>
        <div className="table-shell">
          <div className="table-header table-header--jobs" role="row">
            <span />
            <span>Score</span>
            <span>Role</span>
            <span>Company</span>
            <span>Site</span>
            <span>Status</span>
            <span>Actions</span>
          </div>

          {isLoading ? <div className="table-state">Loading jobs</div> : null}
          {isError ? <div className="table-state">Unable to load jobs</div> : null}

          <div className="table-body" ref={scrollRef}>
            <div
              className="virtual-spacer"
              style={{ height: virtualItems.length ? rowVirtualizer.getTotalSize() : "auto" }}
            >
              {visibleRows.map(({ item, row, fallbackIndex }) => {
                const job = row.original;
                const top = item?.start ?? (fallbackIndex ?? 0) * 58;
                return (
                  <div
                    className="table-row table-row--jobs"
                    key={job.job_id}
                    role="row"
                    style={
                      item
                        ? {
                            position: "absolute",
                            transform: `translateY(${top}px)`
                          }
                        : undefined
                    }
                  >
                    <label className="row-check">
                      <input
                        aria-label={`Select ${job.title}`}
                        checked={selectedIds.has(job.job_id)}
                        onChange={() => toggleSelected(job.job_id)}
                        type="checkbox"
                      />
                    </label>
                    <Badge tone={scoreTone(job.relevance_score)}>{job.relevance_score}</Badge>
                    <button
                      aria-label={`View ${job.title} details`}
                      className="job-title-button"
                      onClick={() => setSelectedJob(job)}
                      type="button"
                    >
                      <span>{job.title}</span>
                      <small>{job.location}</small>
                    </button>
                    <span>{job.company}</span>
                    <span>{job.site ?? "unknown"}</span>
                    <span className="status-stack">{statusBadges(job)}</span>
                    <span className="row-actions">
                      <Button
                        aria-label={`${job.bookmarked ? "Unsave" : "Save"} ${job.title}`}
                        onClick={() => bookmarkMutation.mutate(job)}
                        title={job.bookmarked ? "Unsave" : "Save"}
                      >
                        <Bookmark aria-hidden="true" size={16} />
                      </Button>
                      <Button
                        aria-label={`Mark ${job.title} ${job.applied ? "not applied" : "applied"}`}
                        onClick={() => appliedMutation.mutate(job)}
                        title={job.applied ? "Mark not applied" : "Mark applied"}
                      >
                        <Check aria-hidden="true" size={16} />
                      </Button>
                      <Button
                        aria-label={`Open ${job.title} details`}
                        onClick={() => setSelectedJob(job)}
                        title="Details"
                      >
                        <PanelRightOpen aria-hidden="true" size={16} />
                      </Button>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {selectedJob ? (
          <aside className="detail-panel" aria-label="Job detail">
            <div className="detail-header">
              <div>
                <h2>{selectedJob.title}</h2>
                <p>{selectedJob.company}</p>
              </div>
              <Button aria-label="Close details" onClick={() => setSelectedJob(null)}>
                <X aria-hidden="true" size={16} />
              </Button>
            </div>
            <div className="detail-meta">
              <Badge tone={scoreTone(selectedJob.relevance_score)}>
                {selectedJob.relevance_score}
              </Badge>
              <span>{selectedJob.location}</span>
              <span>{selectedJob.site ?? "unknown"}</span>
            </div>
            <p className="detail-description">
              {selectedJob.description ?? "No description available."}
            </p>
            {selectedJob.job_url ? (
              <a className="external-link" href={selectedJob.job_url}>
                <ExternalLink aria-hidden="true" size={16} />
                Open job
              </a>
            ) : null}
          </aside>
        ) : null}
      </div>
    </section>
  );
}
