import { useState } from "react";
import type { Json, ListResult, Source } from "../../api";
import { Button, Dialog, ErrorBanner, Loading } from "../../design";
import { useResource, useWorkspace } from "../../state";
import {
  limitValues,
  scheduleValues,
  sharedProperties,
  terms,
  type SourceSchema,
} from "./model";
import { ScheduleFields } from "./Schedule";
import { SharedLimits } from "./SourceFields";

const NO_SCHEMAS: ListResult<SourceSchema> = { items: [], total: 0 };
const named = (sources: Source[]) =>
  sources.length === 1 ? sources[0].name : `${sources.length} sources`;

function useShared(sources: Source[]) {
  const schemas = useResource("/sources/schemas", NO_SCHEMAS);
  return {
    schemas,
    properties: sharedProperties(
      schemas.data.items,
      sources.map((source) => source.kind),
    ),
  };
}

/** Run once with limits for this run only; saved settings stay as they are. */
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
  const { schemas, properties } = useShared(sources);
  const unavailable = schemas.loading || !!schemas.error;
  return (
    <Dialog title={`Run ${named(sources)} with options`} onClose={onClose}>
      <form
        className="stack"
        onSubmit={async (event) => {
          event.preventDefault();
          if (unavailable) return;
          const overrides = limitValues(
            new FormData(event.currentTarget),
            properties,
          );
          if (await onRun(overrides)) onClose();
        }}
      >
        <p>
          These limits apply to this run only. Saved settings stay the same.
        </p>
        {schemas.loading ? (
          <Loading label="Loading the limits…" />
        ) : schemas.error ? (
          <ErrorBanner message={schemas.error} retry={schemas.reload} />
        ) : (
          <SharedLimits properties={properties} placeholder="Saved setting" />
        )}
        <p className="caption">
          Empty fields use each source's saved setting. Request spacing and
          provider pauses still apply; a run already in progress must finish or
          be stopped first.
        </p>
        <div className="row">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending || unavailable}>
            Run with options
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Change the schedule, limits or filters of several sources at once. */
export function BulkConfigureDialog({
  sources,
  onClose,
  onSave,
}: {
  sources: Source[];
  onClose: () => void;
  onSave: (patch: Json) => Promise<boolean>;
}) {
  const { pending } = useWorkspace();
  const { schemas, properties } = useShared(sources);
  const [schedule, setSchedule] = useState(false),
    [limits, setLimits] = useState(false),
    [filters, setFilters] = useState(false);
  return (
    <Dialog title={`Configure ${named(sources)}`} onClose={onClose}>
      <form
        className="stack"
        onSubmit={async (event) => {
          event.preventDefault();
          const f = new FormData(event.currentTarget),
            patch: Json = {};
          if (schedule) patch.schedule = scheduleValues(f);
          if (limits) {
            if (schemas.loading || schemas.error) return;
            const config = limitValues(f, properties);
            if (Object.keys(config).length) patch.config = config;
          }
          if (filters)
            patch.filters = {
              titles: terms(f.get("titles")),
              locations: terms(f.get("locations")),
              exclude_titles: terms(f.get("exclude_titles")),
            };
          if (await onSave(patch)) onClose();
        }}
      >
        <p>Choose what to change. Every other setting is kept.</p>
        <label className="toggle">
          <input
            type="checkbox"
            checked={schedule}
            onChange={(event) => setSchedule(event.target.checked)}
          />
          Replace the schedule
        </label>
        {schedule && (
          <div className="form-grid">
            <ScheduleFields schedule={sources[0].schedule} />
          </div>
        )}
        <label className="toggle">
          <input
            type="checkbox"
            checked={limits}
            onChange={(event) => setLimits(event.target.checked)}
          />
          Change acquisition limits
        </label>
        {limits &&
          (schemas.loading ? (
            <Loading label="Loading the limits…" />
          ) : schemas.error ? (
            <ErrorBanner message={schemas.error} retry={schemas.reload} />
          ) : (
            <SharedLimits properties={properties} placeholder="Keep current" />
          ))}
        <label className="toggle">
          <input
            type="checkbox"
            checked={filters}
            onChange={(event) => setFilters(event.target.checked)}
          />
          Replace the title, location and left-out filters
        </label>
        {filters && (
          <div className="form-grid">
            {[
              ["titles", "Titles to keep"],
              ["locations", "Locations to keep"],
              ["exclude_titles", "Words to leave out"],
            ].map(([name, label]) => (
              <label className="field" key={name}>
                <span>{label}</span>
                <input name={name} placeholder="Empty clears the filter" />
              </label>
            ))}
          </div>
        )}
        <div className="row">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={
              pending ||
              (!schedule && !limits && !filters) ||
              (limits && (schemas.loading || !!schemas.error))
            }
          >
            Save changes
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
