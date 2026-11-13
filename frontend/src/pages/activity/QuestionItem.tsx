import { useState } from "react";
import { api, type OwnerQuestion } from "../../api";
import { ActorChip, AnswerControls, Button, Question } from "../../design";
import { dayTime } from "../../library/time";
import { SubjectLink, type Links, type Outcome } from "./records";
import { RunLink } from "./RunTag";

export type Act = (
  call: () => Promise<unknown>,
  message: string,
) => Promise<Outcome>;

const answerOf = (question: OwnerQuestion) =>
  [question.answer_choice, question.answer].filter(Boolean).join(" · ");

/**
 * One question for the owner. Open: answered in place. Answered: the answer,
 * who gave it and when, and a way to correct it. Withdrawn: who withdrew it.
 */
export function QuestionItem({
  question,
  act,
  busy,
  onAnswered,
  canWithdraw = false,
  ...links
}: Links & {
  question: OwnerQuestion;
  act: Act;
  busy: boolean;
  /** Called once an open question is answered or withdrawn. */
  onAnswered?: (id: string) => void;
  /** Offer Withdraw beside the answer controls (Activity). */
  canWithdraw?: boolean;
}) {
  const [correcting, setCorrecting] = useState(false);
  const open = question.state === "open";
  const subject = question.subject && (
    <>
      About: <SubjectLink subject={question.subject} {...links} />
    </>
  );
  async function answer(text: string, choice?: string) {
    const outcome = await act(
      () =>
        api(`/questions/${question.id}/answer`, "POST", {
          expected_version: question.version,
          answer: text,
          ...(choice ? { choice } : {}),
        }),
      "Answer saved.",
    );
    if (outcome !== "ok") return;
    setCorrecting(false);
    if (open) onAnswered?.(question.id);
  }
  const controls = (
    <AnswerControls
      choices={question.choices}
      open={!open || !question.choices.length}
      initialText={open ? "" : question.answer}
      submitLabel={open ? "Answer" : "Save answer"}
      placeholder="Your agent reads your answer at the start of its next run."
      busy={busy}
      onAnswer={answer}
      extra={
        open && canWithdraw ? (
          <Button
            type="button"
            variant="quiet"
            size="sm"
            disabled={busy}
            onClick={async () => {
              const outcome = await act(
                () =>
                  api(`/questions/${question.id}/withdraw`, "POST", {
                    expected_version: question.version,
                  }),
                "Question withdrawn.",
              );
              if (outcome === "ok") onAnswered?.(question.id);
            }}
          >
            Withdraw
          </Button>
        ) : undefined
      }
    />
  );
  if (open)
    return (
      <Question
        ask={question.question}
        why={question.why}
        time={dayTime(question.created_at)}
        lead={
          <ActorChip
            actor={question.asked_by}
            detail={question.run_workflow || undefined}
          />
        }
        about={
          (subject || question.run_id) && (
            <>
              {subject}
              {subject && question.run_id && " · "}
              {question.run_id && (
                <RunLink id={question.run_id} label="Asked in this run" />
              )}
            </>
          )
        }
      >
        {controls}
      </Question>
    );
  const closedBy =
    question.state === "answered"
      ? question.answered_by
      : question.withdrawn_by;
  const closedAt =
    question.state === "answered"
      ? question.answered_at
      : question.withdrawn_at;
  return (
    <Question ask={question.question} small>
      {question.state === "answered" && (
        <p className="answered prose">{answerOf(question)}</p>
      )}
      <p className="caption about">
        <ActorChip actor={closedBy} />{" "}
        {question.state === "answered" ? "answered" : "withdrew it"} ·{" "}
        {dayTime(closedAt)}
        {question.subject && (
          <>
            {" · about "}
            <SubjectLink subject={question.subject} {...links} />
          </>
        )}
        {question.run_id && (
          <>
            {" · asked by "}
            {question.asked_by.label} in <RunLink id={question.run_id} />
          </>
        )}
      </p>
      {question.state === "answered" &&
        (correcting ? (
          controls
        ) : (
          <div className="answer">
            <Button
              variant="quiet"
              size="sm"
              onClick={() => setCorrecting(true)}
            >
              Change answer
            </Button>
          </div>
        ))}
    </Question>
  );
}
