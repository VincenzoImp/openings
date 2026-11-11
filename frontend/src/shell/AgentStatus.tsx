import type { ListResult, Run } from "../api";
import { ActorChip } from "../design";

/**
 * The agent's status line: who is working and on what, while a run is open.
 * Nothing is shown when no run is open.
 */
export function AgentStatus({
  runs,
  onOpen,
}: {
  runs: ListResult<Run>;
  onOpen: () => void;
}) {
  const run = runs.items[0];
  if (!run) return null;
  const others = runs.total - 1;
  return (
    <div className="sidebar-foot caption" role="status">
      <ActorChip actor={run.actor} />
      <a
        href="#activity?section=runs"
        onClick={(event) => {
          event.preventDefault();
          onOpen();
        }}
      >
        Run in progress: {run.workflow || "unnamed"}
      </a>
      {others > 0 && ` and ${others} more`}
    </div>
  );
}
