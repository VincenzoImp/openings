import type { Application, ListResult } from "../api";
import { Pipeline } from "../design";
import { PageHead } from "../library/common";
import { useFresh } from "../library/useFresh";
import { READY_QUEUE, stageHref } from "./applications/links";
import { Ready } from "./today/Ready";
import { SetupBanner } from "./today/SetupBanner";
import { todaySummary } from "./today/summary";
import { Waiting } from "./today/Waiting";

const NONE = { items: [], total: 0 };
const APPLICATIONS = [
  "applications",
  "jobs",
  "documents",
  "files",
  "responses",
];

/** The first screen: what is ready to apply, where applications stand and what waits for a reply. */
export default function TodayPage() {
  const ready = useFresh<ListResult<Application>>(
    "/applications?readiness=ready&sort=deadline&limit=5",
    NONE,
    APPLICATIONS,
  );
  const stages = useFresh<ListResult<Application>>(
    "/applications?limit=1",
    NONE,
    APPLICATIONS,
  );
  const blocked = useFresh<ListResult<Application>>(
    "/applications?readiness=blocked&status=draft&limit=1",
    NONE,
    APPLICATIONS,
  );
  // Applied applications past the no-reply period: the owner's setting
  // (Preferences, Facts about me), or 30, as the server reads it.
  const waiting = useFresh<ListResult<Application>>(
    "/applications?no_reply_due=true&limit=1",
    NONE,
    [...APPLICATIONS, "settings"],
  );
  const days = waiting.data.no_reply?.days ?? 30;

  const counted = [ready, blocked, waiting];
  const summary = counted.some((item) => item.error)
    ? {
        lead: "Some of today's numbers could not be loaded.",
        rest: "The cards below say which, and let you try again.",
      }
    : counted.some((item) => item.loading)
      ? null
      : todaySummary({
          ready: ready.data.total,
          blocked: blocked.data.total,
          waiting: waiting.data.total,
          days,
        });
  const counts = stages.loading || stages.error ? null : stages.data;
  const stage = (name: string) => counts?.stage_counts?.[name];
  const marked = counts?.ready_count ?? 0;
  return (
    <>
      <PageHead title="Today">
        {summary ? (
          <>
            <strong>{summary.lead}</strong> {summary.rest}
          </>
        ) : (
          "Reading your workspace…"
        )}
      </PageHead>
      <div className="roomy">
        <SetupBanner />
        <div className="cols">
          <div className="roomy">
            <Ready list={ready} />
          </div>
          <div className="roomy">
            <Pipeline
              label="Pipeline"
              steps={[
                {
                  label: "Preparing",
                  value: counts ? (stage("draft") ?? 0) - marked : undefined,
                  href: stageHref("preparing"),
                },
                {
                  label: "Ready",
                  value: counts ? marked : undefined,
                  href: READY_QUEUE,
                  ready: true,
                },
                ...[
                  ["Applied", "applied"],
                  ["Interview", "interview"],
                  ["Offer", "offer"],
                ].map(([label, name]) => ({
                  label,
                  value: stage(name),
                  href: stageHref(name),
                })),
              ]}
            />
            <Waiting list={waiting} applied={stage("applied")} days={days} />
          </div>
        </div>
      </div>
    </>
  );
}
