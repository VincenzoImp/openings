import { CircleAlert, CircleCheck } from "lucide-react";
import { useProfile, useSetup } from "../../query/setup";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Callout, SkeletonRows } from "../../ui/Page";
import { Checklist } from "./Checklist";
import { useToday } from "./data";
import { dueThisWeek, greeting, needsAttention, summaryParts } from "./model";
import {
  Attention,
  NewJobs,
  Ready,
  Stages,
  Waiting,
  type StageCounts,
} from "./Sections";
import "./today.css";

/**
 * Today answers "what do I do now": what is ready to apply, what needs
 * attention, what waits for a reply and what is new, then where every
 * application stands. While the workspace is not set up, the setup checklist
 * takes the place of the sections.
 */
export default function Today() {
  const today = useToday();
  const setup = useSetup();
  const name = useProfile().data?.name ?? "";

  const ready = today.ready.data;
  const shortlisted = today.shortlisted.data?.items ?? [];
  const waiting = today.waiting.data;
  const jobs = today.newJobs.data;
  const counts = (ready?.stage_counts ?? {}) as StageCounts;
  const applications = ["shortlisted", "applied", "interview", "offer"].reduce(
    (sum, stage) => sum + (counts[stage as keyof StageCounts] ?? 0),
    0,
  );
  const attention = needsAttention(shortlisted);
  const deadlines = shortlisted.filter((row) => dueThisWeek(row.deadline));
  const parts = summaryParts({
    ready: ready?.total ?? 0,
    deadlines: deadlines.length,
    newJobs: jobs?.total ?? 0,
  });
  const settled = !today.loading && setup.loaded;
  // An unfinished workspace without applications has nothing else to show.
  const onlySetup = settled && !setup.finished && applications === 0;
  const caughtUp =
    settled &&
    !ready?.total &&
    !attention.length &&
    !waiting?.total &&
    !onlySetup;

  return (
    <div className="today">
      <div className="today-main">
        <header className="today-head">
          <h1>Today</h1>
          <p className="today-summary">
            <span className="today-greeting">{greeting(name)}</span>
            {onlySetup ? (
              <span>Three steps and Openings is ready for you.</span>
            ) : (
              settled && parts.length > 0 && <span>{parts.join(" · ")}</span>
            )}
          </p>
        </header>
        {today.error && (
          <div role="alert">
            <Callout
              icon={CircleAlert}
              tone="danger"
              title="Some of today's lists could not be loaded."
              actions={
                <Button size="sm" onClick={today.retry}>
                  Try again
                </Button>
              }
            />
          </div>
        )}
        {!settled ? (
          <SkeletonRows rows={5} />
        ) : onlySetup ? (
          <>
            <Checklist setup={setup} />
            {jobs && jobs.total > 0 && (
              <NewJobs jobs={jobs} recent={today.recent.data ?? 0} />
            )}
          </>
        ) : (
          <>
            {!setup.finished && <Checklist setup={setup} compact />}
            {caughtUp && (
              <p className="today-caught-up">
                <Icon icon={CircleCheck} />
                Nothing needs you right now.
              </p>
            )}
            {ready && ready.total > 0 && <Ready page={ready} />}
            {attention.length > 0 && <Attention rows={attention} />}
            {waiting && waiting.total > 0 && (
              <Waiting
                rows={waiting.items}
                days={waiting.no_reply?.days ?? 30}
              />
            )}
            {jobs && jobs.total > 0 && (
              <NewJobs jobs={jobs} recent={today.recent.data ?? 0} />
            )}
          </>
        )}
        {settled && applications > 0 && <Stages counts={counts} />}
      </div>
    </div>
  );
}
