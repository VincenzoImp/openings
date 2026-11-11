import { useState, type FormEvent } from "react";
import {
  actorLabel,
  api,
  formatTime,
  type AgentRequest,
  type ListResult,
  type RequestState,
} from "../api";
import { useResource, useUrlState, useWorkspace } from "../state";
import {
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Icon,
  Loading,
  Pagination,
  PendingResults,
} from "../ui";
import {
  RecordLink,
  subjectNames,
  type Links,
  type Open,
} from "./ActivityLinks";

const PAGE = 30;
const empty = { items: [], total: 0 };
const states: Record<RequestState, { label: string; tone: string }> = {
  open: { label: "Waiting for the agent", tone: "amber" },
  taken: { label: "Taken by the agent", tone: "green" },
  done: { label: "Done", tone: "green" },
  declined: { label: "Declined", tone: "danger" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};
const LIMITS =
  "Your agent reads requests at the start of its next run. A request cannot make it submit an application, contact an employer or record Applied.";

function StateTag({ request }: { request: AgentRequest }) {
  return (
    <span className={`tag ${states[request.state].tone}`}>
      {states[request.state].label}
    </span>
  );
}

/** Write a request, optionally about one job, application or Career entry. */
function RequestForm({
  subjectType,
  subjectId,
  label = "Request for your agent",
}: {
  subjectType?: "job" | "application";
  subjectId?: string;
  label?: string;
}) {
  const { mutate, pending } = useWorkspace();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const text = String(new FormData(form).get("text") || "").trim();
    if (!text) return;
    const sent = await mutate(
      () =>
        api("/requests", "POST", {
          text,
          ...(subjectId
            ? { subject_type: subjectType, subject_id: subjectId }
            : {}),
        }),
      "Request saved. Your agent reads it at its next run.",
    );
    if (sent) form.reset();
  }
  return (
    <form onSubmit={submit} className="request-form">
      <Field label={label} hint={LIMITS}>
        <textarea
          name="text"
          rows={3}
          maxLength={4000}
          required
          placeholder="For example: prepare this one too, or rewrite the letter with more focus on data pipelines."
        />
      </Field>
      <div className="actions">
        <Button variant="primary" disabled={pending}>
          Send request
        </Button>
      </div>
    </form>
  );
}

function Outcome({ request, onRun }: { request: AgentRequest; onRun?: Open }) {
  const run = request.run_id && onRun && (
    <>
      {" · "}
      <button
        type="button"
        className="inline-link"
        onClick={() => onRun(request.run_id!)}
      >
        View run
      </button>
    </>
  );
  if (request.state === "open") return null;
  if (request.state === "taken")
    return (
      <p className="muted smalltext">
        Taken by {actorLabel(request.taken_by)} ·{" "}
        {formatTime(request.taken_at || undefined)}
        {run}
      </p>
    );
  if (request.state === "withdrawn")
    return (
      <p className="muted smalltext">
        Withdrawn by {actorLabel(request.resolved_by)} ·{" "}
        {formatTime(request.resolved_at || undefined)}
      </p>
    );
  return (
    <div className="note request-result">
      <Icon name={request.state === "done" ? "check" : "info"} />
      <div>
        <strong>{request.result}</strong>
        <br />
        {request.state === "done" ? "Completed" : "Declined"} by{" "}
        {actorLabel(request.resolved_by)} ·{" "}
        {formatTime(request.resolved_at || undefined)}
        {run}
      </div>
    </div>
  );
}

function RequestCard({
  request,
  onRun,
  compact = false,
  ...links
}: Partial<Links> & {
  request: AgentRequest;
  onRun?: Open;
  compact?: boolean;
}) {
  const { mutate, pending } = useWorkspace();
  const subject = request.subject;
  return (
    <article
      className={`request-card ${compact ? "" : "card sectioncard"}`}
      aria-label={request.text}
    >
      {subject && !compact && (
        <p className="smalltext question-subject">
          {subject.deleted || !links.onOpenJob || !links.onOpenApplication ? (
            <span className="muted">
              {subjectNames[subject.type]}: {subject.label}
              {subject.deleted ? " (deleted)" : ""}
            </span>
          ) : (
            <RecordLink
              onOpenJob={links.onOpenJob}
              onOpenApplication={links.onOpenApplication}
              type={subject.type}
              id={subject.id}
              jobId={subject.type === "job" ? subject.id : null}
              applicationId={subject.type === "application" ? subject.id : null}
              label={subject.label}
            />
          )}
        </p>
      )}
      <div className="request-head">
        <p className="request-text">{request.text}</p>
        <StateTag request={request} />
      </div>
      <p className="muted smalltext">
        Written by {actorLabel(request.created_by)} ·{" "}
        {formatTime(request.created_at)}
      </p>
      <Outcome request={request} onRun={onRun} />
      {(request.state === "open" || request.state === "taken") && (
        <div className="actions">
          <Button
            type="button"
            className="small"
            disabled={pending}
            onClick={() =>
              void mutate(
                () =>
                  api(`/requests/${request.id}/withdraw`, "POST", {
                    expected_version: request.version,
                  }),
                "Request withdrawn.",
              )
            }
          >
            Withdraw
          </Button>
        </div>
      )}
    </article>
  );
}

