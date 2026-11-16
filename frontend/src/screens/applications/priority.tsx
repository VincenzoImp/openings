import { ChevronsUp } from "lucide-react";
import { Icon } from "../../ui/Icon";

/**
 * The one priority mark a row may carry: only the highest priority (1) is
 * marked, so the deadline or the status stays the row's signal.
 */
export function HighPriority({ priority }: { priority?: number | null }) {
  if (priority !== 1) return null;
  return (
    <span
      className="ap-high"
      role="img"
      aria-label="High priority"
      title="High priority"
    >
      <Icon icon={ChevronsUp} size="sm" />
    </span>
  );
}

/** A Ready row's place in the best-first order (priority, then deadline). */
export function ReadyRank({ rank }: { rank: number }) {
  return (
    <span className="ui-row-rank" title="Best first: priority, then deadline">
      <span className="ui-sr">Rank </span>
      {rank}
    </span>
  );
}

/** "Priority 2", or nothing when the application has no priority. */
export const priorityText = (priority?: number | null) =>
  priority ? `Priority ${priority}` : "";
