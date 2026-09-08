import type { JobDetail, JobEvent, JobStatus } from "../../api/types";
import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { formatDateTime, relativeDays } from "../shared/format";
import { EVENT_LABELS, EVENT_TONE, STATUS_LABELS } from "../shared/labels";

function statusName(value: unknown): string {
  return typeof value === "string" && value in STATUS_LABELS
    ? STATUS_LABELS[value as JobStatus]
    : String(value);
}

/** Render the structured part of an event as short "key value" chips. */
function EventData({ event }: { event: JobEvent }) {
  const data = event.data;
  if (!data) {
    return null;
  }
  const chips: string[] = [];
  if (event.kind === "status" && "from" in data && "to" in data) {
    chips.push(`${statusName(data.from)} → ${statusName(data.to)}`);
  }
  for (const [key, value] of Object.entries(data)) {
    if (["from", "to"].includes(key) && event.kind === "status") {
      continue;
    }
    if (value === null || value === undefined || value === "") {
      continue;
    }
    const text = Array.isArray(value)
      ? value.join(", ")
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
    if (text.length > 120) {
      continue;
    }
    chips.push(`${key.replace(/_/g, " ")}: ${text}`);
  }
  if (chips.length === 0) {
    return null;
  }
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {chips.map((chip) => (
        <Badge key={chip} className="max-w-full truncate">
          {chip}
        </Badge>
      ))}
    </div>
  );
}

export function ActivityTab({ job }: { job: JobDetail }) {
  const events = [...job.events].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  return (
    <Card title="Timeline">
      {events.length === 0 ? (
        <p className="text-sm text-fg-muted">No activity recorded.</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {events.map((event) => (
            <li
              key={event.id}
              className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 sm:grid-cols-[9rem_auto_1fr]"
            >
              <time
                dateTime={event.created_at}
                title={formatDateTime(event.created_at)}
                className="col-span-2 text-xs text-fg-muted sm:col-span-1"
              >
                {relativeDays(event.created_at)} · {formatDateTime(event.created_at)}
              </time>
              <Badge tone={EVENT_TONE[event.kind] ?? "neutral"}>
                {EVENT_LABELS[event.kind] ?? event.kind}
              </Badge>
              <div className="min-w-0">
                <span className="break-words text-sm text-fg">{event.summary}</span>
                <EventData event={event} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
