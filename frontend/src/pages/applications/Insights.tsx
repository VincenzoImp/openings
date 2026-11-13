import type { InsightMetrics, Insights as Report } from "../../api";
import {
  Card,
  ErrorBanner,
  Loading,
  RateBar,
  SegmentedControl,
  Stat,
  Stats,
  percent,
} from "../../design";
import { plural } from "../../library/common";
import { dayBefore } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useUrlState } from "../../state";
import { CloseNoReply } from "./CloseNoReply";
import { InsightTable } from "./InsightTable";
import { Progress } from "./Progress";

const SCOPES = ["applications", "jobs", "settings"];

/** "34%"; a dash when the sample is too small for a rate. */
const rateOf = (rate: number | null) => (rate === null ? "–" : percent(rate));
/** "11 of 32", and why a rate is missing. */
const ofSent = (count: number, sent: number, rate: number | null) =>
  `${count} of ${sent}${rate === null ? " · too few to show a rate" : ""}`;

function Overall({ data, min }: { data: InsightMetrics; min: number }) {
  const median = data.median_days_to_response;
  return (
    <Stats>
      <Stat label="Applications sent" value={data.sent} />
      <Stat
        label="Got an answer"
        value={rateOf(data.response_rate)}
        note={ofSent(data.responded, data.sent, data.response_rate)}
      />
      <Stat
        label="Led to an interview"
        value={rateOf(data.interview_rate)}
        note={ofSent(data.interviews, data.sent, data.interview_rate)}
      />
      <Stat label="Offers" value={data.offers} />
      <Stat
        label="Median time to an answer"
        value={median === null ? "–" : plural(Math.round(median), "day")}
        note={
          median === null
            ? `Shown from ${min} dated answers`
            : `From ${plural(data.timed, "dated answer")}`
        }
      />
      <Stat label="Closed as no reply" value={data.no_reply} />
    </Stats>
  );
}

/**
 * How employers answered the applications the owner sent: rates overall and
 * by role family, source, location, month and seniority, with the time to an
 * answer and the applications that still wait.
 */
export function Insights() {
  const [period, setPeriod] = useUrlState("period", "all");
  const recent = period === "90";
  const report = useFresh<Report | null>(
    "/insights" + (recent ? "?applied_since=" + dayBefore(90) : ""),
    null,
    SCOPES,
  );
  const data = report.data;
  return (
    <div className="stack insight">
      <div className="spread wrap">
        <p className="muted measure">
          Only employer answers count. Applications you never sent and jobs your
          agent dismissed are left out. A rate is shown from{" "}
          {plural(data?.min_sample ?? 5, "sent application")}.
        </p>
        <SegmentedControl
          label="Period"
          value={recent ? "90" : "all"}
          onChange={(value) => setPeriod(value === "90" ? "90" : "all")}
          options={[
            { id: "90", label: "Last 90 days" },
            { id: "all", label: "All time" },
          ]}
        />
      </div>
      {report.error ? (
        <ErrorBanner message={report.error} retry={report.reload} />
      ) : report.loading || !data ? (
        <Loading label="Loading insights…" />
      ) : (
        <>
          <div className="tiles">
            <Overall data={data.overall} min={data.min_sample} />
          </div>
          {(data.excluded.shortlisted > 0 ||
            data.excluded.closed_unsent > 0) && (
            <p className="caption">
              Not counted:{" "}
              {plural(data.excluded.shortlisted, "shortlisted application")} not
              sent yet and {plural(data.excluded.closed_unsent, "application")}{" "}
              closed without being sent.
            </p>
          )}
          <div className="insight-grid">
            <InsightTable
              title="By role family"
              name="Role family"
              groups={data.groups.role_family}
            />
            <InsightTable
              title="By source"
              name="Source"
              groups={data.groups.source}
            />
            <InsightTable
              title="By location"
              name="Location"
              groups={data.groups.location}
            />
            <TimeToAnswer data={data} />
            <InsightTable
              title="By month sent"
              name="Month"
              groups={data.groups.month}
            />
            <InsightTable
              title="By seniority"
              name="Seniority in the title"
              groups={data.groups.seniority}
            />
          </div>
        </>
      )}
      <Progress />
    </div>
  );
}

/** How long answered applications waited, and the ones still waiting. */
function TimeToAnswer({ data }: { data: Report }) {
  const answered = data.overall.timed;
  const waiting = data.overall.waiting;
  const due = data.no_reply.overdue ?? 0;
  return (
    <Card
      title="Time to an answer"
      actions={
        <span className="caption">{plural(answered, "dated answer")}</span>
      }
      footer={
        waiting > 0 ? (
          <>
            <span className="grow">
              {plural(waiting, "application")} still{" "}
              {waiting === 1 ? "waits" : "wait"}
              {due
                ? `; ${due} of them for more than ${data.no_reply.days} days, when an answer is unlikely.`
                : "."}
            </span>
            <CloseNoReply due={due} days={data.no_reply.days} />
          </>
        ) : undefined
      }
    >
      <div className="datatable-wrap">
        <table className="datatable stack num">
          <thead>
            <tr>
              <th scope="col">Answered</th>
              <th scope="col" className="right">
                Applications
              </th>
              <th scope="col">Share of answers</th>
            </tr>
          </thead>
          <tbody>
            {data.time_to_response.map((row) => (
              <tr key={row.key}>
                <td className="primary">{row.label}</td>
                <td className="right" data-label="Applications">
                  {row.count}
                </td>
                <td data-label="Share">
                  {row.share === null ? (
                    <span className="meta">
                      Too few answers to show a share
                    </span>
                  ) : (
                    <RateBar rate={row.share} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.overall.undated > 0 && (
        <p className="body caption">
          {plural(data.overall.undated, "answer")} without a sent date{" "}
          {data.overall.undated === 1 ? "is" : "are"} not timed.
        </p>
      )}
    </Card>
  );
}
