import { useState, type FormEvent } from "react";
import { api, localToday, type Application, type Reply } from "../../api";
import {
  actorPhrase,
  Button,
  Field,
  Statement,
  StatementList,
} from "../../design";
import { ConfirmDialog } from "../../library/common";
import { shortDate } from "../../library/time";
import { useWorkspace } from "../../state";
import { replyLabels } from "../applications/model";
import { Respond } from "../applications/Respond";

/** "10 Oct" for a calendar day (YYYY-MM-DD), read in local time. */
export const day = (value: string) => {
  const [year, month, date] = value.split("-").map(Number);
  return shortDate(new Date(year, month - 1, date));
};

/** Correct a reply's kind, day or note: an update of its application. */
function Edit({
  application,
  reply,
  onDone,
}: {
  application: Application;
  reply: Reply;
  onDone: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const ok = await mutate(
      () =>
        api(`/applications/${application.id}`, "PATCH", {
          expected_version: application.version,
          reply: {
            id: reply.id,
            kind: form.get("kind"),
            date: form.get("date"),
            note: String(form.get("note") || ""),
          },
        }),
      "Reply corrected.",
    );
    if (ok) onDone();
  }
  return (
    <form
      className="edit-grid grow"
      onSubmit={save}
      aria-label="Correct the reply"
    >
      <Field label="What happened">
        <select name="kind" defaultValue={reply.kind}>
          {Object.entries(replyLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Date of the reply">
        <input
          type="date"
          name="date"
          required
          max={localToday()}
          defaultValue={reply.date}
        />
      </Field>
      <Field label="Note" className="wide">
        <input name="note" maxLength={2000} defaultValue={reply.note} />
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
 * The employer's replies to this application, newest first, each with who
 * recorded it; a reply stays correctable. A sent application can record one.
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
  const [removing, setRemoving] = useState<Reply | null>(null);
  const replies = application.replies || [];
  const sent = ["applied", "interview", "offer"].includes(application.status);
  return (
    <section className="stack" aria-labelledby="replies-title">
      <div className="spread">
        <h3 id="replies-title">Employer replies</h3>
        {sent && !adding && (
          <Button size="sm" icon="plus" onClick={() => setAdding(true)}>
            Record reply
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
      {replies.length ? (
        <StatementList label="Employer replies">
          {replies.map((reply) => (
            <Statement
              key={reply.id}
              name={`${replyLabels[reply.kind]} of ${reply.date}`}
              movable={false}
              editing={editing === reply.id}
              label={`${replyLabels[reply.kind]} · ${day(reply.date)}`}
              caption={
                actorPhrase(reply.created_by)
                  ? `Recorded ${actorPhrase(reply.created_by)}`
                  : undefined
              }
              actions={
                <>
                  <Button
                    size="sm"
                    variant="quiet"
                    onClick={() => setEditing(reply.id)}
                  >
                    Edit
                    <span className="sr"> the reply of {reply.date}</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="quiet danger"
                    onClick={() => setRemoving(reply)}
                  >
                    Remove
                    <span className="sr"> the reply of {reply.date}</span>
                  </Button>
                </>
              }
            >
              {editing === reply.id ? (
                <Edit
                  application={application}
                  reply={reply}
                  onDone={() => setEditing(null)}
                />
              ) : (
                reply.note && <p className="prose">{reply.note}</p>
              )}
            </Statement>
          ))}
        </StatementList>
      ) : (
        <p className="muted">
          {application.status === "shortlisted"
            ? "Once you send this application, the employer's replies are recorded here."
            : "No reply is recorded."}
        </p>
      )}
      {removing && (
        <ConfirmDialog
          title="Remove this reply?"
          confirm="Remove the reply"
          keep="Keep it"
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            if (
              await mutate(
                () =>
                  api(`/applications/${application.id}`, "PATCH", {
                    expected_version: application.version,
                    reply: { id: removing.id, remove: true },
                  }),
                "Reply removed.",
              )
            )
              setRemoving(null);
          }}
        >
          <p>
            The {replyLabels[removing.kind].toLowerCase()} of{" "}
            {day(removing.date)} is removed. The stage of the application does
            not change.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
