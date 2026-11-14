import { useEffect, useState } from "react";
import type {
  Application,
  CollectionRun,
  ListResult,
  OwnerQuestion,
  Run,
} from "../api";
import { Pipeline } from "../design";
import { PageHead } from "../library/common";
import { useFresh } from "../library/useFresh";
import type { Links } from "./activity/records";
import { lastRunLine } from "./activity/wording";
import { READY_QUEUE, stageHref } from "./applications/links";
import { Decisions } from "./today/Decisions";
import { Ready } from "./today/Ready";
import { SetupBanner } from "./today/SetupBanner";
import { Since } from "./today/Since";
import { todaySummary } from "./today/summary";
import { beginVisit, sinceOf, touchVisit } from "./today/visit";
import { Waiting } from "./today/Waiting";

const NONE = { items: [], total: 0 };
const APPLICATIONS = [
  "applications",
  "jobs",
  "documents",
  "files",
  "responses",
];

/** The visit Today counts "since your last visit" from (see today/visit.ts). */
function useVisit() {
  const [state, setState] = useState(() => {
    const now = new Date();
    const visit = beginVisit(now);
    return { visit, since: sinceOf(visit, now) };
  });
  useEffect(() => {
    const { visit } = state;
    const touch = () => touchVisit(visit);
    // Coming back to a tab left in the background may start a new visit.
    const seen = () => {
      if (document.visibilityState === "hidden") return touch();
      const now = new Date();
      const next = beginVisit(now);
      if (next.since !== visit.since)
        setState({ visit: next, since: sinceOf(next, now) });
    };
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") touch();
    }, 60_000);
    document.addEventListener("visibilitychange", seen);
    window.addEventListener("pagehide", touch);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", seen);
      window.removeEventListener("pagehide", touch);
      touch();
    };
  }, [state]);
  return { since: state.since, firstVisit: state.visit.since === null };
}

/**
 * The first screen: what is ready to apply, what needs the owner's decision,
 * what happened since the last visit and what waits for a reply.
 */
export default function TodayPage(links: Links) {
  const { since, firstVisit } = useVisit();
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
    "/applications?readiness=blocked&status=draft&sort=deadline&limit=3",
    NONE,
    APPLICATIONS,
  );
  const questions = useFresh<ListResult<OwnerQuestion>>(
    "/questions?state=open&limit=3",
    NONE,
    ["questions"],
  );
  // Applied applications past the no-reply period: the owner's setting
  // (Preferences, Facts about me), or 30, as the server reads it.
  const waiting = useFresh<ListResult<Application>>(
    "/applications?no_reply_due=true&limit=1",
    NONE,
    [...APPLICATIONS, "settings"],
  );
  const days = waiting.data.no_reply?.days ?? 30;
  const runs = useFresh<ListResult<Run>>(
    `/runs?active_since=${encodeURIComponent(since)}&limit=5`,
    NONE,
    ["runs"],
  );
  const lastRun = useFresh<ListResult<Run>>("/runs?limit=1", NONE, ["runs"]);
  const collection = useFresh<ListResult<CollectionRun>>(
    "/collection/runs?limit=100",
    NONE,
    ["collection", "sources"],
  );
  // Jobs not dismissed whose posting text is incomplete: the owner pastes it.
  const incomplete = useFresh<ListResult<never>>(
    "/jobs?complete=false&triage=active&limit=1",
    NONE,
    ["jobs"],
  );

  const counted = [ready, questions, blocked, waiting, lastRun];
  const summary = counted.some((item) => item.error)
    ? {
        lead: "Some of today's numbers could not be loaded.",
        rest: "The cards below say which, and let you try again.",
      }
    : counted.some((item) => item.loading)
      ? null
      : todaySummary(
          {
            ready: ready.data.total,
            questions: questions.data.total,
            blocked: blocked.data.total,
            waiting: waiting.data.total,
            days,
          },
          lastRunLine(lastRun.data.items[0]),
        );
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
            <Decisions
              questions={questions}
              blocked={blocked}
              incomplete={incomplete.data.total}
              {...links}
            />
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
            <Since
              since={since}
              firstVisit={firstVisit}
              runs={runs}
              collection={collection}
            />
            <Waiting list={waiting} applied={stage("applied")} days={days} />
          </div>
        </div>
      </div>
    </>
  );
}
