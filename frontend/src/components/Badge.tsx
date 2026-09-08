import type { ReactNode } from "react";

import type { JobStatus } from "../api/types";
import { STATUS_LABELS, STATUS_TONE } from "../features/shared/labels";
import type { Tone } from "../features/shared/labels";

const TONE: Record<Tone, string> = {
  neutral: "bg-surface-2 text-fg-muted",
  muted: "bg-surface-2 text-fg-faint",
  info: "bg-info/12 text-info",
  accent: "bg-accent/12 text-accent",
  positive: "bg-positive/12 text-positive",
  warning: "bg-warning/14 text-warning",
  negative: "bg-negative/12 text-negative",
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
      className={`inline-flex max-w-full items-center gap-1 truncate rounded px-1.5 py-0.5 text-[11px] font-medium leading-4 ${TONE[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: JobStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABELS[status]}</Badge>;
}
