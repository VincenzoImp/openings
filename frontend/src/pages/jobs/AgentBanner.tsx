import type { JobList, ListResult, Run } from "../../api";
import { ActorChip, Banner } from "../../design";
import { plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { dayTime } from "../../library/time";
import { countsLine } from "../activity/wording";
import { JOB_SCOPES } from "./model";

const NONE = { items: [], total: 0 };
export const REVIEW_WORKFLOW = "review-inbox";

/**
 * Who reviews this queue: the agent's last review-inbox run, what it changed
 * and how many jobs arrived since; or how the queue gets reviewed at all.
 */
export function AgentBanner() {
  const runs = useFresh<ListResult<Run>>(
    `/runs?workflow=${REVIEW_WORKFLOW}&limit=1`,
    NONE,
    ["runs"],
  );
  const run = runs.data.items[0];
  const since = run?.ended_at || run?.last_activity_at;
  const arrived = useFresh<JobList>(
    since
      ? `/jobs?queue=inbox&limit=1&created_since=${encodeURIComponent(since)}`
      : null,
    NONE,
    JOB_SCOPES,
  );
  if (runs.loading || runs.error) return null;
  if (!run)
    return (
      <Banner tone="info">
        <strong>New jobs wait here for review.</strong> An agent with the
        review-inbox skill reviews them against your preferences and leaves what
        it cannot decide for you. You can shortlist or dismiss any job yourself.
      </Banner>
    );
  const changed = countsLine(run.change_counts || {});
  return (
    <Banner
      tone="info"
      action={
        <a
          className="btn sm"
          href={`#activity?section=runs&run=${encodeURIComponent(run.id)}`}
        >
          Run report
        </a>
      }
    >
      <strong>Your agent reviews this queue.</strong>{" "}
      {run.status === "open"
        ? "A review is running now, started "
        : "Last review: "}
      {dayTime(run.status === "open" ? run.started_at : since)} by{" "}
      <ActorChip actor={run.actor} />
      {changed ? ` (${changed}).` : "."}{" "}
      {run.status !== "open" &&
        arrived.data.total > 0 &&
        `${plural(arrived.data.total, "job")} arrived since and ${arrived.data.total === 1 ? "waits" : "wait"} for the next run.`}
    </Banner>
  );
}
