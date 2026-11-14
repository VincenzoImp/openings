import { api, type Application, type ListResult } from "../../api";
import { Button, Card, EmptyState, List, ListRow } from "../../design";
import { Loaded, plural } from "../../library/common";
import type { Fresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { CloseNoReply } from "../applications/CloseNoReply";
import { INSIGHTS, reviewHref } from "../applications/links";
import { daysBetween } from "../applications/model";
import { localToday } from "../../api";

const SHOWN = 5;

/** Applications sent long ago without a recorded reply: record one, or close them as no reply. */
export function Waiting({
  list,
  applied,
  days,
}: {
  /** Applied applications past the no-reply period. */
  list: Fresh<ListResult<Application>>;
  /** Every application in Applied; undefined while it loads. */
  applied?: number;
  /** The no-reply period. */
  days: number;
}) {
  const { mutate, pending } = useWorkspace();
  const close = (application: Application) =>
    void mutate(
      () =>
        api(`/applications/${application.id}`, "PATCH", {
          expected_version: application.version,
          status: "closed",
          outcome: "no_response",
        }),
      "Closed as no reply.",
    );
  return (
    <Card
      title="Waiting for a reply"
      count={applied}
      actions={
        <a className="btn quiet sm" href={INSIGHTS}>
          Insights
        </a>
      }
    >
      <Loaded from={list} label="Loading applications…">
        {({ items, total }) =>
          total ? (
            <div className="body stack">
              <List label="Applications without a reply">
                {items.slice(0, SHOWN).map((application) => {
                  const title = application.job?.title || "Untitled role";
                  return (
                    <ListRow
                      key={application.id}
                      title={title}
                      href={reviewHref(application.id)}
                      meta={[
                        application.job?.company,
                        application.applied_at &&
                          `sent ${daysBetween(application.applied_at, localToday())} days ago`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    >
                      <Button
                        size="sm"
                        disabled={pending}
                        onClick={() => close(application)}
                      >
                        Close as no reply<span className="sr"> {title}</span>
                      </Button>
                    </ListRow>
                  );
                })}
              </List>
              <p>
                {total === 1
                  ? "1 application was"
                  : `${total} applications were`}{" "}
                sent more than {days} days ago without an answer. Record what
                happened, or close {total === 1 ? "it" : "them"} as no reply so
                your numbers stay true.
              </p>
              <div className="row">
                <a
                  className="btn sm"
                  href="#applications?stage=applied&waiting=1"
                >
                  Record replies
                </a>
                <CloseNoReply due={total} days={days} />
              </div>
            </div>
          ) : (
            <EmptyState title="No long wait">
              {applied
                ? `None of your ${plural(applied, "sent application")} has waited more than ${days} days for a reply.`
                : "Applications you sent appear here while they wait for a reply."}
            </EmptyState>
          )
        }
      </Loaded>
    </Card>
  );
}
