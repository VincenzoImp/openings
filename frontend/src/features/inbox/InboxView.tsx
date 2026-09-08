import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Filter, Search, SlidersHorizontal, X } from "lucide-react";

import { api } from "../../api/client";
import type { JobListParams, JobSort, JobStatus, JobSummary, SortDirection } from "../../api/types";
import { JOB_SORTS } from "../../api/types";
import { saveBlob } from "../../app/download";
import { useHotkeys } from "../../app/hotkeys";
import { setParams, useRoute } from "../../app/router";
import { useToast } from "../../app/toastContext";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { EmptyState, ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Input, Select } from "../../components/Field";
import { useJobActions } from "../shared/actions";
import { JobList } from "../shared/JobList";
import { LabelsEditor } from "../shared/LabelsEditor";
import { useJobsInfinite } from "../shared/queries";
import { StatusNoteDialog } from "../shared/StatusNoteDialog";
import { useSelection } from "../shared/useSelection";
import { BulkBar } from "./BulkBar";
import { FilterDrawer } from "./FilterDrawer";
import { activeFilterCount, clearedFilters, paramsToFilters } from "./filters";
import { rememberList } from "../shared/listContext";
import { useSemanticSearch } from "./useSemanticSearch";

const VISITED_KEY = "openings.inbox.visited-at";

function readVisited(): string | null {
  try {
    return localStorage.getItem(VISITED_KEY);
  } catch {
    return null;
  }
}

function writeVisited(): void {
  try {
    localStorage.setItem(VISITED_KEY, new Date().toISOString());
  } catch {
    // storage unavailable: no "since last visit" marker
  }
}

