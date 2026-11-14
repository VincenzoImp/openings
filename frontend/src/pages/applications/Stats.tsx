import type { Stats as Report, StatsPeriod } from "../../api";
import {
  Card,
  ErrorBanner,
  Loading,
  RateBar,
  SegmentedControl,
  Stat,
  Stats as Numbers,
  percent,
} from "../../design";
import { useFresh } from "../../library/useFresh";
import { useUrlState } from "../../state";

const SCOPES = ["applications", "responses", "jobs", "settings"];

const PERIODS: { id: StatsPeriod; label: string }[] = [
  { id: "90d", label: "Last 90 days" },
  { id: "12m", label: "Last 12 months" },
  { id: "all", label: "All time" },
];

const STAGES: Record<string, string> = {
  applied: "Applied",
  replied: "Replied",
  interview: "Interview",
  offer: "Offer",
};

/** "34%"; a dash when nothing was sent. */
const rateOf = (rate: number | null) => (rate === null ? "–" : percent(rate));

/**
 * What happened to the applications the owner sent in a period: how many,
 * how many got a reply or an interview, how long a reply took, the stages
 * they reached and, when there are enough, the replies of each source.
 */
export function Stats() {
  const [stored, setPeriod] = useUrlState("period", "90d");
  const period: StatsPeriod = PERIODS.some((item) => item.id === stored)
    ? (stored as StatsPeriod)
    : "90d";
  const report = useFresh<Report | null>(
    `/stats?period=${period}`,
    null,
    SCOPES,
  );
  const data = report.data;
  return (
    <div className="stack">
      <div className="spread wrap">
        <p className="muted measure">
          Only applications you sent count; a reply is any answer from the
          employer.
        </p>
        <SegmentedControl
          label="Period"
          value={period}
          onChange={setPeriod}
          options={PERIODS}
        />
      </div>
      {report.error ? (
        <ErrorBanner message={report.error} retry={report.reload} />
      ) : report.loading || !data ? (
        <Loading label="Loading stats…" />
      ) : (
        <>
          <div className="tiles">
            <Numbers>
              <Stat label="Applied" value={data.applied} />
              <Stat
                label="Reply rate"
                value={rateOf(data.reply_rate)}
                note={`${data.replied} of ${data.applied}`}
              />
              <Stat
                label="Interview rate"
                value={rateOf(data.interview_rate)}
                note={`${data.interviews} of ${data.applied}`}
              />
              <Stat
                label="Median days to a reply"
                value={
                  data.median_days_to_reply === null
                    ? "–"
                    : String(data.median_days_to_reply)
                }
              />
            </Numbers>
          </div>
          <Card title="Funnel">
            <div className="datatable-wrap">
              <table className="datatable num" aria-label="Funnel">
                <thead>
                  <tr>
                    <th scope="col">Stage</th>
                    <th scope="col">Applications</th>
                  </tr>
                </thead>
                <tbody>
                  {data.funnel.map((step) => (
                    <tr key={step.stage}>
                      <td className="primary">
                        {STAGES[step.stage] ?? step.stage}
                      </td>
                      <td>
                        <RateBar
                          rate={data.applied ? step.count / data.applied : 0}
                          count={step.count}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          {data.by_source && (
            <Card title="Replies by source">
              <div className="datatable-wrap">
                <table
                  className="datatable stack num"
                  aria-label="Replies by source"
                >
                  <thead>
                    <tr>
                      <th scope="col">Source</th>
                      <th scope="col" className="right">
                        Applied
                      </th>
                      <th scope="col" className="right">
                        Replied
                      </th>
                      <th scope="col" className="right">
                        Reply rate
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_source.map((row) => (
                      <tr key={row.source}>
                        <td className="primary">{row.source}</td>
                        <td className="right" data-label="Applied">
                          {row.applied}
                        </td>
                        <td className="right" data-label="Replied">
                          {row.replied}
                        </td>
                        <td className="right" data-label="Reply rate">
                          {rateOf(row.reply_rate)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
          {data.applied === 0 && (
            <p className="caption">
              No application was recorded as Applied in this period. Once you
              send one, it is counted here.
            </p>
          )}
        </>
      )}
    </div>
  );
}
