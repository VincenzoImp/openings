import { useState, type FormEvent } from "react";
import {
  api,
  localToday,
  type Application,
  type EmployerResponse,
  type ListResult,
  type ResponseKind,
} from "../../api";
import {
  ActorChip,
  Button,
  ErrorBanner,
  Field,
  Loading,
  Statement,
  StatementList,
} from "../../design";
import { ConfirmDialog } from "../../library/common";
import { shortDate } from "../../library/time";
import { useResource, useWorkspace } from "../../state";
import { responseLabels } from "../applications/model";
import { Respond } from "../applications/Respond";

/** "10 Oct" for a calendar day (YYYY-MM-DD), read in local time. */
export const day = (value: string) => {
  const [year, month, date] = value.split("-").map(Number);
  return shortDate(new Date(year, month - 1, date));
};

function Edit({
  response,
  onDone,
}: {
  response: EmployerResponse;
  onDone: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const ok = await mutate(
      () =>
        api(`/responses/${response.id}`, "PATCH", {
          expected_version: response.version,
          kind: form.get("kind"),
          date: form.get("date"),
          note: String(form.get("note") || ""),
        }),
      "Response corrected.",
    );
    if (ok) onDone();
  }
  return (
    <form
      className="edit-grid grow"
      onSubmit={save}
      aria-label="Correct the response"
    >
      <Field label="Answer">
        <select name="kind" defaultValue={response.kind}>
          {Object.entries(responseLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Date of the answer">
        <input
          type="date"
          name="date"
          required
          max={localToday()}
          defaultValue={response.date}
        />
      </Field>
      <Field label="Note" className="wide">
        <input name="note" maxLength={2000} defaultValue={response.note} />
      </Field>
      <div className="row wide">
        <Button variant="primary" size="sm" disabled={pending}>
          Save
        </Button>
        <Button type="button" variant="quiet" size="sm" onClick={onDone}>
          Keep it as it was
        </Button>
      </div>
    </form>
  );
}

/**
 * The employer's answers to this application, newest first, each with who
 * recorded it; the day stays correctable. A sent application can record one.
 */
export function Responses({
  application,
  reload,
}: {
  application: Application;
  reload: () => void;
}) {
  const { mutate } = useWorkspace();
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<EmployerResponse | null>(null);
  const list = useResource<ListResult<EmployerResponse>>(
    `/applications/${application.id}/responses`,
    { items: [], total: 0 },
  );
  const responses = list.data.items;
  const sent = ["applied", "interview", "offer"].includes(application.status);
  return (
    <section className="stack" aria-labelledby="responses-title">
      <div className="spread">
        <h3 id="responses-title">Employer responses</h3>
        {sent && !adding && (
          <Button size="sm" icon="plus" onClick={() => setAdding(true)}>
            Record a response
          </Button>
        )}
      </div>
      {adding && (
        <div className="on-soft">
          <Respond
            application={application}
            reload={reload}
            onDone={() => setAdding(false)}
          />
        </div>
      )}
      {list.error && <ErrorBanner message={list.error} retry={list.reload} />}
      {list.loading ? (
        <Loading label="Loading the responses…" />
      ) : responses.length ? (
        <StatementList label="Employer responses">
          {responses.map((response) => (
            <Statement
              key={response.id}
              name={`${responseLabels[response.kind as ResponseKind]} of ${response.date}`}
              movable={false}
              editing={editing === response.id}
              label={`${responseLabels[response.kind as ResponseKind]} · ${day(response.date)}`}
              caption={<ActorChip actor={response.created_by} />}
              actions={
                <>
                  <Button
                    size="sm"
                    variant="quiet"
                    onClick={() => setEditing(response.id)}
                  >
                    Edit
                    <span className="sr"> the response of {response.date}</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="quiet danger"
                    onClick={() => setRemoving(response)}
                  >
                    Remove
                    <span className="sr"> the response of {response.date}</span>
                  </Button>
                </>
              }
            >
              {editing === response.id ? (
                <Edit response={response} onDone={() => setEditing(null)} />
              ) : (
                response.note && <p className="prose">{response.note}</p>
              )}
            </Statement>
          ))}
        </StatementList>
      ) : (
        <p className="muted">
          {application.status === "draft"
            ? "Once you send this application, the employer's answers are recorded here."
            : "No answer is recorded."}
        </p>
      )}
      {removing && (
        <ConfirmDialog
          title="Remove this response?"
          confirm="Remove the response"
          keep="Keep it"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(
                    `/responses/${removing.id}?expected_version=${removing.version}`,
                    "DELETE",
                  ),
                "Response removed.",
              )
            )
              setRemoving(null);
          }}
        >
          <p>
            The {responseLabels[removing.kind as ResponseKind].toLowerCase()} of{" "}
            {day(removing.date)} is removed. The stage of the application does
            not change.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
