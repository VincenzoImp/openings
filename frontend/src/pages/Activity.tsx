import { type FormEvent, type ReactNode } from "react";
import {
  api,
  formatTime,
  type Activity,
  type ListResult,
  type OwnerQuestion,
  type Run,
  type RunStatus,
} from "../api";
import { useResource, useUrlState, useWorkspace } from "../state";
import { readyReason } from "./ApplicationReady";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Icon,
  Loading,
  Pagination,
  PendingResults,
  Tabs,
  stageLabels,
} from "../ui";

const PAGE = 30;
const empty = { items: [], total: 0 };
type Open = (id: string) => void;
interface Links {
  onOpenJob: Open;
  onOpenApplication: Open;
}
const runStatus: Record<RunStatus, { label: string; tone: string }> = {
  open: { label: "Open", tone: "green" },
  finished: { label: "Finished", tone: "neutral" },
  interrupted: { label: "Interrupted", tone: "amber" },
};
const subjectNames: Record<string, string> = {
  job: "Job",
  application: "Application",
  knowledge: "Career entry",
  claim: "Claim",
  template: "Template",
  source: "Source",
  collection_run: "Collection run",
  collection: "Collection settings",
  provider: "Provider",
  task: "Collection task",
  profile: "Profile",
  instructions: "Instructions",
  note: "Note",
  context: "Context",
  document: "Document",
  file: "File",
  question: "Question",
  token: "API token",
  workspace: "Workspace",
};
const sections: Record<string, string> = {
  knowledge: "#career?section=knowledge",
  claim: "#career?section=claims",
  profile: "#career",
  template: "#templates?section=templates",
  instructions: "#templates",
  source: "#collection",
  collection: "#collection",
  collection_run: "#collection",
  provider: "#collection",
  task: "#collection",
  token: "#settings?section=agents",
  workspace: "#settings",
};
export function changeLabel(kind?: string) {
  const text = (kind || "updated").replaceAll("_", " ");
  return text[0].toUpperCase() + text.slice(1);
}
function changeDetail(event: Activity) {
  const payload = event.payload || {};
  const stage = (value: unknown) =>
    stageLabels[String(value) as keyof typeof stageLabels] || String(value);
  if (payload.to)
    return `${payload.from ? stage(payload.from) + " → " : ""}${stage(payload.to)}`;
  if (Array.isArray(payload.fields) && payload.fields.length)
    return "Fields: " + payload.fields.join(", ").replaceAll("_", " ");
  if (event.kind === "application_ready_cleared") return readyReason(payload);
  return "";
}
function RecordLink({
  type,
  id,
  jobId,
  applicationId,
  label,
  onOpenJob,
  onOpenApplication,
}: Links & {
  type?: string | null;
  id?: string | null;
  jobId?: string | null;
  applicationId?: string | null;
  label?: string;
}) {
  const name = subjectNames[type || ""] || "Record";
  const text = label ? `${name}: ${label}` : name;
  if (applicationId)
    return (
      <button
        type="button"
        className="inline-link"
        onClick={() => onOpenApplication(applicationId)}
      >
        {text}
      </button>
    );
  if (jobId)
    return (
      <button
        type="button"
        className="inline-link"
        onClick={() => onOpenJob(jobId)}
      >
        {text}
      </button>
    );
  if (id && sections[type || ""])
    return (
      <a className="inline-link" href={sections[type || ""]}>
        {text}
      </a>
    );
  return <span>{type ? text : ""}</span>;
}
function Changes({
  items,
  onRun,
  ...links
}: Links & { items: Activity[]; onRun?: Open }) {
  return (
    <div className="stack change-list">
      {items.map((event) => (
        <article className="activity" key={event.id}>
          <span className="activity-icon">
            <Icon name="clock" />
          </span>
          <div>
            <strong>{changeLabel(event.kind)}</strong>
            <p>
              <RecordLink
                {...links}
                type={event.subject?.type}
                id={event.subject?.id}
                // A deleted job or attempt has no record left to open.
                jobId={
                  event.kind === "job_forgotten" ? null : event.job_id || null
                }
                applicationId={
                  event.kind === "application_deleted"
                    ? null
                    : event.application_id || null
                }
                label={event.subject?.label}
              />
              {changeDetail(event) && (
                <span className="muted"> · {changeDetail(event)}</span>
              )}
            </p>
            <time>
              {formatTime(event.created_at)} · {event.actor?.label}
              {event.run_id && onRun && (
                <>
                  {" · "}
                  <button
                    type="button"
                    className="inline-link"
                    onClick={() => onRun(event.run_id!)}
                  >
                    View run
                  </button>
                </>
              )}
            </time>
          </div>
        </article>
      ))}
    </div>
  );
}
function Asked({ question, onRun }: { question: OwnerQuestion; onRun: Open }) {
  return (
    <p className="muted smalltext">
      Asked by {question.asked_by.label} · {formatTime(question.created_at)}
      {question.run_id && (
        <>
          {" · "}
          <button
            type="button"
            className="inline-link"
            onClick={() => onRun(question.run_id!)}
          >
            View run
          </button>
        </>
      )}
    </p>
  );
}
function AnswerForm({ question }: { question: OwnerQuestion }) {
  const { mutate, pending } = useWorkspace();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const choice = form.get("choice");
    void mutate(
      () =>
        api(`/questions/${question.id}/answer`, "POST", {
          expected_version: question.version,
          answer: String(form.get("answer") || ""),
          ...(choice ? { choice: String(choice) } : {}),
        }),
      "Answer saved.",
    );
  }
  return (
    <form onSubmit={submit} className="question-form">
      {question.choices.length > 0 && (
        <fieldset className="question-choices">
          <legend className="fieldlabel">Choose an answer</legend>
          {question.choices.map((choice) => (
            <label key={choice}>
              <input
                type="radio"
                name="choice"
                value={choice}
                defaultChecked={question.answer_choice === choice}
              />
              <span>{choice}</span>
            </label>
          ))}
        </fieldset>
      )}
      <Field
        label={
          question.choices.length ? "Add a comment (optional)" : "Your answer"
        }
      >
        <textarea
          name="answer"
          rows={3}
          maxLength={8000}
          defaultValue={question.answer}
          required={!question.choices.length}
        />
      </Field>
      <div className="actions">
        <Button variant="primary" disabled={pending}>
          {question.state === "answered" ? "Save answer" : "Answer"}
        </Button>
        {question.state === "open" && (
          <Button
            type="button"
            disabled={pending}
            onClick={() =>
              void mutate(
                () =>
                  api(`/questions/${question.id}/withdraw`, "POST", {
                    expected_version: question.version,
                  }),
                "Question withdrawn.",
              )
            }
          >
            Withdraw
          </Button>
        )}
      </div>
    </form>
  );
}
function QuestionCard({
  question,
  onRun,
  ...links
}: Links & { question: OwnerQuestion; onRun: Open }) {
  const subject = question.subject;
  return (
    <article
      className="card sectioncard question-card"
      aria-label={question.question}
    >
      {subject && (
        <p className="smalltext question-subject">
          {subject.deleted ? (
            <span className="muted">
              {subjectNames[subject.type]}: {subject.label} (deleted)
            </span>
          ) : (
            <RecordLink
              {...links}
              type={subject.type}
              id={subject.id}
              jobId={subject.type === "job" ? subject.id : null}
              applicationId={subject.type === "application" ? subject.id : null}
              label={subject.label}
            />
          )}
        </p>
      )}
      <h2>{question.question}</h2>
      {question.why && <p className="question-why">{question.why}</p>}
      <Asked question={question} onRun={onRun} />
      {question.state === "open" && <AnswerForm question={question} />}
      {question.state === "answered" && (
        <>
          <div className="note question-answer">
            <Icon name="check" />
            <div>
              <strong>
                {[question.answer_choice, question.answer]
                  .filter(Boolean)
                  .join(" · ")}
              </strong>
              <br />
              Answered by {question.answered_by?.label} ·{" "}
              {formatTime(question.answered_at || undefined)}
            </div>
          </div>
          <details className="question-edit">
            <summary>Change answer</summary>
            <AnswerForm question={question} />
          </details>
        </>
      )}
      {question.state === "withdrawn" && (
        <p className="muted">
          Withdrawn by {question.withdrawn_by?.label} ·{" "}
          {formatTime(question.withdrawn_at || undefined)}
        </p>
      )}
    </article>
  );
}
function Questions({ onRun, ...links }: Links & { onRun: Open }) {
  const [state, setState] = useUrlState("state", "open"),
    [offset, setOffset] = useUrlState("offset", "0");
  const resource = useResource<ListResult<OwnerQuestion>>(
    `/questions?state=${state}&limit=${PAGE}&offset=${offset}`,
    empty,
  );
  return (
    <>
      <div className="toolbar activity-toolbar">
        <Field label="State">
          <select
            value={state}
            onChange={(event) => {
              setOffset("0");
              setState(event.target.value);
            }}
          >
            <option value="open">Open</option>
            <option value="answered">Answered</option>
            <option value="withdrawn">Withdrawn</option>
          </select>
        </Field>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      {resource.loading ? (
        <Loading />
      ) : resource.data.items.length ? (
        <>
          <PendingResults pending={resource.refreshing} />
          {resource.data.items.map((question) => (
            <QuestionCard
              key={`${question.id}-${question.version}`}
              question={question}
              onRun={onRun}
              {...links}
            />
          ))}
          <Pagination
            offset={Number(offset)}
            total={resource.data.total}
            limit={PAGE}
            onChange={(value) => setOffset(String(value))}
            label="Question pages"
          />
        </>
      ) : (
        !resource.error && (
          <div className="card">
            <Empty
              title={
                state === "open" ? "No open questions" : `No ${state} questions`
              }
            >
              {state === "open"
                ? "When your agent needs a fact or a decision from you, its question appears here."
                : "Questions move here once they are " + state + "."}
            </Empty>
          </div>
        )
      )}
    </>
  );
}
function RunStatusTag({ run }: { run: Run }) {
  return (
    <span className={`tag ${runStatus[run.status].tone}`}>
      {runStatus[run.status].label}
    </span>
  );
}
function Runs({ onRun }: { onRun: Open }) {
  const [status, setStatus] = useUrlState("status", ""),
    [offset, setOffset] = useUrlState("offset", "0");
  const resource = useResource<ListResult<Run>>(
    `/runs?limit=${PAGE}&offset=${offset}${status ? "&status=" + status : ""}`,
    empty,
  );
  return (
    <>
      <div className="toolbar activity-toolbar">
        <Field label="Status">
          <select
            value={status}
            onChange={(event) => {
              setOffset("0");
              setStatus(event.target.value);
            }}
          >
            <option value="">All runs</option>
            <option value="open">Open</option>
            <option value="finished">Finished</option>
            <option value="interrupted">Interrupted</option>
          </select>
        </Field>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      {resource.loading ? (
        <Loading />
      ) : resource.data.items.length ? (
        <section className="card run-list" aria-label="Agent runs">
          <PendingResults pending={resource.refreshing} />
          {resource.data.items.map((run) => (
            <button
              type="button"
              className="run-row"
              key={run.id}
              onClick={() => onRun(run.id)}
            >
              <span className="run-row-main">
                <strong>{run.workflow}</strong>
                <span className="muted">
                  {run.summary || run.note || run.scope || "No report yet"}
                </span>
              </span>
              <span className="run-row-meta">
                <RunStatusTag run={run} />
                <span className="muted smalltext">
                  {run.actor.label} · {formatTime(run.started_at)} ·{" "}
                  {run.changes_total}{" "}
                  {run.changes_total === 1 ? "change" : "changes"}
                  {run.questions_count
                    ? ` · ${run.questions_count} ${run.questions_count === 1 ? "question" : "questions"}`
                    : ""}
                </span>
              </span>
            </button>
          ))}
          <Pagination
            offset={Number(offset)}
            total={resource.data.total}
            limit={PAGE}
            onChange={(value) => setOffset(String(value))}
            label="Run pages"
          />
        </section>
      ) : (
        !resource.error && (
          <div className="card">
            <Empty title="No runs to show">
              A run appears here when an agent opens one for a workflow. Its
              report and the changes it made stay readable afterwards.
            </Empty>
          </div>
        )
      )}
    </>
  );
}
function ReportSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="report-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}
function RunDetail({
  id,
  onBack,
  onQuestions,
  ...links
}: Links & { id: string; onBack: () => void; onQuestions: () => void }) {
  const [offset, setOffset] = useUrlState("offset", "0");
  const resource = useResource<Run | null>(
    `/runs/${id}?changes_limit=${PAGE}&changes_offset=${offset}`,
    null,
  );
  const run = resource.data;
  const report = run?.report;
  const counts = Object.entries(run?.change_counts || {});
  return (
    <>
      <div className="toolbar activity-toolbar">
        <Button type="button" onClick={onBack}>
          Back to runs
        </Button>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      {resource.loading ? (
        <Loading />
      ) : (
        run && (
          <>
            <section className="card sectioncard run-detail">
              <div className="sectiontitle">
                <div>
                  <h2>{run.workflow}</h2>
                  <p className="muted">
                    {run.actor.label} · started {formatTime(run.started_at)}
                    {run.ended_at
                      ? ` · ended ${formatTime(run.ended_at)}`
                      : ` · last activity ${formatTime(run.last_activity_at)}`}
                  </p>
                </div>
                <RunStatusTag run={run} />
              </div>
              {run.status === "interrupted" && (
                <div className="note">
                  <Icon name="info" />
                  <div>
                    {run.interruption === "superseded"
                      ? "The agent started another run before closing this one, so it has no report."
                      : "This run was never closed and has had no recent activity. The changes it made are listed below."}
                  </div>
                </div>
              )}
              {run.scope && (
                <ReportSection title="Scope">
                  <p className="report-text">{run.scope}</p>
                </ReportSection>
              )}
              {run.note && !report && (
                <ReportSection title="Progress note">
                  <p className="report-text">{run.note}</p>
                </ReportSection>
              )}
              {report ? (
                <>
                  <ReportSection title="Summary">
                    <p className="report-text">{report.summary}</p>
                  </ReportSection>
                  <ReportSection title="Changes">
                    {report.changes.text && (
                      <p className="report-text">{report.changes.text}</p>
                    )}
                    <ChangeCounts counts={counts} />
                  </ReportSection>
                  <ReportSection title="Not done">
                    {report.not_done.length ? (
                      <ul className="report-list">
                        {report.not_done.map((item, index) => (
                          <li key={index}>
                            <strong>{item.item}</strong>
                            {item.subject_type && (
                              <>
                                {" "}
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
                                    item.label &&
                                    item.subject_type === "application"
                                      ? item.subject_id
                                      : null
                                  }
                                  label={item.label}
                                />
                              </>
                            )}
                            <br />
                            <span className="muted">{item.reason}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">Nothing was left undone.</p>
                    )}
                  </ReportSection>
                  <ReportSection title="Checks">
                    {report.checks.length ? (
                      <ul className="report-list">
                        {report.checks.map((item, index) => (
                          <li key={index}>
                            <span
                              className={`tag ${item.verified ? "green" : "amber"}`}
                            >
                              {item.verified ? "Verified" : "Not verified"}
                            </span>{" "}
                            {item.check}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">No checks were reported.</p>
                    )}
                  </ReportSection>
                  <ReportSection title="Statement of limits">
                    <p className="report-text">
                      {report.limits || "None stated."}
                    </p>
                  </ReportSection>
                  <ReportSection title="Method">
                    <p className="report-text">
                      {report.method || "Nothing reported."}
                    </p>
                  </ReportSection>
                </>
              ) : (
                <ReportSection title="Report">
                  <p className="muted">
                    {run.status === "open"
                      ? "The run is still open. Its report is stored when the agent closes it."
                      : "This run ended without a report."}
                  </p>
                  <ChangeCounts counts={counts} />
                </ReportSection>
              )}
              <ReportSection title="Questions for you">
                {run.questions?.length ? (
                  <ul className="report-list">
                    {run.questions.map((question) => (
                      <li key={question.id}>
                        <span
                          className={`tag ${question.state === "open" ? "amber" : "neutral"}`}
                        >
                          {question.state}
                        </span>{" "}
                        {question.question}
                        {question.state === "answered" && (
                          <>
                            <br />
                            <span className="muted">
                              {[question.answer_choice, question.answer]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">No questions were asked in this run.</p>
                )}
                {run.questions?.some((item) => item.state === "open") && (
                  <button
                    type="button"
                    className="inline-link"
                    onClick={onQuestions}
                  >
                    Answer open questions
                  </button>
                )}
              </ReportSection>
            </section>
            <section className="card sectioncard">
              <div className="sectiontitle">
                <div>
                  <h2>Changes made</h2>
                  <p className="muted">
                    Every record this run changed, newest first.
                  </p>
                </div>
              </div>
              {run.changes?.items.length ? (
                <>
                  <Changes items={run.changes.items} {...links} />
                  <Pagination
                    offset={Number(offset)}
                    total={run.changes.total}
                    limit={PAGE}
                    onChange={(value) => setOffset(String(value))}
                    label="Change pages"
                  />
                </>
              ) : (
                <p className="muted">This run changed no records.</p>
              )}
            </section>
          </>
        )
      )}
    </>
  );
}
function ChangeCounts({ counts }: { counts: [string, number][] }) {
  return counts.length ? (
    <p className="change-counts">
      {counts.map(([kind, count]) => (
        <span className="tag neutral" key={kind}>
          {changeLabel(kind)} · {count}
        </span>
      ))}
    </p>
  ) : (
    <p className="muted">No changes were recorded.</p>
  );
}
function AllChanges({ onRun, ...links }: Links & { onRun: Open }) {
  const [actor, setActor] = useUrlState("actor", ""),
    [offset, setOffset] = useUrlState("offset", "0");
  const resource = useResource<ListResult<Activity>>(
    `/events?limit=${PAGE}&offset=${offset}${actor ? "&actor=" + actor : ""}`,
    empty,
  );
  return (
    <>
      <div className="toolbar activity-toolbar">
        <Field label="Made by">
          <select
            value={actor}
            onChange={(event) => {
              setOffset("0");
              setActor(event.target.value);
            }}
          >
            <option value="">Anyone</option>
            <option value="owner">Owner (dashboard)</option>
            <option value="token">API tokens</option>
            <option value="system">System</option>
            <option value="unknown">Unknown (before 0.17)</option>
          </select>
        </Field>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      {resource.loading ? (
        <Loading />
      ) : resource.data.items.length ? (
        <section className="card sectioncard">
          <PendingResults pending={resource.refreshing} />
          <Changes items={resource.data.items} onRun={onRun} {...links} />
          <Pagination
            offset={Number(offset)}
            total={resource.data.total}
            limit={PAGE}
            onChange={(value) => setOffset(String(value))}
            label="Change pages"
          />
        </section>
      ) : (
        !resource.error && (
          <div className="card">
            <Empty title="No changes to show">
              Changes to jobs, applications, Career records and collection
              appear here with who made them.
            </Empty>
          </div>
        )
      )}
    </>
  );
}
export default function ActivityPage({
  openQuestions,
  ...links
}: Links & { openQuestions: number }) {
  const [section, setSection] = useUrlState("section", "questions"),
    [run, setRun] = useUrlState("run", ""),
    [, setOffset] = useUrlState("offset", "0");
  const show = (next: string, runId = "") => {
    setOffset("0");
    setRun(runId);
    setSection(next);
    window.scrollTo(0, 0);
  };
  const onRun = (id: string) => show("runs", id);
  return (
    <>
      <Heading
        title="Activity"
        description="Answer your agent's questions and review what each run changed."
      />
      <Tabs
        label="Activity sections"
        value={section}
        onChange={(next) => show(next)}
        items={[
          { id: "questions", label: "Questions", count: openQuestions },
          { id: "runs", label: "Runs" },
          { id: "changes", label: "Changes" },
        ]}
      />
      {section === "runs" ? (
        run ? (
          <RunDetail
            key={run}
            id={run}
            onBack={() => show("runs")}
            onQuestions={() => show("questions")}
            {...links}
          />
        ) : (
          <Runs onRun={onRun} />
        )
      ) : section === "changes" ? (
        <AllChanges onRun={onRun} {...links} />
      ) : (
        <Questions onRun={onRun} {...links} />
      )}
    </>
  );
}
