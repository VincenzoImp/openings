import { useMemo, useRef, useState, type FormEvent } from "react";
import { CircleAlert, FlaskConical } from "lucide-react";
import { ApiError, type Schema } from "../../api/client";
import { ConflictNotice } from "../../query/ConflictNotice";
import { queryClient } from "../../query/query";
import { Button } from "../../ui/Button";
import { ConfirmDialog, Drawer } from "../../ui/Dialog";
import { Checkbox, Field, Input, Select } from "../../ui/Field";
import { Callout } from "../../ui/Page";
import { Segmented } from "../../ui/Tabs";
import { useToast } from "../../ui/Toast";
import {
  KIND_LABELS,
  NATIONAL_SITES,
  POSTED_WITHIN,
  SITES,
  capitalize,
  detectBoard,
  kindOf,
  shortUrl,
  suggestedName,
  terms,
  type SourceKind,
  type SourceView,
} from "./model";
import {
  sourceKeys,
  useCreateSource,
  usePreview,
  useUpdateSource,
} from "./queries";

interface Draft {
  kind: SourceKind;
  name: string;
  query: string;
  location: string;
  country: string;
  sites: string[];
  hours: number;
  include: string;
  exclude: string;
  url: string;
}

const text = (value: unknown) => (typeof value === "string" ? value : "");
const words = (value: unknown) =>
  Array.isArray(value) ? value.filter(Boolean).join(", ") : "";

function draftOf(
  source: SourceView | undefined,
  kind: SourceKind,
  country: string,
): Draft {
  const config = source?.config ?? {};
  return {
    kind: source ? kindOf(source) : kind,
    name: source?.name ?? "",
    query: text(config.query),
    location: text(config.location),
    country: source ? text(config.country) : country,
    sites: Array.isArray(config.providers)
      ? (config.providers as string[])
      : ["linkedin", "indeed"],
    hours: Number(config.hours_old) || 72,
    include: words(source?.filters.titles),
    exclude: words(source?.filters.exclude_titles),
    url: source?.url || text(config.url),
  };
}

const httpUrl = (value: string) => /^https?:\/\/\S+\.\S+/.test(value.trim());

/** What is wrong with a draft, by field; empty when it can be sent. */
function problems(draft: Draft, board: boolean) {
  const found: Partial<Record<keyof Draft, string>> = {};
  if (draft.kind === "search") {
    if (!draft.query.trim())
      found.query = "Add the words to search for, such as data engineer.";
    if (!draft.sites.length) found.sites = "Choose at least one job site.";
    if (
      draft.sites.some((site) => NATIONAL_SITES.includes(site)) &&
      !draft.country.trim()
    )
      found.country =
        "Indeed and Glassdoor search one country's site. Add a country, such as switzerland.";
  } else if (!(board && !draft.url.trim()) && !httpUrl(draft.url))
    found.url =
      draft.kind === "feed"
        ? "Paste the feed's address, starting with https://."
        : "Paste the careers page's address, starting with https://.";
  return found;
}

type Preview = Schema<"SourcePreviewResult"> & {
  kind?: string;
  automatic_collection?: boolean;
};

/**
 * Add a source or change one, in a drawer (full screen on a phone): the
 * kind first, then a typed form. Test asks the sites once through the shared
 * request gate and shows the first ten results; nothing is saved until Save.
 */
export function SourceEditor({
  open,
  onClose,
  source,
  template,
  initialKind = "search",
  country = "",
  interval,
  labels = {},
}: {
  open: boolean;
  onClose: () => void;
  /** The source to change; without it a new one is added. */
  source?: SourceView;
  /** A source to copy into a new one (Duplicate). */
  template?: SourceView;
  initialKind?: SourceKind;
  /** The country to prefill in a new search. */
  country?: string;
  /** The interval, in minutes, a new source is checked at. */
  interval?: number | null;
  labels?: Record<string, string>;
}) {
  return (
    <Editor
      open={open}
      onClose={onClose}
      source={source}
      template={template}
      initialKind={initialKind}
      country={country}
      interval={interval}
      labels={labels}
    />
  );
}

