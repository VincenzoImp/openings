import { useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";

import { JOB_SORTS } from "../../api/types";
import type { JobListParams, JobSort, JobSummary } from "../../api/types";
import { useHotkeys } from "../../app/hotkeys";
import { navigate } from "../../app/router";
import { Badge } from "../../components/Badge";
import { ConfirmDialog, Dialog } from "../../components/Dialog";
import { EmptyState, ErrorNotice, Spinner } from "../../components/EmptyState";
import { Input, Select } from "../../components/Field";
import { JobList } from "../shared/JobList";
import { LabelsEditor } from "../shared/LabelsEditor";
import { useFacets, useJobCommands, useJobs } from "../shared/queries";
import { useSelection } from "../shared/useSelection";

const VISITED_KEY = "openings.inbox.visited-at";
const PAGE = 500;

function readVisited(): string | null {
  try {
    return localStorage.getItem(VISITED_KEY);
  } catch {
    return null;
  }
}

function writeVisited(): void {
  try {
    localStorage.setItem(VISITED_KEY, new Date().toISOString().slice(0, 10));
  } catch {
    // storage unavailable: no "since last visit" marker
  }
}

export function InboxView() {
  const [lastVisit] = useState(() => {
    const previous = readVisited();
    writeVisited();
    return previous;
  });
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [minScore, setMinScore] = useState("");
  const [sort, setSort] = useState<JobSort>("score");
  const [labelsFor, setLabelsFor] = useState<JobSummary | null>(null);
  const [blacklistFor, setBlacklistFor] = useState<JobSummary | null>(null);
  const search = useRef<HTMLInputElement>(null);

  const params = useMemo<JobListParams>(
    () => ({
      status: ["new"],
      limit: PAGE,
      sort,
      text: text.trim() || undefined,
      source: source ? [source] : undefined,
      min_score: minScore === "" ? undefined : Number(minScore),
    }),
    [text, source, minScore, sort],
  );
  const jobsQuery = useJobs(params);
  const facets = useFacets();
  const commands = useJobCommands();
  const jobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data]);
  const selection = useSelection(jobs.length);
  const selected = selection.index >= 0 ? jobs[selection.index] : undefined;

  const isFresh = (job: JobSummary) => lastVisit !== null && job.first_seen > lastVisit;
  const freshCount = jobs.filter(isFresh).length;

  const open = (job: JobSummary) => navigate({ jobId: job.job_id });

  useHotkeys({
    j: selection.next,
    ArrowDown: selection.next,
    k: selection.prev,
    ArrowUp: selection.prev,
    Enter: () => selected && open(selected),
    o: () => selected?.job_url && window.open(selected.job_url, "_blank", "noopener"),
    s: () =>
      selected && commands.setStatus.mutate({ jobIds: [selected.job_id], status: "shortlisted" }),
    a: () =>
      selected && commands.setStatus.mutate({ jobIds: [selected.job_id], status: "applied" }),
    x: () => selected && setBlacklistFor(selected),
    l: () => selected && setLabelsFor(selected),
    "/": () => search.current?.focus(),
    Escape: () => {
      if (document.activeElement === search.current) {
        search.current?.blur();
      }
    },
  });

  return (
    <section className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold">Inbox</h1>
          <span className="text-sm text-slate-500">
            {jobsQuery.data ? `${jobsQuery.data.total} new` : ""}
          </span>
          {freshCount > 0 ? (
            <Badge tone="blue" title="Postings first seen after your previous visit">
              {freshCount} since last visit
            </Badge>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2 top-2.5 text-slate-400" />
            <Input
              ref={search}
              aria-label="Search"
              placeholder="Search title, company, description…  ( / )"
              className="!w-72 !pl-7"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </div>
          <Select
            aria-label="Source"
            className="!w-36"
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            <option value="">All sources</option>
            {facets.data?.sources.map((facet) => (
              <option key={facet.value} value={facet.value}>
                {facet.value} ({facet.count})
              </option>
            ))}
          </Select>
          <Input
            aria-label="Minimum score"
            type="number"
            placeholder="Min score"
            className="!w-24"
            value={minScore}
            onChange={(event) => setMinScore(event.target.value)}
          />
          <Select
            aria-label="Sort"
            className="!w-32"
            value={sort}
            onChange={(event) => setSort(event.target.value as JobSort)}
          >
            {JOB_SORTS.map((value) => (
              <option key={value} value={value}>
                by {value}
              </option>
            ))}
          </Select>
        </div>
      </header>

      {jobsQuery.isPending ? <Spinner /> : null}
      {jobsQuery.error ? <ErrorNotice error={jobsQuery.error} /> : null}
      {jobsQuery.data && jobs.length === 0 ? (
        <EmptyState title="Nothing new">
          Every posting has been shortlisted, applied to or blacklisted. Check back after the next
          run.
        </EmptyState>
      ) : null}
      {jobs.length > 0 ? (
        <JobList
          jobs={jobs}
          selectedIndex={selection.index}
          onSelect={selection.setIndex}
          onOpen={open}
          isFresh={isFresh}
        />
      ) : null}

      <Dialog
        open={labelsFor !== null}
        title={labelsFor ? `Labels for ${labelsFor.title}` : "Labels"}
        onClose={() => setLabelsFor(null)}
      >
        {labelsFor ? (
          <LabelsEditor
            jobId={labelsFor.job_id}
            labels={jobs.find((job) => job.job_id === labelsFor.job_id)?.labels ?? []}
            autoFocus
          />
        ) : null}
      </Dialog>
      <ConfirmDialog
        open={blacklistFor !== null}
        title="Blacklist this posting?"
        message={
          blacklistFor ? (
            <>
              <strong>{blacklistFor.title}</strong> at {blacklistFor.company} will be deleted and
              never ingested again.
            </>
          ) : null
        }
        confirmLabel="Blacklist"
        danger
        onConfirm={() => blacklistFor && commands.blacklist.mutate([blacklistFor.job_id])}
        onClose={() => setBlacklistFor(null)}
      />
    </section>
  );
}
