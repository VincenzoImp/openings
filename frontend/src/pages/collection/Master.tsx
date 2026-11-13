import { api, formatTime } from "../../api";
import { ErrorBanner } from "../../design";
import { plural } from "../../library/common";
import { useResource, useWorkspace } from "../../state";

export interface CollectionState {
  enabled: boolean;
  version: number;
  source_count: number;
  enabled_sources: number;
  queued_tasks: number;
  running_tasks: number;
  next_run_at?: string;
}
const INITIAL: CollectionState = {
  enabled: true,
  version: 0,
  source_count: 0,
  enabled_sources: 0,
  queued_tasks: 0,
  running_tasks: 0,
};

/**
 * The switch of scheduled collection. Pausing stops future scheduled runs;
 * runs already queued or in progress continue until stopped.
 */
export function Master() {
  const collection = useResource("/collection", INITIAL);
  const { mutate, pending } = useWorkspace();
  const state = collection.data;
  if (collection.error)
    return <ErrorBanner message={collection.error} retry={collection.reload} />;
  return (
    <section className="card master" aria-label="Scheduled collection">
      <input
        type="checkbox"
        role="switch"
        className="switch"
        id="collect-on"
        aria-describedby="collect-detail"
        checked={state.enabled}
        disabled={pending || collection.loading}
        onChange={(event) =>
          mutate(
            () =>
              api("/collection", "PATCH", {
                expected_version: state.version,
                enabled: event.target.checked,
              }),
            event.target.checked
              ? "Scheduled collection is on."
              : "Scheduled collection is paused. Runs in progress continue.",
          )
        }
      />
      <div className="grow">
        <label htmlFor="collect-on">
          <strong>
            {state.enabled
              ? "Scheduled collection is on"
              : "Scheduled collection is paused"}
          </strong>
        </label>
        <div className="muted" id="collect-detail">
          {state.enabled_sources} of {plural(state.source_count, "source")} on ·{" "}
          {state.running_tasks} running · {state.queued_tasks} queued
          {state.enabled && state.next_run_at
            ? ` · next run ${formatTime(state.next_run_at)}`
            : ""}
          . Pausing stops future runs; use Stop run to end one in progress.
        </div>
      </div>
    </section>
  );
}
