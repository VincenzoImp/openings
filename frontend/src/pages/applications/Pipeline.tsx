import { useEffect, useMemo, useRef, useState } from "react";
import {
  calendarDate,
  type Application,
  type BulkResult,
  type ListResult,
  type OwnerQuestion,
} from "../../api";
import {
  Banner,
  Button,
  Chips,
  EmptyState,
  ErrorBanner,
  GridTable,
  Loading,
} from "../../design";
import { Pager, plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { selectRecords, useDebounce } from "../../state";
import { BulkBar } from "./BulkBar";
import {
  STAGES,
  bulkActions,
  listQuery,
  outcomeLabels,
  stageCounts,
  type Filters,
} from "./model";
import { COLUMNS, HEAD, Row } from "./Row";

const NONE = { items: [], total: 0 };
const SCOPES = ["applications", "jobs", "documents", "files"];
const LIMIT = 200;
const SORTS: Record<string, string> = {
  updated: "Recently updated",
  deadline: "Deadline, soonest first",
  priority: "Priority, highest first",
  applied: "Sent, newest first",
  newest: "Newest first",
  oldest: "Oldest first",
  company: "Company A to Z",
  stage: "Stage",
};

/**
 * The pipeline: stage chips with their counts, search and filters, and the
 * applications as a list with selection and bulk actions.
 */
export function Pipeline({
  filters,
  setFilters,
}: {
  filters: Filters;
  setFilters: (patch: Partial<Filters>) => void;
}) {
  const q = useDebounce(filters.q);
  const current = { ...filters, q };
  const offset = Number(filters.offset) || 0;
  const list = useFresh<ListResult<Application>>(
    `/applications?${listQuery(current, LIMIT, offset)}`,
    NONE,
    SCOPES,
  );
  const counted = new URLSearchParams({ limit: "1" });
  if (q) counted.set("q", q);
  const counts = useFresh<ListResult<Application>>(
    `/applications?${counted}`,
    NONE,
    SCOPES,
  );
  const questions = useFresh<ListResult<OwnerQuestion>>(
    "/questions?state=open&subject_type=application&limit=200",
    NONE,
    ["questions"],
  );
  const asked = useMemo(
    () => new Set(questions.data.items.map((item) => item.subject?.id || "")),
    [questions.data],
  );
  const [selection, setSelection] = useState<Record<string, number>>({});
  const [failures, setFailures] = useState<string[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const days = counts.data.no_reply?.days ?? 30;
  const chips = stageCounts(counts.data);
  // A new list keeps the selection with the versions it now has.
  useEffect(() => {
    setSelection((selected) => {
      let changed = false;
      const next = { ...selected };
      for (const item of list.data.items)
        if (next[item.id] !== undefined && next[item.id] !== item.version) {
          next[item.id] = item.version;
          changed = true;
        }
      return changed ? next : selected;
    });
  }, [list.data]);
  const scope = [filters.stage, q, filters.outcome].join();
  useEffect(() => {
    setSelection({});
    setFailures([]);
  }, [scope]);
  // An inline form belongs to the rows it was opened among: any change of
  // stage, filter, order or page closes it.
  const shown = [scope, ...Object.values(filters)].join("|");
  useEffect(() => setOpen(null), [shown]);
  const filtered =
    q ||
    filters.outcome ||
    filters.applied_since ||
    filters.applied_until ||
    filters.waiting;
  const clear = () =>
    setFilters({
      q: "",
      outcome: "",
      applied_since: "",
      applied_until: "",
      waiting: "",
      offset: "0",
    });
  function bulkResult(result: BulkResult) {
    const names = new Map(
      list.data.items.map((item) => [
        item.id,
        item.job?.title || "Application",
      ]),
    );
    setSelection((selected) => {
      const next = { ...selected };
      for (const item of result.items) if (item.ok) delete next[item.id];
      return next;
    });
    setFailures(
      result.items
        .filter((item) => item.error)
        .map(
          (item) =>
            `${names.get(item.id) || "Application"}: ${item.error!.message}`,
        ),
    );
  }
  const selected = Object.keys(selection).length;
  // The selected records, also those of other pages, as last read.
  const seen = useRef(new Map<string, Application>());
  for (const item of list.data.items) seen.current.set(item.id, item);
  const actions = bulkActions(
    Object.keys(selection)
      .map((id) => seen.current.get(id))
      .filter((item): item is Application => !!item),
  );
  const rows = list.data.items;
  const firstReady = rows.find(
    (item) => item.status === "shortlisted" && item.ready,
  );
  return (
    <div className="stack">
      <div className="spread wrap">
        <Chips
          label="Stage"
          value={filters.stage}
          onChange={(stage) => setFilters({ stage, offset: "0" })}
          options={STAGES.map((stage) => ({
            ...stage,
            count: counts.loading ? undefined : chips[stage.id],
          }))}
        />
        <div className="row grow-row">
          <label className="search-field">
            <span className="sr">Search applications</span>
            <input
              className="input search"
              type="search"
              placeholder="Search role or company"
              value={filters.q}
              onChange={(event) =>
                setFilters({ q: event.target.value, offset: "0" })
              }
            />
          </label>
        </div>
      </div>
      <div className="filterbar" role="group" aria-label="Filters">
        <label className="toggle">
          <span className="muted">Outcome</span>
          <select
            aria-label="Outcome"
            className="input"
            value={filters.outcome}
            onChange={(event) =>
              setFilters({ outcome: event.target.value, offset: "0" })
            }
          >
            <option value="">Any</option>
            {Object.entries(outcomeLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="toggle">
          <span className="muted">Sort</span>
          <select
            aria-label="Sort"
            className="input"
            value={filters.sort}
            onChange={(event) =>
              setFilters({ sort: event.target.value, offset: "0" })
            }
          >
            {Object.entries(SORTS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {filters.waiting && (
          <Button
            size="sm"
            icon="close"
            onClick={() => setFilters({ waiting: "", offset: "0" })}
          >
            No reply for more than {days} days
            <span className="sr">: remove this filter</span>
          </Button>
        )}
        {(filters.applied_since || filters.applied_until) && (
          <Button
            size="sm"
            icon="close"
            onClick={() =>
              setFilters({ applied_since: "", applied_until: "", offset: "0" })
            }
          >
            Sent
            {filters.applied_since &&
              ` from ${calendarDate(filters.applied_since.slice(0, 10))}`}
            {filters.applied_until &&
              ` on or before ${calendarDate(filters.applied_until.slice(0, 10))}`}
            <span className="sr">: remove this filter</span>
          </Button>
        )}
        {filtered && (
          <Button size="sm" variant="quiet" onClick={clear}>
            Clear filters
          </Button>
        )}
      </div>
      {failures.length > 0 && (
        <Banner
          tone="danger"
          role="alert"
          title={`${plural(failures.length, "selected application")} could not be changed`}
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
      )}
      <section className="card" aria-label="Applications as a list">
        {list.error ? (
          <div className="body">
            <ErrorBanner message={list.error} retry={list.reload} />
          </div>
        ) : list.loading ? (
          <Loading label="Loading applications…" />
        ) : !rows.length ? (
          <EmptyState
            title={
              filtered || filters.stage !== "all"
                ? "No application matches"
                : "No application yet"
            }
            action={
              filtered ? (
                <Button onClick={clear}>Clear filters</Button>
              ) : (
                <a className="btn" href="#jobs?section=new">
                  Open new jobs
                </a>
              )
            }
          >
            {filtered || filters.stage !== "all"
              ? "Try another stage or search, or clear the filters."
              : "Shortlisting a job starts its application. Upload its CV and letter, send it, and record what happened here."}
          </EmptyState>
        ) : (
          <>
            {selected > 0 && (
              <BulkBar
                selection={selection}
                actions={actions}
                hint={
                  filters.waiting
                    ? `Applied, no reply for more than ${days} days`
                    : undefined
                }
                onClear={() => setSelection({})}
                onResult={bulkResult}
              />
            )}
            <GridTable
              label="Applications"
              columns={COLUMNS}
              head={[
                {
                  name: "Select",
                  content: (
                    <label className="toggle">
                      <input
                        type="checkbox"
                        aria-label="Select every application shown"
                        checked={rows.every(
                          (item) => selection[item.id] !== undefined,
                        )}
                        onChange={(event) =>
                          setSelection((current) =>
                            selectRecords(current, rows, event.target.checked),
                          )
                        }
                      />
                      <span className="only-mobile" aria-hidden="true">
                        Select all shown
                      </span>
                    </label>
                  ),
                },
                ...HEAD.slice(1),
              ]}
            >
              {rows.map((application) => (
                <Row
                  key={application.id}
                  application={application}
                  selected={selection[application.id] !== undefined}
                  disabled={selected >= 200}
                  onSelect={(checked) =>
                    setSelection((current) =>
                      selectRecords(current, [application], checked),
                    )
                  }
                  primary={application === firstReady}
                  asked={asked.has(application.id)}
                  open={open === application.id}
                  onRespond={(show) => setOpen(show ? application.id : null)}
                  reload={list.reload}
                  days={days}
                />
              ))}
            </GridTable>
            <Pager
              offset={offset}
              total={list.data.total}
              limit={LIMIT}
              label="Application pages"
              onChange={(next) => setFilters({ offset: String(next) })}
            />
          </>
        )}
      </section>
    </div>
  );
}
