// How a recorded change is put into words. No React: tested directly.
import type { Json } from "../api";
import { readyReason } from "./ready.ts";

/** A recorded change, as a timeline or the change log has it. */
export interface Change {
  kind?: string;
  payload?: Json;
}

// The names of application stages and of job queues a change moves between.
const places: Record<string, string> = {
  draft: "Preparing",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  closed: "Closed",
  inbox: "Inbox",
  saved: "Shortlist",
  dismissed: "Dismissed",
};

// The titles of the Preferences sections a change names.
const sectionTitles: Record<string, string> = {
  looking_for: "What I'm looking for",
  ruled_out: "What I rule out",
  facts: "Facts about me",
  writing: "Writing rules",
  working_with_me: "Working with me",
};

/** What a change did beyond its name: where it moved a record, the fields it touched. */
export function changeDetail(event: Change) {
  const payload = event.payload || {};
  const place = (value: unknown) => places[String(value)] || String(value);
  if (payload.to && payload.to !== payload.from)
    return `${payload.from ? place(payload.from) + " → " : ""}${place(payload.to)}`;
  if (Array.isArray(payload.fields) && payload.fields.length)
    return "Fields: " + payload.fields.join(", ").replaceAll("_", " ");
  if (event.kind === "application_ready_cleared") return readyReason(payload);
  if (event.kind === "preferences_updated" && payload.section)
    return sectionTitles[String(payload.section)] || String(payload.section);
  return "";
}

/** "Application marked ready" from `application_marked_ready`. */
export function changeLabel(kind?: string) {
  const text = (kind || "updated").replaceAll("_", " ");
  return text[0].toUpperCase() + text.slice(1);
}
