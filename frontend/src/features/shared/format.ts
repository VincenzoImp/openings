import type { JobStatus, JobSummary } from "../../api/types";

export const STATUS_LABELS: Record<JobStatus, string> = {
  new: "New",
  shortlisted: "Shortlisted",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export function formatSalary(
  job: Pick<JobSummary, "min_amount" | "max_amount" | "currency">,
): string {
  const { min_amount: min, max_amount: max, currency } = job;
  if (min === null && max === null) {
    return "";
  }
  const unit = currency ? `${currency} ` : "";
  const compact = (value: number) =>
    value >= 1000 ? `${Math.round(value / 1000)}k` : String(Math.round(value));
  if (min !== null && max !== null && min !== max) {
    return `${unit}${compact(min)} - ${compact(max)}`;
  }
  return `${unit}${compact((min ?? max) as number)}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeDays(value: string | null | undefined, now = new Date()): string {
  if (!value) {
    return "";
  }
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(date.getTime())) {
    return value;
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
