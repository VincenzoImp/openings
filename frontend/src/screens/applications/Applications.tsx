import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownUp,
  ChartNoAxesColumn,
  List as ListIcon,
  ListFilter,
  Search,
  SearchX,
  Send,
} from "lucide-react";
import { href, navigate, useRoute } from "../../shell/router";
import { TopBarActions } from "../../shell/context";
import { Button, IconButton } from "../../ui/Button";
import { SearchField } from "../../ui/Field";
import { List, ListGroup, ListRows, useSelection } from "../../ui/List";
import { Menu, type MenuEntry, type MenuGroup } from "../../ui/Menu";
import { LoadError } from "../../ui/LoadError";
import { EmptyState, PageHeader, SkeletonRows } from "../../ui/Page";
import { FilterChips, Segmented, Tabs } from "../../ui/Tabs";
import { useToast } from "../../ui/Toast";
import { BulkActions } from "./Bulk";
import {
  jobOf,
  useApplicationList,
  useUpdateApplication,
  type ApplicationRow,
  type Period,
} from "./data";
import { ApplicationDialogs, errorText, type DialogKind } from "./dialogs";
import {
  DEADLINES,
  PRIORITIES,
  cleared,
  filterChips,
  passes,
  readFilters,
  writeFilters,
  type Filters,
} from "./filters";
import {
  NEEDS_GROUPS,
  OUTCOMES,
  SORTS,
  STAGE_FILTERS,
  isSent,
  needsRank,
  reopenStage,
  sortApplications,
} from "./model";
import { rememberList } from "./back";
import { ApplicationRowView, pageHref } from "./Row";
import { PERIODS, StatsView } from "./Stats";
import "./applications.css";

/**
 * The stage tabs: underline tabs, pills on a phone; a horizontal scroller with
 * a fade where they do not fit. A count shows only once it is known.
 */
function StageTabs({
  value,
  counts,
  onChange,
}: {
  value: Filters["stage"];
  counts: Record<string, number> | null;
  onChange: (stage: Filters["stage"]) => void;
}) {
  const count = (id: string) => {
    if (!counts) return undefined;
    if (id === "all")
      return ["shortlisted", "applied", "interview", "offer", "closed"].reduce(
        (sum, key) => sum + (counts[key] ?? 0),
        0,
      );
    if (id === "shortlisted")
      return (counts.shortlisted ?? 0) - (counts.ready ?? 0);
    return counts[id] ?? 0;
  };
  return (
    <Tabs
      label="Stage"
      idPrefix="ap"
      className="ap-stages"
      value={value}
      onChange={(id) => onChange(id as Filters["stage"])}
      items={STAGE_FILTERS.map((stage) => ({
        id: stage.id,
        label: stage.label,
        count: count(stage.id),
      }))}
    />
  );
}

/** The Filter menu: priority, deadline, source and outcome. */
function filterMenu(
  filters: Filters,
  sources: string[],
  set: (patch: Partial<Filters>) => void,
  withSort: boolean,
): MenuEntry[] {
  const group = (
    heading: string,
    key: "priority" | "deadline" | "source" | "outcome",
    values: Record<string, string>,
  ): MenuGroup => ({
    heading,
    items: Object.entries(values).map(([value, label]) => ({
      id: `${key}-${value}`,
      label,
      kind: "radio",
      checked: filters[key] === value,
      onSelect: () => set({ [key]: filters[key] === value ? "" : value }),
    })),
  });
  return [
    ...(withSort
      ? [
          {
            heading: "Sort",
            items: SORTS.map((sort) => ({
              id: `sort-${sort.id}`,
              label: sort.label,
              kind: "radio" as const,
              checked: filters.sort === sort.id,
              onSelect: () => set({ sort: sort.id }),
            })),
          },
        ]
      : []),
    group("Priority", "priority", PRIORITIES),
    group("Deadline", "deadline", DEADLINES),
    ...(sources.length > 1
      ? [
          group(
            "Source",
            "source",
            Object.fromEntries(sources.map((name) => [name, name])),
          ),
        ]
      : []),
    group("Outcome", "outcome", OUTCOMES),
  ];
}

/**
 * Applications: every application by stage, in the order that needs action
 * first, and Stats on the applications sent. `#applications?stage=ready`
 * opens a stage; `section=stats` the stats.
 */
