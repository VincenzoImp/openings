import type { ReactNode } from "react";
import {
  Bookmark,
  Layers,
  RotateCcw,
  TriangleAlert,
  EyeOff,
  X,
} from "lucide-react";
import { Dot, ToneText } from "../../ui/Badge";
import { Kbd } from "../../ui/Button";
import { formatDate, formatDay, formatFull } from "../../ui/format";
import { Icon, STAGES, StatusGlyph, type Stage } from "../../ui/Icon";
import {
  List,
  ListGroup,
  ListRow,
  ListRows,
  type RowAction,
  type Selection,
} from "../../ui/List";
import {
  SIGNAL_TIPS,
  actorPhrase,
  closesSoon,
  deadlineOf,
  groupRows,
  rowSignal,
  sourceLabel,
  type JobSummary,
  type View,
} from "./model";

const SIGNAL_ICONS = {
  unlisted: EyeOff,
  duplicate: Layers,
  incomplete: TriangleAlert,
};

export interface RowHandlers {
  shortlist: (job: JobSummary) => void;
  dismiss: (job: JobSummary) => void;
  restore: (job: JobSummary) => void;
}

const LABELS = {
  new: "Jobs to review",
  dismissed: "Dismissed jobs",
  all: "All jobs",
};

const stageOf = (job: JobSummary): Stage | null => {
  const status = job.application?.status;
  return status && status in STAGES ? (status as Stage) : null;
};

/** The one trailing value of a row: a deadline, a stage, or when. */
function Meta({ job, view }: { job: JobSummary; view: View }) {
  if (view.section === "dismissed" && job.dismissal?.at)
    return (
      <time dateTime={job.dismissal.at} title={formatFull(job.dismissal.at)}>
        {formatDate(job.dismissal.at)}
      </time>
    );
  const stage = view.section === "all" ? stageOf(job) : null;
  if (stage) return <span>{STAGES[stage]}</span>;
  if (view.section === "all" && job.triage === "dismissed")
    return <span>Dismissed</span>;
  const deadline = deadlineOf(job.metadata);
  if (deadline && closesSoon(deadline))
    return <ToneText tone="warning">Closes {formatDay(deadline)}</ToneText>;
  const signal = rowSignal(job);
  return (
    <>
      {signal && (
        <span
          className="jobs-signal"
          data-tone={signal === "incomplete" ? "warning" : undefined}
          role="img"
          aria-label={SIGNAL_TIPS[signal]}
          title={SIGNAL_TIPS[signal]}
        >
          <Icon icon={SIGNAL_ICONS[signal]} size="sm" />
        </span>
      )}
      <time dateTime={job.created_at} title={formatFull(job.created_at)}>
        {formatDate(job.created_at)}
      </time>
    </>
  );
}

/** The second line: company · place · source, or who dismissed it and why. */
function subLine(job: JobSummary, view: View) {
  if (job.triage === "dismissed" && view.section === "dismissed") {
    const by = actorPhrase(job.dismissal?.by);
    const reason = job.dismissal?.reason;
    return [job.company, [by, reason].filter(Boolean).join(": ")]
      .filter(Boolean)
      .join(" · ");
  }
  return [job.company, job.location, sourceLabel(job)]
    .filter(Boolean)
    .join(" · ");
}

/** The actions a row offers on hover and by swipe, by its state. */
export function rowActions(
  job: JobSummary,
  on: RowHandlers,
): { actions: RowAction[]; swipe?: { left?: RowAction; right?: RowAction } } {
  if (job.triage === "new") {
    const shortlist: RowAction = {
      label: "Shortlist",
      icon: Bookmark,
      shortcut: "S",
      onClick: () => on.shortlist(job),
    };
    const dismiss: RowAction = {
      label: "Dismiss",
      icon: X,
      shortcut: "D",
      onClick: () => on.dismiss(job),
    };
    return {
      actions: [shortlist, dismiss],
      swipe: { right: shortlist, left: dismiss },
    };
  }
  if (job.triage === "dismissed") {
    const restore: RowAction = {
      label: "Restore",
      icon: RotateCcw,
      shortcut: "R",
      onClick: () => on.restore(job),
    };
    return { actions: [restore], swipe: { right: restore } };
  }
  return { actions: [] };
}

/**
 * The jobs of a tab under day headers. Two lines per row; actions appear on
 * hover, focus or selection, and on a phone as swipes.
 */
export function JobList({
  view,
  rows,
  activeId,
  onActiveChange,
  onOpen,
  selection,
  seen,
  on,
  footer,
}: {
  view: View;
  rows: JobSummary[];
  activeId: string;
  onActiveChange: (id: string) => void;
  onOpen: (id: string) => void;
  selection: Selection;
  seen: ReadonlySet<string>;
  on: RowHandlers;
  footer?: ReactNode;
}) {
  const groups = groupRows(rows, view);
  const row = (job: JobSummary) => {
    const stage = view.section === "all" ? stageOf(job) : null;
    const { actions, swipe } = rowActions(job, on);
    return (
      <ListRow
        key={job.id}
        id={job.id}
        leading={
          stage ? (
            <StatusGlyph stage={stage} />
          ) : view.section === "new" ? (
            <Dot hidden={seen.has(job.id)} label="Not opened yet" />
          ) : undefined
        }
        title={job.title || "Untitled role"}
        sub={subLine(job, view)}
        meta={<Meta job={job} view={view} />}
        actions={actions}
        swipe={swipe}
      />
    );
  };
  return (
    <div className="jobs-list">
      <List
        label={LABELS[view.section]}
        activeId={activeId || null}
        onActiveChange={onActiveChange}
        onOpen={onOpen}
        selection={selection}
      >
        {groups.map((group) =>
          group.label ? (
            <ListGroup
              key={group.label}
              label={group.label}
              count={group.rows.length}
            >
              {group.rows.map(row)}
            </ListGroup>
          ) : (
            <ListRows key="rows">{group.rows.map(row)}</ListRows>
          ),
        )}
      </List>
      {footer}
      <p className="jobs-hint" aria-hidden="true">
        <Kbd>j</Kbd> <Kbd>k</Kbd>
        {view.section === "dismissed" ? (
          <>
            {" "}
            · <Kbd>r</Kbd> restore
          </>
        ) : (
          <>
            {" "}
            · <Kbd>s</Kbd> shortlist · <Kbd>d</Kbd> dismiss
          </>
        )}{" "}
        · <Kbd>z</Kbd> undo · <Kbd>x</Kbd> select
      </p>
    </div>
  );
}
