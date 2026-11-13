import { useEffect, useState } from "react";
import { api, type Json, type ListResult, type Source } from "../../api";
import {
  Banner,
  Button,
  Chips,
  EmptyState,
  ErrorBanner,
  Loading,
} from "../../design";
import { ConfirmDialog, Pager, plural } from "../../library/common";
import {
  selectRecords,
  useDebounce,
  useResource,
  useUrlFilters,
  useWorkspace,
} from "../../state";
import { active, isSearch } from "./model";
import { BulkConfigureDialog, RunOptionsDialog } from "./SourceDialogs";
import { SourceEditor } from "./SourceEditor";
import { SourceRow } from "./SourceRow";

const PAGE = 30;
const MAX_SELECTED = 200;
const NONE: ListResult<Source> = { items: [], total: 0 };
type Batch = {
  succeeded: number;
  failed: number;
  items: { id: string; error?: { message: string } }[];
};
export type Editing = Source | "search" | "board" | null;

const searchable = (source: Source) =>
  [
    source.name,
    source.kind,
    source.url,
    source.config.query,
    source.config.location,
    source.config.board,
  ]
    .join(" ")
    .toLowerCase();

/**
 * Saved searches and company boards in one table: switch each on or off, run
 * once, edit, and act on a selection kept across pages and searches.
 */