/** The form; the caller gives it a new key each time it opens. */
function Editor({
  open,
  onClose,
  source,
  template,
  initialKind,
  country,
  interval,
  labels,
}: {
  open: boolean;
  onClose: () => void;
  source?: SourceView;
  template?: SourceView;
  initialKind: SourceKind;
  country: string;
  interval?: number | null;
  labels: Record<string, string>;
}) {
  const toast = useToast();
  const initial = useMemo(() => {
    const draft = draftOf(source ?? template, initialKind, country);
    return template ? { ...draft, name: `${template.name} copy` } : draft;
  }, [source, template, initialKind, country]);
  const [draft, setDraft] = useState<Draft>(initial);
  const [base, setBase] = useState(source?.version ?? 0);
  const [submitted, setSubmitted] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const asked = useRef(0);
  const board = !!source && !source.url && !!source.config.board;

  const latest = () =>
    (
      queryClient.getQueryData(sourceKeys.list) as SourceView[] | undefined
    )?.find((item) => item.id === source?.id);
  const create = useCreateSource();
  const update = useUpdateSource(() => {
    const stored = latest();
    if (!stored) return;
    setDraft(draftOf(stored, initialKind, country));
    setBase(stored.version);
  });
  const test = usePreview();
  const saving = create.isPending || update.isPending;

  const changes = (Object.keys(draft) as (keyof Draft)[]).filter(
    (key) => JSON.stringify(draft[key]) !== JSON.stringify(initial[key]),
  ).length;
  const errors = submitted ? problems(draft, board) : {};
  const detected = draft.kind === "company" ? detectBoard(draft.url) : null;

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    // A result describes the settings it was asked with.
    asked.current += 1;
    setPreview(null);
    setPreviewError("");
  }

  function body() {
    const kept = source?.config ?? template?.config ?? {};
    const filters = {
      ...(source?.filters ?? template?.filters ?? {}),
      titles: terms(draft.include),
      exclude_titles: terms(draft.exclude),
    };
    if (draft.kind === "search") {
      const config: Record<string, unknown> = {
        ...kept,
        query: draft.query.trim(),
        location: draft.location.trim(),
        providers: draft.sites,
        hours_old: draft.hours,
      };
      if (draft.country.trim()) config.country = draft.country.trim();
      else delete config.country;
      return { kind: "jobspy" as const, url: "", config, filters };
    }
    const url = draft.url.trim();
    const sameAddress = source && url === (source.url || text(kept.url));
    if (draft.kind === "feed")
      return { kind: "rss" as const, url, config: { url }, filters };
    return {
      kind: (sameAddress
        ? source.kind
        : "auto") as Schema<"SourceCreate">["kind"],
      url,
      config: sameAddress ? kept : {},
      filters,
    };
  }

  const name = () =>
    draft.name.trim() ||
    suggestedName(draft.kind, draft) ||
    (detected ? capitalize(detected.board) : "") ||
    "New source";

  async function runTest() {
    setSubmitted(true);
    if (Object.keys(problems(draft, board)).length) return;
    const question = ++asked.current;
    setPreview(null);
    setPreviewError("");
    try {
      const result = (await test.mutateAsync({
        ...body(),
        name: name(),
      })) as Preview;
      if (asked.current === question) setPreview(result);
    } catch (error) {
      if (asked.current === question)
        setPreviewError(
          error instanceof Error ? error.message : "The test failed.",
        );
    }
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setSubmitted(true);
    if (Object.keys(problems(draft, board)).length) {
      // Focus moves to the first field that needs a change.
      requestAnimationFrame(() =>
        document
          .querySelector<HTMLElement>(".src-editor [aria-invalid='true']")
          ?.focus(),
      );
      return;
    }
    try {
      if (source) {
        await update.mutateAsync({
          id: source.id,
          expected_version: base,
          name: name(),
          ...body(),
        });
        toast.show({ message: `Saved “${name()}”`, tone: "success" });
      } else {
        await create.mutateAsync({
          ...body(),
          name: name(),
          enabled: true,
          schedule: interval
            ? { kind: "interval", minutes: interval }
            : undefined,
        });
        toast.show({
          message: `Added “${name()}”. Its first check runs soon.`,
          tone: "success",
        });
      }
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) return;
      toast.show({
        message: error instanceof Error ? error.message : "Not saved.",
        tone: "error",
      });
    }
  }

  const close = () => (changes && !saving ? setLeaving(true) : onClose());
  const title = source
    ? `Edit ${source.name}`
    : template
      ? "Duplicate source"
      : "Add a source";
  const kindLocked = !!source;

  return (
    <>
      <Drawer
        open={open}
        onClose={close}
        title={title}
        className="src-editor"
        initialFocus="[data-autofocus]"
        footer={
          <>
            <Button
              icon={FlaskConical}
              onClick={runTest}
              disabled={test.isPending || saving}
            >
              {test.isPending ? "Testing…" : "Test"}
            </Button>
            <span className="src-editor-spacer" />
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              form="source-editor-form"
              disabled={saving}
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <form
          id="source-editor-form"
          className="src-form"
          noValidate
          onSubmit={save}
        >
          {update.conflict && (
            <ConflictNotice
              onReload={() => void update.reload()}
              onKeepEditing={async () => {
                await update.keepEditing();
                const stored = latest();
                if (stored) setBase(stored.version);
              }}
            />
          )}
          {kindLocked ? (
            <p className="src-form-kind">{KIND_LABELS[draft.kind]}</p>
          ) : (
            <Field label="Kind">
              <Segmented<SourceKind>
                label="Kind of source"
                value={draft.kind}
                onChange={(kind) => set("kind", kind)}
                options={(Object.keys(KIND_LABELS) as SourceKind[]).map(
                  (kind) => ({ value: kind, label: KIND_LABELS[kind] }),
                )}
                className="src-kind"
              />
            </Field>
          )}
          {draft.kind === "search" ? (
            <SearchFields draft={draft} set={set} errors={errors} />
          ) : (
            <Field
              label={
                draft.kind === "feed" ? "Feed address" : "Careers page address"
              }
              error={errors.url}
              hint={
                draft.kind === "feed"
                  ? "A public RSS or Atom feed of job postings."
                  : board && !draft.url.trim()
                    ? `Follows the ${labels[source!.kind] ?? capitalize(source!.kind)} board “${text(source!.config.board)}”.`
                    : detected
                      ? `Detected: ${labels[detected.kind] ?? capitalize(detected.kind)}${detected.board ? ` · ${detected.board}` : ""}`
                      : httpUrl(draft.url)
                        ? "Openings looks for a supported job board on this page when you test or save."
                        : "Greenhouse, Lever, Ashby, Workable, Personio and other job boards are detected from the address."
              }
            >
              <Input
                type="url"
                inputMode="url"
                data-autofocus=""
                autoComplete="off"
                value={draft.url}
                placeholder={
                  draft.kind === "feed"
                    ? "https://example.test/jobs.rss"
                    : "https://boards.greenhouse.io/example"
                }
                onChange={(event) => set("url", event.target.value)}
              />
            </Field>
          )}
          <Field
            label="Name"
            optional
            hint="How the source is listed. Left empty, it is named after what it searches."
          >
            <Input
              value={draft.name}
              maxLength={200}
              placeholder={
                suggestedName(draft.kind, draft) ||
                (draft.kind === "search" ? "Data engineer · Zurich" : "")
              }
              onChange={(event) => set("name", event.target.value)}
            />
          </Field>
          <div className="src-form-pair">
            <Field
              label="Title must include"
              optional
              hint="Words separated by commas; any one is enough."
            >
              <Input
                value={draft.include}
                placeholder="engineer, developer"
                onChange={(event) => set("include", event.target.value)}
              />
            </Field>
            <Field
              label="Title must not include"
              optional
              hint="A title with any of these words is skipped."
            >
              <Input
                value={draft.exclude}
                placeholder="intern, working student"
                onChange={(event) => set("exclude", event.target.value)}
              />
            </Field>
          </div>
          {(preview || previewError || test.isPending) && (
            <TestResults
              preview={preview}
              error={previewError}
              pending={test.isPending}
              labels={labels}
            />
          )}
        </form>
      </Drawer>
      <ConfirmDialog
        open={leaving}
        title="Discard unsaved changes?"
        confirm="Discard"
        cancel="Keep editing"
        onClose={() => setLeaving(false)}
        onConfirm={onClose}
      >
        {changes === 1
          ? "You have 1 unsaved change. Discarding it cannot be undone."
          : `You have ${changes} unsaved changes. Discarding them cannot be undone.`}
      </ConfirmDialog>
    </>
  );
}

