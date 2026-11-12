import type { Application, FunnelStep, ListResult, Overview } from "../../api";
import { Button, Card, EmptyState, Stat, Stats } from "../../design";
import { Loaded, plural } from "../../library/common";
import type { Fresh } from "../../library/useFresh";

/** Applications sent long ago without a recorded reply, and where to record one. */
export function Waiting({
  list,
  applied,
  days,
  until,
}: {
  /** Applied applications sent on or before `until`. */
  list: Fresh<ListResult<Application>>;
  /** Every application in Applied; undefined while it loads. */
  applied?: number;
  days: number;
  /** The day (YYYY-MM-DD) before which an application has waited long. */
  until: string;
}) {
  return (
    <Card title="Waiting for a reply" count={applied}>
      <Loaded from={list} label="Loading applications…">
        {({ total }) =>
          total ? (
            <div className="body stack">
              <p>
                {total === 1
                  ? "1 application was"
                  : `${total} applications were`}{" "}
                sent more than {days} days ago. Record what happened so your
                numbers stay true.
              </p>
              <div className="row">
                <a
                  className="btn sm"
                  href={`#applications?status=applied&applied_until=${until}&view=list`}
                >
                  Record replies
                </a>
              </div>
            </div>
          ) : (
            <EmptyState title="No long wait">
              {applied
                ? `None of your ${plural(applied, "sent application")} has waited more than ${days} days for a reply.`
                : "Applications you sent appear here while they wait for a reply."}
            </EmptyState>
          )
        }
      </Loaded>
    </Card>
  );
}

const stageNames: Record<string, string> = {
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
};
const closed = (step: FunnelStep, outcome: string) =>
  step.outcomes[outcome] || 0;

/**
 * How far sent applications went, for a period. This is the funnel of the
 * former Overview; it moves to Applications, Insights when that is built.
 */
export function Progress({
  overview,
  period,
  onPeriod,
}: {
  overview: Fresh<Overview | null>;
  period: Record<string, string>;
  onPeriod: (patch: Record<string, string>) => void;
}) {
  const ranged = Boolean(period.since || period.until);
  return (
    <Card title="Progress">
      <div className="filters">
        <label className="toggle">
          <span className="muted">Sent from</span>
          <input
            className="input"
            type="date"
            value={period.since}
            max={period.until || undefined}
            onChange={(event) => onPeriod({ since: event.target.value })}
          />
        </label>
        <label className="toggle">
          <span className="muted">Through</span>
          <input
            className="input"
            type="date"
            value={period.until}
            min={period.since || undefined}
            onChange={(event) => onPeriod({ until: event.target.value })}
          />
        </label>
        <Button
          size="sm"
          variant="quiet"
          disabled={!ranged}
          onClick={() => onPeriod({ since: "", until: "" })}
        >
          All time
        </Button>
      </div>
      <Loaded from={overview} label="Loading progress…">
        {(data) =>
          data && data.sent ? (
            <>
              <div className="body">
                <Stats>
                  <Stat
                    label="Applications sent"
                    value={data.sent}
                    note={ranged ? "In this period" : "All recorded"}
                  />
                  <Stat label="Reached interview" value={data.interviews} />
                  <Stat label="Offers received" value={data.offers} />
                  <Stat
                    label="Accepted"
                    value={data.funnel.reduce(
                      (sum, step) => sum + closed(step, "accepted"),
                      0,
                    )}
                  />
                </Stats>
              </div>
              <div className="datatable-wrap">
                <table className="datatable stack num">
                  <caption className="sr">
                    Sent applications by the furthest stage they reached
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Stage</th>
                      <th scope="col" className="right">
                        Reached
                      </th>
                      <th scope="col" className="right">
                        Waiting there
                      </th>
                      <th scope="col" className="right">
                        Not selected
                      </th>
                      <th scope="col" className="right">
                        Not pursued
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.funnel.map((step) => (
                      <tr key={step.stage}>
                        <td className="primary">
                          <strong>
                            {stageNames[step.stage] || step.stage}
                          </strong>
                        </td>
                        <td className="right" data-label="Reached">
                          {step.count}
                        </td>
                        <td className="right" data-label="Waiting there">
                          {closed(step, "waiting")}
                        </td>
                        <td className="right" data-label="Not selected">
                          {closed(step, "rejected")}
                        </td>
                        <td className="right" data-label="Not pursued">
                          {closed(step, "not_pursued")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <EmptyState title="No sent applications">
              {ranged
                ? "No application was sent in this period."
                : "Once you record an application as Applied, its progress is counted here."}
            </EmptyState>
          )
        }
      </Loaded>
    </Card>
  );
}
