import type { Application, ListResult } from "../../api";
import { Card, EmptyState } from "../../design";
import { Loaded, plural } from "../../library/common";
import type { Fresh } from "../../library/useFresh";
import { CloseNoReply } from "../applications/CloseNoReply";
import { STATS } from "../applications/links";

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
  return (
    <Card
      title="Waiting for a reply"
      count={applied}
      actions={
        <a className="btn quiet sm" href={STATS}>
          Stats
        </a>
      }
    >
      <Loaded from={list} label="Loading applications…">
        {({ total }) =>
          total ? (
            <div className="body stack">
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
