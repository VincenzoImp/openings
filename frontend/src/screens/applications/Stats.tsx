import { ChartNoAxesColumn } from "lucide-react";
import { formatNumber } from "../../ui/format";
import { EmptyState, Skeleton } from "../../ui/Page";
import { Table } from "../../ui/Table";
import { useStats, type Period } from "./data";

export const PERIODS: { value: Period; label: string }[] = [
  { value: "90d", label: "90 days" },
  { value: "12m", label: "12 months" },
  { value: "all", label: "All time" },
];

const rate = (value?: number | null) =>
  value == null ? "—" : `${Math.round(value * 100)}%`;

const FUNNEL: Record<string, string> = {
  applied: "Applied",
  replied: "Replied",
  interview: "Interview",
  offer: "Offer",
};

/**
 * How employers answered the applications sent in a period: four numbers,
 * the funnel from Applied to Offer, and replies by source when the server
 * has enough of them. Nothing is withheld cell by cell.
 */
export function StatsView({ period }: { period: Period }) {
  const stats = useStats(period);
  const data = stats.data;
  if (stats.isError)
    return (
      <EmptyState icon={ChartNoAxesColumn} title="Stats could not be read">
        Check the connection; they are read again on their own.
      </EmptyState>
    );
  if (!data)
    return (
      <div className="ap-stats" role="status" aria-label="Loading">
        <div className="ap-numbers">
          {[0, 1, 2, 3].map((index) => (
            <div className="ap-number" key={index}>
              <Skeleton width={64} height={28} />
              <Skeleton width={96} height={10} />
            </div>
          ))}
        </div>
      </div>
    );
  if (!data.applied)
    return (
      <EmptyState icon={ChartNoAxesColumn} title="Nothing sent in this period">
        Stats count the applications you marked applied. Choose a longer period,
        or send one first.
      </EmptyState>
    );
  const funnel = data.funnel.map((step) => ({
    stage: String(step.stage),
    count: Number(step.count) || 0,
  }));
  const most = Math.max(1, ...funnel.map((step) => step.count));
  const numbers = [
    { label: "Applied", value: formatNumber(data.applied) },
    { label: "Reply rate", value: rate(data.reply_rate) },
    { label: "Interview rate", value: rate(data.interview_rate) },
    {
      label: "Median days to a reply",
      value:
        data.median_days_to_reply == null
          ? "—"
          : formatNumber(data.median_days_to_reply),
    },
  ];
  const sources = (data.by_source ?? []).map((row) => ({
    source: String(row.source),
    applied: Number(row.applied) || 0,
    replied: Number(row.replied) || 0,
    rate: row.reply_rate as number | null,
  }));
  return (
    <div className="ap-stats">
      <dl className="ap-numbers">
        {numbers.map((item) => (
          <div className="ap-number" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      <section aria-labelledby="ap-funnel-title">
        <h2 className="ap-section-title" id="ap-funnel-title">
          From applied to offer
        </h2>
        <ol className="ap-funnel" aria-label="Funnel">
          {funnel.map((step) => (
            <li key={step.stage}>
              <span className="ap-funnel-label">
                {FUNNEL[step.stage] ?? step.stage}
              </span>
              <span className="ap-funnel-track" aria-hidden="true">
                <span
                  className="ap-funnel-bar"
                  style={{ width: `${(step.count / most) * 100}%` }}
                />
              </span>
              <span className="ap-funnel-count">
                {formatNumber(step.count)}
              </span>
            </li>
          ))}
        </ol>
      </section>
      {sources.length > 0 && (
        <section aria-labelledby="ap-sources-title">
          <h2 className="ap-section-title" id="ap-sources-title">
            Replies by source
          </h2>
          <Table
            caption="Replies by source"
            rowKey={(row) => row.source}
            rows={sources}
            columns={[
              { key: "source", label: "Source", value: (row) => row.source },
              {
                key: "applied",
                label: "Applied",
                numeric: true,
                value: (row) => formatNumber(row.applied),
              },
              {
                key: "replied",
                label: "Replied",
                numeric: true,
                value: (row) => formatNumber(row.replied),
              },
              {
                key: "rate",
                label: "Reply rate",
                numeric: true,
                value: (row) => rate(row.rate),
              },
            ]}
          />
        </section>
      )}
    </div>
  );
}
