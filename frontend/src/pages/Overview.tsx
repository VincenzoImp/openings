import { date, type FunnelStep, type Overview } from "../api";
import { useResource, useUrlFilters } from "../state";
import { Button, Empty, ErrorBox, Heading, Icon, Loading } from "../ui";
import { Field } from "../ui";
const initial: Overview = {
  sent: 0,
  interviews: 0,
  offers: 0,
  active: 0,
  drafts: 0,
  inbox: 0,
  outdated: 0,
  incomplete: 0,
  funnel: [],
  activity: [],
};
const labels: Record<string, string> = {
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  accepted: "Accepted",
  waiting: "Waiting",
  rejected: "Not selected",
  not_pursued: "Not pursued",
};
const colors: Record<string, string> = {
  applied: "#8e9fb4",
  interview: "#a89bb4",
  offer: "#c3a570",
  accepted: "#8b9c7b",
  waiting: "#aab4b1",
  rejected: "#b69488",
  not_pursued: "#b7ab9b",
};
function band(x1: number, y1: number, x2: number, y2: number, height: number) {
  const mid = (x1 + x2) / 2;
  return `M${x1},${y1}C${mid},${y1} ${mid},${y2} ${x2},${y2}v${height}C${mid},${y2 + height} ${mid},${y1 + height} ${x1},${y1 + height}Z`;
}
export function Funnel({ steps }: { steps: FunnelStep[] }) {
  if (!steps.length || !steps[0].count)
    return (
      <Empty title="Your journey starts here.">
        Once you record a submitted application, its progress will appear in
        this view.
      </Empty>
    );
  const accepted = steps.reduce((n, s) => n + (s.outcomes.accepted || 0), 0),
    nodes = [...steps, { stage: "accepted", count: accepted, outcomes: {} }],
    unit = Math.min(22, 155 / Math.max(1, steps[0].count)),
    height = Math.max(
      390,
      ...steps.map(
        (step) =>
          282 +
          Object.entries(step.outcomes)
            .filter(([key, count]) => key !== "accepted" && count > 0)
            .reduce(
              (sum, [, count]) => sum + Math.max(count * unit, 18) + 18,
              0,
            ),
      ),
    ),
    width = 1100,
    x = (i: number) => 48 + (i * (width - 110)) / (nodes.length - 1),
    y = 112;
  return (
    <>
      <div className="funnel-wrap">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Application journey: ${steps.map((s) => `${s.count} ${labels[s.stage] || s.stage}`).join(", ")}, ${accepted} accepted.`}
          className="funnel-svg"
        >
          <title>Application journey based on recorded history</title>
          {nodes.map((node, i) => (
            <g key={node.stage}>
              <text
                className="node-label"
                x={x(i)}
                y={48}
                fill="currentColor"
                fontSize="14"
              >
                {labels[node.stage] || node.stage}
              </text>
              <text
                className="node-count"
                x={x(i)}
                y={79}
                fill="currentColor"
                fontSize="25"
                fontFamily="Georgia, serif"
              >
                {node.count}
              </text>
              <rect
                x={x(i)}
                y={y}
                width="5"
                height={Math.max(node.count ? 2 : 0, node.count * unit)}
                rx="2"
                fill={colors[node.stage] || colors.waiting}
              />
            </g>
          ))}
          {steps.map((step, i) => {
            const next = Math.min(step.count, nodes[i + 1].count),
              stops = Object.entries(step.outcomes).filter(
                ([key, count]) => key !== "accepted" && count > 0,
              );
            let offset = next * unit,
              sinkY = 270;
            return (
              <g key={step.stage}>
                {next > 0 && (
                  <path
                    d={band(x(i) + 5, y, x(i + 1), y, next * unit)}
                    fill={colors[nodes[i + 1].stage]}
                    opacity=".28"
                  />
                )}
                {stops.map(([key, count]) => {
                  const from = y + offset,
                    h = count * unit;
                  offset += h;
                  const dest = sinkY;
                  sinkY += Math.max(h, 18) + 18;
                  return (
                    <g key={key}>
                      <path
                        d={band(x(i) + 5, from, x(i) + 210, dest, h)}
                        fill={colors[key] || colors.waiting}
                        opacity=".22"
                      />
                      <rect
                        x={x(i) + 210}
                        y={dest}
                        width="5"
                        height={h}
                        rx="2"
                        fill={colors[key] || colors.waiting}
                      />
                      <text
                        x={x(i) + 225}
                        y={dest + Math.max(13, h / 2 + 4)}
                        fill="currentColor"
                        fontSize="12"
                      >
                        {count} {labels[key]?.toLowerCase() || key}
                      </text>
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="funnel-scroll-hint">
        Scroll horizontally to explore the full journey.
      </p>
      <div className="funnel-legend">
        {nodes.map((n) => (
          <span key={n.stage}>
            <i style={{ background: colors[n.stage] }} />
            {labels[n.stage] || n.stage}
          </span>
        ))}
      </div>
      <details className="funnel-table">
        <summary>View counts as a table</summary>
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Stage</th>
              <th scope="col">Reached</th>
              <th scope="col">Waiting</th>
              <th scope="col">Closed</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((s) => (
              <tr key={s.stage}>
                <td>{labels[s.stage] || s.stage}</td>
                <td>{s.count}</td>
                <td>{s.outcomes.waiting || 0}</td>
                <td>
                  {Object.entries(s.outcomes)
                    .filter(([k]) => k !== "waiting")
                    .reduce((n, [, v]) => n + v, 0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
export default function OverviewPage({
  onAdd,
  onNavigate,
}: {
  onAdd: () => void;
  onNavigate: (page: string) => void;
}) {
  const [period, setPeriod] = useUrlFilters({ since: "", until: "" });
  const { data, loading, error, reload } = useResource<Overview>(
    `/overview?${new URLSearchParams(Object.fromEntries(Object.entries(period).filter(([, value]) => !!value)))}`,
    initial,
  );
  const attention = [
    {
      count: data.drafts,
      title: "application draft",
      plural: "application drafts",
      description: "Review the documents and decide what comes next.",
      route: "applications?status=draft",
      icon: "file" as const,
    },
    {
      count: data.outdated,
      title: "score needing an update",
      plural: "scores needing an update",
      description: "Your context changed. Nothing was rescored automatically.",
      route: "inbox?triage=active&score_state=outdated",
      icon: "refresh" as const,
    },
    {
      count: data.incomplete,
      title: "job needing the full posting",
      plural: "jobs needing the full posting",
      description: "Paste the text to complete the record.",
      route: "inbox?triage=active&complete=false",
      icon: "inbox" as const,
    },
  ].filter((a) => a.count);
  return (
    <>
      <Heading
        title="Your search, at a glance."
        description="A clear view of your opportunities and the progress you are making."
      >
        <span className="muted smalltext today">
          {new Date().toLocaleDateString("en", {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </span>
        <Button variant="primary" icon="plus" onClick={onAdd}>
          Add job
        </Button>
      </Heading>
      {error && <ErrorBox message={error} retry={reload} />}
      <div className="stats">
        {[
          [
            data.sent,
            "Applications sent",
            period.since || period.until
              ? "Selected submission period"
              : "All recorded attempts",
            "applied",
          ],
          [
            data.interviews,
            "Reached interview",
            "A conversation worth having",
            "interview",
          ],
          [
            data.offers,
            "Offers received",
            "Progress through the funnel",
            "offer",
          ],
          [data.active, "In progress", "Awaiting a next step", "draft"],
        ].map(([value, label, foot, color]) => (
          <section className="card stat" key={String(label)}>
            <div className="stat-top">
              {label}
              <i className={`dot ${color}`} />
            </div>
            <div className="stat-value">{loading ? "—" : value}</div>
            <div className="stat-foot">{foot}</div>
          </section>
        ))}
      </div>
      <section className="card">
        <div className="cardhead">
          <div>
            <h2>Your application journey</h2>
            <p>
              Where submitted applications progressed, and where they stand now.
            </p>
          </div>
          <div className="period-controls">
            <Field label="Submitted from">
              <input
                type="date"
                value={period.since}
                max={period.until || undefined}
                onChange={(e) => setPeriod({ since: e.target.value })}
              />
            </Field>
            <Field label="Through">
              <input
                type="date"
                value={period.until}
                min={period.since || undefined}
                onChange={(e) => setPeriod({ until: e.target.value })}
              />
            </Field>
            <Button
              className="small"
              onClick={() => setPeriod({ since: "", until: "" })}
            >
              All time
            </Button>
          </div>
        </div>
        {loading ? <Loading /> : <Funnel steps={data.funnel} />}
      </section>
      <div className="grid-2">
        <section className="card">
          <div className="cardhead">
            <h2>Worth a look</h2>
            <span className="tag neutral">{attention.length} items</span>
          </div>
          <div className="inner">
            {attention.length ? (
              attention.map((a) => (
                <a className="taskrow" key={a.title} href={`#${a.route}`}>
                  <span className="circle">
                    <Icon name={a.icon} />
                  </span>
                  <span className="taskcopy">
                    <strong>
                      {a.count} {a.count === 1 ? a.title : a.plural}
                    </strong>
                    <small>{a.description}</small>
                  </span>
                  <Icon name="arrow" />
                </a>
              ))
            ) : (
              <div className="quiet-state">
                <Icon name="check" />
                <p>
                  You are up to date. Add an opportunity or follow a company to
                  keep exploring.
                </p>
              </div>
            )}
          </div>
        </section>
        <section className="card">
          <div className="cardhead">
            <h2>Recent activity</h2>
            <button
              className="iconbtn"
              aria-label="View applications"
              onClick={() => onNavigate("applications")}
            >
              <Icon name="arrow" />
            </button>
          </div>
          <div className="inner">
            {data.activity?.length ? (
              data.activity.slice(0, 6).map((item, i) => (
                <article className="activity" key={item.id || i}>
                  <span className="activity-icon">
                    <Icon name="clock" />
                  </span>
                  <div>
                    <strong>
                      {item.message ||
                        item.title ||
                        (
                          item.kind ||
                          item.type ||
                          "Workspace updated"
                        ).replaceAll("_", " ")}
                    </strong>
                    <time>{date(item.created_at)}</time>
                  </div>
                </article>
              ))
            ) : (
              <p className="muted">Your workspace activity will appear here.</p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
