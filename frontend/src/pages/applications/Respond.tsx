import { useState } from "react";
import { api, localToday, newId, type Application } from "../../api";
import { ResponseForm } from "../../design";
import { useAct } from "../activity/records";
import { CHOICES, likelyChoice, respondPlan, type Choice } from "./recording";

/**
 * Record what the employer answered a sent application: an interview, a
 * rejection, an offer, another answer, or no reply. A stage change and its
 * response are one call; another answer is added without moving the stage.
 */
export function Respond({
  application,
  reload,
  onDone,
}: {
  application: Application;
  /** Read the application again after a conflict. */
  reload: () => void;
  onDone: () => void;
}) {
  const [choice, setChoice] = useState<Choice>(() =>
    likelyChoice(application.status),
  );
  const [date, setDate] = useState(localToday);
  const [note, setNote] = useState("");
  const [key] = useState(newId);
  const { act, busy } = useAct(reload);
  const plan = respondPlan(application.status, choice, date, note);
  const title = application.job?.title || "this application";
  const company = application.job?.company || "the employer";
  async function save() {
    const outcome = await act(
      () =>
        plan.call === "update"
          ? api(`/applications/${application.id}`, "PATCH", {
              ...plan.body,
              expected_version: application.version,
            })
          : api(`/applications/${application.id}/responses`, "POST", {
              ...plan.body,
              idempotency_key: key,
            }),
      choice === "no_reply"
        ? "Closed as no reply."
        : choice === "rejection"
          ? "Rejection saved; the application is closed."
          : "Response saved.",
    );
    if (outcome === "ok") onDone();
  }
  return (
    <ResponseForm
      label={`Record the employer's response for ${title}, ${company}`}
      question={`What did ${company} answer?`}
      options={CHOICES}
      choice={choice}
      onChoice={(id) => setChoice(id as Choice)}
      date={date}
      onDate={setDate}
      dateLabel={choice === "no_reply" ? "Concluded on" : "Date of the answer"}
      note={note}
      onNote={setNote}
      withNote={plan.note}
      latest={localToday()}
      submit={plan.submit}
      caption={plan.caption}
      busy={busy}
      onSubmit={save}
      onCancel={onDone}
    />
  );
}
