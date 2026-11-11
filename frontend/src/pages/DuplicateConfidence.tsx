import type { DuplicateReasons } from "../api";

const reasonLabels: Record<string, string> = {
  apply_target: "Same apply link",
  requisition_id: "Same requisition ID",
  posting_text: "Identical posting text",
  near_identical_text: "Nearly identical text",
  similar_text: "Similar text",
  company_title: "Same company and role",
  company: "Same company",
  title: "Same role",
  similar_title: "Similar role",
  location: "Same location",
};
const conflictLabels: Record<string, string> = {
  apply_target: "Different posting ID",
  requisition_id: "Different requisition ID",
  location: "Different location",
  seniority: "Different level",
  posting_text: "Different text",
  posting_date: "Posted months apart",
  ambiguous: "Matches another vacancy too",
};
const tierLabels = { high: "High", medium: "Medium", low: "Low" };

/** Lowest confidence to list: the high tier, the default, or every candidate. */
export function ConfidenceFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <select
      aria-label="Confidence"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="0.85">High confidence</option>
      <option value="0.5">Medium and high</option>
      <option value="0">Every candidate</option>
    </select>
  );
}

/** Confidence with the signals that matched and those that conflict. */
export function ConfidenceTags({
  confidence,
  tier,
  reasons,
}: {
  confidence: number;
  tier: "high" | "medium" | "low";
  reasons: DuplicateReasons;
}) {
  return (
    <>
      <span
        className={`tag ${tier === "high" ? "green" : tier === "low" ? "amber" : "neutral"}`}
        title="How likely these records describe one vacancy"
      >
        {tierLabels[tier]} confidence · {Math.round(confidence * 100)}%
      </span>
      {reasons.matched.map((signal) => (
        <span className="tag neutral" key={signal}>
          {reasonLabels[signal] || signal}
        </span>
      ))}
      {reasons.conflicts.map((signal) => (
        <span className="tag amber" key={signal}>
          {conflictLabels[signal] || signal}
        </span>
      ))}
    </>
  );
}
