import { useEffect, useState } from "react";
import {
  api,
  date,
  formatTime,
  version,
  type Json,
  type ListResult,
  type Source,
} from "../api";
import {
  selectRecords,
  useDebounce,
  useResource,
  useUrlFilters,
  useUrlState,
  useWorkspace,
} from "../state";
import {
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Icon,
  Loading,
  Pagination,
  Switch,
  Tabs,
} from "../ui";
interface Collection {
  enabled: boolean;
  version: number;
  source_count: number;
  enabled_sources: number;
  queued_tasks: number;
  running_tasks: number;
  next_run_at?: string;
}
interface Provider {
  id: string;
  name: string;
  version: number;
  capability: { supported: boolean; kind: string; description: string };
  policy: {
    enabled: boolean;
    min_interval_seconds: number;
  };
  runtime: {
    cooldown_until?: string;
    next_allowed_at?: string;
    last_error?: string;
    last_status?: number;
    requests_hour?: number;
    requests_day?: number;
  };
}
import {
  SourceEditor,
  SourceBulkEditor,
  RunOptionsDialog,
  scheduleLabel,
  RunProgress,
} from "./CollectionForms";
function isSavedSearch(kind: string) {
  return kind === "jobspy";
}
function searchProviders(source: Source) {
  return (source.config.providers as string[]) || [];
}
export default function CompaniesPage() {
  const resource = useResource<ListResult<Source>>(
    "/sources",
    { items: [], total: 0 },
    true,
  );
  const [tab, setTab] = useUrlState("section", "searches");
  const [filters, setFilters] = useUrlFilters({ q: "", offset: "0" });
  const query = useDebounce(filters.q).trim().toLowerCase();
  const [editing, setEditing] = useState<Source | "new" | null>(null),
    [selection, setSelection] = useState<Record<string, number>>({}),
    [confirmDelete, setConfirmDelete] = useState<Source[] | null>(null),
    [bulkEditing, setBulkEditing] = useState(false),
    [runningOptions, setRunningOptions] = useState<Source[] | null>(null),
    [batchErrors, setBatchErrors] = useState<{ id: string; message: string }[]>(
      [],
    );
  const { mutate, pending, notify } = useWorkspace();
  const matches = resource.data.items.filter(
    (s) =>
      (tab === "searches") === isSavedSearch(s.kind) &&
      (!query ||
        [
          s.name,
          s.kind,
          s.url,
          s.config.query,
          s.config.location,
          s.config.board,
        ]
          .join(" ")
          .toLowerCase()
          .includes(query)),
  );
  const limit = 30;
  const offset = Math.min(
    Math.max(0, Number(filters.offset) || 0),
    Math.max(0, Math.ceil(matches.length / limit) - 1) * limit,
  );
  const rows = matches.slice(offset, offset + limit);
  const selected = Object.keys(selection);
  const chosen = resource.data.items
    .filter((s) => selection[s.id] !== undefined)
    .map((s) => ({ ...s, version: selection[s.id] }));
  async function batch(action: string, items = chosen, extra: Json = {}) {
    let result:
      | {
          succeeded: number;
          failed: number;
          items: { id: string; error?: { message: string } }[];
        }
      | undefined;
    const ok = await mutate(
      async () => {
        result = await api("/sources/bulk", "POST", {
          action,
          items: items.map((s) => ({ id: s.id, expected_version: s.version })),
          ...extra,
        });
      },
      action === "run"
        ? "Collection runs queued."
        : action === "configure"
          ? "Collection settings saved."
          : `Sources ${action === "delete" ? "removed" : action === "enable" ? "enabled" : "paused"}.`,
    );
    if (!ok || !result) return false;
    const failures = result.items
      .filter((item) => item.error)
      .map((item) => ({ id: item.id, message: item.error!.message }));
    setBatchErrors(failures);
    if (action === "run" && failures.length)
      setRunningOptions((current) =>
        current
          ? items.filter((source) =>
              failures.some((error) => error.id === source.id),
            )
          : null,
      );
    setSelection((current) => {
      const next = { ...current };
      for (const item of result!.items) if (!item.error) delete next[item.id];
      for (const item of failures) {
        const selected = items.find((s) => s.id === item.id);
        if (selected) next[item.id] = selected.version;
      }
      return next;
    });
    setConfirmDelete(null);
    if (result.failed)
      notify(
        `${result.succeeded} completed; ${result.failed} failed. See the source errors below.`,
        true,
      );
    return result.failed === 0;
  }
  const collecting = resource.data.items.some(
    (source) =>
      source.last_run && ["queued", "running"].includes(source.last_run.state),
  );
  useEffect(() => {
    if (!collecting) return;
    const timer = setInterval(resource.reload, 5000);
    return () => clearInterval(timer);
  }, [collecting]);
  return (
    <>
      <Heading
        title="Collection"
        description="Configure searches, company boards, schedules and provider request settings."
      >
        <Button icon="refresh" onClick={resource.reload}>
          Refresh
        </Button>
        <Button variant="primary" icon="plus" onClick={() => setEditing("new")}>
          {tab === "searches" ? "Save a search" : "Add company"}
        </Button>
      </Heading>
      <CollectionControl compact />
      <Tabs
        label="Collection sections"
        value={tab}
        onChange={(id) => {
          setTab(id);
          setFilters({ offset: "0" });
          setSelection({});
        }}
        items={[
          {
            id: "searches",
            label: "Saved searches",
            count: resource.data.items.filter((s) => isSavedSearch(s.kind))
              .length,
          },
          {
            id: "companies",
            label: "Companies",
            count: resource.data.items.filter((s) => !isSavedSearch(s.kind))
              .length,
          },
        ]}
      />
      <p className="collection-explainer">
        {tab === "searches"
          ? "Search only the keywords and locations you choose, on your selected job boards. Each saved search has its own schedule."
          : "Monitor the companies and feeds you choose. Optional title and location filters narrow their listings."}
      </p>
      <div className="toolbar">
        <div className="search">
          <Icon name="search" />
          <input
            aria-label="Search collection sources"
            placeholder="Find a search, company or feed"
            value={filters.q}
            onChange={(event) =>
              setFilters({ q: event.target.value, offset: "0" })
            }
          />
        </div>
      </div>
      <div className="collection-caption">
        <label className="checkline">
          <input
            type="checkbox"
            checked={
              !!rows.length && rows.every((s) => selection[s.id] !== undefined)
            }
            disabled={!rows.length}
            onChange={(e) =>
              setSelection((current) =>
                selectRecords(current, rows, e.target.checked),
              )
            }
          />
          Select this page
        </label>
        <a href="#settings?section=collection" className="textbutton">
          Provider request settings <Icon name="arrow" />
        </a>
      </div>
      {chosen.length > 0 && (
        <div className="bulkbar" role="region" aria-label="Selected sources">
          <strong>{chosen.length} selected across pages</strong>
          {["enable", "pause", "run"].map((action) => (
            <Button
              key={action}
              disabled={pending}
              onClick={() => batch(action)}
            >
              {action === "run"
                ? "Run once"
                : action === "enable"
                  ? "Enable"
                  : "Pause"}
            </Button>
          ))}
          <Button disabled={pending} onClick={() => setBulkEditing(true)}>
            Configure
          </Button>
          <Button disabled={pending} onClick={() => setRunningOptions(chosen)}>
            Run with options
          </Button>
          <Button variant="danger" onClick={() => setConfirmDelete(chosen)}>
            Remove
          </Button>
          <button className="textbutton" onClick={() => setSelection({})}>
            Clear selection
          </button>
        </div>
      )}
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      {!!batchErrors.length && (
        <div className="batch-errors" role="alert">
          <strong>Some sources need attention</strong>
          <ul>
            {batchErrors.map((error) => (
              <li key={error.id}>
                <b>
                  {resource.data.items.find((s) => s.id === error.id)?.name ||
                    error.id}
                </b>
                : {error.message}
              </li>
            ))}
          </ul>
          <Button
            className="small"
            onClick={() => {
              setSelection((current) =>
                Object.fromEntries(
                  Object.keys(current).map((id) => [
                    id,
                    resource.data.items.find((s) => s.id === id)?.version ||
                      current[id],
                  ]),
                ),
              );
              setBatchErrors([]);
              resource.reload();
            }}
          >
            Use current versions
          </Button>
        </div>
      )}
      <div className="companygrid">
        {resource.loading && !resource.data.items.length ? (
          <Loading />
        ) : rows.length ? (
          rows.map((source) => (
            <article className="card companycard" key={source.id}>
              <div className="companyhead">
                <input
                  type="checkbox"
                  aria-label={`Select ${source.name}`}
                  checked={selection[source.id] !== undefined}
                  disabled={
                    selection[source.id] === undefined && selected.length >= 200
                  }
                  onChange={(e) =>
                    setSelection((current) =>
                      selectRecords(current, [source], e.target.checked),
                    )
                  }
                />
                <span className="source-icon">
                  <Icon
                    name={isSavedSearch(source.kind) ? "search" : "companies"}
                  />
                </span>
                <div>
                  <h3>{source.name}</h3>
                  <p>
                    {isSavedSearch(source.kind)
                      ? `${String(source.config.query || "")} · ${String(source.config.location || source.config.country || "All locations")}`
                      : `${source.kind} · ${String(source.config.board || "Company board")}`}
                  </p>
                </div>
                <Switch
                  label={`Enable ${source.name}`}
                  checked={source.enabled}
                  disabled={pending || !source.automatic_collection}
                  onChange={(enabled) =>
                    mutate(
                      () =>
                        api(
                          `/sources/${source.id}`,
                          "PATCH",
                          version(source, { enabled }),
                        ),
                      enabled ? "Source enabled." : "Source paused.",
                    )
                  }
                />
              </div>
              {isSavedSearch(source.kind) && (
                <div className="provider-tags">
                  {searchProviders(source).map((p) => (
                    <span className="tag neutral" key={p}>
                      {p}
                    </span>
                  ))}
                </div>
              )}
              <div className="companyfacts">
                <div>
                  <span>Collection</span>
                  <strong>{source.enabled ? "Enabled" : "Paused"}</strong>
                </div>
                <div>
                  <span>Schedule</span>
                  <strong>{scheduleLabel(source.schedule)}</strong>
                </div>
                <div>
                  <span>Last run</span>
                  <strong>{date(source.last_run_at)}</strong>
                </div>
                <div>
                  <span>Next due</span>
                  <strong>{formatTime(source.next_run_at)}</strong>
                </div>
              </div>
              {source.last_run && <RunProgress run={source.last_run} compact />}
              {!source.automatic_collection && (
                <p className="source-error">
                  This source cannot supply full posting text. Use a supported
                  portal or add the full posting manually.
                </p>
              )}
              {source.last_error &&
                !["queued", "running"].includes(
                  source.last_run?.state || "",
                ) && (
                  <p className="source-error">
                    <Icon name="error" />
                    {source.last_error}
                  </p>
                )}
              {[
                ...new Set(
                  source.last_diagnostics?.flatMap((d) => d.warnings || []) ||
                    [],
                ),
              ].map((warning) => (
                <p className="hint" key={warning}>
                  {warning}
                </p>
              ))}
              <div className="companyfoot">
                <Button
                  className="small"
                  icon="edit"
                  onClick={() => setEditing(source)}
                >
                  Edit settings
                </Button>
                <Button
                  className="small"
                  icon="play"
                  disabled={pending || !source.automatic_collection}
                  onClick={() => batch("run", [source])}
                >
                  Run once
                </Button>
                <Button
                  className="small"
                  disabled={pending || !source.automatic_collection}
                  onClick={() => setRunningOptions([source])}
                >
                  Run with options
                </Button>
                <a
                  className="textbutton smalltext"
                  href={`#settings?section=activity&source_id=${source.id}`}
                >
                  View progress
                </a>
                {source.last_run &&
                  ["queued", "running"].includes(source.last_run.state) && (
                    <Button
                      className="small"
                      disabled={pending}
                      onClick={() =>
                        mutate(
                          () =>
                            api(
                              `/collection/runs/${source.last_run!.id}/cancel`,
                              "POST",
                            ),
                          "Current run stopped.",
                        )
                      }
                    >
                      Stop run
                    </Button>
                  )}
                <button
                  className="iconbtn danger"
                  aria-label={`Remove ${source.name}`}
                  onClick={() => setConfirmDelete([source])}
                >
                  <Icon name="trash" />
                </button>
              </div>
            </article>
          ))
        ) : (
          <section className="card full-grid">
            <Empty
              title={
                query
                  ? "No sources match this search."
                  : tab === "searches"
                    ? "Your next role starts with a focused search."
                    : "Follow a team you would like to join."
              }
              action={
                query ? (
                  <Button onClick={() => setFilters({ q: "", offset: "0" })}>
                    Clear search
                  </Button>
                ) : (
                  <Button icon="plus" onClick={() => setEditing("new")}>
                    {tab === "searches"
                      ? "Save your first search"
                      : "Add your first company"}
                  </Button>
                )
              }
            >
              {query
                ? "Try another name, query, location or board."
                : tab === "searches"
                  ? "Choose one query and location, select providers, then preview or save it for later collection."
                  : "Paste a company board or RSS URL and choose a collection schedule."}
            </Empty>
          </section>
        )}
      </div>
      <Pagination
        offset={offset}
        total={matches.length}
        limit={limit}
        onChange={(offset) => setFilters({ offset: String(offset) })}
      />
      <p className="hint">
        Up to 200 selected sources per action. Selections are kept while you
        search or change pages.
      </p>
      {editing && (
        <SourceEditor
          key={editing === "new" ? `new-${tab}` : editing.id}
          source={editing === "new" ? undefined : editing}
          search={
            editing === "new" ? tab === "searches" : editing.kind === "jobspy"
          }
          onClose={() => setEditing(null)}
        />
      )}
      {bulkEditing && chosen.length > 0 && (
        <SourceBulkEditor
          sources={chosen}
          onClose={() => setBulkEditing(false)}
          onSave={(patch) => batch("configure", chosen, { patch })}
        />
      )}
      {!!runningOptions?.length && (
        <RunOptionsDialog
          sources={runningOptions}
          onClose={() => setRunningOptions(null)}
          onRun={(overrides) => batch("run", runningOptions, { overrides })}
        />
      )}
      {confirmDelete && (
        <Dialog
          title={`Remove ${confirmDelete.length === 1 ? confirmDelete[0].name : `${confirmDelete.length} sources`}?`}
          onClose={() => setConfirmDelete(null)}
        >
          <p className="modal-intro">
            Automatic collection stops for these sources. Collected jobs, notes
            and applications are kept.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setConfirmDelete(null)}>Keep sources</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={() => batch("delete", confirmDelete)}
            >
              Remove sources
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
export function CollectionControl({ compact = false }: { compact?: boolean }) {
  const resource = useResource<Collection>("/collection", {
    enabled: true,
    version: 0,
    source_count: 0,
    enabled_sources: 0,
    queued_tasks: 0,
    running_tasks: 0,
  });
  const { mutate, pending } = useWorkspace();
  return (
    <section
      className={`card sectioncard collection-control ${compact ? "compact" : ""}`}
    >
      {resource.error ? (
        <ErrorBox message={resource.error} retry={resource.reload} />
      ) : (
        <div className="settingrow">
          <div>
            <h3>
              {resource.data.enabled
                ? "Scheduled collection is on"
                : "Scheduled collection is paused"}
            </h3>
            <p>
              {resource.data.enabled_sources} enabled sources ·{" "}
              {resource.data.running_tasks} running ·{" "}
              {resource.data.queued_tasks} queued . Pausing stops future
              scheduled runs; queued and current runs continue. Use Stop run to
              cancel a collection already in progress.
            </p>
          </div>
          <Switch
            label="Scheduled collection"
            checked={resource.data.enabled}
            disabled={pending || resource.loading}
            onChange={(enabled) =>
              mutate(
                () =>
                  api(
                    "/collection",
                    "PATCH",
                    version(resource.data, { enabled }),
                  ),
                enabled
                  ? "Scheduled collection resumed."
                  : "Scheduled collection paused. Existing runs continue.",
              )
            }
          />
        </div>
      )}
    </section>
  );
}
export function ProviderSettings() {
  const resource = useResource<ListResult<Provider>>("/providers", {
    items: [],
    total: 0,
  });
  const { mutate, pending } = useWorkspace();
  const [editing, setEditing] = useState<Provider | null>(null);
  return (
    <>
      <CollectionControl />
      <div className="sectiontitle form-section">
        <div>
          <h2>Provider request settings</h2>
          <p>
            One request interval per provider, shared by searches, company
            boards, previews and manual imports. Providers can request a longer
            pause.
          </p>
        </div>
        <Button icon="refresh" onClick={resource.reload}>
          Refresh
        </Button>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="provider-grid">
        {resource.data.items.map((provider) => {
          const cooldown = provider.runtime.cooldown_until,
            waiting = !!cooldown && new Date(cooldown).valueOf() > Date.now(),
            next = provider.runtime.next_allowed_at,
            pacing = !!next && new Date(next).valueOf() > Date.now();
          return (
            <article className="card sectioncard" key={provider.id}>
              <div className="sectiontitle">
                <div>
                  <h3>{provider.name}</h3>
                  <p>{provider.capability.description}</p>
                </div>
                <span
                  className={`tag ${!provider.capability.supported || waiting ? "amber" : provider.policy.enabled ? "green" : "neutral"}`}
                >
                  {!provider.capability.supported
                    ? "Unsupported"
                    : !provider.policy.enabled
                      ? "Paused"
                      : waiting
                        ? "Waiting on provider"
                        : pacing
                          ? "Pacing requests"
                          : "Ready"}
                </span>
              </div>
              <dl className="detailfacts">
                <div>
                  <dt>Request interval</dt>
                  <dd>
                    {provider.policy.min_interval_seconds
                      ? `At least ${provider.policy.min_interval_seconds}s apart`
                      : "Spacing disabled"}
                  </dd>
                </div>
                <div>
                  <dt>Recent requests</dt>
                  <dd>
                    {provider.runtime.requests_hour || 0} in the last hour ·{" "}
                    {provider.runtime.requests_day || 0} in 24 hours
                  </dd>
                </div>
                <div>
                  <dt>{waiting ? "Provider pause ends" : "Next request"}</dt>
                  <dd>
                    {!provider.policy.enabled
                      ? "Provider paused"
                      : waiting
                        ? formatTime(cooldown)
                        : pacing
                          ? formatTime(next)
                          : "Ready now"}
                  </dd>
                </div>
                <div>
                  <dt>Last response</dt>
                  <dd>
                    {provider.runtime.last_status
                      ? `HTTP ${provider.runtime.last_status}`
                      : "No requests yet"}
                  </dd>
                </div>
              </dl>
              {provider.runtime.last_error && (
                <p className="source-error">{provider.runtime.last_error}</p>
              )}
              <Button
                className="small"
                icon="edit"
                disabled={!provider.capability.supported}
                onClick={() => setEditing(provider)}
              >
                Edit request settings
              </Button>
            </article>
          );
        })}
      </div>
      {editing && (
        <Dialog
          title={`${editing.name} request settings`}
          onClose={() => setEditing(null)}
        >
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              if (
                await mutate(
                  () =>
                    api(
                      `/providers/${editing.id}`,
                      "PATCH",
                      version(editing, {
                        enabled: form.get("enabled") === "on",
                        min_interval_seconds: Number(
                          form.get("min_interval_seconds"),
                        ),
                      }),
                    ),
                  "Provider request settings saved.",
                )
              )
                setEditing(null);
            }}
          >
            <label className="checkline">
              <input
                type="checkbox"
                name="enabled"
                defaultChecked={editing.policy.enabled}
              />
              Enable this provider
            </label>
            <Field
              label="Request interval (seconds)"
              hint="Minimum spacing; default: 5 seconds. Set 0 for no delay. Provider pauses still apply."
            >
              <input
                name="min_interval_seconds"
                type="number"
                required
                min={0}
                max={3600}
                step={0.1}
                defaultValue={editing.policy.min_interval_seconds}
              />
            </Field>
            <p className="hint">
              An active provider pause remains in effect when you save settings.
              Request counts are informational.
            </p>
            <div className="actions form-actions">
              <Button type="button" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button variant="primary" disabled={pending}>
                Save settings
              </Button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  );
}
