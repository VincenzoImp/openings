import { useMemo, useState } from "react";

import type { JobDetail, JobSummary } from "../../api/types";
import { StatusBadge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Checkbox, Input } from "../../components/Field";
import { useJobCommands, useJobs, useSimilar } from "../shared/queries";

function MergeForm({ job, onClose }: { job: JobDetail; onClose: () => void }) {
  const { mergeJobs } = useJobCommands();
  const [text, setText] = useState(job.company);
  const [chosen, setChosen] = useState<Set<string>>(() => new Set());
  const search = useJobs(
    { text: text.trim() || undefined, limit: 30, sort: "updated" },
    text.trim().length > 1,
  );
  const similar = useSimilar(job.job_id);

  const candidates = useMemo(() => {
    const seen = new Map<string, JobSummary>();
    for (const item of [...(similar.data ?? []), ...(search.data?.items ?? [])]) {
      if (item.job_id !== job.job_id && !seen.has(item.job_id)) {
        seen.set(item.job_id, item);
      }
    }
    return Array.from(seen.values());
  }, [similar.data, search.data, job.job_id]);

  const toggle = (id: string) =>
    setChosen((current) => {
      const copy = new Set(current);
      if (copy.has(id)) {
        copy.delete(id);
      } else {
        copy.add(id);
      }
      return copy;
    });

  const submit = () => {
    if (chosen.size === 0) {
      return;
    }
    mergeJobs.mutate(
      { primaryId: job.job_id, otherIds: Array.from(chosen) },
      { onSuccess: onClose },
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-fg-muted">
        Postings, labels, notes, files and the timeline of the selected jobs move here and the
        selected jobs are removed. Similar postings are listed first.
      </p>
      <Input
        aria-label="Search jobs to merge"
        placeholder="Search by title, company or notes…"
        value={text}
        autoComplete="off"
        onChange={(event) => setText(event.target.value)}
        autoFocus
      />
      <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
        {candidates.map((item) => (
          <li
            key={item.job_id}
            className="flex items-start gap-2 rounded-md px-1 py-1 hover:bg-surface-2"
          >
            <Checkbox
              label={
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-medium text-fg">{item.title}</span>
                  <span className="truncate text-xs text-fg-muted">
                    {item.company}
                    {item.location ? ` · ${item.location}` : ""} · {item.source}
                  </span>
                </span>
              }
              checked={chosen.has(item.job_id)}
              onChange={() => toggle(item.job_id)}
              className="min-w-0 flex-1"
            />
            <StatusBadge status={item.status} />
          </li>
        ))}
        {candidates.length === 0 ? (
          <li className="py-4 text-center text-sm text-fg-muted">
            {search.isFetching || similar.isFetching ? "Searching…" : "No other jobs match."}
          </li>
        ) : null}
      </ul>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="primary"
          disabled={chosen.size === 0 || mergeJobs.isPending}
          onClick={submit}
        >
          {mergeJobs.isPending ? "Merging…" : chosen.size ? `Merge ${chosen.size}` : "Merge"}
        </Button>
      </div>
    </div>
  );
}

/** Pick other jobs (duplicates, mirrors) whose material moves into this one. */
export function MergeDialog({
  open,
  job,
  onClose,
}: {
  open: boolean;
  job: JobDetail;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} title="Merge Into This Job" onClose={onClose}>
      <MergeForm job={job} onClose={onClose} />
    </Dialog>
  );
}
