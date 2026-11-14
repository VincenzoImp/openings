// What the old Jobs screen still reads about applications. The Applications
// screen and the application page live in src/screens; this file and
// links.ts go with the old Jobs screen (#223).
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

