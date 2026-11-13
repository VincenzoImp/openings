// What recording an employer's answer does, by the application's stage. No
// React: tested directly.
import type { Stage } from "../../api";

export type Choice = "interview" | "rejection" | "offer" | "no_reply" | "other";
export const CHOICES: { id: Choice; label: string }[] = [
  { id: "interview", label: "Interview" },
  { id: "rejection", label: "Rejection" },
  { id: "offer", label: "Offer" },
  { id: "no_reply", label: "No reply" },
  { id: "other", label: "Other" },
];

export interface Plan {
  /** PATCH the application (a stage change with its response) or POST a response. */
  call: "update" | "add";
  /** The fields of the call, without the version. */
  body: Record<string, unknown>;
  submit: string;
  caption: string;
  /** No reply is an outcome, not a response: it has no note. */
  note: boolean;
}

const CORRECTABLE = "The date stays correctable in its timeline.";

/** The call that records `choice` for an application in `status`. */
export function respondPlan(
  status: Stage,
  choice: Choice,
  date: string,
  note: string,
): Plan {
  const response = {
    response_date: date,
    ...(note ? { response_note: note } : {}),
  };
  const add = (kind: string, submit: string): Plan => ({
    call: "add",
    body: { kind, date, note },
    submit,
    caption: `The stage does not change. ${CORRECTABLE}`,
    note: true,
  });
  if (choice === "rejection")
    return {
      call: "update",
      body: { status: "closed", outcome: "rejected", ...response },
      submit: "Save and close as rejected",
      caption: `A rejection closes the application. ${CORRECTABLE}`,
      note: true,
    };
  if (choice === "no_reply")
    return {
      call: "update",
      body: { status: "closed", outcome: "no_response", concluded_on: date },
      submit: "Close as no reply",
      caption:
        "No reply closes the application. Insights counts it as sent without an answer.",
      note: false,
    };
  if (choice === "interview")
    return status === "applied"
      ? {
          call: "update",
          body: { status: "interview", ...response },
          submit: "Save and move to Interview",
          caption: `The application moves to Interview. ${CORRECTABLE}`,
          note: true,
        }
      : add("interview", "Save the interview");
  if (choice === "offer")
    return status === "offer"
      ? add("offer", "Save the offer")
      : {
          call: "update",
          body: { status: "offer", ...response },
          submit: "Save and move to Offer",
          caption: `The application moves to Offer. ${CORRECTABLE}`,
          note: true,
        };
  return add("other", "Save the answer");
}

/** The answer an owner most likely records next for an application in `status`. */
export const likelyChoice = (status: Stage): Choice =>
  status === "interview" ? "offer" : status === "offer" ? "other" : "interview";
