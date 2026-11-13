import { api, formatTime, type Source } from "../../api";
import { Button, IconButton, Switch, Tag } from "../../design";
import { dayTime } from "../../library/time";
import { useWorkspace } from "../../state";
import {
  active,
  countsLine,
  isSearch,
  providersOf,
  scheduleLabel,
  sourceLine,
  stateTag,
  waitReason,
} from "./model";

/** What happened at the last run of a source, and what needs attention. */
function LastRun({ source }: { source: Source }) {
  const run = source.last_run;
  const running = active(run?.state);
  const tag = run && stateTag(run);
  const warnings = [
    ...new Set(source.last_diagnostics?.flatMap((d) => d.warnings || []) || []),
  ];
  return (
    <>
      {run ? (
        <>
          {tag && tag.text !== "Finished" && (
            <>
              <Tag tone={tag.tone}>{tag.text}</Tag>{" "}
            </>
          )}
          {dayTime(run.started_at || run.created_at)} ·{" "}
          {countsLine(run.counts, run.state)}
          {waitReason(run) && <div className="meta">{waitReason(run)}</div>}
        </>
      ) : (
        <span className="meta">Not run yet</span>
      )}
      {source.last_error && !running && (
        <div className="meta danger-text">{source.last_error}</div>
      )}
      {!source.automatic_collection && (
        <div className="meta danger-text">
          This service gives no posting text; it cannot collect automatically.
        </div>
      )}
      {warnings.map((warning) => (
        <div className="meta" key={warning}>
          {warning}
        </div>
      ))}
      {!running && source.enabled && source.next_run_at && (
        <div className="meta">Next {formatTime(source.next_run_at)}</div>
      )}
    </>
  );
}

/** One source: on/off, what it collects, its schedule and last run, its actions. */
export function SourceRow({
  source,
  selected,
  selectable,
  onSelect,
  onEdit,
  onRun,
  onOptions,
  onRemove,
}: {
  source: Source;
  selected: boolean;
  selectable: boolean;
  onSelect: (selected: boolean) => void;
  onEdit: () => void;
  onRun: () => void;
  onOptions: () => void;
  onRemove: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const run = source.last_run;
  const running = active(run?.state);
  return (
    <tr className={selected ? "is-selected" : undefined}>
      <td className="select">
        <input
          type="checkbox"
          aria-label={`Select ${source.name}`}
          checked={selected}
          disabled={!selected && !selectable}
          onChange={(event) => onSelect(event.target.checked)}
        />
      </td>
      <td>
        <Switch
          label={`${source.name} collects on its schedule`}
          checked={source.enabled}
          disabled={pending || !source.automatic_collection}
          onChange={(enabled) =>
            mutate(
              () =>
                api(`/sources/${source.id}`, "PATCH", {
                  expected_version: source.version,
                  enabled,
                }),
              enabled ? `${source.name} is on.` : `${source.name} is paused.`,
            )
          }
        />
      </td>
      <td className="primary">
        <button type="button" className="link" onClick={onEdit}>
          {source.name}
        </button>
        <div className="meta">{sourceLine(source)}</div>
      </td>
      <td data-label="Providers">
        <span className="tags">
          {providersOf(source).map((name) => (
            <Tag key={name}>{name}</Tag>
          ))}
        </span>
      </td>
      <td data-label="Schedule">
        {source.enabled ? (
          scheduleLabel(source.schedule)
        ) : (
          <span className="meta">
            Paused · {scheduleLabel(source.schedule)}
          </span>
        )}
      </td>
      <td data-label="Last run">
        <LastRun source={source} />
        {run && (
          <div className="meta">
            <a href={`#collection?section=runs&source_id=${source.id}`}>
              Runs of {isSearch(source) ? "this search" : "this board"}
            </a>
          </div>
        )}
      </td>
      <td className="actions">
        <div className="cell-actions">
          {running && run ? (
            <Button
              size="sm"
              disabled={pending}
              onClick={() =>
                mutate(
                  () => api(`/collection/runs/${run.id}/cancel`, "POST"),
                  "The run was stopped. Jobs found so far are kept.",
                )
              }
            >
              Stop run
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={pending || !source.automatic_collection}
              onClick={onRun}
            >
              Run once
            </Button>
          )}
          <Button size="sm" variant="quiet" onClick={onEdit}>
            Edit
          </Button>
          <Button
            size="sm"
            variant="quiet"
            disabled={pending || !source.automatic_collection}
            onClick={onOptions}
          >
            With options
          </Button>
          <IconButton
            icon="trash"
            label={`Remove ${source.name}`}
            onClick={onRemove}
          />
        </div>
      </td>
    </tr>
  );
}
