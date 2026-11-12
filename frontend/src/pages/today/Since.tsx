import type { CollectionRun, ListResult, Run } from "../../api";
import {
  ActorChip,
  Card,
  EmptyState,
  ErrorBanner,
  List,
  ListRow,
  Loading,
  Tag,
} from "../../design";
import { plural } from "../../library/common";
import { dayTime } from "../../library/time";
import type { Fresh } from "../../library/useFresh";
import { RunStatusTag } from "../activity/RunTag";
import { collectedLine, collectedSince } from "./collected";
import { runDuration, runLine } from "../activity/wording";

const SYSTEM = { kind: "system" as const, name: null, label: "System" };

/** What the agent and collection did since the owner last looked at Today. */
export function Since({
  since,
  firstVisit,
  runs,
  collection,
}: {
  since: string;
  /** Nothing is remembered yet: the window is the last 7 days. */
  firstVisit: boolean;
  runs: Fresh<ListResult<Run>>;
  collection: Fresh<ListResult<CollectionRun>>;
}) {
  const collected = collectedSince(collection.data.items, since);
  const more = runs.data.total - runs.data.items.length;
  const empty = !runs.data.items.length && !collected.runs;
  return (
    <Card
      title="Since your last visit"
      actions={
        <span className="caption nowrap">
          {firstVisit ? "Last 7 days" : dayTime(since)}
        </span>
      }
      footer={
        more > 0 ? (
          <a className="btn quiet sm" href="#activity?section=runs">
            {plural(more, "more run")} in Activity
          </a>
        ) : undefined
      }
    >
      {[runs, collection].map(
        (item, index) =>
          item.error && (
            <div className="body" key={index}>
              <ErrorBanner message={item.error} retry={item.reload} />
            </div>
          ),
      )}
      {runs.loading || collection.loading ? (
        <Loading label="Loading what happened…" />
      ) : empty ? (
        !runs.error &&
        !collection.error && (
          <EmptyState title="Nothing new">
            {firstVisit
              ? "Runs of your agent and newly collected jobs appear here."
              : `No agent run and no collection since ${dayTime(since)}.`}
          </EmptyState>
        )
      ) : (
        <List label="Runs and collection">
          {runs.data.items.map((run) => (
            <ListRow
              key={run.id}
              title={run.workflow || "Unnamed run"}
              href={`#activity?section=runs&run=${run.id}`}
              meta={
                <>
                  {runLine(run).replace(/\.$/, "")} ·{" "}
                  <span className="nowrap">{runDuration(run)}</span>
                </>
              }
              foot={<ActorChip actor={run.actor} />}
            >
              <RunStatusTag run={run} />
            </ListRow>
          ))}
          {collected.runs > 0 && (
            <ListRow
              title="Collection"
              href="#collection"
              meta={collectedLine(collected)}
              foot={<ActorChip actor={SYSTEM} />}
            >
              {collected.failed.length > 0 && (
                <Tag tone="attention">Needs attention</Tag>
              )}
            </ListRow>
          )}
        </List>
      )}
    </Card>
  );
}
