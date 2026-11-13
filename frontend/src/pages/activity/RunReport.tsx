import { useEffect, useRef } from "react";
import type { Activity, Run } from "../../api";
import {
  ActorChip,
  Banner,
  CountList,
  CountRow,
  ErrorBanner,
  Loading,
  ReportSection,
  Statement,
  StatementList,
  Tag,
} from "../../design";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { ChangeSubject, RecordLink, type Links } from "./records";
import { requestStates } from "./Requests";
import { RunStatusTag } from "./RunTag";
import { countedAs, runDuration, sortedCounts } from "./wording";

// The report names the records of the first changes; the timeline has them all.
const CHANGES = 100;
const NAMED = 3;

/**
 * The distinct records the changes of one kind touched, as links. Two
 * records with one name (the CV and the letter of one application) are
 * named once.
 */
function Touched({ events, ...links }: Links & { events: Activity[] }) {
  const seen = new Set<string>();
  const records = events.filter((event) => {
    const key = event.subject?.label;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (!records.length) return null;
  return (
    <>
      {": "}
      {records.slice(0, NAMED).map((event, index) => (
        <span key={event.id}>
          {index > 0 && ", "}
          <ChangeSubject event={event} {...links} named={false} />
        </span>
      ))}
      {records.length > NAMED && ` and ${records.length - NAMED} more`}
    </>
  );
}

function Changes({ run, ...links }: Links & { run: Run }) {
  const counts = sortedCounts(run.change_counts);
  const events = run.changes?.items || [];
  return (
    <>
      {run.report?.changes.text && (
        <p className="prose">{run.report.changes.text}</p>
      )}
      {counts.length ? (
        <>
          <CountList>
            {counts.map(([kind, count]) => (
              <CountRow key={kind} count={count}>
                {countedAs(kind, count)}
                <Touched
                  events={events.filter((event) => event.kind === kind)}
                  {...links}
                />
              </CountRow>
            ))}
          </CountList>
          <p>
            <a href={`#activity?section=timeline&run=${run.id}`}>
              {run.changes_total === 1
                ? "The change in the timeline"
                : `All ${run.changes_total} changes in the timeline`}
            </a>
          </p>
        </>
      ) : (
        <p className="muted">This run changed no records.</p>
      )}
    </>
  );
}

/** The report of one run: what it did, what it left undone and why. */
export function RunReport({
  id,
  autoFocus = false,
  ...links
}: Links & { id: string; autoFocus?: boolean }) {
  const {
    data: run,
    loading,
    error,
    reload,
  } = useFresh<Run | null>(`/runs/${id}?changes_limit=${CHANGES}`, null, [
    "runs",
    "questions",
    "requests",
  ]);
  const heading = useRef<HTMLHeadingElement>(null);
  const loaded = Boolean(run);
  useEffect(() => {
    if (autoFocus && loaded) heading.current?.focus();
  }, [autoFocus, loaded]);
  if (error)
    return (
      <div className="card detail">
        <div className="body">
          <ErrorBanner message={error} retry={reload} />
        </div>
      </div>
    );
  if (loading || !run)
    return (
      <div className="card detail">
        <Loading label="Loading the report…" />
      </div>
    );
  const report = run.report;
  return (
    <article className="card detail report" aria-labelledby="run-report">
      <header className="top">
        <div className="grow">
          <h2 id="run-report" tabIndex={-1} ref={heading}>
            {run.workflow}
          </h2>
          <div className="muted">
            {dayTime(run.started_at)}
            {run.ended_at && ` to ${dayTime(run.ended_at)}`} ·{" "}
            {runDuration(run)}
          </div>
          <ActorChip actor={run.actor} />
        </div>
        <RunStatusTag run={run} />
      </header>
      {run.status === "interrupted" && (
        <div className="body">
          <Banner tone="attention">
            {run.interruption === "superseded"
              ? "The agent started another run before closing this one, so it has no report."
              : "This run was never closed and has had no recent activity. The changes it made are kept and listed below."}
          </Banner>
        </div>
      )}
      {run.scope && (
        <ReportSection title="Scope">
          <p className="prose">{run.scope}</p>
        </ReportSection>
      )}
      {run.note && !report && (
        <ReportSection title="Progress note">
          <p className="prose">{run.note}</p>
        </ReportSection>
      )}
      {report ? (
        <ReportSection title="Summary">
          <p className="prose">{report.summary}</p>
        </ReportSection>
      ) : (
        <ReportSection title="Report">
          <p className="muted">
            {run.status === "open"
              ? "The run is still in progress. Its report is stored when the agent closes it."
              : "This run ended without a report."}
          </p>
        </ReportSection>
      )}
      <ReportSection title="Changes">
        <Changes run={run} {...links} />
      </ReportSection>
      {report && (
        <>
          <ReportSection title="Not done">
            {report.not_done.length ? (
              <StatementList label="Not done">
                {report.not_done.map((item, index) => (
                  <Statement
                    key={index}
                    name={item.item}
                    movable={false}
                    label={item.item}
                    caption={
                      item.subject_type && (
                        <RecordLink
                          {...links}
                          type={item.subject_type}
                          id={item.subject_id}
                          jobId={
                            item.label && item.subject_type === "job"
                              ? item.subject_id
                              : null
                          }
                          applicationId={
                            item.label && item.subject_type === "application"
                              ? item.subject_id
                              : null
                          }
                          label={item.label}
                        />
                      )
                    }
                  >
                    <div className="meta prose">{item.reason}</div>
                  </Statement>
                ))}
              </StatementList>
            ) : (
              <p className="muted">Nothing was left undone.</p>
            )}
          </ReportSection>
          <ReportSection title="Checks">
            {report.checks.length ? (
              <ul className="plain tagged">
                {report.checks.map((item, index) => (
                  <li key={index}>
                    <Tag tone={item.verified ? "ready" : "attention"}>
                      {item.verified ? "Verified" : "Not verified"}
                    </Tag>{" "}
                    {item.check}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No checks were reported.</p>
            )}
          </ReportSection>
          <ReportSection title="Limits">
            <p className="prose">{report.limits || "None stated."}</p>
          </ReportSection>
          <ReportSection title="Method">
            <p className="muted">
              What the workflow lacked. What applies to this workspace can
              become a local note of the skill; the rest is for the maintainer
              of the skills.
            </p>
            <p className="prose">{report.method || "Nothing reported."}</p>
            {report.method.trim() && (
              <p>
                <a
                  href={`#settings?section=skills&skill=${encodeURIComponent(run.workflow)}&from_run=${run.id}`}
                >
                  Add to the local notes of {run.workflow}
                </a>
              </p>
            )}
          </ReportSection>
        </>
      )}
      <ReportSection title="Questions for you">
        {run.questions?.length ? (
          <ul className="plain tagged">
            {run.questions.map((question) => (
              <li key={question.id}>
                <Tag tone={question.state === "open" ? "agent" : "neutral"}>
                  {question.state === "open"
                    ? "Open"
                    : question.state === "answered"
                      ? "Answered"
                      : "Withdrawn"}
                </Tag>{" "}
                {question.question}
                {question.state === "answered" && (
                  <div className="answered prose">
                    {[question.answer_choice, question.answer]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No questions were asked in this run.</p>
        )}
        {run.questions?.some((item) => item.state === "open") && (
          <p>
            <a href="#activity">Answer open questions</a>
          </p>
        )}
      </ReportSection>
      <ReportSection title="Requests handled">
        {run.requests?.length ? (
          <ul className="plain tagged">
            {run.requests.map((request) => (
              <li key={request.id}>
                <Tag tone={requestStates[request.state].tone}>
                  {requestStates[request.state].filter}
                </Tag>{" "}
                {request.text}
                {request.result && (
                  <div className="answered prose">{request.result}</div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">This run handled no requests.</p>
        )}
      </ReportSection>
    </article>
  );
}
