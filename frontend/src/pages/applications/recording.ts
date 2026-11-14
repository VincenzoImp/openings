// What recording an employer's reply does, by the application's stage. No
// React: tested directly.
import type { Stage } from "../../api";

export type Choice = "interview" | "rejection" | "offer" | "no_reply" | "other";
export const CHOICES: { id: Choice; label: string }[] = [
  { id: "interview", label: "Interview" },
  { id: "rejection", label: "Rejection" },
  { id: "offer", label: "Offer" },
  { id: "other", label: "Other" },
  { id: "no_reply", label: "No reply" },
];

export interface Plan {
  /** The fields of the application update, without the version. */
  body: Record<string, unknown>;
  submit: string;
  caption: string;
  /** No reply is an outcome, not a reply: it has no note. */
  note: boolean;
}

const CORRECTABLE = "The date stays correctable in its timeline.";

// The stage a reply moves an application to, from the stages it moves it from
// (as the server decides: a Closed application without a reply reopens).
const MOVES: Record<string, { to: Stage; from: Stage[]; words: string }> = {
  interview: {
    to: "interview",
    from: ["applied"],
    words: "The application moves to Interview.",
  },
  offer: {
    to: "offer",
    from: ["applied", "interview"],
    words: "The application moves to Offer.",
  },
  rejection: {
    to: "closed",
    from: ["applied", "interview", "offer"],
    words: "A rejection closes the application.",
  },
};

/** The update that records `choice` for an application in `status`. */
export function replyPlan(
  status: Stage,
  choice: Choice,
  date: string,
  note: string,
  outcome: string | null = null,
): Plan {
  if (choice === "no_reply")
    return {
      body: { status: "closed", outcome: "no_response", concluded_on: date },
      submit: "Close as no reply",
      caption:
        "No reply closes the application. Insights counts it as sent without an answer.",
      note: false,
    };
  const reply = { reply: { kind: choice, date, ...(note ? { note } : {}) } };
  const move = MOVES[choice];
  const moves =
    move &&
    (move.from.includes(status) ||
      (status === "closed" && outcome === "no_response"));
  const submit = {
    interview: "Save the interview",
    rejection: "Save the rejection",
    offer: "Save the offer",
    other: "Save the reply",
  }[choice];
  return {
    body: reply,
    submit,
    caption: `${moves ? move.words : "The stage does not change."} ${CORRECTABLE}`,
    note: true,
  };
}

/** The reply an owner most likely records next for an application in `status`. */
export const likelyChoice = (status: Stage): Choice =>
  status === "interview" ? "offer" : status === "offer" ? "other" : "interview";
