import { Chip } from "@heroui/react";

import type { JobRecord } from "../../api/types";

export function scoreColor(score: number): "default" | "success" | "warning" {
  if (score >= 40) {
    return "success";
  }
  if (score >= 25) {
    return "warning";
  }
  return "default";
}

export function statusChip(job: JobRecord) {
  if (job.applied) {
    return (
      <Chip color="success" size="sm" variant="soft">
        Applied
      </Chip>
    );
  }
  if (job.bookmarked) {
    return (
      <Chip color="warning" size="sm" variant="soft">
        Saved
      </Chip>
    );
  }
  return (
    <Chip color="default" size="sm" variant="soft">
      Open
    </Chip>
  );
}

export function ScoreBadge({ score }: { score: number }) {
  return (
    <Chip
      className="w-9 min-w-9 justify-center px-0 font-semibold tabular-nums"
      color={scoreColor(score)}
      size="sm"
      variant="soft"
    >
      {score}
    </Chip>
  );
}

export function salaryLabel(job: JobRecord) {
  if (job.min_amount === null && job.max_amount === null) {
    return "unknown";
  }
  const currency = job.currency ?? "";
  const min = job.min_amount !== null ? `${currency} ${job.min_amount.toLocaleString()}` : "";
  const max = job.max_amount !== null ? `${currency} ${job.max_amount.toLocaleString()}` : "";
  return [min, max].filter(Boolean).join(" - ");
}

export function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-2">
      <span className="text-xs font-bold uppercase text-slate-500">{label}</span>
      <span className="truncate text-slate-800">{value}</span>
    </div>
  );
}