function SearchFields({
  draft,
  set,
  errors,
}: {
  draft: Draft;
  set: <K extends keyof Draft>(key: K, value: Draft[K]) => void;
  errors: Partial<Record<keyof Draft, string>>;
}) {
  const national = draft.sites.some((site) => NATIONAL_SITES.includes(site));
  return (
    <>
      <Field label="Keywords" error={errors.query} required>
        <Input
          value={draft.query}
          maxLength={300}
          placeholder="data engineer"
          data-autofocus=""
          onChange={(event) => set("query", event.target.value)}
        />
      </Field>
      <div className="src-form-pair">
        <Field label="Location" optional hint="A city, region or country.">
          <Input
            value={draft.location}
            maxLength={300}
            placeholder="Zurich"
            onChange={(event) => set("location", event.target.value)}
          />
        </Field>
        <Field
          label="Country"
          optional={!national}
          error={errors.country}
          hint={
            national
              ? "Indeed and Glassdoor search this country's site."
              : "Only Indeed and Glassdoor use it."
          }
        >
          <Input
            value={draft.country}
            maxLength={100}
            placeholder="switzerland"
            onChange={(event) => set("country", event.target.value)}
          />
        </Field>
      </div>
      <fieldset className="src-sites" aria-describedby="src-sites-note">
        <legend className="ui-field-label">Job sites</legend>
        <div className="src-sites-options">
          {SITES.map(([id, label]) => (
            <Checkbox
              key={id}
              label={label}
              checked={draft.sites.includes(id)}
              onChange={(event) =>
                set(
                  "sites",
                  event.target.checked
                    ? [...draft.sites, id]
                    : draft.sites.filter((site) => site !== id),
                )
              }
            />
          ))}
        </div>
        {errors.sites ? (
          <p className="ui-field-error" id="src-sites-note">
            {errors.sites}
          </p>
        ) : (
          <p className="ui-field-hint" id="src-sites-note">
            Each site is asked through the shared request limits.
          </p>
        )}
      </fieldset>
      <Field label="Posted within">
        <Select
          value={draft.hours}
          onChange={(event) => set("hours", Number(event.target.value))}
        >
          {(POSTED_WITHIN.some(([hours]) => hours === draft.hours)
            ? POSTED_WITHIN
            : [...POSTED_WITHIN, [draft.hours, `${draft.hours} hours`] as const]
          ).map(([hours, label]) => (
            <option key={hours} value={hours}>
              {label}
            </option>
          ))}
        </Select>
      </Field>
    </>
  );
}

