import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  date,
  formatTime,
  jsonValue,
  version,
  type Json,
  type ListResult,
  type Source,
} from "../api";
import { confirmLeave, useResource, useUrlState, useWorkspace } from "../state";
import {
  AdvancedJson,
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Icon,
  Loading,
  Switch,
  Tabs,
} from "../ui";
interface Preview {
  kind: string;
  config: Json;
  url: string;
  items: { title: string; company?: string; location?: string }[];
  total: number;
  diagnostics?: {
    provider: string;
    state: string;
    message: string;
    requests?: number;
    next_run_at?: string;
  }[];
  request_estimate?: { total: number };
}
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
    max_requests_per_hour: number;
    max_requests_per_day: number;
    max_requests_per_run: number;
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
const kinds = [
  "greenhouse",
  "lever",
  "ashby",
  "rss",
  "recruitee",
  "personio",
  "workable",
  "breezy",
  "smartrecruiters",
  "bamboohr",
  "rippling",
  "workday",
  "oracle",
  "joincom",
  "jobcloud",
  "adzuna",
];
export default function CompaniesPage() {
  const resource = useResource<ListResult<Source>>(
    "/sources",
    { items: [], total: 0 },
    true,
  );
  const [tab, setTab] = useUrlState("section", "searches");
  const [editing, setEditing] = useState<Source | "new" | null>(null),
    [selected, setSelected] = useState<string[]>([]),
    [confirmDelete, setConfirmDelete] = useState<Source[] | null>(null);
  const { mutate, pending, notify } = useWorkspace();
  const rows = resource.data.items.filter(
    (s) => (tab === "searches") === (s.kind === "jobspy"),
  );
  const chosen = rows.filter((s) => selected.includes(s.id));
  async function batch(action: string, items = chosen) {
    let result:
      | {
          succeeded: number;
          failed: number;
          items: { error?: { message: string } }[];
        }
      | undefined;
    const ok = await mutate(
      async () => {
        result = await api("/sources/bulk", "POST", {
          action,
          items: items.map((s) => ({ id: s.id, expected_version: s.version })),
        });
      },
      `Source ${action === "run" ? "runs queued" : action === "delete" ? "removed" : action === "enable" ? "enabled" : "paused"}.`,
    );
    if (ok) {
      setSelected([]);
      setConfirmDelete(null);
      if (result?.failed)
        notify(
          `${result.succeeded} completed; ${result.failed} failed. ${result.items.find((i) => i.error)?.error?.message || "Refresh and retry."}`,
          true,
        );
    }
  }
  return (
    <>
      <Heading
        title="Collection"
        description="Configure saved searches, company feeds, schedules and shared provider limits."
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
          setSelected([]);
        }}
        items={[
          {
            id: "searches",
            label: "Saved searches",
            count: resource.data.items.filter((s) => s.kind === "jobspy")
              .length,
          },
          {
            id: "companies",
            label: "Companies",
            count: resource.data.items.filter((s) => s.kind !== "jobspy")
              .length,
          },
        ]}
      />
      <p className="collection-explainer">
        {tab === "searches"
          ? "Search only the keywords and locations you choose, on your selected job boards. Each saved search has its own schedule."
          : "Monitor the companies and feeds you choose. Optional title and location filters narrow their listings."}
      </p>
      <div className="collection-caption">
        <label className="checkline">
          <input
            type="checkbox"
            checked={!!rows.length && chosen.length === rows.length}
            onChange={(e) =>
              setSelected(e.target.checked ? rows.map((s) => s.id) : [])
            }
          />
          Select {rows.length} {tab === "searches" ? "searches" : "sources"}
        </label>
        <a href="#settings?section=collection" className="textbutton">
          Provider budgets & cooldowns <Icon name="arrow" />
        </a>
      </div>
      {chosen.length > 0 && (
        <div className="bulkbar" role="region" aria-label="Selected sources">
          <strong>{chosen.length} selected</strong>
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
          <Button variant="danger" onClick={() => setConfirmDelete(chosen)}>
            Remove
          </Button>
        </div>
      )}
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
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
                  checked={selected.includes(source.id)}
                  onChange={(e) =>
                    setSelected((ids) =>
                      e.target.checked
                        ? [...ids, source.id]
                        : ids.filter((id) => id !== source.id),
                    )
                  }
                />
                <span className="source-icon">
                  <Icon
                    name={source.kind === "jobspy" ? "search" : "companies"}
                  />
                </span>
                <div>
                  <h3>{source.name}</h3>
                  <p>
                    {source.kind === "jobspy"
                      ? `${String(source.config.query || "")} · ${String(source.config.location || "Anywhere")}`
                      : `${source.kind} · ${String(source.config.board || "Company board")}`}
                  </p>
                </div>
                <Switch
                  label={`Enable ${source.name}`}
                  checked={source.enabled}
                  disabled={pending}
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
              {source.kind === "jobspy" && (
                <div className="provider-tags">
                  {((source.config.providers as string[]) || []).map((p) => (
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
                  <strong>
                    {source.schedule.kind === "daily"
                      ? `Daily ${String(source.schedule.at || "07:00")}`
                      : `Every ${Number(source.schedule.minutes || 1440) / 60} hours`}
                  </strong>
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
              {(source.last_counts || source.last_result) && (
                <p className="smalltext muted">
                  {Object.entries(
                    source.last_counts || source.last_result || {},
                  )
                    .filter(([, value]) => typeof value === "number")
                    .map(
                      ([key, value]) => `${key.replaceAll("_", " ")}: ${value}`,
                    )
                    .join(" · ")}
                </p>
              )}
              {source.last_outcome && (
                <p className="smalltext muted">
                  Last outcome: {source.last_outcome}
                </p>
              )}
              {source.last_error && (
                <p className="source-error">
                  <Icon name="error" />
                  {source.last_error}
                </p>
              )}
              <div className="companyfoot">
                <Button
                  className="small"
                  icon="edit"
                  onClick={() => setEditing(source)}
                >
                  Configure
                </Button>
                <Button
                  className="small"
                  icon="play"
                  disabled={pending}
                  onClick={() => batch("run", [source])}
                >
                  Run once
                </Button>
                <a
                  className="textbutton smalltext"
                  href={`#settings?section=activity&source_id=${source.id}`}
                >
                  Progress
                </a>
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
                tab === "searches"
                  ? "Your next role starts with a focused search."
                  : "Follow a team you would like to join."
              }
              action={
                <Button icon="plus" onClick={() => setEditing("new")}>
                  {tab === "searches"
                    ? "Save your first search"
                    : "Add your first company"}
                </Button>
              }
            >
              {tab === "searches"
                ? "Choose one query and location, select providers, then preview or save it for later collection."
                : "Paste a company board or RSS URL and choose a collection schedule."}
            </Empty>
          </section>
        )}
      </div>
      {editing && (
        <SourceEditor
          key={editing === "new" ? `new-${tab}` : editing.id}
          source={editing === "new" ? undefined : editing}
          search={tab === "searches"}
          onClose={() => setEditing(null)}
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
function SourceEditor({
  source,
  search,
  onClose,
}: {
  source?: Source;
  search: boolean;
  onClose: () => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [preview, setPreview] = useState<Preview | null>(null),
    [previewing, setPreviewing] = useState(false),
    [kind, setKind] = useState(source?.kind || (search ? "jobspy" : "auto")),
    [scheduleKind, setScheduleKind] = useState(
      String(source?.schedule.kind || "interval"),
    );
  function values(form: HTMLFormElement) {
    const f = new FormData(form),
      configuration = jsonValue(f, "config", source?.config || {}) as Json;
    const config =
      kind === "jobspy"
        ? {
            ...configuration,
            query: f.get("query"),
            location: f.get("location"),
            country: f.get("country"),
            providers: f.getAll("providers"),
            results_wanted: Number(f.get("results_wanted")),
            hours_old: Number(f.get("hours_old")),
            is_remote: f.get("is_remote") === "on",
            job_type: f.get("job_type") || null,
            fetch_description: f.get("fetch_description") === "on",
          }
        : {
            ...configuration,
            ...(f.get("board") || Object.hasOwn(configuration, "board")
              ? { board: String(f.get("board") || "") }
              : {}),
          };
    return {
      name: f.get("name"),
      kind,
      url: kind === "jobspy" ? "" : f.get("url"),
      config,
      enabled: f.get("enabled") === "on",
      filters: {
        ...jsonValue(f, "filters", source?.filters || {}),
        titles: String(f.get("titles") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        locations: String(f.get("locations") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
      },
      schedule: {
        kind: f.get("schedule_kind"),
        minutes: Number(f.get("minutes") || source?.schedule.minutes || 1440),
        at: f.get("at") || source?.schedule.at || "07:00",
        timezone: f.get("timezone"),
      },
    };
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = values(e.currentTarget);
    if (
      await mutate(
        () =>
          api(
            source ? `/sources/${source.id}` : "/sources",
            source ? "PATCH" : "POST",
            source ? version(source, body) : body,
          ),
        "Collection source saved.",
      )
    )
      onClose();
  }
  async function inspect(form: HTMLFormElement | null) {
    if (!form || previewing || !form.reportValidity()) return;
    setPreviewing(true);
    try {
      const { enabled, schedule, ...body } = values(form);
      setPreview(await api<Preview>("/sources/preview", "POST", body));
      notify("Preview complete. No jobs were saved.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Preview failed.", true);
    } finally {
      setPreviewing(false);
    }
  }
  const filters = (key: string) =>
    Array.isArray(source?.filters[key])
      ? (source.filters[key] as string[]).join(", ")
      : "";
  return (
    <Dialog
      title={
        source
          ? "Configure collection."
          : search
            ? "Save a focused search."
            : "Follow a company."
      }
      onClose={onClose}
    >
      <form onSubmit={save}>
        <Field label={search ? "Search name" : "Company / source name"}>
          <input
            name="name"
            required
            defaultValue={source?.name}
            placeholder={search ? "My saved search" : "Company name"}
          />
        </Field>
        {search ? (
          <>
            <Field
              label="Search query"
              hint="Keywords sent to the selected job boards, for example backend engineer. Use a separate saved search for another query or location."
            >
              <input
                name="query"
                required
                defaultValue={String(source?.config.query || "")}
                placeholder="Enter keywords"
              />
            </Field>
            <div className="formgrid">
              <Field label="Location">
                <input
                  name="location"
                  defaultValue={String(source?.config.location || "")}
                  placeholder="City or region"
                />
              </Field>
              <Field
                label="Country"
                hint="Use an English country name, such as usa, uk or germany."
              >
                <input
                  name="country"
                  required
                  defaultValue={String(source?.config.country || "usa")}
                  placeholder="usa"
                />
              </Field>
            </div>
            <fieldset className="provider-choices">
              <legend>Search providers</legend>
              {["linkedin", "indeed", "glassdoor"].map((provider) => (
                <label className="checkline" key={provider}>
                  <input
                    type="checkbox"
                    name="providers"
                    value={provider}
                    defaultChecked={(
                      (source?.config.providers as string[]) || [
                        "linkedin",
                        "indeed",
                        "glassdoor",
                      ]
                    ).includes(provider)}
                  />
                  {
                    {
                      linkedin: "LinkedIn",
                      indeed: "Indeed",
                      glassdoor: "Glassdoor",
                    }[provider]
                  }
                </label>
              ))}
            </fieldset>
            <div className="formgrid">
              <Field label="Results per provider">
                <input
                  type="number"
                  name="results_wanted"
                  min={1}
                  max={50}
                  defaultValue={Number(source?.config.results_wanted || 20)}
                />
              </Field>
              <Field label="Posted within (hours)">
                <input
                  type="number"
                  name="hours_old"
                  min={1}
                  max={8760}
                  defaultValue={Number(source?.config.hours_old || 72)}
                />
              </Field>
              <Field label="Job type">
                <select
                  name="job_type"
                  defaultValue={String(source?.config.job_type || "")}
                >
                  <option value="">Any type</option>
                  {[
                    "fulltime",
                    "parttime",
                    "contract",
                    "temporary",
                    "internship",
                    "perdiem",
                    "other",
                    "volunteer",
                  ].map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <label className="checkline">
              <input
                type="checkbox"
                name="is_remote"
                defaultChecked={!!source?.config.is_remote}
              />
              Remote roles only
            </label>
            <label className="checkline">
              <input
                type="checkbox"
                name="fetch_description"
                defaultChecked={source?.config.fetch_description !== false}
              />
              Fetch full descriptions where supported
            </label>
          </>
        ) : (
          <>
            <Field label="Career / board URL">
              <input
                type="url"
                name="url"
                required
                defaultValue={source?.url || ""}
                placeholder="https://jobs.lever.co/company"
              />
            </Field>
            <div className="formgrid">
              <Field label="Board type">
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  <option value="auto">Detect from URL</option>
                  {kinds.map((k) => (
                    <option key={k} value={k}>
                      {k === "rss" ? "RSS feed" : k}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Board identifier (optional)">
                <input
                  name="board"
                  defaultValue={String(source?.config.board || "")}
                />
              </Field>
            </div>
          </>
        )}
        <div className="formgrid">
          <Field label="Role filters" hint="Optional comma-separated words.">
            <input name="titles" defaultValue={filters("titles")} />
          </Field>
          <Field
            label="Location filters"
            hint="Optional comma-separated locations."
          >
            <input name="locations" defaultValue={filters("locations")} />
          </Field>
          <Field label="Schedule">
            <select
              name="schedule_kind"
              value={scheduleKind}
              onChange={(e) => setScheduleKind(e.target.value)}
            >
              <option value="daily">At a daily time</option>
              <option value="interval">At an interval</option>
            </select>
          </Field>
          <Field label="Daily time">
            <input
              type="time"
              name="at"
              disabled={scheduleKind !== "daily"}
              defaultValue={String(source?.schedule.at || "07:00")}
            />
          </Field>
          <Field label="Timezone">
            <input
              name="timezone"
              required
              defaultValue={String(source?.schedule.timezone || "UTC")}
            />
          </Field>
          <Field label="Interval in minutes">
            <input
              type="number"
              name="minutes"
              disabled={scheduleKind !== "interval"}
              min={15}
              max={43200}
              defaultValue={Number(source?.schedule.minutes || 1440)}
            />
          </Field>
        </div>
        {!search && (
          <AdvancedJson
            name="config"
            label="Provider configuration"
            value={source?.config || {}}
          />
        )}
        <label className="checkline">
          <input
            type="checkbox"
            name="enabled"
            defaultChecked={source?.enabled || false}
          />
          Enable automatic collection
        </label>
        <p className="hint">
          Preview and Run once share provider request limits. New sources start
          paused.
        </p>
        {preview && (
          <section className="preview-result" aria-live="polite">
            <h3>{preview.total} matching opportunities</h3>
            {preview.request_estimate && (
              <p>{preview.request_estimate.total} estimated requests</p>
            )}
            {preview.diagnostics?.map((d, i) => (
              <p
                className={d.state === "error" ? "source-error" : "smalltext"}
                key={i}
              >
                <b>{d.provider}</b> · {d.state} ·{" "}
                {d.message ||
                  `${d.requests || 0} request${d.requests === 1 ? "" : "s"}`}
                {d.next_run_at ? ` · ${formatTime(d.next_run_at)}` : ""}
              </p>
            ))}
            <div className="source-preview">
              {preview.items?.slice(0, 6).map((j, i) => (
                <article key={i}>
                  <strong>{j.title}</strong>
                  <small>
                    {j.company} · {j.location}
                  </small>
                </article>
              ))}
            </div>
          </section>
        )}
        <div className="actions form-actions">
          <Button
            type="button"
            onClick={() => {
              if (confirmLeave()) onClose();
            }}
          >
            Cancel
          </Button>
          <Button
            type="button"
            icon="play"
            disabled={pending || previewing}
            onClick={(e) => inspect(e.currentTarget.form)}
          >
            {previewing ? "Previewing…" : "Preview"}
          </Button>
          <Button variant="primary" disabled={pending || previewing}>
            Save {search ? "search" : "source"}
          </Button>
        </div>
      </form>
    </Dialog>
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
                ? "Automatic collection is on"
                : "Automatic collection is paused"}
            </h3>
            <p>
              {resource.data.enabled_sources} enabled sources ·{" "}
              {resource.data.running_tasks} running ·{" "}
              {resource.data.queued_tasks} queued
              {!compact &&
                ". Pausing preserves each source’s settings. Manual runs still honor provider budgets."}
            </p>
          </div>
          <Switch
            label="Automatic collection"
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
                  ? "Automatic collection resumed."
                  : "Automatic collection paused.",
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
          <h2>Shared provider limits.</h2>
          <p>
            Limits apply across saved searches, company sources, previews and
            manual runs.
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
        {resource.data.items.map((provider) => (
          <article className="card sectioncard" key={provider.id}>
            <div className="sectiontitle">
              <div>
                <h3>{provider.name}</h3>
                <p>{provider.capability.description}</p>
              </div>
              <span
                className={`tag ${provider.capability.supported ? (provider.policy.enabled ? "green" : "neutral") : "amber"}`}
              >
                {provider.capability.supported
                  ? provider.policy.enabled
                    ? "Enabled"
                    : "Paused"
                  : "Unsupported"}
              </span>
            </div>
            <dl className="detailfacts">
              <div>
                <dt>Hourly / daily requests</dt>
                <dd>
                  {provider.runtime.requests_hour || 0} /{" "}
                  {provider.policy.max_requests_per_hour} ·{" "}
                  {provider.runtime.requests_day || 0} /{" "}
                  {provider.policy.max_requests_per_day}
                </dd>
              </div>
              <div>
                <dt>Per run / spacing</dt>
                <dd>
                  {provider.policy.max_requests_per_run} requests ·{" "}
                  {provider.policy.min_interval_seconds}s
                </dd>
              </div>
              <div>
                <dt>Next allowed</dt>
                <dd>
                  {provider.runtime.cooldown_until ||
                  provider.runtime.next_allowed_at
                    ? formatTime(
                        provider.runtime.cooldown_until ||
                          provider.runtime.next_allowed_at,
                      )
                    : "Ready now"}
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
              Configure limits
            </Button>
          </article>
        ))}
      </div>
      {editing && (
        <Dialog
          title={`${editing.name} limits.`}
          onClose={() => setEditing(null)}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const body = Object.fromEntries(
                [
                  "min_interval_seconds",
                  "max_requests_per_hour",
                  "max_requests_per_day",
                  "max_requests_per_run",
                ].map((key) => [key, Number(f.get(key))]),
              );
              if (
                await mutate(
                  () =>
                    api(
                      `/providers/${editing.id}`,
                      "PATCH",
                      version(editing, {
                        ...body,
                        enabled: f.get("enabled") === "on",
                      }),
                    ),
                  "Provider limits saved.",
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
            <div className="formgrid">
              {[
                ["min_interval_seconds", "Minimum spacing (seconds)"],
                ["max_requests_per_hour", "Maximum requests per hour"],
                ["max_requests_per_day", "Maximum requests per day"],
                ["max_requests_per_run", "Maximum requests per run"],
              ].map(([name, label]) => (
                <Field key={name} label={label}>
                  <input
                    name={name}
                    type="number"
                    required
                    min={name === "min_interval_seconds" ? 0 : 1}
                    max={
                      name === "min_interval_seconds"
                        ? 3600
                        : name === "max_requests_per_run"
                          ? 200
                          : 10000
                    }
                    defaultValue={
                      editing.policy[
                        name as keyof typeof editing.policy
                      ] as number
                    }
                  />
                </Field>
              ))}
            </div>
            <p className="hint">
              An active server cooldown remains in effect when you edit limits.
            </p>
            <Button variant="primary" disabled={pending}>
              Save limits
            </Button>
          </form>
        </Dialog>
      )}
    </>
  );
}
