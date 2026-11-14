import type { MouseEvent } from "react";
import type { Job } from "../../api";
import { Button, Tag, cx } from "../../design";
import {
  dismissalLine,
  foundLine,
  placeTag,
  signalTags,
  type Label,
  type Section,
} from "./model";

/** The address of a job selected in the current tab, keeping its filters. */
export function jobHref(id: string) {
  const [page, query = ""] = location.hash.split("?");
  const params = new URLSearchParams(query);
  params.set("job", id);
  return `${page.startsWith("#jobs") ? page : "#jobs"}?${params}`;
}
/** A plain click is handled in place; one that opens a new tab is left alone. */
export const plainClick = (event: MouseEvent) =>
  event.button === 0 &&
  !event.metaKey &&
  !event.ctrlKey &&
  !event.shiftKey &&
  !event.altKey;

export function Tags({ items }: { items: Label[] }) {
  if (!items.length) return null;
  return (
    <span className="tags">
      {items.map((item) => (
        <Tag key={item.text} tone={item.tone}>
          {item.text}
        </Tag>
      ))}
    </span>
  );
}

export type RowAction = "saved" | "dismissed" | "inbox" | "start";

/** One job of a list: its signals, where it came from, and the actions of its tab. */
export function JobRow({
  job,
  section,
  selected,
  current,
  disabled,
  own,
  busy,
  onSelect,
  onCheck,
  onAction,
}: {
  job: Job;
  section: Section;
  /** Picked for a bulk action. */
  selected: boolean;
  /** Shown beside the list. */
  current: boolean;
  /** The selection is full. */
  disabled: boolean;
  own: Set<string> | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onCheck: (checked: boolean) => void;
  onAction: (action: RowAction) => void;
}) {
  const title = job.title || "Untitled role";
  const name = (
    <span className="sr">
      {" "}
      {title}, {job.company}
    </span>
  );
  const tags = [
    ...(section === "all" ? [placeTag(job)] : []),
    ...signalTags(job, { own }),
  ];
  return (
    <li
      className={cx("job", current && "is-selected", selected && "is-checked")}
      aria-current={current || undefined}
    >
      <span className="check">
        <input
          type="checkbox"
          aria-label={`Select ${title}, ${job.company}`}
          checked={selected}
          disabled={disabled && !selected}
          onChange={(event) => onCheck(event.target.checked)}
        />
      </span>
      <div className="grow">
        <a
          className="title"
          href={jobHref(job.id)}
          onClick={(event) => {
            if (!plainClick(event)) return;
            event.preventDefault();
            onSelect(job.id);
          }}
        >
          {title}
        </a>
        <div className="meta">
          {[job.company, job.location].filter(Boolean).join(" · ")}
        </div>
        <Tags items={tags} />
        {section === "dismissed" && job.dismissal ? (
          <>
            <div className="caption">{dismissalLine(job)}</div>
            {job.dismissal.reason && (
              <div className="meta reason">{job.dismissal.reason}</div>
            )}
          </>
        ) : (
          <div className="caption">{foundLine(job)}</div>
        )}
      </div>
      {section !== "all" && (
        <div className="row row-actions">
          {section === "review" && (
            <>
              <Button
                size="sm"
                disabled={busy}
                onClick={() => onAction("saved")}
              >
                Shortlist{name}
              </Button>
              <Button
                size="sm"
                variant="quiet"
                disabled={busy}
                onClick={() => onAction("dismissed")}
              >
                Dismiss{name}
              </Button>
            </>
          )}
          {section === "shortlist" && (
            <>
              <Button
                size="sm"
                disabled={busy}
                onClick={() => onAction("start")}
              >
                Start application{name}
              </Button>
              <Button
                size="sm"
                variant="quiet"
                disabled={busy}
                onClick={() => onAction("inbox")}
              >
                Remove{name}
              </Button>
            </>
          )}
          {section === "dismissed" && (
            <Button
              size="sm"
              disabled={busy}
              onClick={() =>
                onAction(job.application_count ? "saved" : "inbox")
              }
            >
              Restore{name}
            </Button>
          )}
        </div>
      )}
    </li>
  );
}
