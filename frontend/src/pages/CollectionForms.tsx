import { useRef, useState, type FormEvent } from "react";
import {
  api,
  formatTime,
  jsonValue,
  version,
  type CollectionRun,
  type CollectionSchedule,
  type Json,
  type ListResult,
  type Source,
} from "../api";
import { useResource, useWorkspace } from "../state";
import { AdvancedJson, Button, Dialog, ErrorBox, Field, Loading } from "../ui";

interface ConfigProperty {
  default?: unknown;
  minimum?: number;
  maximum?: number;
}
type ConfigProperties = Record<string, ConfigProperty>;
export interface SourceSchema {
  kind: string;
  label: string;
  config_schema: Json;
  capabilities: {
    search: boolean;
    lookback: boolean;
    details: boolean;
    description_mode: "inline" | "separate" | "metadata" | "portal";
    automatic_collection: boolean;
  };
}
function schemaProperties(schema?: SourceSchema): ConfigProperties {
  return (schema?.config_schema.properties as ConfigProperties) || {};
}
function sharedProperties(
  schemas: SourceSchema[],
  kinds: string[],
): ConfigProperties {
  const properties = kinds.map((kind) =>
    schemaProperties(schemas.find((schema) => schema.kind === kind)),
  );
  return Object.fromEntries(
    Object.entries(properties[0] || {})
      .filter(([key]) => properties.every((item) => Object.hasOwn(item, key)))
      .map(([key, property]) => {
        const minima = properties.flatMap((item) =>
          item[key].minimum == null ? [] : [item[key].minimum!],
        );
        const maxima = properties.flatMap((item) =>
          item[key].maximum == null ? [] : [item[key].maximum!],
        );
        return [
          key,
          {
            ...property,
            minimum: minima.length ? Math.max(...minima) : undefined,
            maximum: maxima.length ? Math.min(...maxima) : undefined,
          },
        ];
      }),
  );
}
const acquisitionLimits = [
  { key: "hours_old", label: "Posted within (hours)" },
  { key: "results_wanted", label: "Results per portal" },
  { key: "max_results", label: "Results per run" },
];
function limitValues(form: FormData, properties: ConfigProperties): Json {
  const values: Json = {};
  for (const { key } of acquisitionLimits) {
    const value = form.get(key);
    if (
      Object.hasOwn(properties, key) &&
      typeof value === "string" &&
      value.trim()
    )
      values[key] = Number(value);
  }
  return values;
}
function SharedAcquisitionLimits({
  properties,
  placeholder,
}: {
  properties: ConfigProperties;
  placeholder: string;
}) {
  const fields = acquisitionLimits.filter(({ key }) =>
    Object.hasOwn(properties, key),
  );
  return fields.length ? (
    <div className="formgrid">
      {fields.map(({ key, label }) => (
        <Field label={label} key={key}>
          <input
            name={key}
            type="number"
            min={properties[key].minimum}
            max={properties[key].maximum}
            placeholder={placeholder}
          />
        </Field>
      ))}
    </div>
  ) : (
    <p className="hint">
      The selected sources have no shared acquisition limits.
    </p>
  );
}
interface Preview {
  kind: string;
  automatic_collection?: boolean;
  total: number;
  items: { title: string; company?: string; location?: string }[];
  diagnostics?: {
    provider: string;
    state: string;
    message: string;
    requests?: number;
    next_run_at?: string;
  }[];
  request_estimate?: { total: number };
  full_request_estimate?: { total: number };
}
export function scheduleLabel(schedule: Json) {
  if (schedule.kind === "daily")
    return `${((schedule.times as string[]) || []).join(", ")} · ${String(schedule.timezone || "UTC")}`;
  const minutes = Number(schedule.minutes || 1440);
  return minutes % 60 ? `Every ${minutes} min` : `Every ${minutes / 60} h`;
}
export function duration(seconds?: number) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const hours = Math.floor(seconds / 3600),
    minutes = Math.floor((seconds % 3600) / 60);
  return hours
    ? `${hours}h ${minutes}m`
    : `${minutes}m ${Math.round(seconds % 60)}s`;
}
export function RunProgress({
  run,
  compact = false,
}: {
  run: CollectionRun;
  compact?: boolean;
}) {
  const active = ["queued", "running"].includes(run.state),
    waiting =
      run.state === "queued" &&
      !!run.next_run_at &&
      new Date(run.next_run_at).valueOf() > Date.now(),
    waitingReason = waiting
      ? run.tasks?.find((task) => task.state === "queued" && task.error)?.error
      : undefined,
    continuing = !!waitingReason && /collection batch/i.test(waitingReason);
  return (
    <div className={`run-progress ${compact ? "compact" : ""}`}>
      <div className="run-state">
        <span
          className={`tag ${run.state === "failed" ? "amber" : run.state === "succeeded" ? "green" : "neutral"}`}
        >
          {continuing
            ? "Continuing collection"
            : waiting
              ? "Waiting"
              : run.state}
        </span>
        <span className="smalltext muted">
          {waiting
            ? `Resumes ${formatTime(run.next_run_at)}`
            : run.started_at
              ? `Started ${formatTime(run.started_at)}`
              : "Ready to start"}
        </span>
      </div>
      {waitingReason && <p className="hint run-wait-reason">{waitingReason}</p>}
      <dl className="run-counts">
        {[
          ["received", "Processed"],
          ["created", "New"],
          ["existing", "Already archived"],
          ["invalid", "Invalid"],
          ["pending_descriptions", "Waiting for text"],
          ["unavailable_descriptions", "Text unavailable"],
        ]
          .filter(
            ([key]) =>
              key !== "unavailable_descriptions" || !!run.counts?.[key],
          )
          .map(([key, label]) => (
            <div key={key}>
              <dt>{label}</dt>
              <dd>{run.counts?.[key] || 0}</dd>
            </div>
          ))}
      </dl>
      {!compact && (
        <p className="smalltext muted">
          Processing {duration(run.processing_seconds)} · Waiting{" "}
          {duration(run.waiting_seconds)} · Total {duration(run.total_seconds)}
          {active ? " so far" : ""}
        </p>
      )}
    </div>
  );
}
function Section({
  title,
  children,
  hint,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="collection-form-section">
      <h3>{title}</h3>
      {hint && <p className="hint section-hint">{hint}</p>}
      {children}
    </section>
  );
}
export function ScheduleFields({ schedule }: { schedule?: Json }) {
  const [kind, setKind] = useState(String(schedule?.kind || "interval"));
  const [times, setTimes] = useState<string[]>(
    (schedule?.times as string[]) || ["07:00"],
  );
  return (
    <>
      <Field label="Frequency">
        <select
          name="schedule_kind"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="interval">Every interval</option>
          <option value="daily">At daily times</option>
        </select>
      </Field>
      {kind === "daily" ? (
        <>
          <div className="daily-times">
            <span className="field-label">Daily times</span>
            <div className="time-inputs">
              {times.map((value, i) => (
                <div className="time-input" key={i}>
                  <input
                    name="daily_times"
                    aria-label={`Daily time ${i + 1}`}
                    type="time"
                    required
                    value={value}
                    onChange={(e) =>
                      setTimes((current) =>
                        current.map((v, index) =>
                          index === i ? e.target.value : v,
                        ),
                      )
                    }
                  />
                  {times.length > 1 && (
                    <button
                      type="button"
                      data-dirty-control="true"
                      className="textbutton"
                      aria-label={`Remove daily time ${i + 1}`}
                      onClick={() =>
                        setTimes((current) =>
                          current.filter((_, index) => index !== i),
                        )
                      }
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
            <Button
              type="button"
              data-dirty-control="true"
              className="small"
              disabled={times.length >= 12}
              onClick={() =>
                setTimes((current) => {
                  const next =
                    Array.from(
                      { length: 24 },
                      (_, index) =>
                        `${String((Number(current[current.length - 1]?.slice(0, 2) || 7) + index + 1) % 24).padStart(2, "0")}:00`,
                    ).find((value) => !current.includes(value)) || "12:00";
                  return [...current, next];
                })
              }
            >
              Add time
            </Button>
          </div>
          <Field
            label="Timezone"
            hint="An IANA timezone, such as Europe/Berlin or America/New_York. Times follow daylight saving changes."
          >
            <input
              name="timezone"
              required
              defaultValue={String(schedule?.timezone || "UTC")}
            />
          </Field>
          <p className="hint">
            One active run per source. Missed times are combined into one run.
          </p>
        </>
      ) : (
        <Field
          label="Interval (minutes)"
          hint="15–43,200 minutes. Default: 1,440 minutes (once a day)."
        >
          <input
            name="minutes"
            type="number"
            required
            min={15}
            max={43200}
            defaultValue={Number(schedule?.minutes || 1440)}
          />
        </Field>
      )}
    </>
  );
}
function scheduleValues(f: FormData): CollectionSchedule {
  return f.get("schedule_kind") === "daily"
    ? {
        kind: "daily",
        times: f.getAll("daily_times").map(String),
        timezone: String(f.get("timezone") || "UTC"),
      }
    : { kind: "interval", minutes: Number(f.get("minutes")) };
}
function terms(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function SourceEditor({
  source,
  search,
  onClose,
}: {
  source?: Source;
  search: boolean;
  onClose: () => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const schemas = useResource<ListResult<SourceSchema>>("/sources/schemas", {
    items: [],
    total: 0,
  });
  const [kind, setKind] = useState(
    source?.kind || (search ? "jobspy" : "auto"),
  );
  const editRevision = useRef(0);
  const [edited, setEdited] = useState(false);
  function markEdited() {
    editRevision.current += 1;
    setPreview(null);
    setEdited(true);
  }
  const [providers, setProviders] = useState<string[]>(
    (source?.config.providers as string[]) || [
      "linkedin",
      "indeed",
      "glassdoor",
    ],
  );
  const [preview, setPreview] = useState<Preview | null>(null),
    [previewing, setPreviewing] = useState(false);
  const searchSource = kind === "jobspy";
  const schema = schemas.data.items.find((s) => s.kind === kind);
  const resolvedSchema =
    schema || schemas.data.items.find((s) => s.kind === preview?.kind);
  const automaticCollection =
    resolvedSchema?.capabilities.automatic_collection !== false &&
    preview?.automatic_collection !== false;
  const properties =
    kind === "auto"
      ? sharedProperties(
          schemas.data.items,
          schemas.data.items
            .filter((item) => !item.capabilities.search)
            .map((item) => item.kind),
        )
      : schemaProperties(schema);
  const hasField = (key: string) => Object.hasOwn(properties, key);
  const defaults = (key: string, fallback: unknown) =>
    properties[key]?.default ?? fallback;
  const providerConfig = Object.fromEntries(
    Object.entries(source?.config || {}).filter(
      ([key]) => kind === "auto" || hasField(key),
    ),
  );
  function values(form: HTMLFormElement) {
    const f = new FormData(form),
      config = { ...(jsonValue(f, "config", providerConfig) as Json) };
    if (kind !== "auto")
      for (const key of Object.keys(config))
        if (!hasField(key)) delete config[key];
    if (searchSource)
      Object.assign(config, {
        query: String(f.get("query")),
        location: String(f.get("location") || ""),
        country: String(f.get("country")),
        providers: f.getAll("providers"),
        results_wanted: Number(f.get("results_wanted")),
        hours_old: Number(f.get("hours_old")),
        is_remote: f.get("is_remote") === "on",
        job_type: f.get("job_type") || null,
      });
    else {
      for (const key of ["board", "region"])
        if (hasField(key) && f.has(key) && f.get(key))
          config[key] = String(f.get(key));
      Object.assign(config, limitValues(f, properties));
      const candidates = f.get("max_candidates");
      if (
        hasField("max_candidates") &&
        typeof candidates === "string" &&
        candidates.trim()
      )
        config.max_candidates = Number(candidates);
    }
    return {
      name: String(f.get("name")),
      kind,
      url: searchSource ? "" : String(f.get("url") || ""),
      config,
      enabled: f.get("enabled") === "on",
      filters: {
        ...source?.filters,
        titles: terms(f.get("titles")),
        locations: terms(f.get("locations")),
      },
      schedule: scheduleValues(f),
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
        "Collection settings saved.",
      )
    )
      onClose();
  }
  async function inspect(form: HTMLFormElement | null) {
    if (!form || previewing || !form.reportValidity()) return;
    setPreviewing(true);
    const revision = editRevision.current;
    try {
      const { enabled, schedule, ...body } = values(form);
      const result = await api<Preview>("/sources/preview", "POST", body);
      if (editRevision.current === revision) {
        setPreview(result);
        notify("Preview complete. No jobs were saved.");
      } else
        notify(
          "Settings changed during the preview. Preview again to see current results.",
        );
    } catch (e) {
      notify(e instanceof Error ? e.message : "Preview failed.", true);
    } finally {
      setPreviewing(false);
    }
  }
  const filters = (key: string) =>
    ((source?.filters[key] as string[]) || []).join(", ");
  if (schemas.loading || (schemas.error && !schemas.data.items.length))
    return (
      <Dialog
        title={
          source
            ? `Configure ${source.name}`
            : search
              ? "Save a search"
              : "Follow a company"
        }
        onClose={onClose}
      >
        {schemas.loading ? (
          <Loading />
        ) : (
          <ErrorBox message={schemas.error!} retry={schemas.reload} />
        )}
      </Dialog>
    );
  return (
    <Dialog
      title={
        source
          ? `Configure ${source.name}`
          : search
            ? "Save a search"
            : "Follow a company"
      }
      onClose={onClose}
    >
      <form
        onSubmit={save}
        className="collection-form"
        onChange={markEdited}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("[data-dirty-control]"))
            markEdited();
        }}
      >
        <Section title="What to collect">
          <Field label={searchSource ? "Search name" : "Company / source name"}>
            <input
              name="name"
              required
              maxLength={200}
              defaultValue={source?.name}
              placeholder={searchSource ? "Backend roles" : "Company name"}
            />
          </Field>
          {searchSource ? (
            <>
              <Field
                label="Search query"
                hint="One query per saved search, sent to each selected portal."
              >
                <input
                  name="query"
                  required
                  maxLength={300}
                  defaultValue={String(source?.config.query || "")}
                  placeholder="backend engineer"
                />
              </Field>
              <div className="formgrid">
                <Field
                  label="Location"
                  hint="City, region or country used by the portal."
                >
                  <input
                    name="location"
                    defaultValue={String(source?.config.location || "")}
                    placeholder="Berlin, Germany"
                  />
                </Field>
                <Field
                  label="Country"
                  hint="Portal market: an English country name such as usa, uk or germany."
                >
                  <input
                    name="country"
                    required
                    defaultValue={String(
                      source?.config.country || defaults("country", "usa"),
                    )}
                  />
                </Field>
              </div>
              <fieldset className="provider-choices">
                <legend>JobSpy portals</legend>
                {[
                  ["linkedin", "LinkedIn"],
                  ["indeed", "Indeed"],
                  ["glassdoor", "Glassdoor"],
                ].map(([id, label]) => (
                  <label className="checkline" key={id}>
                    <input
                      name="providers"
                      type="checkbox"
                      value={id}
                      checked={providers.includes(id)}
                      required={providers.length === 0 && id === "linkedin"}
                      onChange={(e) =>
                        setProviders((current) =>
                          e.target.checked
                            ? [...current, id]
                            : current.filter((value) => value !== id),
                        )
                      }
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
            </>
          ) : (
            <>
              <Field
                label="Official career / board URL"
                hint="Use a supported ATS board or public RSS/Atom feed."
              >
                <input
                  name="url"
                  type="url"
                  required
                  defaultValue={source?.url || ""}
                  placeholder="https://jobs.lever.co/company"
                />
              </Field>
              <Field
                label="Board service"
                hint={
                  source
                    ? "The service is fixed. Add another source for a different service."
                    : "Detect the ATS from its public board URL."
                }
              >
                <select
                  value={kind}
                  disabled={!!source}
                  onChange={(e) => {
                    setKind(e.target.value);
                    setPreview(null);
                  }}
                >
                  <option value="auto">Detect from URL</option>
                  {schemas.data.items
                    .filter((item) => !item.capabilities.search)
                    .map((item) => (
                      <option key={item.kind} value={item.kind}>
                        {item.label}
                      </option>
                    ))}
                </select>
              </Field>
              {hasField("board") && (
                <Field
                  label="Board identifier"
                  hint="Usually detected from the URL. Keep the detected value when editing."
                >
                  <input
                    name="board"
                    key={kind}
                    defaultValue={String(source?.config.board || "")}
                  />
                </Field>
              )}
            </>
          )}
          <div className="formgrid">
            <Field
              label="Role filters"
              hint="Optional comma-separated terms; match any term."
            >
              <input
                name="titles"
                defaultValue={filters("titles")}
                placeholder="engineer, developer"
              />
            </Field>
            <Field
              label="Location filters"
              hint="Optional comma-separated locations; match any term."
            >
              <input
                name="locations"
                defaultValue={filters("locations")}
                placeholder="Germany, worldwide"
              />
            </Field>
          </div>
        </Section>
        <Section
          title="Acquisition"
          hint={
            searchSource
              ? "Limits apply to this query on each selected portal, including jobs already archived."
              : "Limits apply to one collection run. Large boards can require several batches."
          }
        >
          <div className="formgrid" key={kind}>
            {searchSource ? (
              <>
                <Field label="Results per portal" hint="1–50. Default: 20.">
                  <input
                    name="results_wanted"
                    type="number"
                    min={1}
                    max={50}
                    required
                    defaultValue={Number(
                      source?.config.results_wanted ||
                        defaults("results_wanted", 20),
                    )}
                  />
                </Field>
                <Field
                  label="Posted within (hours)"
                  hint="Age window requested from the portal. Default: 72 hours."
                >
                  <input
                    name="hours_old"
                    type="number"
                    min={1}
                    max={8760}
                    required
                    defaultValue={Number(
                      source?.config.hours_old || defaults("hours_old", 72),
                    )}
                  />
                </Field>
              </>
            ) : (
              <>
                {hasField("max_results") && (
                  <Field
                    label="Results per run"
                    hint="1–2,000. Default: 100 matching roles."
                  >
                    <input
                      name="max_results"
                      type="number"
                      min={1}
                      max={2000}
                      required
                      defaultValue={Number(
                        source?.config.max_results ||
                          defaults("max_results", 100),
                      )}
                    />
                  </Field>
                )}
              </>
            )}
          </div>
          {!automaticCollection && (
            <p className="source-error" role="alert">
              This service provides titles and links without posting text and
              cannot be used for automatic collection. Use a supported portal or
              add the full posting manually in Inbox.
            </p>
          )}
          {schema?.capabilities.description_mode === "inline" && (
            <p className="hint">
              Full descriptions are included in the listing; no separate
              description requests are needed.
            </p>
          )}
          {searchSource && (
            <>
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
                  ].map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
              <label className="checkline">
                <input
                  name="is_remote"
                  type="checkbox"
                  defaultChecked={!!source?.config.is_remote}
                />
                Remote roles only
              </label>
            </>
          )}
          <p className="hint">
            Full descriptions are retrieved automatically before jobs enter the
            archive. Result limits bound matches, including known jobs; they do
            not guarantee complete coverage. A portal may require a pause before
            collection can continue.
          </p>
        </Section>
        <Section title="Schedule">
          <ScheduleFields schedule={source?.schedule} />
          <label className="checkline">
            <input
              name="enabled"
              type="checkbox"
              defaultChecked={!!source?.enabled}
              disabled={!automaticCollection}
            />
            Enable automatic collection
          </label>
          <p className="hint">
            New sources start paused. Run once also works while a source is
            paused.
          </p>
        </Section>
        <details className="collection-advanced">
          <summary>Advanced configuration</summary>
          {hasField("region") && (
            <Field
              label="ATS region"
              hint="Usually global. Some services use a regional board endpoint."
            >
              <select
                name="region"
                key={kind}
                defaultValue={String(
                  source?.config.region ?? defaults("region", "global"),
                )}
              >
                <option value="global">Global</option>
                <option value="eu">Europe</option>
              </select>
            </Field>
          )}
          {hasField("max_candidates") && (
            <Field
              label="Candidates to inspect"
              hint="20–10,000 listing candidates before local filters. Default: 2,000; paging resumes across batches."
            >
              <input
                name="max_candidates"
                key={kind}
                type="number"
                min={20}
                max={10000}
                required
                defaultValue={Number(
                  source?.config.max_candidates ??
                    defaults("max_candidates", 2000),
                )}
              />
            </Field>
          )}
          <AdvancedJson
            name="config"
            label="Provider configuration"
            value={providerConfig}
          />
        </details>
        {preview && (
          <section className="preview-result" aria-live="polite">
            <h3>Preview · {preview.total} matches</h3>
            {preview.request_estimate && (
              <p className="smalltext">
                Up to 3 results per portal · about{" "}
                {preview.request_estimate.total} requests for this preview.
              </p>
            )}
            {preview.full_request_estimate && (
              <p className="smalltext">
                Configured run: about {preview.full_request_estimate.total}{" "}
                requests before cache reuse.
              </p>
            )}
            {preview.diagnostics?.map((d, i) => (
              <p
                className={d.state === "error" ? "source-error" : "smalltext"}
                key={i}
              >
                <b>{d.provider}</b> · {d.state} ·{" "}
                {d.message || `${d.requests || 0} requests`}
                {d.next_run_at ? ` · ${formatTime(d.next_run_at)}` : ""}
              </p>
            ))}
            <div className="source-preview">
              {preview.items.slice(0, 6).map((j, i) => (
                <article key={i}>
                  <strong>{j.title}</strong>
                  <small>
                    {[j.company, j.location].filter(Boolean).join(" · ")}
                  </small>
                </article>
              ))}
            </div>
          </section>
        )}
        <div className="actions form-actions">
          <span className="collection-save-hint" role="status">
            {edited
              ? "Unsaved changes"
              : source
                ? "Saved settings"
                : "New source"}
          </span>
          <Button type="button" onClick={onClose}>
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
          <Button
            variant="primary"
            disabled={pending || previewing || !automaticCollection}
          >
            Save {searchSource ? "search" : "source"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function RunOptionsDialog({
  sources,
  onClose,
  onRun,
}: {
  sources: Source[];
  onClose: () => void;
  onRun: (overrides: Json) => Promise<boolean>;
}) {
  const { pending } = useWorkspace();
  const schemas = useResource<ListResult<SourceSchema>>("/sources/schemas", {
    items: [],
    total: 0,
  });
  const properties = sharedProperties(
    schemas.data.items,
    sources.map((source) => source.kind),
  );
  return (
    <Dialog
      title={`Run ${sources.length === 1 ? sources[0].name : `${sources.length} sources`} with options`}
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (schemas.loading || schemas.error) return;
          const overrides = limitValues(
            new FormData(e.currentTarget),
            properties,
          );
          if (await onRun(overrides)) onClose();
        }}
      >
        <p className="modal-intro">
          These options apply to this run only. Saved settings stay the same.
        </p>
        {schemas.loading ? (
          <Loading />
        ) : schemas.error ? (
          <ErrorBox message={schemas.error} retry={schemas.reload} />
        ) : (
          <>
            <SharedAcquisitionLimits
              properties={properties}
              placeholder="Saved setting"
            />
            <p className="hint">
              Empty fields use each source's saved settings. Only limits
              supported by every selected source are shown.
            </p>
          </>
        )}
        <p className="hint">
          Provider request spacing and cooldowns still apply. An incompatible
          active run must finish or be stopped first.
        </p>
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={pending || schemas.loading || !!schemas.error}
          >
            Run with options
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function SourceBulkEditor({
  sources,
  onClose,
  onSave,
}: {
  sources: Source[];
  onClose: () => void;
  onSave: (patch: Json) => Promise<boolean>;
}) {
  const { pending } = useWorkspace();
  const [schedule, setSchedule] = useState(false),
    [acquisition, setAcquisition] = useState(false),
    [filters, setFilters] = useState(false);
  const schemas = useResource<ListResult<SourceSchema>>("/sources/schemas", {
    items: [],
    total: 0,
  });
  const properties = sharedProperties(
    schemas.data.items,
    sources.map((source) => source.kind),
  );
  return (
    <Dialog title={`Configure ${sources.length} sources`} onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget),
            patch: Json = {};
          if (schedule) patch.schedule = scheduleValues(f);
          if (acquisition) {
            if (schemas.loading || schemas.error) return;
            const config = limitValues(f, properties);
            if (Object.keys(config).length) patch.config = config;
          }
          if (filters)
            patch.filters = {
              titles: terms(f.get("titles")),
              locations: terms(f.get("locations")),
            };
          if (await onSave(patch)) onClose();
        }}
      >
        <p className="modal-intro">
          Choose the fields to change. All other settings are preserved.
        </p>
        <Section title="Schedule">
          <label className="checkline">
            <input
              type="checkbox"
              checked={schedule}
              onChange={(e) => setSchedule(e.target.checked)}
            />
            Replace schedule
          </label>
          {schedule && <ScheduleFields schedule={sources[0].schedule} />}
        </Section>
        <Section title="Acquisition">
          <label className="checkline">
            <input
              type="checkbox"
              checked={acquisition}
              onChange={(e) => setAcquisition(e.target.checked)}
            />
            Change acquisition limits
          </label>
          {acquisition && (
            <>
              {schemas.loading ? (
                <Loading />
              ) : schemas.error ? (
                <ErrorBox message={schemas.error} retry={schemas.reload} />
              ) : (
                <SharedAcquisitionLimits
                  properties={properties}
                  placeholder="Keep current"
                />
              )}
              <p className="hint">
                Empty fields keep each source's current value. Only limits
                supported by every selected source are shown.
              </p>
            </>
          )}
        </Section>
        <Section title="Filters">
          <label className="checkline">
            <input
              type="checkbox"
              checked={filters}
              onChange={(e) => setFilters(e.target.checked)}
            />
            Replace role and location filters
          </label>
          {filters && (
            <div className="formgrid">
              <Field
                label="Role filters"
                hint="Comma-separated; leave empty to clear."
              >
                <input name="titles" />
              </Field>
              <Field
                label="Location filters"
                hint="Comma-separated; leave empty to clear."
              >
                <input name="locations" />
              </Field>
            </div>
          )}
        </Section>
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={
              pending ||
              (!schedule && !acquisition && !filters) ||
              (acquisition && (schemas.loading || !!schemas.error))
            }
          >
            Save changes
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
