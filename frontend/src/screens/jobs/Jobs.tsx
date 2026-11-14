import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  ArrowUpDown,
  Bookmark,
  Ellipsis,
  EyeOff,
  Inbox,
  ListFilter,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useShell, TopBarActions } from "../../shell/context";
import { href, navigate, useRoute } from "../../shell/router";
import { Button, IconButton } from "../../ui/Button";
import { ConfirmDialog, Dialog } from "../../ui/Dialog";
import { SearchField } from "../../ui/Field";
import { formatTime, plural } from "../../ui/format";
import { isModKey, isTyping } from "../../ui/keys";
import { BulkBar, useSelection } from "../../ui/List";
import { LoadError } from "../../ui/LoadError";
import { Menu, Popover, type MenuEntry } from "../../ui/Menu";
import { EmptyState, PageHeader, SkeletonRows } from "../../ui/Page";
import { SplitPane } from "../../ui/Split";
import { FilterChips, Tabs, Toolbar } from "../../ui/Tabs";
import { useToast } from "../../ui/Toast";
import {
  fetchJob,
  prefetchJob,
  useBulk,
  useCollection,
  useDistinct,
  useJobList,
  useMerge,
  type BulkAction,
} from "./data";
import { FilterPanel } from "./FilterPanel";
import { CorrectDrawer, MergeDialog, SourcesDialog } from "./JobDialogs";
import { JobDetail, type DetailHandlers } from "./JobDetail";
import { JobList } from "./JobList";
import {
  SECTIONS,
  SORTS,
  chipsOf,
  defaultSort,
  leaves,
  listQuery,
  narrowed,
  neighbour,
  readView,
  sortsOf,
  viewQuery,
  type FilterKey,
  type Job,
  type JobSummary,
  type Section,
  type Sort,
  type View,
} from "./model";
import { useSeen } from "./seen";
import "./jobs.css";

const PAGE = 200;

function useMedia(query: string) {
  const [matches, setMatches] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const list = matchMedia(query);
    const change = () => setMatches(list.matches);
    change();
    list.addEventListener("change", change);
    return () => list.removeEventListener("change", change);
  }, [query]);
  return matches;
}

const title = (job: { title?: string }) => `“${job.title || "Untitled role"}”`;
/** What a decision is called in a sentence: "Couldn't dismiss …". */
const VERB: Record<BulkAction, string> = {
  shortlisted: "shortlist",
  dismissed: "dismiss",
  new: "restore",
  forget: "forget",
};
const DONE: Record<BulkAction, string> = {
  shortlisted: "Shortlisted",
  dismissed: "Dismissed",
  new: "Restored",
  forget: "Forgot",
};

/** The reason of a dismissal, typed in its toast after the fact. */
function ReasonButton({ onSave }: { onSave: (reason: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  if (!editing)
    return (
      <button
        type="button"
        className="ui-toast-action"
        onClick={() => setEditing(true)}
      >
        Add reason
      </button>
    );
  return (
    <form
      className="jobs-reason"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        if (reason.trim()) onSave(reason.trim());
      }}
    >
      <input
        aria-label="Why did you dismiss it?"
        placeholder="Why? Enter saves"
        value={reason}
        maxLength={500}
        autoFocus
        onChange={(event) => setReason(event.target.value)}
      />
    </form>
  );
}

/**
 * The pane beside a selection: what is picked, while the bar above the list
 * carries the actions, so one Shortlist is on screen.
 */
function Picked({ jobs }: { jobs: JobSummary[] }) {
  const shown = jobs.slice(0, 8);
  return (
    <div className="jobs-picked" aria-live="polite">
      <h2>{plural(jobs.length, "job")} selected</h2>
      <ul>
        {shown.map((job) => (
          <li key={job.id}>
            <span className="jobs-picked-title">
              {job.title || "Untitled role"}
            </span>
            {job.company && (
              <span className="jobs-picked-company">{job.company}</span>
            )}
          </li>
        ))}
      </ul>
      {jobs.length > shown.length && (
        <p className="jobs-picked-more">
          and {plural(jobs.length - shown.length, "more job", "more jobs")}
        </p>
      )}
      <p className="jobs-picked-hint">
        Choose what to do with them in the bar above the list. Esc clears the
        selection.
      </p>
    </div>
  );
}

interface Undo {
  id: number;
  run: () => Promise<void>;
}

