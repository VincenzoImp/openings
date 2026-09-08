import type { JobSummary } from "../../api/types";

export { STATUS_LABELS } from "./labels";

const numberFormat = new Intl.NumberFormat();
const dateFormat = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "2-digit",
});
const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});
const compactFormat = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 0,
});

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

function parse(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }
  // A bare date is a calendar day; do not shift it through the time zone.
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatSalary(
  job: Pick<JobSummary, "min_amount" | "max_amount" | "currency">,
): string {
  const { min_amount: min, max_amount: max, currency } = job;
  if (min === null && max === null) {
    return "";
  }
  const unit = currency ? `${currency} ` : "";
  if (min !== null && max !== null && min !== max) {
    return `${unit}${compactFormat.format(min)}–${compactFormat.format(max)}`;
  }
  return `${unit}${compactFormat.format((min ?? max) as number)}`;
}

export function formatDate(value: string | null | undefined): string {
  const date = parse(value);
  return date ? dateFormat.format(date) : "";
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parse(value);
  return date ? dateTimeFormat.format(date) : "";
}

export function relativeDays(value: string | null | undefined, now = new Date()): string {
  const date = parse(value);
  if (!date) {
    return "";
  }
  const days = Math.floor((now.getTime() - date.getTime()) / 86_400_000);
  if (days <= 0) {
    return "today";
  }
  if (days === 1) {
    return "yesterday";
  }
  if (days < 30) {
    return `${days}d ago`;
  }
  return formatDate(value);
}

export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (minutes >= 60) {
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  }
  return `${minutes}m ${rest}s`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function jobMeta(job: JobSummary): string[] {
  const parts: string[] = [];
  if (job.job_type) {
    parts.push(job.job_type);
  }
  if (job.is_remote) {
    parts.push("remote");
  }
  if (job.job_level) {
    parts.push(job.job_level);
  }
  const salary = formatSalary(job);
  if (salary) {
    parts.push(salary);
  }
  return parts;
}
