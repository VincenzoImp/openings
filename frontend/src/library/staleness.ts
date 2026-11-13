// How a change since the documents were written is put into words. No React:
// tested directly.
import type { Application, StaleChange, StaleInput, Staleness } from "../api";

const inputNames: Record<StaleInput, string> = {
  profile: "Profile",
  policy: "Policy",
  instructions: "General instructions",
  template: "Template",
  knowledge: "Career entry",
  claim: "Claim",
};
const states: Record<StaleChange["state"], string> = {
  changed: "changed",
  deleted: "deleted",
  unapproved: "no longer approved",
  added: "added",
  removed: "removed",
  unconfirmed: "no longer confirmed",
  confirmed: "confirmed since",
};
// The section titles of the Policy page.
const sectionTitles: Record<string, string> = {
  decision: "Rules for shortlisting and dismissing jobs",
  eligibility: "Facts employers ask about",
  writing: "Rules for your documents",
  facts: "Other things you have confirmed",
};

const clip = (text: string, size: number) =>
  text.length > size ? `${text.slice(0, size - 1).trimEnd()}…` : text;

/** "Profile summary", "Policy “Work authorization”", "General instructions". */
export function changeName(change: StaleChange, size = 80) {
  if (change.input === "profile")
    return change.id === null
      ? "Profile"
      : `Profile ${change.label.toLowerCase()}`;
  if (change.input === "instructions" || !change.label)
    return inputNames[change.input];
  return `${inputNames[change.input]} “${clip(change.label, size)}”`;
}

/** What happened to it: "changed · Facts employers ask about". */
export function changeState(change: StaleChange) {
  const parts = [states[change.state] || change.state];
  if (change.input === "policy" && change.section)
    parts.push(sectionTitles[change.section] || change.section);
  else if (change.input === "profile" && change.id === null)
    parts.push("compared as a whole");
  else if (
    change.state === "changed" &&
    change.input !== "profile" &&
    change.frozen_version !== null &&
    change.current_version !== null
  )
    parts.push(`version ${change.frozen_version} → ${change.current_version}`);
  return parts.join(" · ");
}

/**
 * The documents one change concerns, when it is not every document written
 * from a frozen copy: a writing rule for the CV leaves the letter current.
 */
export function concerned(
  change: StaleChange,
  report: Staleness,
  kinds: Record<string, string>,
) {
  const compared = report.documents.filter((item) => item.context_id);
  const touched = compared.filter((item) =>
    item.changes.some(
      (other) => other.input === change.input && other.id === change.id,
    ),
  );
  if (!touched.length || touched.length === compared.length) return "";
  return touched.map((item) => kinds[item.kind] || item.kind).join(", ");
}

/**
 * What the comparison could not look at, for frozen copies made before the
 * Profile was compared by part or before the policy existed.
 */
export function comparisonNotes(report: Staleness) {
  const notes: string[] = [];
  const comparisons = report.documents.map((item) => item.comparison);
  if (comparisons.some((item) => item?.profile === "whole"))
    notes.push(
      "A frozen copy could not be read part by part, so any change to the Profile counts for it.",
    );
  if (comparisons.some((item) => item?.policy === "not_frozen"))
    notes.push(
      "A frozen copy made before the policy existed holds none of it, so policy changes are not compared for it.",
    );
  return notes;
}

/** What changed, under the list's "Inputs changed": "Profile summary and 2 more". */
export function staleDetail(app: Application) {
  const first = app.stale_changes?.[0];
  if (!first) return "";
  const rest = (app.stale_changes_total ?? app.stale_changes?.length ?? 1) - 1;
  return `${changeName(first, 32)}${rest > 0 ? ` and ${rest} more` : ""}`;
}
