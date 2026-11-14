// What the old Today and Jobs screens still read about applications. The
// Applications screen and the application page live in src/screens; this
// file, links.ts and CloseNoReply.tsx go with the old screens (#222, #223).
import type { Stage } from "../../api";

export const stageLabels: Record<Stage, string> = {
  shortlisted: "Shortlisted",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
};
export const outcomeLabels: Record<string, string> = {
  accepted: "Accepted",
  rejected: "Rejected",
  not_pursued: "Not pursued",
  no_response: "No reply",
};

const day = (value: string) => {
  const [year, month, date] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, date);
};
/** Whole days from one calendar day to another. */
export const daysBetween = (from: string, to: string) =>
  Math.max(
    0,
    Math.round((day(to).valueOf() - day(from).valueOf()) / 86_400_000),
  );