export default function ApplicationsScreen() {
  const route = useRoute();
  const filters = readFilters(route.query);
  const period = (PERIODS.find(
    (item) => item.value === route.query.get("period"),
  )?.value ?? "90d") as Period;
  const set = (patch: Partial<Filters>, extra: Record<string, string> = {}) =>
    navigate(
      href(
        "applications",
        {},
        { ...writeFilters({ ...filters, ...patch }), ...extra },
      ),
      { replace: true },
    );
  useEffect(() => rememberList("#" + route.hash), [route.hash]);

  const [search, setSearch] = useState(filters.q);
  const [searching, setSearching] = useState(!!filters.q);
  useEffect(() => setSearch(filters.q), [filters.q]);
  useEffect(() => {
    if (search === filters.q) return;
    const timer = setTimeout(() => set({ q: search.trim() }), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const list = useApplicationList({
    stage: filters.stage,
    q: filters.q,
    outcome: filters.outcome,
    waiting: filters.waiting,
    sort: filters.sort,
  });
  const days = list.noReplyDays;
  const rows = useMemo(
    () =>
      sortApplications(
        list.items.filter((app) => passes(app, filters)),
        filters.sort,
        days,
      ),
    [list.items, route.hash, days],
  );
  const sources = useMemo(
    () =>
      [
        ...new Set(list.items.map((app) => jobOf(app).source).filter(Boolean)),
      ].sort(),
    [list.items],
  );

  const selection = useSelection();
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => selection.clear(), [route.hash]);
  const selected = rows.filter((app) => selection.ids.has(app.id));

  const [dialog, setDialog] = useState<{
    kind: DialogKind;
    app: ApplicationRow;
  } | null>(null);
  const update = useUpdateApplication();
  const toast = useToast();
  const reopen = (app: ApplicationRow) =>
    update.mutate(
      {
        id: app.id,
        version: app.version,
        patch: { status: reopenStage(app) },
      },
      {
        onSuccess: () =>
          toast.show({
            message: `Reopened “${jobOf(app).title}”`,
            tone: "success",
          }),
        onError: (error) =>
          toast.show({ message: errorText(error), tone: "error" }),
      },
    );

  const chips = filterChips(filters, days);
  const narrowed = !!filters.q || chips.length > 0;
  const statsToggle = (
    <Segmented
      label="View"
      value={filters.stats ? "stats" : "list"}
      onChange={(value) => set({ stats: value === "stats" })}
      options={[
        { value: "list", label: "List", icon: ListIcon },
        { value: "stats", label: "Stats", icon: ChartNoAxesColumn },
      ]}
    />
  );
  const sortLabel = SORTS.find((sort) => sort.id === filters.sort)!.label;

  let body;
  if (filters.stats) body = <StatsView period={period} />;
  else if (list.isError && !list.data)
    body = (
      <div className="ap-pad">
        <LoadError
          what="your applications"
          error={list.error}
          retry={() => void list.refetch()}
        />
      </div>
    );
  else if (!list.data) body = <SkeletonRows rows={8} />;
  else if (!rows.length) {
    const none =
      !narrowed &&
      ["shortlisted", "applied", "interview", "offer", "closed"].every(
        (key) => !list.counts[key],
      );
    body = none ? (
      <EmptyState
        icon={Send}
        title="No applications yet"
        actions={
          <a className="ui-btn" data-variant="primary" href={href("jobs")}>
            <span className="ui-btn-label">Go to New jobs</span>
          </a>
        }
      >
        Shortlist a job to start one.
      </EmptyState>
    ) : narrowed ? (
      <EmptyState
        icon={SearchX}
        title="No applications match"
        actions={
          <Button onClick={() => set(cleared(filters))}>Clear filters</Button>
        }
      >
        Try another search or fewer filters.
      </EmptyState>
    ) : (
      <EmptyState
        icon={SearchX}
        title={`Nothing in ${
          STAGE_FILTERS.find((stage) => stage.id === filters.stage)!.label
        }`}
        actions={
          <Button variant="ghost" onClick={() => set({ stage: "all" })}>
            Show all applications
          </Button>
        }
      />
    );
  } else {
    const groups =
      filters.sort === "needs"
        ? NEEDS_GROUPS.map((label, rank) => ({
            label,
            items: rows.filter((app) => needsRank(app, days) === rank),
          })).filter((group) => group.items.length)
        : [];
    // The stage glyph tells stages apart only where they mix: the All tab,
    // and its last group.
    const row = (app: ApplicationRow, mixed = filters.stage === "all") => (
      <ApplicationRowView
        key={app.id}
        app={app}
        noReplyDays={days}
        mixed={mixed}
        onDialog={(kind) => setDialog({ kind, app })}
        onReopen={() => reopen(app)}
      />
    );
    body = (
      <List
        label="Applications"
        activeId={active ?? rows[0].id}
        onActiveChange={setActive}
        onOpen={(id) => navigate(pageHref(id))}
        selection={selection}
        shortcuts={{
          r: (id) => {
            const app = rows.find((item) => item.id === id);
            if (app && isSent(app.status)) setDialog({ kind: "reply", app });
          },
        }}
      >
        {groups.length > 1 ? (
          groups.map((group) => (
            <ListGroup
              key={group.label}
              label={group.label}
              count={group.items.length}
            >
              {group.items.map((app) =>
                row(
                  app,
                  filters.stage === "all" &&
                    group.label === NEEDS_GROUPS[NEEDS_GROUPS.length - 1],
                ),
              )}
            </ListGroup>
          ))
        ) : (
          <ListRows>{rows.map((app) => row(app))}</ListRows>
        )}
      </List>
    );
  }

  const target = dialog && {
    id: dialog.app.id,
    version: dialog.app.version,
    status: dialog.app.status,
    title: jobOf(dialog.app).title,
    applied_at: dialog.app.applied_at,
    outcome: dialog.app.outcome,
    deadline: dialog.app.deadline,
    priority: dialog.app.priority,
    required_documents: dialog.app.required_documents,
  };

  return (
    <div className="ap-screen">
      <PageHeader title="Applications" action={statsToggle} />
      <TopBarActions>
        {!filters.stats && (
          <IconButton
            icon={Search}
            label="Search applications"
            tooltip="none"
            aria-pressed={searching}
            onClick={() => setSearching((value) => !value)}
          />
        )}
        {!filters.stats && (
          <Menu
            label="Filter and sort"
            placement="bottom-end"
            items={filterMenu(filters, sources, set, true)}
            trigger={(props) => (
              <IconButton
                {...props}
                icon={ListFilter}
                label="Filter"
                tooltip="none"
              />
            )}
          />
        )}
        <Button
          variant="ghost"
          size="sm"
          icon={filters.stats ? ListIcon : ChartNoAxesColumn}
          onClick={() => set({ stats: !filters.stats })}
        >
          {filters.stats ? "List" : "Stats"}
        </Button>
      </TopBarActions>
      {filters.stats ? (
        <div
          className="ui-toolbar ap-toolbar"
          role="toolbar"
          aria-label="Period"
        >
          <Segmented
            label="Period"
            value={period}
            onChange={(value) =>
              set({}, value === "90d" ? {} : { period: value })
            }
            options={PERIODS}
          />
        </div>
      ) : selected.length ? (
        <BulkActions selected={selected} onClear={selection.clear} />
      ) : (
        <div
          className="ui-toolbar ap-toolbar"
          role="toolbar"
          aria-label="Applications"
        >
          <StageTabs
            value={filters.stage}
            counts={list.data && !list.isError ? list.counts : null}
            onChange={(stage) => set({ stage })}
          />
          <div className="ap-tools">
            <SearchField
              label="Search applications"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Menu
              label="Filter"
              placement="bottom-end"
              items={filterMenu(filters, sources, set, false)}
              trigger={(props) => (
                <Button {...props} variant="ghost" size="sm" icon={ListFilter}>
                  Filter
                </Button>
              )}
            />
            <Menu
              label="Sort"
              placement="bottom-end"
              items={SORTS.map((sort) => ({
                id: sort.id,
                label: sort.label,
                kind: "radio",
                checked: filters.sort === sort.id,
                onSelect: () => set({ sort: sort.id }),
              }))}
              trigger={(props) => (
                <Button
                  {...props}
                  variant="ghost"
                  size="sm"
                  icon={ArrowDownUp}
                  aria-label={`Sort: ${sortLabel}`}
                >
                  {sortLabel}
                </Button>
              )}
            />
          </div>
        </div>
      )}
      {!filters.stats && searching && (
        <div className="ap-search-row">
          <SearchField
            label="Search applications"
            value={search}
            autoFocus
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      )}
      {!filters.stats && (
        <FilterChips
          chips={chips.map((chip) => ({ ...chip, key: chip.key }))}
          onRemove={(key) =>
            set({ [key]: key === "waiting" ? false : "" } as Partial<Filters>)
          }
          onClear={() => set(cleared(filters))}
        />
      )}
      <div
        className="ap-body"
        id="ap-panel"
        role={filters.stats ? undefined : "tabpanel"}
        aria-labelledby={filters.stats ? undefined : `ap-tab-${filters.stage}`}
        data-view={filters.stats ? "stats" : "list"}
      >
        {body}
      </div>
      <ApplicationDialogs
        open={dialog?.kind ?? null}
        target={target}
        onClose={() => setDialog(null)}
      />
    </div>
  );
}