export function Sources({
  editing,
  onEdit,
}: {
  editing: Editing;
  onEdit: (next: Editing) => void;
}) {
  const sources = useResource("/sources?summary=false", NONE, true);
  const [filters, setFilters] = useUrlFilters({ q: "", kind: "", offset: "0" });
  const query = useDebounce(filters.q).trim().toLowerCase();
  const [selection, setSelection] = useState<Record<string, number>>({}),
    [removing, setRemoving] = useState<Source[] | null>(null),
    [configuring, setConfiguring] = useState(false),
    [options, setOptions] = useState<Source[] | null>(null),
    [errors, setErrors] = useState<{ id: string; message: string }[]>([]);
  const { mutate, pending, notify } = useWorkspace();
  const all = sources.data.items;
  const ofKind = (kind: string) =>
    all.filter((s) => !kind || (kind === "search") === isSearch(s));
  const matches = ofKind(filters.kind).filter(
    (source) => !query || searchable(source).includes(query),
  );
  const offset = Math.min(
    Math.max(0, Number(filters.offset) || 0),
    Math.max(0, Math.ceil(matches.length / PAGE) - 1) * PAGE,
  );
  const rows = matches.slice(offset, offset + PAGE);
  const updating = sources.loading || query !== filters.q.trim().toLowerCase();
  const blocked = pending || updating || !!sources.error;
  const chosen = all
    .filter((source) => selection[source.id] !== undefined)
    .map((source) => ({ ...source, version: selection[source.id] }));
  const collecting = all.some((source) => active(source.last_run?.state));
  useEffect(() => {
    if (!collecting) return;
    const timer = setInterval(sources.reload, 5000);
    return () => clearInterval(timer);
  }, [collecting]);

  async function batch(action: string, items = chosen, extra: Json = {}) {
    if (updating || sources.error) return false;
    let result: Batch | undefined;
    const ok = await mutate(
      async () => {
        result = await api<Batch>("/sources/bulk", "POST", {
          action,
          items: items.map((s) => ({ id: s.id, expected_version: s.version })),
          ...extra,
        });
      },
      action === "run"
        ? items.length === 1
          ? `${items[0].name} is collecting.`
          : "Collection runs queued."
        : action === "configure"
          ? "Collection settings saved."
          : action === "delete"
            ? "Sources removed. Their jobs are kept."
            : action === "enable"
              ? "Sources switched on."
              : "Sources paused.",
    );
    if (!ok || !result) return false;
    const failures = result.items
      .filter((item) => item.error)
      .map((item) => ({ id: item.id, message: item.error!.message }));
    setErrors(failures);
    setSelection((current) => {
      const next = { ...current };
      for (const item of result!.items) if (!item.error) delete next[item.id];
      for (const failure of failures) {
        const item = items.find((s) => s.id === failure.id);
        if (item) next[failure.id] = item.version;
      }
      return next;
    });
    setRemoving(null);
    if (result.failed)
      notify(
        `${result.succeeded} done; ${result.failed} failed. The sources that need attention are listed above the table.`,
        true,
      );
    return result.failed === 0;
  }

  const name = (id: string) => all.find((s) => s.id === id)?.name || id;
  const pageSelected =
    !!rows.length && rows.every((s) => selection[s.id] !== undefined);
  return (
    <div className="stack">
      <section className="card" aria-label="Sources">
        <div className="filters" role="search">
          <input
            className="input"
            type="search"
            aria-label="Find a source"
            placeholder="Find a search or company"
            value={filters.q}
            onChange={(event) =>
              setFilters({ q: event.target.value, offset: "0" })
            }
          />
          <Chips
            label="Kind of source"
            value={filters.kind}
            onChange={(kind) => {
              setFilters({ kind, offset: "0" });
              setSelection({});
            }}
            options={[
              { id: "", label: "All", count: all.length },
              {
                id: "search",
                label: "Searches",
                count: ofKind("search").length,
              },
              {
                id: "board",
                label: "Company boards",
                count: ofKind("board").length,
              },
            ]}
          />
        </div>
        {!!rows.length && !updating && (
          <div className="filters">
            <label className="toggle">
              <input
                type="checkbox"
                checked={pageSelected}
                onChange={(event) =>
                  setSelection((current) =>
                    selectRecords(current, rows, event.target.checked),
                  )
                }
              />
              Select the sources on this page
            </label>
          </div>
        )}
        {chosen.length > 0 && (
          <div className="bulkbar" role="region" aria-label="Selected sources">
            <strong>{plural(chosen.length, "source")} selected</strong>
            <Button
              size="sm"
              disabled={blocked}
              onClick={() => batch("enable")}
            >
              Switch on
            </Button>
            <Button size="sm" disabled={blocked} onClick={() => batch("pause")}>
              Pause
            </Button>
            <Button size="sm" disabled={blocked} onClick={() => batch("run")}>
              Run once
            </Button>
            <Button
              size="sm"
              disabled={blocked}
              onClick={() => setOptions(chosen)}
            >
              Run with options
            </Button>
            <Button
              size="sm"
              disabled={blocked}
              onClick={() => setConfiguring(true)}
            >
              Configure
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={updating || !!sources.error}
              onClick={() => setRemoving(chosen)}
            >
              Remove
            </Button>
            <Button size="sm" variant="quiet" onClick={() => setSelection({})}>
              Clear selection
            </Button>
          </div>
        )}
        {!!errors.length && (
          <div className="body">
            <Banner
              tone="danger"
              role="alert"
              title="Some sources need attention"
              action={
                <Button
                  size="sm"
                  onClick={() => {
                    setSelection((current) =>
                      Object.fromEntries(
                        Object.keys(current).map((id) => [
                          id,
                          all.find((s) => s.id === id)?.version || current[id],
                        ]),
                      ),
                    );
                    setErrors([]);
                    sources.reload();
                  }}
                >
                  Use current versions
                </Button>
              }
            >
              <ul className="plain">
                {errors.map((error) => (
                  <li key={error.id}>
                    <strong>{name(error.id)}</strong>: {error.message}
                  </li>
                ))}
              </ul>
            </Banner>
          </div>
        )}
        {sources.error ? (
          <div className="body">
            <ErrorBanner message={sources.error} retry={sources.reload} />
          </div>
        ) : updating ? (
          <Loading label="Loading sources…" />
        ) : rows.length ? (
          <div className="datatable-wrap">
            <table className="datatable stack sources" aria-label="Sources">
              <thead>
                <tr>
                  <th>
                    <span className="sr">Selected</span>
                  </th>
                  <th>On</th>
                  <th>Source</th>
                  <th>Providers</th>
                  <th>Schedule</th>
                  <th>Last run</th>
                  <th>
                    <span className="sr">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((source) => (
                  <SourceRow
                    key={source.id}
                    source={source}
                    selected={selection[source.id] !== undefined}
                    selectable={chosen.length < MAX_SELECTED}
                    onSelect={(value) =>
                      setSelection((current) =>
                        selectRecords(current, [source], value),
                      )
                    }
                    onEdit={() => onEdit(source)}
                    onRun={() => batch("run", [source])}
                    onOptions={() => setOptions([source])}
                    onRemove={() => setRemoving([source])}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title={
              query || filters.kind
                ? "No source matches"
                : "No search or company board yet"
            }
            action={
              query || filters.kind ? (
                <Button
                  onClick={() => setFilters({ q: "", kind: "", offset: "0" })}
                >
                  Show all sources
                </Button>
              ) : (
                <Button variant="primary" onClick={() => onEdit("search")}>
                  Add a search
                </Button>
              )
            }
          >
            {query || filters.kind
              ? "Try another name, query, location or board."
              : "A saved search asks job boards one query in one place; a company board follows the openings of one employer."}
          </EmptyState>
        )}
        <Pager
          offset={offset}
          total={matches.length}
          limit={PAGE}
          label="Source pages"
          onChange={(value) => setFilters({ offset: String(value) })}
        />
        <footer>
          <span className="caption grow">
            Up to {MAX_SELECTED} selected sources per action; the selection is
            kept while you search or change pages.
          </span>
        </footer>
      </section>
      {editing && (
        <SourceEditor
          key={typeof editing === "string" ? `new-${editing}` : editing.id}
          source={typeof editing === "string" ? undefined : editing}
          search={
            typeof editing === "string"
              ? editing === "search"
              : isSearch(editing)
          }
          onClose={() => onEdit(null)}
        />
      )}
      {configuring && chosen.length > 0 && (
        <BulkConfigureDialog
          sources={chosen}
          onClose={() => setConfiguring(false)}
          onSave={(patch) => batch("configure", chosen, { patch })}
        />
      )}
      {!!options?.length && (
        <RunOptionsDialog
          sources={options}
          onClose={() => setOptions(null)}
          onRun={(overrides) => batch("run", options, { overrides })}
        />
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.length === 1 ? removing[0].name : plural(removing.length, "source")}?`}
          confirm={removing.length === 1 ? "Remove source" : "Remove sources"}
          keep={removing.length === 1 ? "Keep source" : "Keep sources"}
          onConfirm={() => void batch("delete", removing)}
          onClose={() => setRemoving(null)}
        >
          <p>
            Collection stops for {removing.length === 1 ? "it" : "them"}. Jobs
            already collected, their notes and applications are kept.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
