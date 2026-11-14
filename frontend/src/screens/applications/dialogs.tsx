// The dialogs of an application, shared by the list and the page: Record
// reply, Close…, Change stage…, the plan (deadline, priority), the required
// documents and the permanent deletion.
import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { ApiError } from "../../api/client";
import { ConflictNotice } from "../../query/ConflictNotice";
import { Button } from "../../ui/Button";
import { Choice } from "../../ui/Choice";
import { ConfirmDialog, Dialog } from "../../ui/Dialog";
import { Checkbox, Field, Input, Select, Textarea } from "../../ui/Field";
import { useToast } from "../../ui/Toast";
import {
  useDeleteApplication,
  useUpdateApplication,
  useVersionedUpdate,
  type Patch,
} from "./data";
import {
  OUTCOMES,
  REPLY_KINDS,
  isSent,
  isoDay,
  likelyReply,
  replyEffect,
  type ReplyKind,
} from "./model";

/** The application a dialog acts on. */
export interface Target {
  id: string;
  version: number;
  status: string;
  title: string;
  applied_at?: string | null;
  outcome?: string | null;
  deadline?: string | null;
  priority?: number | null;
  required_documents?: string[];
}

export const errorText = (error: unknown) =>
  error instanceof ApiError
    ? error.fields[0] || error.message
    : "Something went wrong. Try again.";

/** A dialog whose body is a form: Enter submits, the primary is its submit. */
function FormDialog({
  open,
  onClose,
  title,
  submit,
  busy,
  disabled,
  onSubmit,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  submit: string;
  busy?: boolean;
  disabled?: boolean;
  onSubmit: () => void;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      initialFocus="input:not([type=hidden]), textarea, select"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form={id}
            disabled={busy || disabled}
          >
            {busy ? "Saving…" : submit}
          </Button>
        </>
      }
    >
      <form
        id={id}
        className="ap-form"
        aria-label={title}
        noValidate
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (!busy && !disabled) onSubmit();
        }}
      >
        {children}
      </form>
    </Dialog>
  );
}

/** Run a single-record change and report it as a toast. */
function useChange(onDone: () => void) {
  const update = useUpdateApplication();
  const toast = useToast();
  const run = (target: Target, patch: Patch, message: string) =>
    update.mutate(
      { id: target.id, version: target.version, patch },
      {
        onSuccess: () => {
          toast.show({ message, tone: "success" });
          onDone();
        },
        onError: (error) =>
          toast.show({ message: errorText(error), tone: "error" }),
      },
    );
  return { run, busy: update.isPending };
}

/**
 * Record reply: what happened (interview invitation, rejection, offer,
 * other), its day (today by default) and a note. It records the reply and
 * moves the stage with it.
 */
