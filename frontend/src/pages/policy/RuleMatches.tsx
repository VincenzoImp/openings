import { useEffect, useState } from "react";
import {
  api,
  type JobList,
  type PolicyItem,
  type RulePreview,
} from "../../api";
import { plural } from "../../library/common";
import { useFresh } from "../../library/useFresh";
import { useWorkspace } from "../../state";

const NONE: JobList = { items: [], total: 0 };

/**
 * What a rule does with today's jobs: how many jobs waiting for review it
 * matches (a dry run; rules act only on new jobs) and how many it dismissed.
 */
export function RuleMatches({ item }: { item: PolicyItem }) {
  const { revision } = useWorkspace();
  const [preview, setPreview] = useState<RulePreview | null>(null);
  const rule = JSON.stringify(item.rule);
  useEffect(() => {
    if (!item.rule) return;
    const abort = new AbortController();
    api<RulePreview>(
      "/policy/rules/preview",
      "POST",
      { rule: item.rule },
      abort.signal,
    ).then(setPreview, () => setPreview(null));
    return () => abort.abort();
  }, [rule, revision]);
  const dismissed = useFresh<JobList>(
    `/jobs?rule_id=${encodeURIComponent(item.id)}&queue=dismissed&limit=1`,
    NONE,
    ["jobs"],
  );
  if (!item.rule) return null;
  return (
    <span className="muted rule-matches">
      {preview &&
        `It matches ${preview.matches} of the ${plural(preview.inbox, "job")} to review now${
          preview.pending
            ? `, ${preview.pending} of them without signals yet`
            : ""
        }; a rule acts only on jobs nobody has reviewed yet, when their signal arrives.`}{" "}
      {dismissed.data.total > 0 && (
        <a
          href={`#jobs?section=dismissed&rule_id=${encodeURIComponent(item.id)}`}
        >
          {plural(dismissed.data.total, "job")} dismissed by it
        </a>
      )}
    </span>
  );
}
