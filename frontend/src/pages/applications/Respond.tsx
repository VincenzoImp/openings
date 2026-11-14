import { useState } from "react";
import { api, localToday, type Application } from "../../api";
import { ResponseForm } from "../../design";
import { useAct } from "../../library/records";
import { CHOICES, likelyChoice, replyPlan, type Choice } from "./recording";

/**
 * Record reply: what the employer did about a sent application (an interview,
 * a rejection, an offer or another reply), or close it as no reply. One update
 * records the reply and moves the stage when the reply implies it.
 */
export function Respond({
  application,
  reload,
  onDone,
  stacked = false,
}: {
  application: Application;
  /** Laid out for a dialog: one field under the other. */
  stacked?: boolean;
  /** Read the application again after a conflict. */
  reload: () => void;
  onDone: () => void;
}) {
  const [choice, setChoice] = useState<Choice>(() =>
    likelyChoice(application.status),
  );
  const [date, setDate] = useState(localToday);
  const [note, setNote] = useState("");
  const { act, busy } = useAct(reload);
  const plan = replyPlan(
    application.status,
    choice,
    date,
    note,
    application.outcome,
  );
  const title = application.job?.title || "this application";
  const company = application.job?.company || "the employer";
  async function save() {
    const outcome = await act(
      () =>
        api(`/applications/${application.id}`, "PATCH", {
          ...plan.body,
          expected_version: application.version,
        }),
      choice === "no_reply" ? "Closed as no reply." : "Reply saved.",
    );
    if (outcome === "ok") onDone();
  }
  return (
    <ResponseForm
      label={`Record the employer's reply for ${title}, ${company}`}
      question={`What happened with ${company}?`}
      options={CHOICES}
      choice={choice}
      onChoice={(id) => setChoice(id as Choice)}
      date={date}
      onDate={setDate}
      dateLabel={choice === "no_reply" ? "Concluded on" : "Date of the reply"}
      note={note}
      onNote={setNote}
      withNote={plan.note}
      latest={localToday()}
      submit={plan.submit}
      caption={plan.caption}
      busy={busy}
      stacked={stacked}
      onSubmit={save}
      onCancel={onDone}
    />
  );
}