export function RecordReplyDialog({
  target,
  onClose,
}: {
  target: Target | null;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<ReplyKind>("interview");
  const [date, setDate] = useState(isoDay());
  const [note, setNote] = useState("");
  useEffect(() => {
    if (!target) return;
    setKind(likelyReply(target.status));
    setDate(isoDay());
    setNote("");
  }, [target]);
  const change = useChange(onClose);
  const words = REPLY_KINDS.find((item) => item.id === kind)!.label;
  return (
    <FormDialog
      open={!!target}
      onClose={onClose}
      title="Record reply"
      submit="Record reply"
      busy={change.busy}
      disabled={!date}
      onSubmit={() =>
        target &&
        change.run(
          target,
          {
            reply: {
              kind,
              date,
              note: note.trim() || undefined,
              remove: false,
            },
          },
          `Recorded: ${words.toLowerCase()} for "${target.title}"`,
        )
      }
    >
      <Choice
        legend="What happened"
        options={REPLY_KINDS.map((item) => ({
          value: item.id,
          label: item.label,
        }))}
        value={kind}
        onChange={setKind}
      />
      <Field label="Date of the reply">
        <Input
          type="date"
          value={date}
          max={isoDay()}
          required
          onChange={(event) => setDate(event.target.value)}
        />
      </Field>
      <Field label="Note" optional>
        <Textarea
          rows={3}
          value={note}
          maxLength={5000}
          onChange={(event) => setNote(event.target.value)}
        />
      </Field>
      {target && (
        <p className="ap-caption">
          {replyEffect(target.status, kind, target.outcome)}
        </p>
      )}
    </FormDialog>
  );
}

/** The outcomes a Close can record for these applications. */
export function closeOutcomes(
  targets: Pick<Target, "status" | "applied_at">[],
) {
  const sent = targets.every((target) => !!target.applied_at);
  const offer = targets.every((target) => target.status === "offer");
  return [
    { value: "rejected", label: "Rejected", hint: "The employer said no." },
    ...(sent
      ? [
          {
            value: "no_response",
            label: "No reply",
            hint: "No answer came within the no-reply period.",
          },
        ]
      : []),
    {
      value: "not_pursued",
      label: "Not pursuing",
      hint: "You stopped. Never sent ones stay out of Stats.",
    },
    ...(offer
      ? [{ value: "accepted", label: "Accepted", hint: "You took the offer." }]
      : []),
  ] as { value: string; label: string; hint: string }[];
}

/** Close…: choose the outcome. Reopen undoes it. */
export function CloseDialog({
  target,
  onClose,
}: {
  target: Target | null;
  onClose: () => void;
}) {
  const [outcome, setOutcome] = useState("rejected");
  useEffect(() => {
    if (target) setOutcome(isSent(target.status) ? "rejected" : "not_pursued");
  }, [target]);
  const change = useChange(onClose);
  return (
    <FormDialog
      open={!!target}
      onClose={onClose}
      title="Close the application"
      submit="Close"
      busy={change.busy}
      onSubmit={() =>
        target &&
        change.run(
          target,
          { status: "closed", outcome: outcome as Patch["outcome"] },
          `Closed "${target.title}" · ${OUTCOMES[outcome].toLowerCase()}`,
        )
      }
    >
      <Choice
        legend="Outcome"
        options={closeOutcomes(target ? [target] : [])}
        value={outcome}
        onChange={setOutcome}
      />
    </FormDialog>
  );
}

const STAGE_CHOICES = [
  { value: "shortlisted", label: "Shortlisted", hint: "Not sent yet." },
  { value: "applied", label: "Applied", hint: "Sent; waiting for a reply." },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "closed", label: "Closed", hint: "With an outcome." },
];

/** Change stage…: any stage, with an outcome when it is Closed. */
export function StageDialog({
  target,
  onClose,
}: {
  target: Target | null;
  onClose: () => void;
}) {
  const [stage, setStage] = useState("applied");
  const [outcome, setOutcome] = useState("rejected");
  useEffect(() => {
    if (!target) return;
    setStage(target.status);
    setOutcome(target.outcome || "rejected");
  }, [target]);
  const change = useChange(onClose);
  const label = STAGE_CHOICES.find((item) => item.value === stage)?.label;
  return (
    <FormDialog
      open={!!target}
      onClose={onClose}
      title="Change stage"
      submit="Change stage"
      busy={change.busy}
      disabled={!target || (stage === target.status && stage !== "closed")}
      onSubmit={() =>
        target &&
        change.run(
          target,
          stage === "closed"
            ? { status: "closed", outcome: outcome as Patch["outcome"] }
            : { status: stage as Patch["status"] },
          `Moved "${target.title}" to ${label}`,
        )
      }
    >
      <Choice
        legend="Stage"
        options={STAGE_CHOICES}
        value={stage}
        onChange={setStage}
      />
      {stage === "closed" && target && (
        <Choice
          legend="Outcome"
          options={closeOutcomes([target])}
          value={outcome}
          onChange={setOutcome}
        />
      )}
    </FormDialog>
  );
}

