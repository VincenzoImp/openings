import type { FormEvent } from "react";
import { api, type AgentRequest, type ListResult } from "../../api";
import { Button, ErrorBanner, Field } from "../../design";
import { useFresh } from "../../library/useFresh";
import { RequestItem } from "../activity/Requests";
import { useAct, type Links } from "../activity/records";

const NONE: ListResult<AgentRequest> = { items: [], total: 0 };
const EXAMPLES = {
  application: "For example: rewrite the letter with more on data pipelines.",
  job: "For example: find out whether this team hires remotely.",
};

/** Requests for the agent about an application or a job: write one, follow the earlier ones. */
export function AskAgent({
  subjectType,
  subjectId,
  ...links
}: Links & { subjectType: "application" | "job"; subjectId: string }) {
  const requests = useFresh<ListResult<AgentRequest>>(
    `/requests?subject_type=${subjectType}&subject_id=${subjectId}&limit=10`,
    NONE,
    ["requests"],
  );
  const { act, busy } = useAct(requests.reload);
  const titleId = `ask-${subjectType}-title`;
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const text = String(new FormData(form).get("text") || "").trim();
    if (!text) return;
    const outcome = await act(
      () =>
        api("/requests", "POST", {
          text,
          subject_type: subjectType,
          subject_id: subjectId,
        }),
      "Request saved. Your agent reads it at its next run.",
    );
    if (outcome === "ok") {
      form.reset();
      form.dataset.dirty = "false";
    }
  }
  return (
    <section className="stack" aria-labelledby={titleId}>
      <h3 id={titleId}>Ask your agent</h3>
      <form className="stack" onSubmit={send}>
        <Field
          label={`A request about this ${subjectType}`}
          hint="Your agent reads it at the start of its next run. It never submits an application, contacts an employer or records Applied for you."
        >
          <textarea
            name="text"
            rows={3}
            maxLength={4000}
            required
            placeholder={EXAMPLES[subjectType]}
          />
        </Field>
        <div className="row">
          <Button size="sm" disabled={busy}>
            Send the request
          </Button>
        </div>
      </form>
      {requests.error && (
        <ErrorBanner message={requests.error} retry={requests.reload} />
      )}
      {requests.data.items.length > 0 && (
        <div className="card">
          {requests.data.items.map((request) => (
            <RequestItem
              key={request.id}
              request={request}
              act={act}
              busy={busy}
              {...links}
            />
          ))}
        </div>
      )}
    </section>
  );
}