/** The first ten results of a Test, and what each site answered. */
function TestResults({
  preview,
  error,
  pending,
  labels,
}: {
  preview: Preview | null;
  error: string;
  pending: boolean;
  labels: Record<string, string>;
}) {
  const items = (preview?.items ?? []).slice(0, 10);
  const notes = (preview?.diagnostics ?? [])
    .map((item) => {
      const provider = String(item.provider ?? "");
      const message = String(item.message ?? "").trim();
      return message
        ? `${labels[provider] ?? capitalize(provider)}: ${message}`
        : "";
    })
    .filter(Boolean);
  const total = preview?.total ?? 0;
  return (
    <section
      className="src-test"
      aria-labelledby="src-test-title"
      aria-live="polite"
      aria-busy={pending}
    >
      <h3 id="src-test-title" className="src-test-title">
        {pending
          ? "Testing…"
          : error
            ? "Test failed"
            : total
              ? `${total} ${total === 1 ? "job" : "jobs"} found${total > items.length ? ` · the first ${items.length}` : ""}`
              : "No jobs found"}
      </h3>
      {error && (
        <Callout icon={CircleAlert} tone="danger" title={error}>
          Nothing was saved. Check the address or the words, then test again.
        </Callout>
      )}
      {preview?.kind && preview.kind !== "jobspy" && preview.kind !== "rss" && (
        <p className="src-test-note">
          Job board: {labels[preview.kind] ?? capitalize(preview.kind)}
          {typeof preview.url === "string" && preview.url
            ? ` · ${shortUrl(preview.url)}`
            : ""}
        </p>
      )}
      {preview?.automatic_collection === false && (
        <p className="src-test-note src-danger">
          This site gives titles without the posting text, so it cannot be
          checked automatically.
        </p>
      )}
      {notes.map((note) => (
        <p className="src-test-note" key={note}>
          {note}
        </p>
      ))}
      {items.length > 0 && (
        <ul className="src-test-list">
          {items.map((item, index) => (
            <li key={index}>
              <span className="src-test-job">
                {String(item.title ?? "Untitled")}
              </span>
              <span className="src-test-where">
                {[item.company, item.location]
                  .filter((part) => typeof part === "string" && part)
                  .join(" · ")}
              </span>
            </li>
          ))}
        </ul>
      )}
      {preview && (
        <p className="src-test-note">
          A test saves nothing. Saved, the source is checked on the schedule.
        </p>
      )}
    </section>
  );
}