/** The deadline and priority of an application. */
export function PlanDialog({
  target,
  onClose,
}: {
  target: Target | null;
  onClose: () => void;
}) {
  const [deadline, setDeadline] = useState("");
  const [priority, setPriority] = useState("");
  useEffect(() => {
    if (!target) return;
    setDeadline(target.deadline || "");
    setPriority(target.priority ? String(target.priority) : "");
  }, [target]);
  const update = useVersionedUpdate();
  const toast = useToast();
  return (
    <FormDialog
      open={!!target}
      onClose={onClose}
      title="Deadline and priority"
      submit="Save"
      busy={update.isPending}
      onSubmit={() =>
        target &&
        update.mutate(
          {
            id: target.id,
            version: target.version,
            patch: {
              deadline: deadline || null,
              priority: priority ? Number(priority) : null,
            },
          },
          {
            onSuccess: () => {
              toast.show({ message: "Plan saved", tone: "success" });
              onClose();
            },
            onError: (error) => {
              if (!(error instanceof ApiError && error.status === 409))
                toast.show({ message: errorText(error), tone: "error" });
            },
          },
        )
      }
    >
      {update.conflict && (
        <ConflictNotice
          onReload={() => {
            void update.reload();
            onClose();
          }}
          onKeepEditing={() => void update.keepEditing()}
        />
      )}
      <Field label="Deadline" hint="The employer's closing day.">
        <Input
          type="date"
          value={deadline}
          onChange={(event) => setDeadline(event.target.value)}
        />
      </Field>
      <Field label="Priority">
        <PrioritySelect value={priority} onChange={setPriority} />
      </Field>
    </FormDialog>
  );
}

export function PrioritySelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">None</option>
      <option value="1">1 · Highest</option>
      <option value="2">2 · High</option>
      <option value="3">3 · Medium</option>
      <option value="4">4 · Low</option>
      <option value="5">5 · Lowest</option>
    </Select>
  );
}

/** The documents Ready needs: CV, letter or both. */
export function RequiredDialog({
  target,
  onClose,
}: {
  target: Target | null;
  onClose: () => void;
}) {
  const [kinds, setKinds] = useState<string[]>([]);
  useEffect(() => {
    if (target) setKinds(target.required_documents ?? ["cv", "letter"]);
  }, [target]);
  const change = useChange(onClose);
  const toggle = (kind: string, on: boolean) =>
    setKinds((current) =>
      on ? [...current, kind] : current.filter((item) => item !== kind),
    );
  return (
    <FormDialog
      open={!!target}
      onClose={onClose}
      title="Required documents"
      submit="Save"
      busy={change.busy}
      onSubmit={() =>
        target &&
        change.run(
          target,
          { required_documents: kinds as ("cv" | "letter")[] },
          "Required documents saved",
        )
      }
    >
      <p className="ap-caption">
        The application is Ready once these are uploaded and no blocking
        requirement is open.
      </p>
      <div className="ap-checks">
        <Checkbox
          label="CV"
          checked={kinds.includes("cv")}
          onChange={(event) => toggle("cv", event.target.checked)}
        />
        <Checkbox
          label="Letter"
          checked={kinds.includes("letter")}
          onChange={(event) => toggle("letter", event.target.checked)}
        />
      </div>
    </FormDialog>
  );
}

/** Delete permanently, after a confirmation naming what is lost. */
export function DeleteDialog({
  target,
  onClose,
  onDeleted,
}: {
  target: Target | null;
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const remove = useDeleteApplication();
  const toast = useToast();
  return (
    <ConfirmDialog
      open={!!target}
      title="Delete this application permanently?"
      confirm="Delete permanently"
      onClose={onClose}
      onConfirm={() =>
        target &&
        remove.mutate(
          { id: target.id, version: target.version },
          {
            onSuccess: () => {
              toast.show({
                message: `Deleted "${target.title}"`,
                tone: "success",
              });
              onDeleted?.();
            },
            onError: (error) =>
              toast.show({ message: errorText(error), tone: "error" }),
          },
        )
      }
    >
      {`"${target?.title ?? ""}" is deleted with its documents, replies, notes and history. The job stays. This cannot be undone.`}
    </ConfirmDialog>
  );
}

/** Which dialog of an application is open. */
export type DialogKind =
  "reply" | "close" | "stage" | "plan" | "required" | "delete";

/** The dialogs of one application, opened by kind. */
export function ApplicationDialogs({
  open,
  target,
  onClose,
  onDeleted,
}: {
  open: DialogKind | null;
  target: Target | null;
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const pick = (kind: DialogKind) => (open === kind ? target : null);
  return (
    <>
      <RecordReplyDialog target={pick("reply")} onClose={onClose} />
      <CloseDialog target={pick("close")} onClose={onClose} />
      <StageDialog target={pick("stage")} onClose={onClose} />
      <PlanDialog target={pick("plan")} onClose={onClose} />
      <RequiredDialog target={pick("required")} onClose={onClose} />
      <DeleteDialog
        target={pick("delete")}
        onClose={onClose}
        onDeleted={onDeleted}
      />
    </>
  );
}
