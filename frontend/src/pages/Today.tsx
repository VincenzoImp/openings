import { useEffect, useState } from "react";
import type {
  Application,
  CollectionRun,
  ListResult,
  OwnerQuestion,
  Overview,
  PolicySection,
  Run,
} from "../api";
import { Pipeline } from "../design";
import { PageHead } from "../library/common";
import { dayBefore } from "../library/time";
import { useFresh } from "../library/useFresh";
import { useUrlFilters } from "../state";
import type { Links } from "./activity/records";
import { lastRunLine } from "./activity/wording";
import { Decisions } from "./today/Decisions";
import { READY_QUEUE, Ready } from "./today/Ready";
import { Since } from "./today/Since";
import { DEFAULT_REPLY_DAYS, replyDays, todaySummary } from "./today/summary";
import { beginVisit, sinceOf, touchVisit } from "./today/visit";
import { Progress, Waiting } from "./today/Waiting";

const NONE = { items: [], total: 0 };
const APPLICATIONS = ["applications", "jobs", "documents", "files"];

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
  const [period, setPeriod] = useUrlFilters({ since: "", until: "" });
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
  // The period after which a sent application has waited long is the owner's
  // "No reply" decision in the policy, when it holds a number of days.
  const policy = useFresh<PolicySection | null>("/policy/decision", null, [
    "policy",
  ]);
  const days = policy.data ? replyDays(policy.data.items) : DEFAULT_REPLY_DAYS;
  const until = dayBefore(days);
  const waiting = useFresh<ListResult<Application>>(
    policy.loading
      ? null
      : `/applications?status=applied&applied_until=${until}&limit=1`,
    NONE,
    APPLICATIONS,
  );
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
  const overview = useFresh<Overview | null>(
    `/overview?${new URLSearchParams(Object.entries(period).filter(([, value]) => value))}`,
    null,
    ["applications", "jobs"],
  );

  const counted = [ready, questions, blocked, waiting, lastRun];
  const summary = counted.some((item) => item.error)
    ? {
        lead: "Some of today's numbers could not be loaded.",
        rest: "The cards below say which, and let you try again.",
      }
    : counted.some((item) => item.loading) || policy.loading
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
        <div className="cols">
          <div className="roomy">
            <Ready list={ready} />
            <Decisions
              questions={questions}
              blocked={blocked}
              incomplete={overview.data?.incomplete ?? 0}
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
                  href: "#applications?status=draft",
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
                  href: `#applications?status=${name}`,
                })),
              ]}
            />
            <Since
              since={since}
              firstVisit={firstVisit}
              runs={runs}
              collection={collection}
            />
            <Waiting
              list={waiting}
              applied={stage("applied")}
              days={days}
              until={until}
            />
          </div>
        </div>
        <Progress overview={overview} period={period} onPeriod={setPeriod} />
      </div>
    </>
  );
}
