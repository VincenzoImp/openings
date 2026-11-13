import type { Application, ListResult } from "../../api";
import { Card, EmptyState, List, ListRow, Tag, cx } from "../../design";
import { Loaded, plural } from "../../library/common";
import { deadlineTag } from "../../library/time";
import type { Fresh } from "../../library/useFresh";

export const READY_QUEUE = "#applications?readiness=ready&sort=ready&view=list";
/** The page of an application. Stage 3 replaces it with the review screen. */
export const applicationHref = (id: string, detail = "") =>
  `#applications?application=${id}${detail ? "&detail=" + detail : ""}`;

/** The Ready queue: closest deadline first, then priority; the first row is the one to act on. */
export function Ready({ list }: { list: Fresh<ListResult<Application>> }) {
  const settled = !list.loading && !list.error;
  return (
    <Card
      title="Ready to apply"
      count={settled ? list.data.total : undefined}
      actions={
        <a className="btn quiet sm" href="#applications">
          All applications
        </a>
      }
    >
      <Loaded from={list} label="Loading ready applications…">
        {({ items, total }) =>
          items.length ? (
            <List label="Ready applications">
              {items.map((application, index) => {
                const deadline = deadlineTag(application.deadline);
                const title = application.job?.title || "Untitled role";
                return (
                  <ListRow
                    key={application.id}
                    title={title}
                    href={applicationHref(application.id)}
                    meta={[application.job?.company, application.job?.location]
                      .filter(Boolean)
                      .join(" · ")}
                  >
                    {deadline && (
                      <Tag
                        tone={
                          deadline.tone === "neutral"
                            ? undefined
                            : deadline.tone
                        }
                      >
                        {deadline.text}
                      </Tag>
                    )}
                    {application.priority != null && (
                      <Tag>
                        <span className="sr">Priority </span>P
                        {application.priority}
                      </Tag>
                    )}
                    <a
                      className={cx("btn sm", index === 0 && "primary")}
                      href={applicationHref(application.id)}
                    >
                      Review<span className="sr"> {title}</span>
                    </a>
                  </ListRow>
                );
              })}
              {total > items.length && (
                <li>
                  <a className="muted" href={READY_QUEUE}>
                    {plural(total - items.length, "more ready application")}
                  </a>
                </li>
              )}
            </List>
          ) : (
            <EmptyState title="Nothing is ready to apply">
              Your agent marks an application ready when its documents are
              written, built and approved. It then appears here, closest
              deadline first.
            </EmptyState>
          )
        }
      </Loaded>
    </Card>
  );
}
