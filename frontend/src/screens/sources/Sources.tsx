import { useMemo, useState } from "react";
import { Ellipsis, Pause, Play, Plus, Radar, RefreshCw } from "lucide-react";
import { type Schema } from "../../api/client";
import { TopBarActions, useTitle } from "../../shell/context";
import { Button, IconButton } from "../../ui/Button";
import { ConfirmDialog, Dialog } from "../../ui/Dialog";
import { Select } from "../../ui/Field";
import { formatFull, plural } from "../../ui/format";
import { listIndex, plainKey } from "../../ui/keys";
import { Menu } from "../../ui/Menu";
import {
  EmptyState,
  PageHeader,
  Properties,
  SkeletonRows,
} from "../../ui/Page";
import { useToast } from "../../ui/Toast";
import {
  INTERVALS,
  ago,
  clock,
  commonInterval,
  intervalLabel,
  sortSources,
  sourceStatus,
  usualCountry,
  type SourceKind,
  type SourceView,
} from "./model";
import {
  useCheckNow,
  useCollection,
  useDeleteSource,
  useKindLabels,
  useSetCollection,
  useSetEnabled,
  useSources,
  useSourcesBulk,
  useStopCheck,
} from "./queries";
import { RecentChecks } from "./RecentChecks";
import { SourceEditor } from "./SourceEditor";
import { SourceRow, type SourceActions } from "./SourceRow";
import "./sources.css";
import { LoadError } from "../../ui/LoadError";

/** Row letters: e edits, c checks now, p pauses or resumes. */
const SHORTCUTS: Record<string, "edit" | "check" | "toggle"> = {
  e: "edit",
  c: "check",
  p: "toggle",
};

type Editing = {
  /** A new key per opening, so the form starts from its record. */
  key: number;
  source?: SourceView;
  template?: SourceView;
  kind: SourceKind;
};

/**
 * Job sources: where new jobs come from and whether that works. The top
 * line sets how often every source is checked; each row says what a source
 * searches, how its last check went and what its jobs became. Recent checks
 * sit collapsed at the bottom.
 */
