import { useState } from "react";

import type { JobStatus } from "../../api/types";
import { JOB_STATUSES } from "../../api/types";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field, Select, Textarea } from "../../components/Field";
import { STATUS_LABELS } from "./labels";
import { useJobCommands } from "./queries";

function StatusNoteForm({
  jobIds,
  initialStatus,
  onClose,
}: {
  jobIds: string[];
  initialStatus: JobStatus;
  onClose: () => void;
}) {
  const { setStatus } = useJobCommands();
  const [status, setStatusValue] = useState<JobStatus>(initialStatus);
  const [note, setNote] = useState("");

  const submit = () => {
    setStatus.mutate({ jobIds, status, note: note.trim() || undefined }, { onSuccess: onClose });
  };

  return (
    <form
      id="status-note-form"
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Field label="Status" htmlFor="status-note-status">
        <Select
          id="status-note-status"
          value={status}
          onChange={(event) => setStatusValue(event.target.value as JobStatus)}
          autoFocus
        >
          {JOB_STATUSES.filter((value) => value !== "blacklisted").map((value) => (
            <option key={value} value={value}>
              {STATUS_LABELS[value]}
            </option>
          ))}
        </Select>
      </Field>
      <Field
        label="Note for the timeline"
        htmlFor="status-note-text"
        hint="Optional: channel, date, what you sent."
      >
        <Textarea
          id="status-note-text"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Applied through the careers page with the tailored CV…"
        />
      </Field>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={setStatus.isPending}>
          {setStatus.isPending ? "Saving…" : "Save Status"}
        </Button>
      </div>
    </form>
  );
}

/** Change status with a note that lands on the timeline ("applied via LinkedIn on …"). */
export function StatusNoteDialog({
  open,
  jobIds,
  initialStatus,
  onClose,
}: {
  open: boolean;
  jobIds: string[];
  initialStatus: JobStatus;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={open}
      title={jobIds.length > 1 ? `Change status of ${jobIds.length} jobs` : "Change status"}
      onClose={onClose}
    >
      <StatusNoteForm jobIds={jobIds} initialStatus={initialStatus} onClose={onClose} />
    </Dialog>
  );
}
