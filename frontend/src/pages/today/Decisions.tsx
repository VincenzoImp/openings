import type { Application, ListResult, OwnerQuestion } from "../../api";
import {
  Card,
  EmptyState,
  ErrorBanner,
  Loading,
  Question,
  Tag,
} from "../../design";
import { plural } from "../../library/common";
import type { Fresh } from "../../library/useFresh";
import { QuestionItem } from "../activity/QuestionItem";
import { useAct, type Links } from "../activity/records";
import { reviewHref } from "../applications/links";

const role = (application: Application) =>
  [application.job?.title, application.job?.company]
    .filter(Boolean)
    .join(" · ") || "An application";

/** An application the agent will not write for until a requirement is resolved. */
function Blocked({ application }: { application: Application }) {
  const count = application.blocking_requirements || 1;
  return (
    <Question
      ask={`${role(application)} is blocked by ${count === 1 ? "a requirement" : `${count} requirements`}.`}
      why="Your agent does not write documents for this application until you resolve it or decide not to pursue the job."
      lead={<Tag tone="danger">Blocking requirement</Tag>}
    >
      <div className="answer">
        <a className="btn sm" href={reviewHref(application.id, "requirements")}>
          Open the requirements
        </a>
      </div>
    </Question>
  );
}

/**
 * What only the owner can settle: the agent's open questions, answered in
 * place, and applications stopped by a blocking requirement.
 */
export function Decisions({
  questions,
  blocked,
  incomplete,
  ...links
}: Links & {
  questions: Fresh<ListResult<OwnerQuestion>>;
  blocked: Fresh<ListResult<Application>>;
  /** Jobs whose posting text is not complete; the owner pastes it. */
  incomplete: number;
}) {
  const { act, busy } = useAct(questions.reload);
  const loading = questions.loading || blocked.loading;
  const failed = [questions, blocked].filter((item) => item.error);
  const moreQuestions = questions.data.total - questions.data.items.length;
  const moreBlocked = blocked.data.total - blocked.data.items.length;
  const empty = !questions.data.items.length && !blocked.data.items.length;
  return (
    <Card
      title="Needs your decision"
      count={
        loading || failed.length
          ? undefined
          : questions.data.total + blocked.data.total
      }
      footer={
        moreQuestions > 0 || moreBlocked > 0 || incomplete > 0 ? (
          <>
            {moreQuestions > 0 && (
              <a className="btn quiet sm" href="#activity">
                {plural(moreQuestions, "more question")} in Activity
              </a>
            )}
            {moreBlocked > 0 && (
              <a
                className="btn quiet sm"
                href="#applications?stage=preparing&readiness=blocked"
              >
                {plural(moreBlocked, "more blocked application")}
              </a>
            )}
            {incomplete > 0 && (
              <a
                className="btn quiet sm"
                href="#jobs?section=all&complete=false"
              >
                {incomplete === 1
                  ? "1 job needs its full posting"
                  : `${incomplete} jobs need their full posting`}
              </a>
            )}
          </>
        ) : undefined
      }
    >
      {failed.map((item, index) => (
        <div className="body" key={index}>
          <ErrorBanner message={item.error!} retry={item.reload} />
        </div>
      ))}
      {loading ? (
        <Loading label="Loading decisions…" />
      ) : (
        <>
          {questions.data.items.map((question) => (
            <QuestionItem
              key={question.id}
              question={question}
              act={act}
              busy={busy}
              onAnswered={(id) =>
                questions.setData((current) => ({
                  items: current.items.filter((item) => item.id !== id),
                  total: Math.max(0, current.total - 1),
                }))
              }
              {...links}
            />
          ))}
          {blocked.data.items.map((application) => (
            <Blocked key={application.id} application={application} />
          ))}
          {empty && !failed.length && (
            <EmptyState title="No decision is waiting">
              When your agent needs a fact or a decision from you, or a
              requirement blocks an application, it appears here.
            </EmptyState>
          )}
        </>
      )}
    </Card>
  );
}