export default function SourcesScreen() {
  useTitle("Sources");
  const sources = useSources();
  const labels = useKindLabels();
  const toast = useToast();
  // The last opened form stays drawn while the drawer closes.
  const [editing, setEditing] = useState<Editing | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [opened, setOpened] = useState(0);
  const [removing, setRemoving] = useState<SourceView | null>(null);
  const [details, setDetails] = useState<SourceView | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const list = useMemo(() => sortSources(sources.data ?? []), [sources.data]);
  const interval = commonInterval(list);
  const country = usualCountry(list);
  const checkNow = useCheckNow();
  const stop = useStopCheck();
  const setEnabled = useSetEnabled();
  const remove = useDeleteSource();

  const open = (next: Omit<Editing, "key">) => {
    setOpened((count) => count + 1);
    setEditing({ ...next, key: opened + 1 });
    setEditorOpen(true);
  };
  const failed = (error: Error) =>
    toast.show({ message: error.message, tone: "error" });

  const actions: SourceActions = {
    edit: (source) => open({ source, kind: "search" }),
    duplicate: (source) => open({ template: source, kind: "search" }),
    details: setDetails,
    remove: setRemoving,
    check: (source) => {
      if (!source.automatic_collection) return;
      checkNow.mutate(source, {
        onSuccess: () =>
          toast.show({ message: `Checking “${source.name}” now` }),
        onError: failed,
      });
    },
    stop: (source) => {
      const run = source.last_run?.id;
      if (typeof run !== "string") return;
      stop.mutate(run, {
        onSuccess: () =>
          toast.show({
            message: `Stopped the check of “${source.name}”. Jobs it found stay.`,
          }),
        onError: failed,
      });
    },
    toggle: (source) => {
      if (!source.automatic_collection) return;
      const enabled = !source.enabled;
      setEnabled.mutate(
        { source, enabled },
        {
          onSuccess: (saved) =>
            toast.show({
              message: `${enabled ? "Resumed" : "Paused"} “${source.name}”`,
              action: {
                label: "Undo",
                undo: true,
                run: () =>
                  setEnabled.mutate(
                    {
                      source: saved,
                      enabled: !enabled,
                    },
                    { onError: failed },
                  ),
              },
            }),
          onError: failed,
        },
      );
    },
  };
  const byId = (id: string) => list.find((source) => source.id === id);
  const run = (action: (source: SourceView) => void) => (id: string) => {
    const source = byId(id);
    if (source) action(source);
  };
  const tabStop = activeId && byId(activeId) ? activeId : (list[0]?.id ?? null);

  return (
    <div className="src-screen">
      <PageHeader
        title="Sources"
        action={
          list.length > 0 && (
            <Button icon={Plus} onClick={() => open({ kind: "search" })}>
              Add source
            </Button>
          )
        }
      />
      <TopBarActions>
        <IconButton
          icon={Plus}
          label="Add source"
          size="touch"
          tooltip="none"
          onClick={() => open({ kind: "search" })}
        />
      </TopBarActions>
      {sources.isPending ? (
        <SkeletonRows rows={4} />
      ) : sources.isError ? (
        <LoadError
          what="your job sources"
          error={sources.error}
          retry={() => void sources.refetch()}
        />
      ) : list.length === 0 ? (
        <EmptyState
          icon={Radar}
          title="No job sources yet"
          actions={
            <>
              <Button
                variant="primary"
                onClick={() => open({ kind: "search" })}
              >
                Add a search
              </Button>
              <Button onClick={() => open({ kind: "company" })}>
                Add a company careers page
              </Button>
            </>
          }
        >
          Add a search to get new jobs every few hours.
        </EmptyState>
      ) : (
        <>
          <ScheduleLine sources={list} interval={interval} />
          <div
            role="region"
            aria-label="Job sources"
            aria-keyshortcuts="J K E C P"
            onKeyDown={(event) => {
              const key = plainKey(event.nativeEvent);
              if (!key) return;
              const rows = [
                ...event.currentTarget.querySelectorAll<HTMLElement>(
                  "[data-row-id]",
                ),
              ];
              const ids = rows.map((row) => row.dataset.rowId!);
              const index = ids.indexOf(tabStop ?? "");
              const next = listIndex(key, index, ids.length);
              if (next != null) {
                event.preventDefault();
                setActiveId(ids[next]);
                rows[next].focus();
                return;
              }
              const shortcut = SHORTCUTS[key.toLowerCase()];
              if (shortcut && key.length === 1 && tabStop) {
                event.preventDefault();
                run(actions[shortcut])(tabStop);
              }
            }}
          >
            <ul className="src-rows">
              {list.map((source) => (
                <SourceRow
                  key={source.id}
                  source={source}
                  active={source.id === tabStop}
                  labels={labels}
                  actions={actions}
                  onFocusRow={() => setActiveId(source.id)}
                />
              ))}
            </ul>
          </div>
          <RecentChecks />
        </>
      )}
      <SourceEditor
        key={editing?.key ?? 0}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        source={editing?.source}
        template={editing?.template}
        initialKind={editing?.kind}
        country={country}
        interval={interval}
        labels={labels}
      />
      <ConfirmDialog
        open={!!removing}
        title={`Delete “${removing?.name ?? ""}”?`}
        confirm="Delete source"
        onClose={() => setRemoving(null)}
        onConfirm={() => {
          const source = removing;
          if (!source) return;
          remove.mutate(source, {
            onSuccess: () =>
              toast.show({
                message: `Deleted “${source.name}”. Its jobs stay in Jobs.`,
                tone: "success",
              }),
            onError: failed,
          });
        }}
      >
        It stops looking for new jobs, and its recent checks go with it. The
        jobs it already found stay in Jobs. This cannot be undone.
      </ConfirmDialog>
      <CheckDetails
        source={details}
        onClose={() => setDetails(null)}
        onCheck={(source) => {
          setDetails(null);
          actions.check(source);
        }}
      />
    </div>
  );
}

/**
 * "Checked every [6 h] · next check 14:00 · Check all now", with the
 * switch of every automatic check in `…`.
 */
