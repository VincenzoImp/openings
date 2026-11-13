// What the Collection screen derives from sources, runs and tasks. Pure
// functions without React, so they can be tested on their own.
import type { BackgroundTask, CollectionRun, Json, Source } from "../../api";

export interface ConfigProperty {
  default?: unknown;
  minimum?: number;
  maximum?: number;
}
export type ConfigProperties = Record<string, ConfigProperty>;
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
export interface Preview {
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

/** A saved search asks job boards a query; every other kind follows one company board. */
export const isSearch = (source: { kind: string }) => source.kind === "jobspy";

export const PORTALS: [string, string][] = [
  ["linkedin", "LinkedIn"],
  ["indeed", "Indeed"],
  ["glassdoor", "Glassdoor"],
];
/** The portals that search one country's site, and so need a country. */
export const NATIONAL = ["indeed", "glassdoor"];
const portalName = (id: string) =>
  PORTALS.find(([key]) => key === id)?.[1] || id;

/** The providers a source asks: the portals of a search, the board of a company. */
export function providersOf(source: Source) {
  if (isSearch(source))
    return ((source.config.providers as string[]) || []).map(portalName);
  const kind = String(source.kind);
  return [kind === "rss" ? "RSS feed" : kind[0].toUpperCase() + kind.slice(1)];
}

/** What a source collects, in one line. */
export function sourceLine(source: Source) {
  if (isSearch(source)) {
    const where = String(
      source.config.location || source.config.country || "All locations",
    );
    const query = String(source.config.query || "").trim();
    return ["Search", query && `"${query}"`, where].filter(Boolean).join(" · ");
  }
  return `Company board · ${String(source.url || source.config.board || source.kind)}`;
}

export function scheduleLabel(schedule: Json) {
  if (schedule.kind === "daily")
    return `Daily ${((schedule.times as string[]) || []).join(", ")} · ${String(schedule.timezone || "UTC")}`;
  const minutes = Number(schedule.minutes || 1440);
  if (minutes === 1440) return "Once a day";
  return minutes % 60 ? `Every ${minutes} min` : `Every ${minutes / 60} h`;
}

/** A length in seconds as a person says it: "45s", "2m 5s", "1h 3m". */
export function seconds(value?: number) {
  if (value == null) return "—";
  if (value < 60) return `${Math.round(value)}s`;
  const hours = Math.floor(value / 3600),
    minutes = Math.floor((value % 3600) / 60);
  return hours
    ? `${hours}h ${minutes}m`
    : `${minutes}m ${Math.round(value % 60)}s`;
}

export const active = (state?: string) =>
  state === "queued" || state === "running";

const waitingNow = (item: { state: string; next_run_at?: string }) =>
  item.state === "queued" &&
  !!item.next_run_at &&
  new Date(item.next_run_at).valueOf() > Date.now();

type Tone = "ready" | "attention" | "danger" | "info" | "neutral";
/** The state of a collection run or task as a tag: words and a tone. */
export function stateTag(item: CollectionRun | BackgroundTask): {
  text: string;
  tone: Tone;
} {
  if (waitingNow(item)) {
    const reason =
      "task_ids" in item
        ? item.tasks?.find((task) => task.state === "queued" && task.error)
            ?.error
        : (item as BackgroundTask).error;
    return {
      text:
        reason && /collection batch/i.test(reason)
          ? "Continuing collection"
          : "Waiting",
      tone: "info",
    };
  }
  switch (item.state) {
    case "queued":
      return { text: "Queued", tone: "info" };
    case "running":
      return { text: "In progress", tone: "info" };
    case "succeeded":
      return { text: "Finished", tone: "ready" };
    case "failed":
      return { text: "Failed", tone: "danger" };
    case "cancelled":
      return { text: "Stopped", tone: "neutral" };
    default:
      return { text: item.state, tone: "neutral" };
  }
}

/** Why a waiting run or task waits, when it says so. */
export function waitReason(run: CollectionRun) {
  if (!waitingNow(run)) return "";
  return (
    run.tasks?.find((task) => task.state === "queued" && task.error)?.error ||
    ""
  );
}

export const COUNTS: [string, string][] = [
  ["received", "Processed"],
  ["created", "New"],
  ["existing", "Already archived"],
  ["invalid", "Invalid"],
  ["pending_descriptions", "Waiting for text"],
  ["unavailable_descriptions", "Text unavailable"],
];

/** The counts of a run or task that say something, as "3 new · 40 already archived". */
export function countsLine(counts: Json | undefined, state = "") {
  const values = counts || {};
  const parts = COUNTS.filter(
    ([key]) => typeof values[key] === "number" && (values[key] as number) > 0,
  ).map(([key, label]) => `${values[key]} ${label.toLowerCase()}`);
  return (
    parts.join(" · ") || (active(state) ? "Nothing found yet" : "Nothing found")
  );
}

/** The properties of a source kind's configuration schema. */
export function schemaProperties(schema?: SourceSchema): ConfigProperties {
  return (schema?.config_schema.properties as ConfigProperties) || {};
}

/** The properties every one of these kinds has, with the narrowest limits. */
export function sharedProperties(
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

export const LIMITS = [
  { key: "hours_old", label: "Posted within (hours)" },
  { key: "results_wanted", label: "Results per portal" },
  { key: "max_results", label: "Results per run" },
];

/** The acquisition limits filled in a form, for the properties the sources share. */
export function limitValues(form: FormData, properties: ConfigProperties) {
  const values: Json = {};
  for (const { key } of LIMITS) {
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

/** Comma-separated terms as a list, without empty ones. */
export function terms(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function scheduleValues(form: FormData) {
  return form.get("schedule_kind") === "daily"
    ? {
        kind: "daily" as const,
        times: form.getAll("daily_times").map(String),
        timezone: String(form.get("timezone") || "UTC"),
      }
    : { kind: "interval" as const, minutes: Number(form.get("minutes")) };
}

/** The next free whole hour after the last daily time, for "Add a time". */
export function nextTime(times: string[]) {
  const last = Number(times[times.length - 1]?.slice(0, 2) || 7);
  for (let step = 1; step <= 24; step++) {
    const value = `${String((last + step) % 24).padStart(2, "0")}:00`;
    if (!times.includes(value)) return value;
  }
  return "12:00";
}

// Configuration keys the source form edits with its own controls; the rest
// of a source's configuration is edited as rows.
export const OWN_FIELDS = [
  "query",
  "location",
  "country",
  "providers",
  "results_wanted",
  "hours_old",
  "is_remote",
  "job_type",
  "board",
  "region",
  "max_results",
  "max_candidates",
];
