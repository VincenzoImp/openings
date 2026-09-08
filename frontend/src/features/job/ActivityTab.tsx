import type { EventKind, JobDetail } from "../../api/types";
import { Badge } from "../../components/Badge";
import type { Tone } from "../../components/Badge";
import { formatDateTime } from "../shared/format";

const KIND_TONE: Record<EventKind, Tone> = {
  ingested: "neutral",
  status: "blue",
  label: "violet",
  note: "amber",
  attachment: "green",
};

export function ActivityTab({ job }: { job: JobDetail }) {
  const events = [...job.events].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      {events.length === 0 ? (
        <p className="text-sm text-slate-500">No activity recorded.</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {events.map((event) => (
            <li key={event.id} className="flex items-start gap-3">
              <span className="w-36 shrink-0 text-xs text-slate-500">
                {formatDateTime(event.created_at)}
              </span>
              <Badge tone={KIND_TONE[event.kind]}>{event.kind}</Badge>
              <span className="text-sm text-slate-800">{event.summary}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
