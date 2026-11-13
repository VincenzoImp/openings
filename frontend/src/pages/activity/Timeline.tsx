import { Fragment } from "react";
import type { Activity, ListResult, Run } from "../../api";
import {
  ActorChip,
  Button,
  Card,
  Chips,
  DayHeading,
  EmptyState,
  ErrorBanner,
  FilterBar,
  Loading,
  Tag,
  TimelineEntry,
} from "../../design";
import { Pager } from "../../library/common";
import { clock, dayLabel } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useUrlFilters } from "../../state";
import { RunLink } from "./RunTag";
import { ChangeSubject, changeGroups, groupOf, type Links } from "./records";
import { changeDetail, changeLabel } from "./wording";

const PAGE = 30;
const NONE: ListResult<Activity> = { items: [], total: 0 };
const NO_TOKENS: ListResult<{ id: string; name: string }> = {
  items: [],
  total: 0,
};
/** Changes grouped by day, newest first. */
function ChangeList({ items, ...links }: Links & { items: Activity[] }) {
  const days: { label: string; events: Activity[] }[] = [];
  for (const event of items) {
    const label = dayLabel(event.created_at);
    if (days[days.length - 1]?.label === label)
      days[days.length - 1].events.push(event);
    else days.push({ label, events: [event] });
  }
  return days.map((day) => (
    <Fragment key={day.label}>
      <DayHeading>{day.label}</DayHeading>
      <ul className="list" aria-label={`Changes, ${day.label}`}>
        {day.events.map((event) => {
          const detail = changeDetail(event);
          const subject = <ChangeSubject event={event} {...links} />;
          const group = groupOf(event.subject?.type);
          return (
            <TimelineEntry
              key={event.id}
              title={changeLabel(event.kind)}
              meta={
                <>
                  {subject}
                  {detail && ` · ${detail}`}
                  {event.run_id && (
                    <>
                      {" · "}
                      <RunLink id={event.run_id} label="View run" />
                    </>
                  )}
                </>
              }
              tag={group && <Tag>{group.label}</Tag>}
              actor={
                <ActorChip
                  actor={event.actor}
                  detail={event.run_workflow || undefined}
                />
              }
              time={clock(event.created_at)}
            />
          );
        })}
      </ul>
    </Fragment>
  ));
}

/** Every recorded change, filtered by who made it, its kind, a period and a run. */
export function Timeline(links: Links) {
  const [filters, setFilters] = useUrlFilters({
    actor: "",
    token: "",
    kind: "",
    since: "",
    until: "",
    run: "",
    offset: "0",
  });
  const set = (patch: Record<string, string>) =>
    setFilters({ ...patch, offset: "0" });
  const tokens = useFresh("/tokens", NO_TOKENS, ["tokens"]);
  const run = useFresh<Run | null>(
    filters.run ? `/runs/${filters.run}?changes_limit=1` : null,
    null,
    [],
  );
  const query = new URLSearchParams({
    limit: String(PAGE),
    offset: String(Number(filters.offset) || 0),
  });
  if (filters.actor) query.set("actor", filters.actor);
  if (filters.actor === "token" && filters.token)
    query.set("token_id", filters.token);
  if (filters.since) query.set("since", filters.since);
  if (filters.until) query.set("until", filters.until);
  if (filters.run) query.set("run_id", filters.run);
  for (const type of changeGroups.find((group) => group.id === filters.kind)
    ?.types || [])
    query.append("subject_types", type);
  const list = useFresh(`/events?${query}`, NONE, [
    "events",
    "jobs",
    "applications",
    "questions",
    "requests",
    "preferences",
    "settings",
    "career",
    "templates",
    "notes",
    "documents",
    "sources",
  ]);
  const filtered = Object.entries(filters).some(
    ([key, value]) => key !== "offset" && value,
  );
  return (
    <>
      <FilterBar label="Filters">
        <Chips
          label="Made by"
          value={filters.actor}
          onChange={(actor) => set({ actor, token: "" })}
          options={[
            { id: "", label: "Everyone" },
            { id: "owner", label: "Owner" },
            { id: "token", label: "API tokens" },
            { id: "system", label: "System" },
            { id: "unknown", label: "Not recorded" },
          ]}
        />
        {filters.actor === "token" && tokens.data.items.length > 0 && (
          <select
            className="input"
            aria-label="API token"
            value={filters.token}
            onChange={(event) => set({ token: event.target.value })}
          >
            <option value="">All tokens</option>
            {tokens.data.items.map((token) => (
              <option key={token.id} value={token.id}>
                {token.name}
              </option>
            ))}
          </select>
        )}
        <select
          className="input"
          aria-label="Kind of change"
          value={filters.kind}
          onChange={(event) => set({ kind: event.target.value })}
        >
          <option value="">All kinds</option>
          {changeGroups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.label}
            </option>
          ))}
        </select>
        <label className="toggle">
          <span className="muted">From</span>
          <input
            className="input"
            type="date"
            value={filters.since}
            max={filters.until || undefined}
            onChange={(event) => set({ since: event.target.value })}
          />
        </label>
        <label className="toggle">
          <span className="muted">To</span>
          <input
            className="input"
            type="date"
            value={filters.until}
            min={filters.since || undefined}
            onChange={(event) => set({ until: event.target.value })}
          />
        </label>
        {filters.run && (
          <button
            type="button"
            className="chip"
            aria-label={`Run: ${run.data?.workflow || "one run"}, remove this filter`}
            onClick={() => set({ run: "" })}
          >
            Run: {run.data?.workflow || "one run"}
            <span aria-hidden="true">×</span>
          </button>
        )}
      </FilterBar>
      <Card>
        {list.error ? (
          <div className="body">
            <ErrorBanner message={list.error} retry={list.reload} />
          </div>
        ) : list.loading ? (
          <Loading label="Loading changes…" />
        ) : list.data.items.length ? (
          <ChangeList items={list.data.items} {...links} />
        ) : (
          <EmptyState
            title={
              filtered ? "No changes match these filters" : "No changes yet"
            }
            action={
              filtered && (
                <Button
                  onClick={() =>
                    setFilters({
                      actor: "",
                      token: "",
                      kind: "",
                      since: "",
                      until: "",
                      run: "",
                      offset: "0",
                    })
                  }
                >
                  Clear filters
                </Button>
              )
            }
          >
            {filtered
              ? "Try a wider period or another kind of change."
              : "Changes to jobs, applications, the Career record and collection appear here with who made them."}
          </EmptyState>
        )}
        <Pager
          offset={Number(filters.offset) || 0}
          total={list.data.total}
          limit={PAGE}
          onChange={(value) => setFilters({ offset: String(value) })}
          label="Change pages"
        />
      </Card>
    </>
  );
}
