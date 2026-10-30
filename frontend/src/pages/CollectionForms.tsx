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
import { confirmLeave, useResource, useWorkspace } from "../state";
import { AdvancedJson, Button, Dialog, Field } from "../ui";

const boardKinds = [
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
];
interface SourceSchema {
  kind: string;
  label: string;
  config_schema: Json;
  capabilities: { search: boolean; lookback: boolean; details: boolean };
}
interface Preview {
  kind: string;
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
      new Date(run.next_run_at).valueOf() > Date.now();
  return (
    <div className={`run-progress ${compact ? "compact" : ""}`}>
      <div className="run-state">
        <span
          className={`tag ${run.state === "failed" ? "amber" : run.state === "succeeded" ? "green" : "neutral"}`}
        >
          {waiting ? "Waiting" : run.state}
        </span>
        <span className="smalltext muted">
          {waiting
            ? `Resumes ${formatTime(run.next_run_at)}`
            : run.started_at
              ? `Started ${formatTime(run.started_at)}`
              : "Ready to start"}
        </span>
      </div>
      {waiting &&
        run.tasks?.find((task) => task.state === "queued" && task.error)
          ?.error && (
          <p className="hint run-wait-reason">
            {
              run.tasks.find((task) => task.state === "queued" && task.error)!
                .error
            }
          </p>
        )}
      <dl className="run-counts">
        {[
          ["received", "Found"],
          ["created", "New"],
          ["existing", "Already archived"],
          ["invalid", "Invalid"],
          ["pending_descriptions", "Pending text"],
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
  const [providers, setProviders] = useState<string[]>(
    (source?.config.providers as string[]) || [
      "linkedin",
      "indeed",
      "glassdoor",
    ],
  );
  const [preview, setPreview] = useState<Preview | null>(null),
    [previewing, setPreviewing] = useState(false);
  const searchSource = kind === "jobspy",
    board = kind !== "auto" && !searchSource && kind !== "rss";
  const schema = schemas.data.items.find((s) => s.kind === kind);
  const defaults = (key: string, fallback: unknown) =>
    (schema?.config_schema.properties as Record<string, Json> | undefined)?.[
      key
    ]?.default ?? fallback;
  function values(form: HTMLFormElement) {
    const f = new FormData(form),
      config = jsonValue(f, "config", source?.config || {}) as Json;
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
        fetch_description: f.get("fetch_description") === "on",
      });
    else {
      if (board && f.get("board")) config.board = String(f.get("board"));
      if (board) {
        config.region = String(
          f.get("region") || source?.config.region || "global",
        );
        config.max_details = Number(f.get("max_details"));
        if (f.has("max_candidates"))
          config.max_candidates = Number(f.get("max_candidates"));
      }
      config.max_results = Number(f.get("max_results") || 100);
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
        onChange={() => {
          editRevision.current += 1;
          setPreview(null);
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
                  {boardKinds.map((value) => (
                    <option key={value} value={value}>
                      {value === "rss" ? "RSS / Atom" : value}
                    </option>
                  ))}
                </select>
              </Field>
              {board && (
                <Field
                  label="Board identifier"
                  hint="Usually detected from the URL. Keep the detected value when editing."
                >
                  <input
                    name="board"
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
          <div className="formgrid">
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
                {board && (
                  <Field
                    label="Description requests per batch"
                    hint="0–25. Default: 10; unfinished descriptions continue in later batches."
                  >
                    <input
                      name="max_details"
                      type="number"
                      min={0}
                      max={25}
                      required
                      defaultValue={Number(
                        source?.config.max_details ??
                          defaults("max_details", 10),
                      )}
                    />
                  </Field>
                )}
              </>
            )}
          </div>
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
              <label className="checkline">
                <input
                  name="fetch_description"
                  type="checkbox"
                  defaultChecked={source?.config.fetch_description !== false}
                />
                Fetch full descriptions
              </label>
            </>
          )}
          <p className="hint">
            Result limits do not guarantee full coverage of the age window.
            Shared request budgets can delay a run.
          </p>
        </Section>
        <Section title="Schedule">
          <ScheduleFields schedule={source?.schedule} />
          <label className="checkline">
            <input
              name="enabled"
              type="checkbox"
              defaultChecked={!!source?.enabled}
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
          {kind === "lever" && (
            <Field
              label="ATS region"
              hint="Usually global. Some services use a regional board endpoint."
            >
              <select
                name="region"
                defaultValue={String(source?.config.region || "global")}
              >
                <option value="global">Global</option>
                <option value="eu">Europe</option>
              </select>
            </Field>
          )}
          {["workday", "oracle", "smartrecruiters"].includes(kind) && (
            <Field
              label="Candidates to inspect"
              hint="20–10,000 listing candidates before local filters. Default: 2,000; paging resumes across batches."
            >
              <input
                name="max_candidates"
                type="number"
                min={20}
                max={10000}
                required
                defaultValue={Number(
                  source?.config.max_candidates ||
                    defaults("max_candidates", 2000),
                )}
              />
            </Field>
          )}
          <AdvancedJson
            name="config"
            label="Provider configuration"
            value={source?.config || {}}
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
  const searches = sources.every((s) => s.kind === "jobspy"),
    companies = sources.every((s) => s.kind !== "jobspy");
  return (
    <Dialog
      title={`Run ${sources.length === 1 ? sources[0].name : `${sources.length} sources`} with options`}
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget),
            overrides: Json = {};
          for (const key of [
            "hours_old",
            "results_wanted",
            "max_results",
            "max_details",
          ])
            if (String(f.get(key) || "").trim())
              overrides[key] = Number(f.get(key));
          if (await onRun(overrides)) onClose();
        }}
      >
        <p className="modal-intro">
          These options apply to this run only. Saved settings stay the same.
        </p>
        {searches ? (
          <div className="formgrid">
            <Field
              label="Posted within (hours)"
              hint="Leave empty to use each saved window."
            >
              <input
                name="hours_old"
                type="number"
                min={1}
                max={8760}
                placeholder="Saved setting"
              />
            </Field>
            <Field
              label="Results per portal"
              hint="Includes jobs already archived."
            >
              <input
                name="results_wanted"
                type="number"
                min={1}
                max={50}
                placeholder="Saved setting"
              />
            </Field>
          </div>
        ) : companies ? (
          <div className="formgrid">
            <Field label="Results per run">
              <input
                name="max_results"
                type="number"
                min={1}
                max={2000}
                placeholder="Saved setting"
              />
            </Field>
            {sources.every((s) => s.kind !== "rss") && (
              <Field label="Description requests per batch">
                <input
                  name="max_details"
                  type="number"
                  min={0}
                  max={25}
                  placeholder="Saved setting"
                />
              </Field>
            )}
          </div>
        ) : (
          <p className="hint">
            Select only saved searches or only company sources to change run
            limits.
          </p>
        )}
        <p className="hint">
          Provider limits and cooldowns still apply. An incompatible active run
          must finish or be stopped first.
        </p>
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
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
  const searches = sources.every((s) => s.kind === "jobspy"),
    companies = sources.every((s) => s.kind !== "jobspy");
  return (
    <Dialog title={`Configure ${sources.length} sources`} onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget),
            patch: Json = {};
          if (schedule) patch.schedule = scheduleValues(f);
          if (acquisition) {
            const config: Json = {};
            for (const key of [
              "hours_old",
              "results_wanted",
              "max_results",
              "max_details",
            ])
              if (String(f.get(key) || "").trim())
                config[key] = Number(f.get(key));
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
              {searches ? (
                <div className="formgrid">
                  <Field label="Posted within (hours)">
                    <input
                      name="hours_old"
                      type="number"
                      min={1}
                      max={8760}
                      placeholder="Keep current"
                    />
                  </Field>
                  <Field label="Results per portal">
                    <input
                      name="results_wanted"
                      type="number"
                      min={1}
                      max={50}
                      placeholder="Keep current"
                    />
                  </Field>
                </div>
              ) : companies ? (
                <div className="formgrid">
                  <Field label="Results per run">
                    <input
                      name="max_results"
                      type="number"
                      min={1}
                      max={2000}
                      placeholder="Keep current"
                    />
                  </Field>
                  {sources.every((s) => s.kind !== "rss") && (
                    <Field label="Description requests per batch">
                      <input
                        name="max_details"
                        type="number"
                        min={0}
                        max={25}
                        placeholder="Keep current"
                      />
                    </Field>
                  )}
                </div>
              ) : (
                <p className="hint">
                  Select only saved searches or only company sources to share
                  acquisition limits.
                </p>
              )}
              <p className="hint">
                Empty fields keep each source's current value.
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
            disabled={pending || (!schedule && !acquisition && !filters)}
          >
            Save changes
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
