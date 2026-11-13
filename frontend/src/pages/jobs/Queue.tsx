import { useEffect, useMemo, useState } from "react";
import {
  api,
  newId,
  type Application,
  type BulkResult,
  type JobCounts,
  type JobList,
  type ListResult,
  type OwnerQuestion,
} from "../../api";
import {
  Banner,
  Button,
  Chips,
  EmptyState,
  ErrorBanner,
  Loading,
} from "../../design";
import { Pager, plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { selectRecords, useDebounce, useWorkspace } from "../../state";
import { reviewHref } from "../applications/links";
import { BulkBar } from "./BulkBar";
import { JobRow, type RowAction } from "./JobRow";
import { MoreFilters } from "./MoreFilters";
import {
  DISMISSED_BY,
  JOB_SCOPES,
  NARROWING,
  SIGNAL_FILTERS,
  SORTS,
  listQuery,
  sortOf,
  type Filters,
  type Section,
} from "./model";

const NONE: JobList = { items: [], total: 0 };
const LIMIT = 200;
const LABELS: Record<Section, string> = {
  review: "Jobs to review",
  shortlist: "Shortlisted jobs without an application",
  dismissed: "Dismissed jobs",
  all: "All jobs",
};

/**
 * The jobs of one tab: search, signal filter and order, selection with bulk
 * actions, and each job's own actions. Selecting a row shows it beside.
 */
export function Queue({
  section,
  filters,
  setFilters,
  counts,
  selected,
  onSelect,
  onRows,
  leaving,
  onAdd,
  own,
}: {
  section: Section;
  filters: Filters;
  setFilters: (patch: Partial<Filters>) => void;
  counts?: JobCounts;
  selected: string;
  onSelect: (id: string) => void;
  /** The ids of the rows shown, in order, whenever they change. */
  onRows: (ids: string[]) => void;
  /** Before a triage: what moves the selection on once the job left the list. */
  leaving: (id: string) => (() => void) | null;
  onAdd: () => void;
  /** The languages the owner works in, from the policy. */
  own: Set<string> | null;
}) {
  const { mutate, pending } = useWorkspace();
  const q = useDebounce(filters.q);
  const query = listQuery({ ...filters, q }, LIMIT);
  if (section === "all") query.set("include_facets", "true");
  const list = useFresh<JobList>(`/jobs?${query}`, NONE, JOB_SCOPES);
  const questions = useFresh<ListResult<OwnerQuestion>>(
    "/questions?state=open&subject_type=job&limit=200",
    { items: [], total: 0 },
    ["questions"],
  );
  const asked = useMemo(
    () => new Set(questions.data.items.map((item) => item.subject?.id || "")),
    [questions.data],
  );
  const [selection, setSelection] = useState<Record<string, number>>({});
  const [failures, setFailures] = useState<string[]>([]);
  const offset = Number(filters.offset) || 0;
  const rows = list.data.items;
  useEffect(() => {
    onRows(rows.map((item) => item.id));
  }, [rows, onRows]);
  const scope = [section, ...NARROWING.map((key) => filters[key])].join("|");
  useEffect(() => {
    setSelection({});
    setFailures([]);
  }, [scope]);
  // A new list keeps the selection with the versions it now has.
  useEffect(() => {
    setSelection((current) => {
      let changed = false;
      const next = { ...current };
      for (const item of rows)
        if (next[item.id] !== undefined && next[item.id] !== item.version) {
          next[item.id] = item.version;
          changed = true;
        }
      return changed ? next : current;
    });
  }, [list.data]);
  const narrowed = NARROWING.some((key) => filters[key]);
  const clear = () =>
    setFilters(
      Object.fromEntries([
        ...NARROWING.map((key) => [key, ""]),
        ["offset", "0"],
      ]),
    );
  function report(result: BulkResult) {
    const names = new Map(rows.map((item) => [item.id, item.title]));
    setSelection((current) => {
      const next = { ...current };
      for (const item of result.items) if (item.ok) delete next[item.id];
      return next;
    });
    setFailures(
      result.items
        .filter((item) => item.error)
        .map(
          (item) => `${names.get(item.id) || "Job"}: ${item.error!.message}`,
        ),
    );
  }
  async function act(id: string, version: number, action: RowAction) {
    if (action === "start") {
      let created: Application | undefined;
      const ok = await mutate(async () => {
        created = await api<Application>("/applications", "POST", {
          job_id: id,
          idempotency_key: newId(),
        });
      }, "Application started. Your agent prepares its documents.");
      if (ok && created) location.hash = reviewHref(created.id);
      return;
    }
    const next = leaving(id);
    const ok = await mutate(
      () =>
        api(`/jobs/${id}/triage`, "POST", {
          triage: action,
          expected_version: version,
        }),
      action === "dismissed"
        ? "Dismissed. It can be restored from Dismissed."
        : action === "saved"
          ? "Shortlisted."
          : section === "dismissed"
            ? "Restored."
            : "Returned to the jobs to review.",
    );
    if (ok) next?.();
  }
  const count = Object.keys(selection).length;
  return (
    <section className="card job-queue" aria-label={LABELS[section]}>
      <header className="queue-head">
        <label className="toggle">
          <input
            type="checkbox"
            aria-label="Select every job shown"
            disabled={!rows.length}
            checked={
              !!rows.length &&
              rows.every((item) => selection[item.id] !== undefined)
            }
            onChange={(event) =>
              setSelection((current) =>
                selectRecords(current, rows, event.target.checked),
              )
            }
          />
          <span className="sr">All</span>
        </label>
        <label className="search-field grow">
          <span className="sr">Search jobs</span>
          <input
            className="input search"
            type="search"
            placeholder="Search jobs"
            value={filters.q}
            onChange={(event) =>
              setFilters({ q: event.target.value, offset: "0" })
            }
          />
        </label>
        <label>
          <span className="sr">Filter by signal</span>
          <select
            className="input"
            value={
              filters.signal ||
              (filters.complete === "false" ? "incomplete" : "")
            }
            onChange={(event) => {
              const value = event.target.value;
              setFilters(
                value === "incomplete"
                  ? { signal: "", complete: "false", offset: "0" }
                  : { signal: value, complete: "", offset: "0" },
              );
            }}
          >
            <option value="">All signals</option>
            {Object.entries(SIGNAL_FILTERS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
            <option value="incomplete">Text incomplete</option>
          </select>
        </label>
        <label>
          <span className="sr">Order</span>
          <select
            className="input"
            value={sortOf(filters)}
            onChange={(event) =>
              setFilters({ sort: event.target.value, offset: "0" })
            }
          >
            {Object.entries(SORTS)
              .filter(
                ([value]) => value !== "dismissed" || section === "dismissed",
              )
              .map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
          </select>
        </label>
      </header>
      {section === "dismissed" && (
        <div className="queue-chips">
          <Chips
            label="Dismissed by"
            value={filters.dismissed_by}
            onChange={(id) => setFilters({ dismissed_by: id, offset: "0" })}
            options={DISMISSED_BY.map((item) => ({
              ...item,
              count: !counts
                ? undefined
                : item.id
                  ? counts.dismissed_by[item.id]
                  : counts.dismissed,
            }))}
          />
        </div>
      )}
      {section === "dismissed" && filters.rule_id && (
        <div className="queue-chips">
          <Button
            size="sm"
            icon="close"
            onClick={() => setFilters({ rule_id: "", offset: "0" })}
          >
            Dismissed by one policy rule
            <span className="sr">: remove this filter</span>
          </Button>
        </div>
      )}
      {section === "all" && (
        <MoreFilters
          filters={filters}
          facets={list.data.facets || {}}
          setFilters={setFilters}
        />
      )}
      {count > 0 && (
        <BulkBar
          section={section}
          selection={selection}
          onClear={() => setSelection({})}
          onResult={report}
        />
      )}
      {failures.length > 0 && (
        <div className="body">
          <Banner
            tone="danger"
            role="alert"
            title={`${plural(failures.length, "selected job")} could not be changed`}
            action={
              <Button size="sm" onClick={() => setFailures([])}>
                Dismiss
              </Button>
            }
          >
            <ul className="plain">
              {failures.map((failure) => (
                <li key={failure}>{failure}</li>
              ))}
            </ul>
          </Banner>
        </div>
      )}
      {list.error ? (
        <div className="body">
          <ErrorBanner message={list.error} retry={list.reload} />
        </div>
      ) : list.loading ? (
        <Loading label="Loading jobs…" />
      ) : !rows.length ? (
        <EmptyState
          title={
            narrowed
              ? "No job matches"
              : section === "review"
                ? "Nothing to review"
                : section === "shortlist"
                  ? "The Shortlist is empty"
                  : section === "dismissed"
                    ? "No dismissed job"
                    : "No job yet"
          }
          action={
            narrowed ? (
              <>
                <Button onClick={clear}>Clear the filters</Button>
                {section === "all" && filters.q && (
                  <a className="btn quiet" href="#collection">
                    Add a search for it
                  </a>
                )}
              </>
            ) : section === "all" || section === "review" ? (
              <Button onClick={onAdd} icon="plus">
                Add a job
              </Button>
            ) : undefined
          }
        >
          {narrowed
            ? `${counts ? plural(counts.all, "job is", "jobs are") + " stored. " : ""}Search looks at titles, companies and posting text.`
            : section === "review"
              ? "New jobs from your searches and company boards arrive here. Your agent reviews them against your policy."
              : section === "shortlist"
                ? "Shortlist the jobs you want to pursue. Your agent starts a Draft for each in its next prepare-shortlist run."
                : section === "dismissed"
                  ? "Dismissed jobs stay remembered here, so they are not collected again, and can be restored."
                  : "Add a posting by its address, or set up a saved search in Collection."}
        </EmptyState>
      ) : (
        <ul className="list job-list" aria-label={LABELS[section]}>
          {rows.map((job) => (
            <JobRow
              key={job.id}
              job={job}
              section={section}
              selected={selection[job.id] !== undefined}
              current={job.id === selected}
              disabled={count >= 200}
              asked={asked.has(job.id)}
              own={own}
              busy={pending}
              onSelect={onSelect}
              onCheck={(checked) =>
                setSelection((current) =>
                  selectRecords(current, [job], checked),
                )
              }
              onAction={(action) => act(job.id, job.version, action)}
            />
          ))}
        </ul>
      )}
      <Pager
        offset={offset}
        total={list.data.total}
        limit={LIMIT}
        label="Job pages"
        onChange={(next) => setFilters({ offset: String(next) })}
      />
      {section === "shortlist" && counts && counts.applications > 0 && (
        <footer>
          <span className="muted grow">
            {plural(
              counts.applications,
              "job already has",
              "jobs already have",
            )}{" "}
            an application.
          </span>
          <a className="btn quiet sm" href="#applications">
            Applications
          </a>
        </footer>
      )}
      {section === "dismissed" && (
        <footer>
          <span className="muted grow">
            Dismissed jobs are remembered, so they are not collected again.
            Forgetting one for good is a separate action in its details.
          </span>
        </footer>
      )}
    </section>
  );
}