/** The Requests tab of Activity: write a request and follow what the agent did with each. */
export function Requests({ onRun, ...links }: Links & { onRun: Open }) {
  const [state, setState] = useUrlState("state", ""),
    [offset, setOffset] = useUrlState("offset", "0");
  const resource = useResource<ListResult<AgentRequest>>(
    `/requests?limit=${PAGE}&offset=${offset}${state ? "&state=" + state : ""}`,
    empty,
  );
  return (
    <>
      <section className="card sectioncard">
        <RequestForm label="Ask your agent" />
      </section>
      <div className="toolbar activity-toolbar">
        <Field label="State">
          <select
            value={state}
            onChange={(event) => {
              setOffset("0");
              setState(event.target.value);
            }}
          >
            <option value="">All requests</option>
            {Object.entries(states).map(([value, item]) => (
              <option key={value} value={value}>
                {item.label}
              </option>
            ))}
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
          {resource.data.items.map((request) => (
            <RequestCard
              key={`${request.id}-${request.version}`}
              request={request}
              onRun={onRun}
              {...links}
            />
          ))}
          <Pagination
            offset={Number(offset)}
            total={resource.data.total}
            limit={PAGE}
            onChange={(value) => setOffset(String(value))}
            label="Request pages"
          />
        </>
      ) : (
        !resource.error && (
          <div className="card">
            <Empty title={state ? "No requests in this state" : "No requests"}>
              {state
                ? "Choose another state to see the other requests."
                : "Write what your agent should do next. It reads open requests at the start of every run and reports the result here."}
            </Empty>
          </div>
        )
      )}
    </>
  );
}

/** The requests a run handled, in the run detail. */
export function RunRequests({ items }: { items?: AgentRequest[] }) {
  if (!items?.length)
    return <p className="muted">This run handled no requests.</p>;
  return (
    <ul className="report-list">
      {items.map((request) => (
        <li key={request.id}>
          <StateTag request={request} /> {request.text}
          {request.result && (
            <>
              <br />
              <span className="muted">{request.result}</span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

/** "Ask your agent" on a job or an application: write a request about this record. */
export function AskAgent({
  subjectType,
  subjectId,
  name,
}: {
  subjectType: "job" | "application";
  subjectId: string;
  name: string;
}) {
  const [open, setOpen] = useState(false);
  const resource = useResource<ListResult<AgentRequest>>(
    `/requests?subject_type=${subjectType}&subject_id=${subjectId}&limit=5`,
    empty,
  );
  const waiting = resource.data.items.filter(
    (item) => item.state === "open" || item.state === "taken",
  ).length;
  return (
    <div className="ask-agent">
      <Button className="small" icon="plus" onClick={() => setOpen(true)}>
        Ask your agent
      </Button>
      {resource.data.total > 0 && (
        <button
          type="button"
          className="inline-link smalltext"
          onClick={() => setOpen(true)}
        >
          {waiting
            ? `${waiting} request${waiting === 1 ? "" : "s"} waiting`
            : `${resource.data.total} earlier request${resource.data.total === 1 ? "" : "s"}`}
        </button>
      )}
      {open && (
        <Dialog title="Ask your agent" onClose={() => setOpen(false)}>
          <p className="modal-intro">About {name}.</p>
          <RequestForm subjectType={subjectType} subjectId={subjectId} />
          {resource.error && (
            <ErrorBox message={resource.error} retry={resource.reload} />
          )}
          {resource.data.items.length > 0 && (
            <section
              className="request-history"
              aria-label="Requests about this record"
            >
              <h3>Requests about this record</h3>
              {resource.data.items.map((request) => (
                <RequestCard
                  key={`${request.id}-${request.version}`}
                  request={request}
                  compact
                />
              ))}
              {resource.data.total > resource.data.items.length && (
                <a
                  className="inline-link smalltext"
                  href="#activity?section=requests"
                >
                  All requests
                </a>
              )}
            </section>
          )}
        </Dialog>
      )}
    </div>
  );
}