export function InboxView() {
  const route = useRoute();
  const toast = useToast();
  const actions = useJobActions();
  const search = useRef<HTMLInputElement>(null);
  const [lastVisit] = useState(readVisited);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [labelsFor, setLabelsFor] = useState<string[] | null>(null);
  const [statusFor, setStatusFor] = useState<{ ids: string[]; status: JobStatus } | null>(null);

  // The marker moves when you leave, not when you arrive: a reload mid-session keeps it.
  useEffect(() => {
    const leave = () => {
      if (document.visibilityState === "hidden") {
        writeVisited();
      }
    };
    document.addEventListener("visibilitychange", leave);
    return () => {
      document.removeEventListener("visibilitychange", leave);
      writeVisited();
    };
  }, []);

  const text = route.params.get("q") ?? "";
  const semantic = text.startsWith("~");
  const filters = useMemo(() => paramsToFilters(route.params), [route.params]);
  const sort = (route.params.get("sort") as JobSort) || "score";
  const direction = (route.params.get("direction") as SortDirection) || undefined;

  const params = useMemo<JobListParams>(
    () => ({
      statuses: ["new"],
      text: semantic ? undefined : text.trim() || undefined,
      sort,
      direction,
      ...filters,
    }),
    [text, semantic, sort, direction, filters],
  );

  const listQuery = useJobsInfinite(params, !semantic);
  const semanticQuery = useSemanticSearch(semantic ? text.slice(1).trim() : "", ["new"]);
  const semanticItems = semanticQuery.data;
  const listItems = listQuery.items;
  const jobs: JobSummary[] = useMemo(
    () => (semantic ? (semanticItems ?? []) : listItems),
    [semantic, semanticItems, listItems],
  );
  const total = semantic ? jobs.length : listQuery.total;
  const loading = semantic ? semanticQuery.isPending && text.length > 1 : listQuery.isPending;
  const error = semantic ? semanticQuery.error : listQuery.error;

  const ids = useMemo(() => jobs.map((job) => job.job_id), [jobs]);
  const selection = useSelection(ids);
  const selected = selection.index >= 0 ? jobs[selection.index] : undefined;
  const targets = useMemo(
    () => jobs.filter((job) => selection.targets.includes(job.job_id)),
    [jobs, selection.targets],
  );

  const isFresh = useCallback(
    (job: JobSummary) =>
      lastVisit !== null && (job.status_changed_at ?? job.first_seen) > lastVisit,
    [lastVisit],
  );
  const freshCount = jobs.filter(isFresh).length;

  const open = useCallback(
    (job: JobSummary) => {
      rememberList(ids);
      actions.open(job);
    },
    [actions, ids],
  );

  const loadMore = useCallback(() => {
    if (!semantic && listQuery.hasNextPage && !listQuery.isFetchingNextPage) {
      void listQuery.fetchNextPage();
    }
  }, [semantic, listQuery]);

  const exportCurrent = async () => {
    try {
      const download = await api.exportJobs({ ...params, limit: 0 }, "csv");
      saveBlob(download.blob, download.filename);
    } catch (exc) {
      toast.push(exc instanceof Error ? exc.message : String(exc), "error");
    }
  };

  useHotkeys("view", [
    {
      key: "j",
      run: selection.next,
      description: "Next / previous job",
      group: "Lists",
      label: "j / k",
    },
    { key: "k", run: selection.prev },
    { key: "ArrowDown", run: selection.next },
    { key: "ArrowUp", run: selection.prev },
    {
      key: "J",
      run: () => selection.extendTo(selection.index + 1),
      description: "Extend selection down / up",
      group: "Lists",
      label: "J / K",
    },
    { key: "K", run: () => selection.extendTo(selection.index - 1) },
    {
      key: " ",
      run: selection.toggleCurrent,
      description: "Select / deselect the job",
      group: "Lists",
      label: "Space",
    },
    { key: "*", run: selection.checkAll, description: "Select every loaded job", group: "Lists" },
    {
      key: "Enter",
      run: () => selected && open(selected),
      description: "Open the job page",
      group: "Lists",
    },
    {
      key: "o",
      run: () => selected && actions.openPosting(selected),
      description: "Open the posting in a new tab",
      group: "Lists",
    },
    {
      key: "s",
      run: () =>
        targets.length &&
        actions.setStatus.mutate({ jobIds: targets.map((j) => j.job_id), status: "shortlisted" }),
      description: "Shortlist",
      group: "Lists",
    },
    {
      key: "a",
      run: () =>
        targets.length &&
        actions.setStatus.mutate({ jobIds: targets.map((j) => j.job_id), status: "applied" }),
      description: "Mark applied",
      group: "Lists",
    },
    {
      key: "S",
      run: () =>
        targets.length &&
        setStatusFor({ ids: targets.map((j) => j.job_id), status: "shortlisted" }),
      description: "Change status with a note",
      group: "Lists",
      label: "Shift+S",
    },
    {
      key: "x",
      run: () => void actions.blacklist(targets),
      description: "Blacklist (asks first)",
      group: "Lists",
    },
    {
      key: "d",
      run: () => void actions.remove(targets),
      description: "Delete (asks first)",
      group: "Lists",
    },
    {
      key: "l",
      run: () => targets.length && setLabelsFor(targets.map((j) => j.job_id)),
      description: "Edit labels",
      group: "Lists",
    },
    {
      key: "/",
      run: () => search.current?.focus(),
      description: "Search (prefix ~ for semantic search)",
      group: "Lists",
    },
    { key: "f", run: () => setFiltersOpen(true), description: "Filters", group: "Lists" },
    {
      key: "e",
      run: () => void exportCurrent(),
      description: "Export the current list as CSV",
      group: "Lists",
    },
    {
      key: "Escape",
      run: () => {
        if (document.activeElement === search.current) {
          search.current?.blur();
        } else if (selection.checked.size) {
          selection.clear();
        }
      },
    },
  ]);

  const filterCount = activeFilterCount(filters);
  const noResults = !loading && jobs.length === 0 && (text || filterCount > 0);

  return (
    <section className="flex h-[calc(100dvh-8.5rem)] flex-col gap-3 md:h-[calc(100dvh-3rem)]">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold">Inbox</h1>
          <span className="tabular text-sm text-fg-muted" aria-live="polite">
            {loading ? "" : `${total} new`}
          </span>
          {freshCount > 0 ? (
            <Badge tone="info" title="Postings that arrived after your previous visit">
              {freshCount} since last visit
            </Badge>
          ) : null}
        </div>
        <div className="grid grid-cols-[1fr_auto] gap-2 sm:flex sm:flex-wrap sm:items-center">
          <div className="relative min-w-0 sm:w-80">
            <Search
              size={14}
              className="absolute left-2 top-2.5 text-fg-faint"
              aria-hidden="true"
            />
            <Input
              ref={search}
              aria-label="Search"
              name="q"
              autoComplete="off"
              spellCheck={false}
              placeholder="Search… (~ for semantic)"
              className="!pl-7"
              value={text}
              onChange={(event) => setParams({ q: event.target.value })}
            />
            {text ? (
              <button
                type="button"
                aria-label="Clear search"
                className="absolute right-2 top-2 text-fg-faint hover:text-fg"
                onClick={() => setParams({ q: null })}
              >
                <X size={14} aria-hidden="true" />
              </button>
            ) : null}
          </div>
          <Button onClick={() => setFiltersOpen(true)} aria-label="Filters">
            <Filter size={14} aria-hidden="true" />
            <span className="hidden sm:inline">Filters</span>
            {filterCount > 0 ? <Badge tone="accent">{filterCount}</Badge> : null}
          </Button>
          <div className="col-span-2 flex items-center gap-2 sm:col-auto">
            <SlidersHorizontal size={14} className="text-fg-faint" aria-hidden="true" />
            <Select
              aria-label="Sort"
              className="!w-auto"
              value={sort}
              onChange={(event) => setParams({ sort: event.target.value })}
            >
              {JOB_SORTS.map((value) => (
                <option key={value} value={value}>
                  by {value.replace("_", " ")}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Direction"
              className="!w-auto"
              value={direction ?? ""}
              onChange={(event) => setParams({ direction: event.target.value || null })}
            >
              <option value="">natural</option>
              <option value="desc">descending</option>
              <option value="asc">ascending</option>
            </Select>
          </div>
        </div>
      </header>

      {selection.checked.size > 0 ? (
        <BulkBar
          count={selection.checked.size}
          onClear={selection.clear}
          onShortlist={() =>
            actions.setStatus.mutate({ jobIds: selection.targets, status: "shortlisted" })
          }
          onApplied={() =>
            actions.setStatus.mutate({ jobIds: selection.targets, status: "applied" })
          }
          onStatus={() => setStatusFor({ ids: selection.targets, status: "shortlisted" })}
          onLabels={() => setLabelsFor(selection.targets)}
          onBlacklist={() => void actions.blacklist(targets)}
          onDelete={() => void actions.remove(targets)}
        />
      ) : null}

      {error ? (
        <ErrorNotice
          error={error}
          onRetry={() => (semantic ? semanticQuery.refetch() : listQuery.refetch())}
        />
      ) : null}
      {loading ? (
        <div className="rounded-lg border border-edge bg-surface p-4">
          <Skeleton lines={6} />
        </div>
      ) : null}
      {!loading && !error && jobs.length === 0 ? (
        noResults ? (
          <EmptyState
            title="No postings match"
            action={
              <Button onClick={() => setParams({ q: null, ...clearedFilters() })}>
                Clear Search and Filters
              </Button>
            }
          >
            Try fewer filters or a different search. Semantic search starts with ~.
          </EmptyState>
        ) : (
          <EmptyState title="Nothing new">
            Every posting has been shortlisted, applied to or blacklisted. The next run adds more.
          </EmptyState>
        )
      ) : null}
      {jobs.length > 0 ? (
        <JobList
          jobs={jobs}
          selectedIndex={selection.index}
          checked={selection.checked}
          onSelect={selection.setIndex}
          onToggle={selection.toggle}
          onOpen={open}
          onEndReached={loadMore}
          isFresh={isFresh}
          className="flex-1"
          footer={
            semantic
              ? `${jobs.length} semantic matches`
              : `${jobs.length} of ${total} loaded${listQuery.isFetchingNextPage ? "…" : ""}`
          }
        />
      ) : null}

      <FilterDrawer open={filtersOpen} onClose={() => setFiltersOpen(false)} filters={filters} />
      <Dialog
        open={labelsFor !== null}
        title={labelsFor && labelsFor.length > 1 ? `Labels for ${labelsFor.length} jobs` : "Labels"}
        onClose={() => setLabelsFor(null)}
      >
        {labelsFor ? (
          <LabelsEditor
            jobIds={labelsFor}
            labels={
              labelsFor.length === 1
                ? (jobs.find((job) => job.job_id === labelsFor[0])?.labels ?? [])
                : []
            }
            autoFocus
          />
        ) : null}
      </Dialog>
      <StatusNoteDialog
        open={statusFor !== null}
        jobIds={statusFor?.ids ?? []}
        initialStatus={statusFor?.status ?? "shortlisted"}
        onClose={() => setStatusFor(null)}
      />
    </section>
  );
}
