import { useMemo } from "react";
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
const APPLICATIONS = ["applications", "jobs", "documents", "files"];

/** The first screen: what is ready to apply, where applications stand and what waits for a reply. */
export default function TodayPage() {
  const ready = useFresh<ListResult<Application>>(
    "/applications?stage=ready&sort=deadline&limit=5",
    NONE,
    APPLICATIONS,
  );
  const stages = useFresh<ListResult<Application>>(
    "/applications?limit=1",
    NONE,
    APPLICATIONS,
  );
  // Shortlisted applications held by a blocking requirement.
  const shortlisted = useFresh<ListResult<Application>>(
    "/applications?stage=shortlisted&sort=deadline&limit=200",
    NONE,
    APPLICATIONS,
  );
  const blocked = useMemo(() => {
    const items = shortlisted.data.items.filter(
      (item) => (item.blocking_requirements || 0) > 0,
    );
    return {
      ...shortlisted,
      data: { items: items.slice(0, 3), total: items.length },
    };
  }, [shortlisted]);
  // Applied applications without a reply past the no-reply period (the owner's
  // setting in Preferences, or 30), as the server reads it; closed by hand.
  const waiting = useFresh<ListResult<Application>>(
    "/applications?needs=reply_overdue&sort=applied&limit=200",
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
  const marked = stage("ready") ?? 0;
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
                  label: "Shortlisted",
                  value: counts
                    ? (stage("shortlisted") ?? 0) - marked
                    : undefined,
                  href: stageHref("shortlisted"),
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
