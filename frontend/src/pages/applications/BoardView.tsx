import type { CSSProperties } from "react";
import type { Application, ListResult } from "../../api";
import { Button, ErrorBanner, Tag } from "../../design";
import { plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { reviewHref } from "./links";
import {
  STAGES,
  listQuery,
  planTags,
  replyLine,
  type Filters,
  type StageKey,
} from "./model";

const NONE = { items: [], total: 0 };
const SCOPES = ["applications", "jobs", "documents", "files"];
const TILES = 6;

/** One stage of the board: its first applications as tiles, and a link to the rest. */
function Column({
  stage,
  filters,
  days,
  onStage,
}: {
  stage: StageKey;
  filters: Filters;
  days: number;
  onStage: (stage: StageKey) => void;
}) {
  const list = useFresh<ListResult<Application>>(
    `/applications?${listQuery({ ...filters, stage }, TILES)}`,
    NONE,
    SCOPES,
  );
  const label = STAGES.find((item) => item.id === stage)!.label;
  const rest = list.data.total - list.data.items.length;
  return (
    <section aria-label={`${label} applications`}>
      <h3>
        {label}{" "}
        <span className="muted num">
          {list.loading ? "–" : list.data.total}
        </span>
      </h3>
      {list.error && <ErrorBanner message={list.error} retry={list.reload} />}
      {list.data.items.map((application) => {
        const response = replyLine(application, days);
        const tags = [
          ...planTags(application).filter((tag) => tag.tone),
          ...(response.text && stage !== "closed" ? [response] : []),
        ];
        return (
          <a
            key={application.id}
            className="tile"
            href={reviewHref(application.id)}
          >
            <strong>{application.job?.title || "Untitled role"}</strong>
            <span className="meta muted">{application.job?.company}</span>
            {!!tags.length && (
              <span className="tags">
                {tags.map((tag) => (
                  <Tag key={tag.text} tone={tag.tone}>
                    {tag.text}
                  </Tag>
                ))}
              </span>
            )}
          </a>
        );
      })}
      {!list.loading && !list.data.total && (
        <p className="caption">Nothing in {label} now.</p>
      )}
      {rest > 0 && (
        <Button size="sm" variant="quiet" onClick={() => onStage(stage)}>
          {rest} more
          <span className="sr"> in {label}</span>
        </Button>
      )}
    </section>
  );
}

/** The open stages side by side; closed applications on request. */
export function BoardView({
  filters,
  days,
  closedCount,
  showClosed,
  onShowClosed,
  onStage,
}: {
  filters: Filters;
  days: number;
  closedCount: number;
  showClosed: boolean;
  onShowClosed: (show: boolean) => void;
  onStage: (stage: StageKey) => void;
}) {
  const stages: StageKey[] = [
    "shortlisted",
    "ready",
    "applied",
    "interview",
    "offer",
    ...(showClosed ? (["closed"] as const) : []),
  ];
  return (
    <>
      <div
        className="board"
        style={{ "--columns": stages.length } as CSSProperties}
      >
        {stages.map((stage) => (
          <Column
            key={stage}
            stage={stage}
            filters={filters}
            days={days}
            onStage={onStage}
          />
        ))}
      </div>
      <footer>
        <span className="muted grow">
          {showClosed
            ? "Closed applications are the last column."
            : `${plural(closedCount, "closed application")} ${closedCount === 1 ? "is" : "are"} not on the board.`}
        </span>
        <Button
          size="sm"
          variant="quiet"
          onClick={() => onShowClosed(!showClosed)}
        >
          {showClosed ? "Hide closed" : "Show closed"}
        </Button>
      </footer>
    </>
  );
}
