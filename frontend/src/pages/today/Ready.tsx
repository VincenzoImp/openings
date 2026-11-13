import type { Application, ListResult } from "../../api";
import { Card, EmptyState, List, ListRow, Tag, cx } from "../../design";
import { Loaded, plural } from "../../library/common";
import { deadlineTag } from "../../library/time";
import type { Fresh } from "../../library/useFresh";
import { READY_QUEUE, reviewHref } from "../applications/links";

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
                    href={reviewHref(application.id)}
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
                      href={reviewHref(application.id)}
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
