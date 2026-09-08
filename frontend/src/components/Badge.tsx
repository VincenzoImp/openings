import type { ReactNode } from "react";

import type { JobStatus } from "../api/types";
import { STATUS_LABELS } from "../features/shared/format";

export type Tone = "neutral" | "blue" | "green" | "amber" | "rose" | "violet" | "slate";

const TONE: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  slate: "bg-slate-700 text-white",
  blue: "bg-sky-100 text-sky-800",
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-800",
  rose: "bg-rose-100 text-rose-800",
  violet: "bg-violet-100 text-violet-800",
};

export function Badge({
  tone = "neutral",
  children,
  className = "",
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${TONE[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export const STATUS_TONE: Record<JobStatus, Tone> = {
  new: "neutral",
  shortlisted: "blue",
  applied: "violet",
  interviewing: "amber",
  offer: "green",
  rejected: "rose",
  withdrawn: "slate",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABELS[status]}</Badge>;
}
