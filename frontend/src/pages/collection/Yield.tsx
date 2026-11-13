import { useState } from "react";
import type { SourceYield, YieldCounts, YieldRow } from "../../api";
import {
  Banner,
  Card,
  Cell,
  ErrorBanner,
  GridRow,
  GridTable,
  Loading,
  RateBar,
  SegmentedControl,
} from "../../design";
import { plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";

const PERIODS: Record<string, number | null> = {
  "30": 30,
  "90": 90,
  all: null,
};
const DAY = 86_400_000;
// A source this busy that keeps this little costs the agent time on every run.
const NOISY_RATE = 0.02;

const since = (days: number | null) =>
  days === null
    ? ""
    : new Date(Date.now() - days * DAY).toISOString().slice(0, 10);

function dismissedLine(row: Pick<YieldRow, "dismissed" | "dismissed_by">) {
  if (!row.dismissed) return "";
  const parts = [
    [row.dismissed_by.agent, "by an agent"],
    [row.dismissed_by.owner, "by you"],
  ]
    .filter(([count]) => count)
    .map(([count, who]) => `${count} ${who}`);
  return parts.join(", ");
}

const COLUMNS =
  "minmax(200px, 2fr) 78px 78px 88px minmax(150px, 1.2fr) 70px 80px minmax(150px, 1.3fr)";
const HEAD = [
  "Source",
  "Collected",
  "To review",
  "Shortlisted",
  "Kept",
  "Applied",
  "Answers",
  "Dismissed",
];

/** The counts of one source, or of all of them, as the cells after its name. */
function Counts({
  row,
}: {
  row: YieldCounts & Pick<YieldRow, "dismissed_by" | "kept_rate">;
}) {
  return (
    <>
      <Cell label="Collected" className="num">
        {row.collected}
      </Cell>
      <Cell label="To review" className="num">
        {row.to_review}
      </Cell>
      <Cell label="Shortlisted" className="num">
        {row.shortlisted}
      </Cell>
      <Cell label="Kept">
        {row.kept_rate === null ? (
          <span className="meta">Too few jobs to judge</span>
        ) : (
          <RateBar
            rate={row.kept_rate}
            tone={row.kept_rate < NOISY_RATE ? "attention" : undefined}
          />
        )}
      </Cell>
      <Cell label="Applied" className="num">
        {row.applied}
      </Cell>
      <Cell label="Answers" className="num">
        {row.responded}
        {row.interviews > 0 && (
          <div className="meta">{plural(row.interviews, "interview")}</div>
        )}
      </Cell>
      <Cell label="Dismissed">
        {row.dismissed}
        {dismissedLine(row) && <div className="meta">{dismissedLine(row)}</div>}
      </Cell>
    </>
  );
}

function sourceLine(row: YieldRow) {
  const boards = row.providers
    .filter((provider) => provider.collected)
    .map((provider) => `${provider.label} ${provider.collected}`);
  return [
    row.kind_label,
    boards.length > 1 || row.kind === "search" ? boards.join(", ") : "",
    row.enabled === false ? "paused" : "",
    row.last_error ? "last run failed" : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * What each source brought, from collected jobs to employer answers: the
 * jobs each saved search or company board collected first, how many were
 * kept, applied to and answered, and who dismissed the rest.
 */
export function SourceYieldView() {
  const [period, setPeriod] = useState("90");
  const query = new URLSearchParams();
  const start = since(PERIODS[period]);
  if (start) query.set("since", start);
  const result = useFresh<SourceYield | null>(
    `/collection/yield?${query}`,
    null,
    ["jobs", "applications", "sources", "responses"],
  );
  const data = result.data;
  const noisy = data?.items
    .filter(
      (row) =>
        row.source_id &&
        row.kept_rate !== null &&
        row.collected >= 3 * data.min_sample &&
        row.kept_rate < NOISY_RATE,
    )
    .sort((a, b) => b.collected - a.collected)[0];
  return (
    <div className="stack">
      <div className="spread wrap">
        <p className="muted measure">
          What each source brought, from collected jobs to employer answers. A
          source that collects much and keeps little costs your agent time on
          every run. Each job counts once, for the source that found it first.
        </p>
        <SegmentedControl
          label="Period"
          value={period}
          onChange={setPeriod}
          options={[
            { id: "30", label: "30 days" },
            { id: "90", label: "90 days" },
            { id: "all", label: "All time" },
          ]}
        />
      </div>
      {noisy && (
        <Banner tone="attention" title={`“${noisy.name}” is noisy`}>
          It collected {plural(noisy.collected, "job")} and {noisy.shortlisted}{" "}
          {noisy.shortlisted === 1 ? "was" : "were"} kept. Narrow its terms or
          places, or pause it, in Sources.
        </Banner>
      )}
      <Card
        title={`Yield by source${PERIODS[period] ? `, last ${PERIODS[period]} days` : ""}`}
      >
        {result.error ? (
          <div className="body">
            <ErrorBanner message={result.error} retry={result.reload} />
          </div>
        ) : result.loading || !data ? (
          <Loading label="Counting what each source yielded…" />
        ) : (
          <GridTable
            label="Yield by source"
            columns={COLUMNS}
            className="yield-table"
            head={HEAD.map((name) => ({ name }))}
          >
            {data.items.map((row) => (
              <GridRow key={row.source_id || "none"}>
                <Cell kind="primary">
                  <span className="title">{row.name}</span>
                  <div className="meta">{sourceLine(row)}</div>
                </Cell>
                <Counts row={row} />
              </GridRow>
            ))}
            <GridRow className="total">
              <Cell kind="primary">
                <strong>Total</strong>
                <div className="meta">
                  {plural(data.total.sources, "source")} and jobs added by hand
                </div>
              </Cell>
              <Counts row={data.total} />
            </GridRow>
          </GridTable>
        )}
      </Card>
    </div>
  );
}