/**
 * Jobs: decide fast, one job after another. New, Dismissed and All beside
 * the selected job; after a shortlist or a dismissal the next job is shown,
 * every decision has Undo, and the keyboard does it all (j/k, s, d, z, o, x).
 * `#jobs?section=…&job=…` keeps the tab, the filters and the job.
 */
export default function Jobs() {
  const route = useRoute();
  const view = useMemo(() => readView(route.query), [route.query]);
  const shell = useShell();
  const toast = useToast();
  const wide = useMedia("(min-width: 1024px)");
  const phone = useMedia("(max-width: 719px)");
  const [limit, setLimit] = useState(PAGE);
  const query = useMemo(() => listQuery(view, limit), [view, limit]);
  const list = useJobList(query);
  const collection = useCollection();
  const { seen, mark } = useSeen();
  const picked = useSelection();
  const [hidden, setHidden] = useState<ReadonlySet<string>>(() => new Set());
  const [cursor, setCursor] = useState("");
  const [search, setSearch] = useState(view.q);
  const [searching, setSearching] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [correcting, setCorrecting] = useState<Job | null>(null);
  const [merging, setMerging] = useState<Job | null>(null);
  const [sourcesOf, setSourcesOf] = useState<Job | null>(null);
  const [forgetting, setForgetting] = useState<JobSummary[] | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const pushed = useRef(false);
  const focusNext = useRef<string | null>(null);
  const undos = useRef<Undo[]>([]);
  const versions = useRef(new Map<string, number>());
  const counter = useRef(0);

  const bulk = useBulk();
  const merge = useMerge();
  const distinct = useDistinct();

  const items = list.data?.items;
  // A job that left the list stays hidden until the list read again no
  // longer has it.
  useEffect(() => {
    if (!items) return;
    setHidden((current) => {
      if (!current.size) return current;
      const present = new Set(items.map((item) => item.id));
      const next = new Set([...current].filter((id) => present.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [items]);
  const rows = useMemo(
    () => (items ?? []).filter((item) => !hidden.has(item.id)),
    [items, hidden],
  );
  const ids = useMemo(() => rows.map((row) => row.id), [rows]);
  const gone = (items?.length ?? 0) - rows.length;
  const total = Math.max(0, (list.data?.total ?? 0) - gone);
  const open = !!view.job;
  const selected = view.job || (wide ? (ids[0] ?? "") : "");
  const active = wide
    ? selected
    : view.job || (ids.includes(cursor) ? cursor : (ids[0] ?? ""));
  const position = ids.indexOf(selected) + 1 || undefined;
  const row = rows.find((item) => item.id === selected);

  // The address. Filters and the selected job replace the entry; opening a
  // job on a phone pushes one, so Back returns to the list.
  const setView = useCallback(
    (patch: Partial<View>, push = false) => {
      navigate(href("jobs", {}, viewQuery({ ...view, ...patch })), {
        replace: !push,
      });
    },
    [view],
  );
  const setFilter = (key: FilterKey, value: string) =>
    setView({ filters: { ...view.filters, [key]: value }, job: "" });

  // The search field writes the address once typing pauses.
  useEffect(() => setSearch(view.q), [view.q]);
  useEffect(() => {
    if (search === view.q) return;
    const timer = setTimeout(() => setView({ q: search, job: "" }), 250);
    return () => clearTimeout(timer);
  }, [search, view.q, setView]);

  // A new tab or filter starts without a selection and from the first page.
  const scope = JSON.stringify([view.section, view.q, view.filters, view.sort]);
  useEffect(() => {
    picked.clear();
    setLimit(PAGE);
  }, [scope]); // Only when the tab or a filter changes.

  // The job on screen is read; the next one is read ahead.
  const shown = wide || open ? selected : "";
  useEffect(() => {
    if (!shown) return;
    mark(shown);
    prefetchJob(ids[ids.indexOf(shown) + 1] ?? "");
  }, [shown]); // Only when another job is shown.

  // After a decision, focus follows the selection to the next row.
  useLayoutEffect(() => {
    const id = focusNext.current;
    if (id == null) return;
    focusNext.current = null;
    const rowEl = document.querySelector<HTMLElement>(
      `.jobs-list [data-row-id="${CSS.escape(id)}"]`,
    );
    rowEl?.focus({ preventScroll: true });
    rowEl?.scrollIntoView({ block: "nearest" });
  });

  /** Show `id`: in the pane beside the list, or as the pushed page. */
  function select(id: string) {
    if (wide || open) setView({ job: id });
    else setCursor(id);
  }
  function openJob(id: string) {
    if (wide) return setView({ job: id });
    pushed.current = !open;
    setView({ job: id }, !open);
  }
  function close() {
    if (pushed.current) {
      pushed.current = false;
      history.back();
    } else setView({ job: "" });
  }
  /** Move the selection by one row. */
  function move(step: number, focusRow: boolean) {
    const index = ids.indexOf(active);
    const next = ids[Math.max(0, Math.min(ids.length - 1, index + step))];
    if (!next) return;
    if (index + step >= ids.length && total > ids.length)
      setLimit((value) => value + PAGE);
    select(next);
    if (focusRow) focusNext.current = next;
  }
  /** Once `gone` leave the list, show the job after them. */
  function advance(goneIds: string[]) {
    const current = active;
    if (!goneIds.includes(current)) return;
    const rest = ids.filter((id) => !goneIds.includes(id) || id === current);
    let next = neighbour(rest, current);
    if (goneIds.includes(next)) next = "";
    const inList = !!document.activeElement?.closest(".jobs-list");
    const onBody =
      document.activeElement === document.body ||
      document.activeElement?.id === "content";
    if (wide) setView({ job: next });
    else if (open) {
      if (next) setView({ job: next });
      else close();
    } else setCursor(next);
    if (next && (inList || onBody)) focusNext.current = next;
  }
  const hide = (list: string[]) =>
    setHidden((current) => new Set([...current, ...list]));
  const unhide = (list: string[]) =>
    setHidden((current) => {
      const next = new Set(current);
      for (const id of list) next.delete(id);
      return next;
    });

  function remember(run: () => Promise<void>) {
    counter.current += 1;
    const entry = { id: counter.current, run };
    undos.current = [...undos.current.slice(-19), entry];
    return entry;
  }
  const forgetUndo = (entry: Undo) => {
    undos.current = undos.current.filter((item) => item !== entry);
  };
  /** Undo one decision: the latest, or the one a toast names. */
  function undo(id?: number) {
    const entry =
      id == null
        ? undos.current.at(-1)
        : undos.current.find((item) => item.id === id);
    if (!entry) return;
    undos.current = undos.current.filter((item) => item !== entry);
    toast.close();
    void entry.run();
  }
  const versionOf = (id: string, fallback: number) =>
    versions.current.get(id) ?? fallback;
  const record = (id: string, version?: number | null) => {
    if (version != null) versions.current.set(id, version);
  };

  /** One bulk request; the versions it returns are kept for the next. */
  async function run(action: BulkAction, jobs: JobSummary[], reason?: string) {
    const results = await bulk.mutateAsync({
      action,
      items: jobs.map((job) => ({
        id: job.id,
        version: versionOf(job.id, job.version),
      })),
      reason,
    });
    for (const item of results) if (item.id) record(item.id, item.version);
    return results;
  }

  async function addReason(jobs: JobSummary[], reason: string) {
    try {
      await run("dismissed", jobs, reason);
      toast.show({ tone: "success", message: "Saved the reason" });
    } catch {
      toast.show({
        tone: "error",
        message: "Couldn't save the reason. Try again.",
      });
    }
  }

  /**
   * Shortlist, dismiss, restore or forget jobs: the row, the pane, a key and
   * the bulk bar all come here. The jobs leave the list at once and the next
   * one is shown; a failure brings them back and says why. Every decision
   * but forgetting can be undone.
   */
  async function decide(jobs: JobSummary[], to: BulkAction) {
    const moving = jobs.filter((job) => job.triage !== to);
    picked.clear();
    if (!moving.length) return;
    const movingIds = moving.map((job) => job.id);
    const before = active;
    const leaving = to === "forget" || leaves(view.section, to);
    if (leaving) {
      hide(movingIds);
      advance(movingIds);
    }
    const one = moving.length === 1 ? moving[0] : null;
    const what = one ? title(one) : plural(moving.length, "job");
    const pending = run(to, moving);
    const doneOf = (results: Awaited<typeof pending>) =>
      moving.filter((job) =>
        results.some((item) => item.ok && item.id === job.id),
      );
    // Undo is ready at once: `z` pressed while the request is on its way
    // waits for it, then turns it back.
    let undone = false;
    const entry = remember(async () => {
      undone = true;
      let done: JobSummary[];
      try {
        done = doneOf(await pending);
      } catch {
        return;
      }
      const groups = new Map<string, JobSummary[]>();
      for (const job of done) {
        const key = `${job.triage}\n${job.dismissal?.reason ?? ""}`;
        groups.set(key, [...(groups.get(key) ?? []), job]);
      }
      try {
        for (const [key, group] of groups) {
          const [from, reason] = key.split("\n");
          await run(from as BulkAction, group, reason || undefined);
        }
        unhide(done.map((job) => job.id));
        if (done.length === 1) select(done[0].id);
        toast.show({
          tone: "success",
          message: `Undid ${DONE[to].toLowerCase()} ${done.length === 1 ? title(done[0]) : plural(done.length, "job")}`,
        });
      } catch {
        toast.show({
          tone: "error",
          message: "Couldn't undo. Try again.",
        });
      }
    });
    let results;
    try {
      results = await pending;
    } catch {
      forgetUndo(entry);
      if (leaving) {
        unhide(movingIds);
        // The job stays where it was: the selection comes back to it.
        if (one) select(before);
      }
      toast.show({
        tone: "error",
        message: `Couldn't ${VERB[to]} ${what}. Try again.`,
      });
      return;
    }
    const failed = results.filter((item) => !item.ok);
    const done = doneOf(results);
    if (failed.length) {
      unhide(failed.map((item) => item.id ?? ""));
      if (leaving && one) select(before);
      const conflict = failed.some(
        (item) => (item.error as { code?: string } | null)?.code === "conflict",
      );
      toast.show({
        tone: "error",
        message: `Couldn't ${VERB[to]} ${one ? what : `${failed.length} of ${what}`}${
          conflict ? ": changed elsewhere. Try again." : ". Try again."
        }`,
      });
    }
    if (to === "forget" || !done.length) {
      forgetUndo(entry);
      if (to === "forget" && done.length && !failed.length)
        toast.show({ tone: "success", message: `${DONE.forget} ${what}` });
      return;
    }
    if (undone) return;
    if (failed.length) return;
    toast.show({
      message: `${DONE[to]} ${what}`,
      icon:
        to === "dismissed"
          ? EyeOff
          : to === "shortlisted"
            ? Bookmark
            : RotateCcw,
      action: { label: "Undo", undo: true, run: () => undo(entry.id) },
      // The only second action: why a job was dismissed.
      extra:
        to === "dismissed" ? (
          <ReasonButton
            key={entry.id}
            onSave={(reason) => void addReason(done, reason)}
          />
        ) : undefined,
    });
  }

  async function mergeInto(job: Job, target: JobSummary) {
    setMerging(null);
    hide([job.id]);
    advance([job.id]);
    try {
      await merge.mutateAsync({ job, target });
      toast.show({
        tone: "success",
        message: `Merged ${title(job)} into ${title(target)}`,
      });
    } catch {
      unhide([job.id]);
      toast.show({
        tone: "error",
        message: `Couldn't merge ${title(job)}. Try again.`,
      });
    }
  }

  const handlers: DetailHandlers = {
    shortlist: (job) => void decide([job], "shortlisted"),
    dismiss: (job) => void decide([job], "dismissed"),
    restore: (job) => void decide([job], "new"),
    correct: setCorrecting,
    merge: setMerging,
    sources: setSourcesOf,
    forget: (job) => setForgetting([job]),
    mergeInto: (job, other) => void mergeInto(job, other),
    keepBoth: async (job, other) => {
      try {
        await distinct.mutateAsync({ id: job.id, otherId: other.id });
        toast.show({
          tone: "success",
          message: `Kept ${title(job)} and ${title(other)} as two jobs`,
        });
      } catch {
        toast.show({
          tone: "error",
          message: "Couldn't keep both. Try again.",
        });
      }
    },
    select: (id) => setView({ job: id }),
  };

  const pickedJobs = rows.filter((job) => picked.ids.has(job.id));
  const current = rows.find((job) => job.id === active);

  // The screen's keys, before the shell's: a key handled here is not read
  // again by the shell (`/` searches this list instead of opening ⌘K).
  const state = {
    active,
    current,
    pickedJobs,
    move,
    decide,
    undo,
    picked,
    ids,
    wide,
    open,
    openJob,
    close,
    phone,
    setCorrecting,
  };
  const latest = useRef(state);
  latest.current = state;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (document.querySelector("dialog[open]")) return;
      const state = latest.current;
      const target = event.target as HTMLElement;
      const consume = () => {
        event.preventDefault();
        event.stopPropagation();
      };
      if (event.altKey) return;
      if (isModKey(event)) {
        if (
          event.key.toLowerCase() === "z" &&
          !event.shiftKey &&
          !isTyping(target)
        ) {
          consume();
          state.undo();
        }
        return;
      }
      if (isTyping(target)) {
        if (event.key === "Escape" && target === searchRef.current) {
          consume();
          target.blur();
        }
        return;
      }
      if (target.closest?.("[role=menu], [popover], [role=tablist]")) return;
      const inList = !!target.closest?.(".jobs-list");
      const neutral =
        inList || target === document.body || target.id === "content";
      const job = state.current;
      const many = state.pickedJobs;
      switch (event.key) {
        case "j":
        case "k":
          consume();
          return state.move(event.key === "j" ? 1 : -1, inList || neutral);
        case "ArrowDown":
        case "ArrowUp":
          if (!neutral) return;
          consume();
          return state.move(event.key === "ArrowDown" ? 1 : -1, true);
        case "J":
        case "K": {
          consume();
          const step = event.key === "J" ? 1 : -1;
          const index = state.ids.indexOf(state.active);
          const next = state.ids[index + step];
          if (!state.picked.ids.size && state.active)
            state.picked.toggle(state.active);
          if (next) {
            state.picked.extend(state.ids, next);
            state.move(step, inList || neutral);
          }
          return;
        }
        case "x":
          if (!state.active) return;
          consume();
          return state.picked.toggle(state.active);
        case "s":
        case "d":
        case "r": {
          const to: BulkAction =
            event.key === "s"
              ? "shortlisted"
              : event.key === "d"
                ? "dismissed"
                : "new";
          const from = to === "new" ? "dismissed" : "new";
          const jobs = (many.length ? many : job ? [job] : []).filter(
            (item) => item.triage === from,
          );
          if (!jobs.length) return;
          consume();
          return void state.decide(jobs, to);
        }
        case "z":
          consume();
          return state.undo();
        case "o":
          if (!job?.url) return;
          consume();
          window.open(job.url, "_blank", "noopener,noreferrer");
          return;
        case "e":
          if (!job) return;
          consume();
          return void fetchJob(job.id).then(
            state.setCorrecting,
            () => undefined,
          );
        case "Enter":
          if (!neutral || !state.active) return;
          consume();
          if (state.wide) document.getElementById("job-title")?.focus();
          else state.openJob(state.active);
          return;
        case "/":
          // On a phone, and while the bulk bar hides the search, `/` is
          // the shell's search.
          if (state.phone || !searchRef.current) return;
          consume();
          searchRef.current.focus();
          return;
        case "Escape":
          if (state.picked.ids.size) {
            consume();
            state.picked.clear();
          } else if (!state.wide && state.open) {
            consume();
            state.close();
          }
          return;
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, []);
  useEffect(() => {
    if (searching) searchRef.current?.focus();
  }, [searching]);

  const counts = list.data?.counts;
  const newCount =
    counts && Math.max(0, counts.new - (view.section === "new" ? gone : 0));
  const chips = chipsOf(view);
  const filtered = narrowed(view);
  const unspoken = list.data?.unspoken_required;
  const filterPanel = (withSort: boolean) => (
    <FilterPanel
      view={view}
      query={query}
      withSort={withSort}
      unspoken={unspoken}
      total={list.data?.total ?? 0}
      dismissedCounts={counts?.dismissed_by}
      onFilter={setFilter}
      onSort={(sort: Sort) => setView({ sort, job: "" })}
    />
  );
  const sortMenu: MenuEntry[] = sortsOf(view.section).map((sort) => ({
    id: sort,
    label: SORTS[sort],
    kind: "radio",
    checked: view.sort === sort,
    onSelect: () => setView({ sort, job: "" }),
  }));
  const bulkMenu: MenuEntry[] = [
    {
      id: "forget",
      label: "Forget permanently…",
      icon: Trash2,
      danger: true,
      onSelect: () => setForgetting(pickedJobs),
    },
  ];
  const newIn = pickedJobs.filter((job) => job.triage === "new");
  const dismissedIn = pickedJobs.filter((job) => job.triage === "dismissed");

  const toolbar = picked.ids.size ? (
    <BulkBar count={picked.ids.size} onClear={picked.clear}>
      {newIn.length > 0 && (
        <Button
          size="sm"
          icon={Bookmark}
          onClick={() => void decide(newIn, "shortlisted")}
        >
          Shortlist
        </Button>
      )}
      {newIn.length > 0 && (
        <Button
          size="sm"
          variant="ghost"
          icon={X}
          onClick={() => void decide(newIn, "dismissed")}
        >
          Dismiss
        </Button>
      )}
      {dismissedIn.length > 0 && (
        <Button
          size="sm"
          icon={RotateCcw}
          onClick={() => void decide(dismissedIn, "new")}
        >
          Restore
        </Button>
      )}
      <Menu
        label="More bulk actions"
        items={bulkMenu}
        placement="bottom-start"
        trigger={(props) => (
          <IconButton {...props} icon={Ellipsis} label="More" size="sm" />
        )}
      />
    </BulkBar>
  ) : (
    <Toolbar
      label="Jobs"
      tools={
        <>
          <SearchField
            ref={searchRef}
            label="Search jobs"
            shortcut="/"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Popover
            label="Filter"
            placement="bottom-end"
            trigger={(props) => (
              <Button {...props} variant="ghost" icon={ListFilter}>
                Filter
              </Button>
            )}
          >
            {filterPanel(false)}
          </Popover>
          <Menu
            label="Sort"
            items={sortMenu}
            placement="bottom-end"
            trigger={(props) => (
              <Button {...props} variant="ghost" icon={ArrowUpDown}>
                {SORTS[view.sort]}
              </Button>
            )}
          />
        </>
      }
    >
      <Tabs
        label="Jobs"
        idPrefix="jobs"
        value={view.section}
        onChange={(id) =>
          setView({
            section: id as Section,
            job: "",
            sort: defaultSort(id as Section),
          })
        }
        items={SECTIONS.map((item) => ({
          ...item,
          // A search or filter narrows the list, not the count of New.
          count:
            item.id === "new" && !filtered
              ? (newCount ?? undefined)
              : undefined,
        }))}
      />
    </Toolbar>
  );

  const next = collection.data?.next_run_at;
  const empty = !list.isPending && !list.isError && !rows.length;
  const onlySearch = !!view.q && !chips.length;
  const emptyState = filtered ? (
    <EmptyState
      icon={Search}
      title="No jobs match"
      actions={
        <Button
          onClick={() => {
            setSearch("");
            setView({
              q: "",
              job: "",
              filters: Object.fromEntries(
                Object.keys(view.filters).map((key) => [key, ""]),
              ) as View["filters"],
            });
          }}
        >
          {onlySearch ? "Clear search" : "Clear filters"}
        </Button>
      }
    >
      Search looks at titles, companies and posting text.
    </EmptyState>
  ) : view.section === "new" ? (
    <EmptyState
      icon={Inbox}
      title="You're all caught up."
      actions={
        <>
          <Button variant="primary" icon={Plus} onClick={shell.addJob}>
            Add a job
          </Button>
          {collection.data && !collection.data.source_count && (
            <a className="ui-btn" data-variant="ghost" href={href("sources")}>
              <span className="ui-btn-label">Add a job source</span>
            </a>
          )}
        </>
      }
    >
      {next
        ? `Your sources are checked next at ${formatTime(next)}.`
        : "New jobs from your sources arrive here."}
    </EmptyState>
  ) : view.section === "dismissed" ? (
    <EmptyState icon={Inbox} title="Nothing dismissed.">
      Jobs you dismiss stay here, so they are not collected again.
    </EmptyState>
  ) : (
    <EmptyState
      icon={Inbox}
      title="No jobs yet."
      actions={
        <Button variant="primary" icon={Plus} onClick={shell.addJob}>
          Add a job
        </Button>
      }
    >
      Add a posting by its address, or set up a source that finds jobs.
    </EmptyState>
  );

  return (
    <div className="jobs" data-pushed={(!wide && open) || undefined}>
      <PageHeader title="Jobs" />
      <TopBarActions>
        <IconButton
          icon={Search}
          label="Search jobs"
          size="touch"
          tooltip="none"
          aria-pressed={searching}
          onClick={() => setSearching((value) => !value)}
        />
        <IconButton
          icon={ListFilter}
          label="Filter and sort"
          size="touch"
          tooltip="none"
          onClick={() => setSheet(true)}
        />
        <IconButton
          icon={Plus}
          label="Add job"
          size="touch"
          tooltip="none"
          onClick={shell.addJob}
        />
      </TopBarActions>
      {toolbar}
      {phone && (searching || view.q) && (
        <div className="jobs-phone-search">
          <SearchField
            ref={searchRef}
            label="Search jobs"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Button
            variant="ghost"
            onClick={() => {
              setSearch("");
              setSearching(false);
            }}
          >
            Cancel
          </Button>
        </div>
      )}
      <FilterChips
        chips={chips.map((chip) => ({ ...chip, key: chip.key }))}
        onRemove={(key) => setFilter(key as FilterKey, "")}
        onClear={() =>
          setView({
            job: "",
            filters: Object.fromEntries(
              Object.keys(view.filters).map((key) => [key, ""]),
            ) as View["filters"],
          })
        }
      />
      {list.isError && (
        <div className="jobs-error">
          <LoadError
            what="your jobs"
            error={list.error}
            retry={() => void list.refetch()}
          />
        </div>
      )}
      <div
        className="jobs-panel"
        id="jobs-panel"
        role="tabpanel"
        aria-labelledby={`jobs-tab-${view.section}`}
      >
        {empty ? (
          <div className="jobs-empty">{emptyState}</div>
        ) : (
          <SplitPane
            open={open}
            onClose={close}
            label="Job"
            list={
              list.isPending ? (
                <SkeletonRows rows={8} />
              ) : (
                <JobList
                  view={view}
                  rows={rows}
                  activeId={active}
                  onActiveChange={(id) => (wide ? select(id) : openJob(id))}
                  onOpen={openJob}
                  selection={picked}
                  seen={seen}
                  on={handlers}
                  footer={
                    total > rows.length ? (
                      <div className="jobs-more">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setLimit((value) => value + PAGE)}
                        >
                          Show more ({total - rows.length})
                        </Button>
                      </div>
                    ) : null
                  }
                />
              )
            }
            detail={
              wide && pickedJobs.length > 0 ? (
                <Picked jobs={pickedJobs} />
              ) : selected ? (
                <JobDetail
                  key={selected}
                  id={selected}
                  row={row}
                  position={position}
                  total={position ? total : undefined}
                  onPrevious={() => move(-1, false)}
                  onNext={() => move(1, false)}
                  onBack={close}
                  on={handlers}
                  pushed={phone && open}
                />
              ) : list.isPending ? (
                <div className="jobs-pane-loading">
                  <SkeletonRows rows={3} />
                </div>
              ) : null
            }
          />
        )}
      </div>
      <Dialog
        open={sheet}
        onClose={() => setSheet(false)}
        title="Filter and sort"
        className="jobs-sheet"
        footer={
          <Button variant="primary" onClick={() => setSheet(false)}>
            Show {plural(total, "job")}
          </Button>
        }
      >
        {sheet && filterPanel(true)}
      </Dialog>
      <CorrectDrawer job={correcting} onClose={() => setCorrecting(null)} />
      <MergeDialog
        job={merging}
        onClose={() => setMerging(null)}
        onMerge={(job, target) => void mergeInto(job, target)}
      />
      <SourcesDialog job={sourcesOf} onClose={() => setSourcesOf(null)} />
      <ConfirmDialog
        open={!!forgetting}
        title={
          forgetting?.length === 1
            ? `Forget ${title(forgetting[0])} permanently?`
            : `Forget ${plural(forgetting?.length ?? 0, "job")} permanently?`
        }
        confirm={forgetting?.length === 1 ? "Forget job" : "Forget jobs"}
        onClose={() => setForgetting(null)}
        onConfirm={() => forgetting && void decide(forgetting, "forget")}
      >
        {forgetting?.length === 1 ? "The job is" : "The jobs are"} deleted with
        their applications, notes and files, and cannot be restored. If a source
        finds one again, it comes back as a new job. To stop seeing a job and
        keep its history, dismiss it instead.
      </ConfirmDialog>
    </div>
  );
}
