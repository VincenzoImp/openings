import { useState } from "react";
import {
  api,
  date,
  type DuplicateGroup,
  type DuplicateReasons,
  type Job,
  type ListResult,
} from "../../api";
import { Button, Tag } from "../../design";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";
import { MergeDialog } from "./MergeDialog";
import { JOB_SCOPES, placeTag, sourceLabel } from "./model";

const MATCHED: Record<string, string> = {
  apply_target: "the same apply link",
  requisition_id: "the same requisition ID",
  posting_text: "identical posting text",
  near_identical_text: "nearly identical text",
  similar_text: "similar text",
  company_title: "the same company and role",
  company: "the same company",
  title: "the same role",
  similar_title: "a similar role",
  location: "the same place",
};
const CONFLICTS: Record<string, string> = {
  apply_target: "a different posting ID",
  requisition_id: "a different requisition ID",
  location: "a different place",
  seniority: "a different level",
  posting_text: "different text",
  posting_date: "posted months apart",
  ambiguous: "it matches another vacancy too",
};

/** Why two records look like one vacancy, in a sentence, without a score. */
export function reasonsLine(reasons: DuplicateReasons) {
  const matched = reasons.matched.map(
    (key) => MATCHED[key] || key.replaceAll("_", " "),
  );
  const conflicts = reasons.conflicts.map(
    (key) => CONFLICTS[key] || key.replaceAll("_", " "),
  );
  const parts = [];
  if (matched.length) parts.push(`Both have ${matched.join(", ")}`);
  if (conflicts.length) parts.push(`but ${conflicts.join(", ")}`);
  return parts.length ? parts.join("; ").replace("; but", ", but") + "." : "";
}

/**
 * "Is this the same vacancy?": the earlier job this one likely repeats, with
 * why, and the decision: merge the two, or mark them as different vacancies.
 */
export function Duplicate({
  job,
  onOpenJob,
}: {
  job: Job;
  onOpenJob: (id: string) => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [merging, setMerging] = useState(false);
  const flag = job.signals.duplicate!;
  const other = useFresh<Job | null>(
    `/jobs/${encodeURIComponent(flag.job_id)}`,
    null,
    JOB_SCOPES,
  );
  const group = useFresh<ListResult<DuplicateGroup>>(
    `/jobs/duplicates?job_id=${encodeURIComponent(job.id)}&min_confidence=0&limit=1`,
    { items: [], total: 0 },
    JOB_SCOPES,
  );
  if (other.error || other.loading || !other.data) return null;
  const candidate = other.data;
  const members = group.data.items[0];
  const item = members?.items.find((entry) => entry.id === candidate.id);
  const reasons = item?.reasons || members?.reasons;
  const place = placeTag(candidate);
  return (
    <section className="detail-section" aria-labelledby="duplicate-title">
      <h3 id="duplicate-title">Is this the same vacancy?</h3>
      <div className="duplicate">
        <a
          className="title"
          href={`#jobs?job=${encodeURIComponent(candidate.id)}`}
          onClick={(event) => {
            if (event.button !== 0 || event.metaKey || event.ctrlKey) return;
            event.preventDefault();
            onOpenJob(candidate.id);
          }}
        >
          {candidate.title}
        </a>
        <div className="meta">
          {[candidate.company, candidate.location].filter(Boolean).join(" · ")}{" "}
          · found on {sourceLabel(candidate)}, {date(candidate.created_at)}
        </div>
        <div className="row">
          <Tag tone="info">Possible duplicate</Tag>
          <Tag tone={place.tone}>{place.text}</Tag>
          {reasons && <span className="caption">{reasonsLine(reasons)}</span>}
        </div>
        <div className="row">
          <Button size="sm" disabled={pending} onClick={() => setMerging(true)}>
            Merge into one job
          </Button>
          <Button
            size="sm"
            disabled={pending}
            onClick={() =>
              mutate(
                () =>
                  api(`/jobs/${job.id}/distinct`, "POST", {
                    other_id: candidate.id,
                  }),
                "Marked as a different vacancy.",
              )
            }
          >
            Keep both
          </Button>
        </div>
      </div>
      <p className="caption">
        Merging keeps one job with both sources and both timelines, so you do
        not apply twice. Nothing is merged without this decision.
      </p>
      {merging && (
        <MergeDialog
          job={job}
          target={candidate}
          onClose={() => setMerging(false)}
          onMerged={(kept) => {
            setMerging(false);
            onOpenJob(kept);
          }}
        />
      )}
    </section>
  );
}
