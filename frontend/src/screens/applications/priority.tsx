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
