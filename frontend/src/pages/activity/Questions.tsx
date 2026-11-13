import { useEffect, useRef } from "react";
import type { ListResult, OwnerQuestion } from "../../api";
import { Card, EmptyState, ErrorBanner, Loading } from "../../design";
import { Pager } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useUrlState } from "../../state";
import { QuestionItem } from "./QuestionItem";
import { useAct, type Links } from "./records";

const PAGE = 10;
const NONE: ListResult<OwnerQuestion> = { items: [], total: 0 };
type State = OwnerQuestion["state"];
const words: Record<State, { title: string; empty: string; hint: string }> = {
  open: {
    title: "Open",
    empty: "No open questions",
    hint: "When your agent needs a fact or a decision from you, it asks here and goes on with the rest.",
  },
  answered: {
    title: "Answered",
    empty: "No answers yet",
    hint: "Your answers stay here with the day you gave them.",
  },
  withdrawn: {
    title: "Withdrawn",
    empty: "No withdrawn questions",
    hint: "A question that no longer needs an answer is kept here.",
  },
};

/** The questions in one state, with their own pages. */
function QuestionList({
  state,
  focus,
  ...links
}: Links & { state: State; focus: boolean }) {
  // The open list keeps the `offset` of earlier links; the others have their own.
  const [offset, setOffset] = useUrlState(
    state === "open" ? "offset" : state,
    "0",
  );
  const list = useFresh(
    `/questions?state=${state}&limit=${PAGE}&offset=${Number(offset) || 0}`,
    NONE,
    ["questions"],
  );
  const { act, busy } = useAct(list.reload);
  const card = useRef<HTMLElement>(null);
  // `#activity?state=answered` (a link of an earlier version) shows that list.
  useEffect(() => {
    if (focus) card.current?.scrollIntoView({ block: "start" });
  }, [focus]);
  const { title, empty, hint } = words[state];
  return (
    <Card
      ref={card}
      className={state === "answered" ? "detail block" : "detail"}
      title={title}
      count={state === "open" ? list.data.total : undefined}
      actions={
        state !== "open" && (
          <span className="caption num">{list.data.total}</span>
        )
      }
    >
      {list.error ? (
        <div className="body">
          <ErrorBanner message={list.error} retry={list.reload} />
        </div>
      ) : list.loading ? (
        <Loading label="Loading questions…" />
      ) : list.data.items.length ? (
        list.data.items.map((question) => (
          <QuestionItem
            key={question.id}
            question={question}
            act={act}
            busy={busy}
            canWithdraw
            onAnswered={(id) =>
              list.setData((current) => ({
                items: current.items.filter((item) => item.id !== id),
                total: Math.max(0, current.total - 1),
              }))
            }
            {...links}
          />
        ))
      ) : (
        <EmptyState title={empty}>{hint}</EmptyState>
      )}
      <Pager
        offset={Number(offset) || 0}
        total={list.data.total}
        limit={PAGE}
        onChange={(value) => setOffset(String(value))}
        label={`${title} question pages`}
      />
    </Card>
  );
}

/** Questions for the owner: open ones to answer, and what became of the others. */
export function Questions(links: Links) {
  const [state] = useUrlState("state", "open");
  return (
    <div className="cols">
      <QuestionList state="open" focus={false} {...links} />
      <div>
        <QuestionList
          state="answered"
          focus={state === "answered"}
          {...links}
        />
        <QuestionList
          state="withdrawn"
          focus={state === "withdrawn"}
          {...links}
        />
      </div>
    </div>
  );
}
