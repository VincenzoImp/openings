import type { ListResult, Run } from "../../api";
import {
  ActorChip,
  Card,
  Chips,
  EmptyState,
  ErrorBanner,
  List,
  ListRow,
  Loading,
  Split,
} from "../../design";
import { Pager, plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useUrlState } from "../../state";
import { RunReport } from "./RunReport";
import { RunStatusTag } from "./RunTag";
import type { Links } from "./records";
import { countsLine, runWhen } from "./wording";

const PAGE = 10;
const NONE: ListResult<Run> = { items: [], total: 0 };

const REQUEST_KINDS = [
  "request_taken",
  "request_completed",
  "request_declined",
];
/**
 * What a run changed, asked and handled, in one line. Questions and requests
 * are added only when the counts of changes do not already name them.
 */
function runCounts(run: Run) {
  const counts = run.change_counts || {};
  return [
    run.changes_total ? countsLine(counts, 3) : "No change",
    run.questions_count && !counts.question_asked
      ? plural(run.questions_count, "question")
      : "",
    run.requests_count && !REQUEST_KINDS.some((kind) => counts[kind])
      ? plural(run.requests_count, "request")
      : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** Agent runs beside the report of the selected one. */
export function Runs({
  run,
  onRun,
  autoFocus,
  ...links
}: Links & {
  /** The run whose report is shown; empty for the newest one. */
  run: string;
  onRun: (id: string) => void;
  /** Move focus to the report: the owner just opened it. */
  autoFocus: boolean;
}) {
  const [status, setStatus] = useUrlState("status", ""),
    [offset, setOffset] = useUrlState("offset", "0");
  const list = useFresh(
    `/runs?limit=${PAGE}&offset=${Number(offset) || 0}${status ? "&status=" + status : ""}`,
    NONE,
    ["runs"],
  );
  // Without a chosen run, wide screens show the report of the newest one.
  const selected = run || list.data.items[0]?.id || "";
  return (
    <Split
      columns="minmax(0, 1fr) minmax(0, 1.1fr)"
      labels={["Runs", "Report"]}
      pane={run ? 1 : 0}
      onPane={(pane) => onRun(pane ? selected : "")}
    >
      <Card>
        <div className="filters">
          <Chips
            label="Status"
            value={status}
            onChange={(next) => {
              setOffset("0");
              setStatus(next);
            }}
            options={[
              { id: "", label: "All" },
              { id: "open", label: "In progress" },
              { id: "finished", label: "Finished" },
              { id: "interrupted", label: "Interrupted" },
            ]}
          />
        </div>
        {list.error ? (
          <div className="body">
            <ErrorBanner message={list.error} retry={list.reload} />
          </div>
        ) : list.loading ? (
          <Loading label="Loading runs…" />
        ) : list.data.items.length ? (
          <List label="Agent runs">
            {list.data.items.map((item) => (
              <ListRow
                key={item.id}
                title={item.workflow}
                onOpen={() => onRun(item.id)}
                selected={item.id === selected}
                meta={
                  <>
                    {runWhen(item)}
                    {item.scope && ` · ${item.scope}`}
                    <br />
                    {runCounts(item)}
                  </>
                }
                foot={<ActorChip actor={item.actor} />}
              >
                <RunStatusTag run={item} />
              </ListRow>
            ))}
          </List>
        ) : (
          <EmptyState title={status ? "No runs in this state" : "No runs yet"}>
            {status
              ? "Choose another status to see the other runs."
              : "A run appears here when an agent opens one for a workflow. Its report and the changes it made stay readable afterwards."}
          </EmptyState>
        )}
        <Pager
          offset={Number(offset) || 0}
          total={list.data.total}
          limit={PAGE}
          onChange={(value) => setOffset(String(value))}
          label="Run pages"
        />
      </Card>
      {selected ? (
        <RunReport
          key={selected}
          id={selected}
          autoFocus={autoFocus && Boolean(run)}
          {...links}
        />
      ) : (
        <Card className="detail">
          <EmptyState title="No report to show">
            Choose a run to read what it did, what it left undone and why.
          </EmptyState>
        </Card>
      )}
    </Split>
  );
}
