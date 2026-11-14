import type { FunnelStep, Overview } from "../../api";
import { Button, Card, EmptyState, Stat, Stats } from "../../design";
import { Loaded } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useUrlFilters } from "../../state";

const stageNames: Record<string, string> = {
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
};
const closed = (step: FunnelStep, outcome: string) =>
  step.outcomes[outcome] || 0;

/**
 * How far sent applications went, by the furthest stage each reached, for a
 * period of sending: the numbers of the former Overview (`overview.read`).
 */
export function Progress() {
  const [period, setPeriod] = useUrlFilters({ since: "", until: "" });
  const overview = useFresh<Overview | null>(
    `/overview?${new URLSearchParams(Object.entries(period).filter(([, value]) => value))}`,
    null,
    ["applications", "jobs"],
  );
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
            onChange={(event) => setPeriod({ since: event.target.value })}
          />
        </label>
        <label className="toggle">
          <span className="muted">Through</span>
          <input
            className="input"
            type="date"
            value={period.until}
            min={period.since || undefined}
            onChange={(event) => setPeriod({ until: event.target.value })}
          />
        </label>
        <Button
          size="sm"
          variant="quiet"
          disabled={!ranged}
          onClick={() => setPeriod({ since: "", until: "" })}
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
                      {[
                        "Reached",
                        "Waiting there",
                        "Rejected",
                        "No reply",
                        "Not pursued",
                      ].map((name) => (
                        <th scope="col" className="right" key={name}>
                          {name}
                        </th>
                      ))}
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
                        <td className="right" data-label="Rejected">
                          {closed(step, "rejected")}
                        </td>
                        <td className="right" data-label="No reply">
                          {closed(step, "no_response")}
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
