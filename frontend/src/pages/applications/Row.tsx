import type { Application } from "../../api";
import { Button, Cell, GridRow, Tag, cx } from "../../design";
import { staleDetail } from "../../library/staleness";
import { dayTime } from "../../library/time";
import { reviewHref } from "./links";
import {
  awaitsAnswer,
  documentState,
  planTags,
  responseLine,
  sentLine,
  stageOf,
  stageTag,
  type Label,
} from "./model";
import { Respond } from "./Respond";

export const COLUMNS =
  "28px minmax(180px, 2fr) 92px minmax(150px, 1.3fr) minmax(130px, 1.2fr) minmax(150px, 1.4fr) 92px minmax(132px, max-content)";
export const HEAD = [
  { name: "Select", hidden: true },
  { name: "Role and company" },
  { name: "Stage" },
  { name: "Plan" },
  { name: "Documents" },
  { name: "Employer response" },
  { name: "Updated" },
  { name: "Action", hidden: true },
];

function Tags({ items }: { items: Label[] }) {
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

/** What the owner does next with this application, from its row. */
function Action({
  application,
  title,
  primary,
  asked,
  open,
  onRespond,
}: {
  application: Application;
  title: string;
  primary: boolean;
  asked: boolean;
  open: boolean;
  onRespond: () => void;
}) {
  const stage = stageOf(application);
  const name = <span className="sr"> {title}</span>;
  if (awaitsAnswer(application))
    return (
      <Button
        size="sm"
        aria-expanded={open}
        aria-controls={`respond-${application.id}`}
        onClick={onRespond}
      >
        Record response{name}
      </Button>
    );
  if (stage === "ready")
    return (
      <a
        className={cx("btn sm", primary && "primary")}
        href={reviewHref(application.id)}
      >
        Review{name}
      </a>
    );
  if (stage === "preparing" && asked)
    return (
      <a className="btn sm" href="#activity">
        Answer{name}
      </a>
    );
  if (stage === "preparing" && application.blocking_requirements)
    return (
      <a className="btn sm" href={reviewHref(application.id, "requirements")}>
        Decide{name}
      </a>
    );
  return (
    <a
      className={cx("btn sm", stage === "closed" && "quiet")}
      href={reviewHref(application.id)}
    >
      Open{name}
    </a>
  );
}

/** One application of the list, and under it the form that records a response. */
export function Row({
  application,
  selected,
  onSelect,
  disabled,
  primary,
  asked,
  open,
  onRespond,
  reload,
  days,
}: {
  application: Application;
  selected: boolean;
  onSelect: (checked: boolean) => void;
  /** The selection is full. */
  disabled: boolean;
  /** The first Ready row carries the primary action. */
  primary: boolean;
  /** The agent waits for the owner's answer to a question about it. */
  asked: boolean;
  open: boolean;
  onRespond: (open: boolean) => void;
  reload: () => void;
  /** The no-reply period in days. */
  days: number;
}) {
  const title = application.job?.title || "Untitled role";
  const company = application.job?.company || "";
  const tag = stageTag(application);
  const sent = sentLine(application);
  const response = responseLine(application, days);
  const documents = documentState(application);
  const stale = application.status === "draft" ? staleDetail(application) : "";
  return (
    <>
      <GridRow selected={selected}>
        <Cell kind="select">
          <input
            type="checkbox"
            aria-label={`Select ${title}${company ? ", " + company : ""}`}
            checked={selected}
            disabled={disabled && !selected}
            onChange={(event) => onSelect(event.target.checked)}
          />
        </Cell>
        <Cell kind="primary">
          <a className="title" href={reviewHref(application.id)}>
            {title}
          </a>
          <div className="meta">
            {[company, application.job?.location].filter(Boolean).join(" · ")}
          </div>
        </Cell>
        <Cell>
          <Tag tone={tag.tone}>{tag.text}</Tag>
        </Cell>
        {sent ? (
          <Cell className="meta">{sent}</Cell>
        ) : (
          <Cell label="Plan">
            {planTags(application).length ? (
              <Tags items={planTags(application)} />
            ) : undefined}
          </Cell>
        )}
        <Cell label="Documents">
          <span>{documents[0].text}</span>
          <Tags
            items={[
              ...documents.slice(1),
              ...(asked
                ? [{ text: "Waits for your answer", tone: "agent" as const }]
                : []),
            ]}
          />
          {stale && <div className="meta">{stale}</div>}
        </Cell>
        <Cell label="Response">
          {response.text ? (
            response.badge ? (
              <Tag tone={response.tone}>{response.text}</Tag>
            ) : (
              <span className={cx(response.quiet && "meta")}>
                {response.text}
              </span>
            )
          ) : undefined}
        </Cell>
        <Cell label="Updated" className="meta">
          {dayTime(application.updated_at || application.created_at)}
        </Cell>
        <Cell kind="actions">
          <Action
            application={application}
            title={title}
            primary={primary}
            asked={asked}
            open={open}
            onRespond={() => onRespond(!open)}
          />
        </Cell>
      </GridRow>
      {open && (
        <GridRow className="expansion" id={`respond-${application.id}`}>
          <Cell kind="full">
            <Respond
              application={application}
              reload={reload}
              onDone={() => onRespond(false)}
            />
          </Cell>
        </GridRow>
      )}
    </>
  );
}
