import type { FormEvent } from "react";
import {
  api,
  type AgentRequest,
  type Application,
  type ListResult,
} from "../../api";
import { Button, ErrorBanner, Field } from "../../design";
import { useFresh } from "../../library/useFresh";
import { RequestItem } from "../activity/Requests";
import { useAct, type Links } from "../activity/records";

const NONE: ListResult<AgentRequest> = { items: [], total: 0 };

/** Requests for the agent about this application: write one, follow the earlier ones. */
export function AskAgent({
  application,
  ...links
}: Links & { application: Application }) {
  const requests = useFresh<ListResult<AgentRequest>>(
    `/requests?subject_type=application&subject_id=${application.id}&limit=10`,
    NONE,
    ["requests"],
  );
  const { act, busy } = useAct(requests.reload);
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const text = String(new FormData(form).get("text") || "").trim();
    if (!text) return;
    const outcome = await act(
      () =>
        api("/requests", "POST", {
          text,
          subject_type: "application",
          subject_id: application.id,
        }),
      "Request saved. Your agent reads it at its next run.",
    );
    if (outcome === "ok") {
      form.reset();
      form.dataset.dirty = "false";
    }
  }
  return (
    <section className="stack" aria-labelledby="ask-title">
      <h3 id="ask-title">Ask your agent</h3>
      <form className="stack" onSubmit={send}>
        <Field
          label="A request about this application"
          hint="Your agent reads it at the start of its next run. It never submits an application, contacts an employer or records Applied for you."
        >
          <textarea
            name="text"
            rows={3}
            maxLength={4000}
            required
            placeholder="For example: rewrite the letter with more on data pipelines."
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
