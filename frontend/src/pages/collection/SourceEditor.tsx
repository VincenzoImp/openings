import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Json, type ListResult, type Source } from "../../api";
import { Button, ErrorBanner, Field, Loading } from "../../design";
import { useEditorRecord, useResource, useWorkspace } from "../../state";
import {
  OWN_FIELDS,
  schemaProperties,
  scheduleValues,
  sharedProperties,
  terms,
  type Preview,
  type SourceSchema,
} from "./model";
import { PreviewResult } from "./PreviewResult";
import { ScheduleFields } from "./Schedule";
import {
  AcquisitionFields,
  BoardFields,
  FilterFields,
  SearchFields,
} from "./SourceFields";

const NO_SCHEMAS: ListResult<SourceSchema> = { items: [], total: 0 };

/**
 * A new search or company board, or the settings of one: every field has
 * its own control. A version conflict keeps the draft and offers the latest
 * values (the form's conflict recovery).
 */
export function SourceEditor(props: {
  source?: Source;
  search: boolean;
  onClose: () => void;
}) {
  const source = useEditorRecord(
    props.source,
    props.source ? `/sources/${props.source.id}` : "",
  );
  return (
    <SourceForm key={source?.version || "new"} {...props} source={source} />
  );
}

function SourceForm({
  source,
  search,
  onClose,
}: {
  source?: Source;
  search: boolean;
  onClose: () => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const schemas = useResource("/sources/schemas", NO_SCHEMAS);
  const heading = useRef<HTMLHeadingElement>(null);
  const [kind, setKind] = useState(
    source?.kind || (search ? "jobspy" : "auto"),
  );
  const [providers, setProviders] = useState<string[]>(
    (source?.config.providers as string[]) || ["linkedin", "indeed"],
  );
  const [preview, setPreview] = useState<Preview | null>(null),
    [previewing, setPreviewing] = useState(false);
  const revision = useRef(0);
  useEffect(() => {
    heading.current?.scrollIntoView({ block: "start" });
    heading.current?.focus({ preventScroll: true });
  }, []);
  const searching = kind === "jobspy";
  const schema = schemas.data.items.find((item) => item.kind === kind);
  const resolved =
    schema || schemas.data.items.find((item) => item.kind === preview?.kind);
  const automatic =
    resolved?.capabilities.automatic_collection !== false &&
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
  const has = (key: string) => Object.hasOwn(properties, key);
  const defaults = (key: string, fallback: unknown) =>
    properties[key]?.default ?? fallback;
  // Configuration the form has no control for is kept as it is.
  const kept = Object.fromEntries(
    Object.entries(source?.config || {}).filter(
      ([key]) => !OWN_FIELDS.includes(key) && (kind === "auto" || has(key)),
    ),
  );
  function changed() {
    revision.current += 1;
    setPreview(null);
  }
  function values(form: HTMLFormElement) {
    const f = new FormData(form);
    const config: Json = { ...kept };
    if (searching)
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
        if (has(key) && f.get(key)) config[key] = String(f.get(key));
      for (const key of ["max_results", "max_candidates"]) {
        const value = f.get(key);
        if (has(key) && typeof value === "string" && value.trim())
          config[key] = Number(value);
      }
    }
    return {
      name: String(f.get("name")),
      kind,
      url: searching ? "" : String(f.get("url") || ""),
      config,
      enabled: f.get("enabled") === "on",
      filters: {
        ...source?.filters,
        titles: terms(f.get("titles")),
        locations: terms(f.get("locations")),
        exclude_titles: terms(f.get("exclude_titles")),
      },
      schedule: scheduleValues(f),
    };
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = values(event.currentTarget);
    if (
      await mutate(
        () =>
          source
            ? api(`/sources/${source.id}`, "PATCH", {
                ...body,
                expected_version: source.version,
              })
            : api("/sources", "POST", body),
        searching ? "Search saved." : "Company board saved.",
      )
    )
      onClose();
  }
  async function inspect(form: HTMLFormElement | null) {
    if (!form || previewing || !form.reportValidity()) return;
    setPreviewing(true);
    const asked = revision.current;
    try {
      const { enabled, schedule, ...body } = values(form);
      const result = await api<Preview>("/sources/preview", "POST", body);
      if (revision.current === asked) {
        setPreview(result);
        notify("Preview complete. No job was saved.");
      } else notify("The settings changed during the preview. Preview again.");
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : "Preview failed.", true);
    } finally {
      setPreviewing(false);
    }
  }
  const title = source
    ? `Edit ${source.name}`
    : searching
      ? "New search"
      : "New company board";
  return (
    <section className="card" aria-labelledby="source-editor">
      <header>
        <h2 id="source-editor" className="grow" tabIndex={-1} ref={heading}>
          {title}
        </h2>
        <span className="caption">
          Every field has its own control; no configuration text to write
        </span>
      </header>
      {schemas.loading ? (
        <Loading label="Loading the source settings…" />
      ) : schemas.error && !schemas.data.items.length ? (
        <div className="body">
          <ErrorBanner message={schemas.error} retry={schemas.reload} />
        </div>
      ) : (
        <form
          className="body stack"
          onSubmit={save}
          onChange={changed}
          onClick={(event) => {
            if ((event.target as HTMLElement).closest("[data-dirty-control]"))
              changed();
          }}
        >
          <div className="form-grid">
            <Field label={searching ? "Name" : "Company name"}>
              <input
                name="name"
                required
                maxLength={200}
                defaultValue={source?.name}
                placeholder={searching ? "Data engineer Basel" : "Example Labs"}
              />
            </Field>
            {searching ? (
              <SearchFields
                source={source}
                country={String(defaults("country", "usa"))}
                providers={providers}
                onProviders={setProviders}
              />
            ) : (
              <BoardFields
                source={source}
                kind={kind}
                onKind={(next) => {
                  setKind(next);
                  setPreview(null);
                }}
                schemas={schemas.data.items}
                hasBoard={has("board")}
              />
            )}
            <AcquisitionFields
              source={source}
              search={searching}
              properties={properties}
              defaults={defaults}
            />
            <FilterFields source={source} />
            <ScheduleFields schedule={source?.schedule} />
            <label className="toggle wide">
              <input
                name="enabled"
                type="checkbox"
                defaultChecked={!!source?.enabled}
                disabled={!automatic}
              />
              Collect on this schedule (new sources start paused; Run once works
              either way)
            </label>
          </div>
          {!automatic && (
            <div role="alert" className="banner danger">
              This service gives titles and links without the posting text, so
              it cannot collect automatically. Use a supported board, or add the
              full posting in Jobs.
            </div>
          )}
          {!searching && (has("region") || has("max_candidates")) && (
            <details>
              <summary>Advanced settings</summary>
              <div className="form-grid">
                {has("region") && (
                  <Field
                    label="Board region"
                    hint="Usually global; some services have a European endpoint."
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
                {has("max_candidates") && (
                  <Field
                    label="Listings to inspect"
                    hint="20 to 10,000 listings before your filters; 2,000 by default."
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
              </div>
            </details>
          )}
          {preview && <PreviewResult preview={preview} />}
          <div className="row">
            <Button
              variant="primary"
              size="sm"
              disabled={pending || previewing || !automatic}
            >
              {searching ? "Save the search" : "Save the board"}
            </Button>
            <Button
              type="button"
              size="sm"
              loading={previewing}
              disabled={pending}
              onClick={(event) => inspect(event.currentTarget.form)}
            >
              Preview results
            </Button>
            <Button type="button" variant="quiet" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <span className="caption">
              A preview asks the providers once, through the same request limits
              as a run, and saves nothing.
            </span>
          </div>
        </form>
      )}
    </section>
  );
}