function ScheduleLine({
  sources,
  interval,
}: {
  sources: SourceView[];
  interval: number | null;
}) {
  const collection = useCollection();
  const bulk = useSourcesBulk();
  const setCollection = useSetCollection();
  const toast = useToast();
  const on = collection.data?.enabled ?? true;
  const next = collection.data?.next_run_at;
  const versions = (items: SourceView[]) =>
    items.map((source) => ({
      id: source.id,
      expected_version: source.version,
    }));
  const failed = (error: Error) =>
    toast.show({ message: error.message, tone: "error" });
  const checkable = sources.filter((source) => source.automatic_collection);
  const enabled = checkable.filter((source) => source.enabled);
  const targets = enabled.length ? enabled : checkable;

  function schedule(minutes: number) {
    bulk.mutate(
      {
        action: "configure",
        items: versions(sources),
        patch: { schedule: { kind: "interval", minutes } },
      } as Schema<"SourceBulk">,
      {
        onSuccess: () =>
          toast.show({
            message: `Sources are checked every ${intervalLabel(minutes)}`,
            tone: "success",
          }),
        onError: failed,
      },
    );
  }
  function toggle() {
    if (!collection.data) return;
    setCollection.mutate(
      { enabled: !on, expected_version: collection.data.version },
      {
        onSuccess: () =>
          toast.show({
            message: on
              ? "Paused automatic checks. Check now still works."
              : "Resumed automatic checks",
          }),
        onError: failed,
      },
    );
  }
  const options =
    interval == null || INTERVALS.includes(interval)
      ? INTERVALS
      : [...INTERVALS, interval].sort((a, b) => a - b);
  return (
    <div className="src-topline">
      <div className="src-topline-text">
        {on ? (
          <>
            <label className="src-interval">
              <span>Checked every</span>
              <Select
                aria-label="How often sources are checked"
                value={interval ?? "mixed"}
                disabled={bulk.isPending}
                onChange={(event) => schedule(Number(event.target.value))}
              >
                {interval == null && (
                  <option value="mixed" disabled>
                    own schedules
                  </option>
                )}
                {options.map((minutes) => (
                  <option key={minutes} value={minutes}>
                    {intervalLabel(minutes)}
                  </option>
                ))}
              </Select>
            </label>
            {next && (
              <span title={formatFull(next)}>
                <span aria-hidden="true">· </span>next check {clock(next)}
              </span>
            )}
          </>
        ) : (
          <span>
            Automatic checks are paused{" "}
            <Button variant="ghost" size="sm" icon={Play} onClick={toggle}>
              Resume
            </Button>
          </span>
        )}
      </div>
      <div className="src-topline-tools">
        <Button
          variant="ghost"
          size="sm"
          icon={RefreshCw}
          disabled={!targets.length || bulk.isPending}
          onClick={() =>
            bulk.mutate(
              { action: "run", items: versions(targets) },
              {
                onSuccess: (result) => toast.show(checkAllMessage(result)),
                onError: failed,
              },
            )
          }
        >
          Check all now
        </Button>
        <Menu
          label="Automatic checks"
          placement="bottom-end"
          items={[
            {
              id: "collection",
              label: on ? "Pause automatic checks" : "Resume automatic checks",
              icon: on ? Pause : Play,
              disabled: !collection.data,
              onSelect: toggle,
            },
          ]}
          trigger={(props) => (
            <IconButton
              {...props}
              icon={Ellipsis}
              label="More about automatic checks"
              size="sm"
            />
          )}
        />
      </div>
    </div>
  );
}

/** What Check all now did: how many it queued, and what it could not. */
function checkAllMessage(result: Schema<"BatchResult">) {
  if (!result.failed)
    return { message: `Checking ${plural(result.succeeded, "source")} now` };
  const reason = result.items.find((item) => !item.ok)?.error?.message;
  return {
    message: `Checking ${plural(result.succeeded, "source")} now; ${plural(result.failed, "source")} could not be checked${reason ? `: ${reason}` : "."}`,
    tone: "error" as const,
  };
}

/** The last check of a failing source: what happened, and Check now. */
function CheckDetails({
  source,
  onClose,
  onCheck,
}: {
  source: SourceView | null;
  onClose: () => void;
  onCheck: (source: SourceView) => void;
}) {
  const run = source?.last_run ?? null;
  const when =
    (run?.finished_at as string | undefined) ||
    (run?.started_at as string | undefined) ||
    (source?.last_run_at as string | undefined);
  return (
    <Dialog
      open={!!source}
      onClose={onClose}
      title={`Last check of “${source?.name ?? ""}”`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="primary"
            icon={RefreshCw}
            onClick={() => source && onCheck(source)}
          >
            Check now
          </Button>
        </>
      }
    >
      {source && (
        <>
          <p className="src-details-error">
            {source.last_error || sourceStatus(source).text}
          </p>
          <Properties
            items={[
              { label: "When", value: when ? `${ago(when)}` : "" },
              {
                label: "Requests",
                value:
                  typeof run?.http_requests === "number"
                    ? String(run.http_requests)
                    : "",
              },
            ]}
          />
          <p className="src-details-note">
            A site that blocks or limits requests usually works again later. If
            it keeps failing, edit the source or check the address.
          </p>
        </>
      )}
    </Dialog>
  );
}
