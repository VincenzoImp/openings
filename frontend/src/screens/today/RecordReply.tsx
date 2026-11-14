import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { Field, Input, Select, Textarea } from "../../ui/Field";
import { useToast } from "../../ui/Toast";
import { useRecordReply, type Application, type ReplyKind } from "./data";
import { localDay, roleOf } from "./model";

const KINDS: { value: ReplyKind; label: string }[] = [
  { value: "interview", label: "Interview invitation" },
  { value: "rejection", label: "Rejection" },
  { value: "offer", label: "Offer" },
  { value: "other", label: "Other" },
];

/**
 * Record the employer's reply to a sent application: what happened, when,
 * and a note. The server moves the stage (an invitation to Interview, a
 * rejection to Closed).
 */
export function RecordReply({
  application,
  onClose,
}: {
  application: Application | null;
  onClose: () => void;
}) {
  const record = useRecordReply();
  const toast = useToast();
  const today = localDay(new Date());
  const [kind, setKind] = useState<ReplyKind>("interview");
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  // The form starts afresh for each application.
  const id = application?.id;
  useEffect(() => {
    if (!id) return;
    setKind("interview");
    setDate(localDay(new Date()));
    setNote("");
    record.reset();
  }, [id]); // `record` changes on every render.

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!application) return;
    const done = await record
      .mutateAsync({
        id: application.id,
        version: application.version,
        kind,
        date,
        note: note.trim(),
      })
      .catch(() => null);
    if (!done) return;
    const { title, company } = roleOf(application);
    toast.show({
      message: `Recorded the reply ${company ? `from ${company}` : `to “${title}”`}`,
      tone: "success",
    });
    onClose();
  }
  const role = application && roleOf(application);
  return (
    <Dialog
      open={Boolean(application)}
      onClose={onClose}
      title="Record reply"
      description={
        role && [role.title, role.company].filter(Boolean).join(" · ")
      }
      initialFocus="select"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="record-reply-form"
            disabled={record.isPending || !date}
          >
            {record.isPending ? "Recording…" : "Record reply"}
          </Button>
        </>
      }
    >
      <form
        id="record-reply-form"
        className="today-form"
        data-unguarded=""
        onSubmit={submit}
      >
        <Field label="What happened" error={record.error?.message}>
          <Select
            value={kind}
            onChange={(event) => setKind(event.target.value as ReplyKind)}
          >
            {KINDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Date">
          <Input
            type="date"
            value={date}
            max={today}
            required
            onChange={(event) => setDate(event.target.value)}
          />
        </Field>
        <Field label="Note" optional>
          <Textarea
            rows={3}
            value={note}
            maxLength={4000}
            onChange={(event) => setNote(event.target.value)}
          />
        </Field>
      </form>
    </Dialog>
  );
}
