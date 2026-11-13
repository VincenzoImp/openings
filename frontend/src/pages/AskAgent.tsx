// "Ask your agent" on a job or an application, for the pages written before
// the design system. Activity has the full list (pages/activity/Requests.tsx).
import { useState, type FormEvent } from "react";
import {
  actorLabel,
  api,
  formatTime,
  type AgentRequest,
  type ListResult,
  type RequestState,
} from "../api";
import { useResource, useWorkspace } from "../state";
import { Button, Dialog, ErrorBox, Field, Icon } from "../ui";

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

function RequestForm({
  subjectType,
  subjectId,
}: {
  subjectType: "job" | "application";
  subjectId: string;
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
          subject_type: subjectType,
          subject_id: subjectId,
        }),
      "Request saved. Your agent reads it at its next run.",
    );
    if (sent) form.reset();
  }
  return (
    <form onSubmit={submit} className="request-form">
      <Field label="Request for your agent" hint={LIMITS}>
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

function Outcome({ request }: { request: AgentRequest }) {
  if (request.state === "open") return null;
  if (request.state === "taken")
    return (
      <p className="muted smalltext">
        Taken by {actorLabel(request.taken_by)} ·{" "}
        {formatTime(request.taken_at || undefined)}
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
      </div>
    </div>
  );
}

function RequestCard({ request }: { request: AgentRequest }) {
  const { mutate, pending } = useWorkspace();
  return (
    <article className="request-card" aria-label={request.text}>
      <div className="request-head">
        <p className="request-text">{request.text}</p>
        <span className={`tag ${states[request.state].tone}`}>
          {states[request.state].label}
        </span>
      </div>
      <p className="muted smalltext">
        Written by {actorLabel(request.created_by)} ·{" "}
        {formatTime(request.created_at)}
      </p>
      <Outcome request={request} />
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

/** Write a request about this record and see the earlier ones. */
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
