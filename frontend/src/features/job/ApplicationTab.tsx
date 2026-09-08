import { useState } from "react";
import { Download, Eye, Package, Pencil, Trash2 } from "lucide-react";

import { api } from "../../api/client";
import { ATTACHMENT_KINDS } from "../../api/types";
import type { Attachment, AttachmentKind, JobDetail, Note } from "../../api/types";
import { useConfirm } from "../../app/confirmContext";
import { saveBlob } from "../../app/download";
import { useToast } from "../../app/toastContext";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Dialog } from "../../components/Dialog";
import { Field, Input, Select, Textarea } from "../../components/Field";
import { FileDrop } from "../../components/FileDrop";
import { MarkdownBody } from "../../components/MarkdownBody";
import { formatBytes, formatDateTime } from "../shared/format";
import { ATTACHMENT_LABELS } from "../shared/labels";
import { useJobMaterial, useSettings } from "../shared/queries";
import { AttachmentPreview } from "./AttachmentPreview";

interface QueueItem {
  id: number;
  name: string;
  size: number;
  state: "uploading" | "done" | "error";
  message?: string;
}

function NoteEditor({
  note,
  onSave,
  onCancel,
  pending,
}: {
  note: Note;
  onSave: (title: string | null, body: string) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [title, setTitle] = useState(note.title ?? "");
  const [body, setBody] = useState(note.body);
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (body.trim()) {
          onSave(note.kind === "qa" ? title.trim() || null : null, body.trim());
        }
      }}
    >
      {note.kind === "qa" ? (
        <Input
          aria-label="Question"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          autoFocus
        />
      ) : null}
      <Textarea
        aria-label="Body"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        autoFocus={note.kind !== "qa"}
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" variant="primary" disabled={pending || !body.trim()}>
          Save
        </Button>
        <Button size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function NoteItem({ note, jobId }: { note: Note; jobId: string }) {
  const material = useJobMaterial(jobId);
  const confirm = useConfirm();
  const [editing, setEditing] = useState(false);

  const remove = async () => {
    const ok = await confirm({
      title: note.kind === "qa" ? "Delete this answer?" : "Delete this note?",
      message: "It is removed from the job; the timeline keeps a record of the deletion.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (ok) {
      material.deleteNote.mutate(note.id);
    }
  };

  return (
    <li className="rounded-md border border-edge p-3">
      {editing ? (
        <NoteEditor
          note={note}
          pending={material.updateNote.isPending}
          onCancel={() => setEditing(false)}
          onSave={(title, body) =>
            material.updateNote.mutate(
              { noteId: note.id, title, body },
              { onSuccess: () => setEditing(false) },
            )
          }
        />
      ) : (
        <>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              {note.kind === "qa" ? (
                <p className="break-words text-sm font-semibold">{note.title}</p>
              ) : null}
              <span className="text-xs text-fg-muted">
                {formatDateTime(note.created_at)}
                {note.updated_at ? ` · edited ${formatDateTime(note.updated_at)}` : ""}
              </span>
            </div>
            <div className="flex shrink-0 gap-1">
              <Button size="sm" variant="ghost" aria-label="Edit" onClick={() => setEditing(true)}>
                <Pencil size={14} aria-hidden="true" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label={note.kind === "qa" ? "Delete answer" : "Delete note"}
                onClick={() => void remove()}
              >
                <Trash2 size={14} aria-hidden="true" />
              </Button>
            </div>
          </div>
          <MarkdownBody text={note.body} className="mt-1" />
        </>
      )}
    </li>
  );
}

function AttachmentRow({
  attachment,
  jobId,
  onPreview,
}: {
  attachment: Attachment;
  jobId: string;
  onPreview: () => void;
}) {
  const material = useJobMaterial(jobId);
  const confirm = useConfirm();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [kind, setKind] = useState<AttachmentKind>(attachment.kind);
  const [note, setNote] = useState(attachment.note ?? "");
  const [filename, setFilename] = useState(attachment.filename);

  const download = async () => {
    try {
      const file = await api.downloadAttachment(jobId, attachment);
      saveBlob(file.blob, file.filename);
    } catch (error) {
      toast.push(error instanceof Error ? error.message : String(error), "error");
    }
  };
  const remove = async () => {
    const ok = await confirm({
      title: `Delete ${attachment.filename}?`,
      message: "The file is removed from disk. This cannot be undone.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (ok) {
      material.deleteAttachment.mutate(attachment.id);
    }
  };
  const save = () => {
    material.updateAttachment.mutate(
      {
        attachmentId: attachment.id,
        kind: kind !== attachment.kind ? kind : undefined,
        note: note.trim() !== (attachment.note ?? "") ? note.trim() || null : undefined,
        filename:
          filename.trim() && filename.trim() !== attachment.filename ? filename.trim() : undefined,
      },
      { onSuccess: () => setEditing(false) },
    );
  };

  return (
    <li className="py-2">
      <div className="flex items-start gap-3">
        <Badge tone="positive">{ATTACHMENT_LABELS[attachment.kind]}</Badge>
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={onPreview}
            className="block max-w-full truncate text-left text-sm font-medium text-fg hover:underline"
          >
            {attachment.filename}
          </button>
          <div className="text-xs text-fg-muted">
            {formatBytes(attachment.size_bytes)} · {formatDateTime(attachment.created_at)}
            {attachment.note ? ` · ${attachment.note}` : ""}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Preview ${attachment.filename}`}
            onClick={onPreview}
          >
            <Eye size={14} aria-hidden="true" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Download ${attachment.filename}`}
            onClick={() => void download()}
          >
            <Download size={14} aria-hidden="true" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Edit ${attachment.filename}`}
            onClick={() => setEditing((value) => !value)}
          >
            <Pencil size={14} aria-hidden="true" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Delete ${attachment.filename}`}
            onClick={() => void remove()}
          >
            <Trash2 size={14} aria-hidden="true" />
          </Button>
        </div>
      </div>
      {editing ? (
        <form
          className="mt-2 grid gap-2 sm:grid-cols-[140px_1fr_1fr_auto] sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          <Field label="Kind" htmlFor={`kind-${attachment.id}`}>
            <Select
              id={`kind-${attachment.id}`}
              value={kind}
              onChange={(event) => setKind(event.target.value as AttachmentKind)}
            >
              {ATTACHMENT_KINDS.map((value) => (
                <option key={value} value={value}>
                  {ATTACHMENT_LABELS[value]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="File name" htmlFor={`name-${attachment.id}`}>
            <Input
              id={`name-${attachment.id}`}
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
            />
          </Field>
          <Field label="Note" htmlFor={`note-${attachment.id}`}>
            <Input
              id={`note-${attachment.id}`}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </Field>
          <Button
            type="submit"
            size="md"
            variant="primary"
            disabled={material.updateAttachment.isPending}
          >
            Save
          </Button>
        </form>
      ) : null}
    </li>
  );
}

export function ApplicationTab({
  job,
  onBundle,
}: {
  job: JobDetail;
  onBundle: () => Promise<void>;
}) {
  const material = useJobMaterial(job.job_id);
  const settings = useSettings();
  const toast = useToast();
  const [kind, setKind] = useState<AttachmentKind>("cv");
  const [attachmentNote, setAttachmentNote] = useState("");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [preview, setPreview] = useState<Attachment | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [note, setNote] = useState("");

  const maxMb = settings.data?.attachments.max_size_mb ?? 25;
  const questions = job.notes.filter((entry) => entry.kind === "qa");
  const notes = job.notes.filter((entry) => entry.kind === "note");

  const upload = (files: File[]) => {
    const noteText = attachmentNote.trim() || undefined;
    setAttachmentNote("");
    for (const file of files) {
      const id = Date.now() + Math.random();
      if (file.size > maxMb * 1024 * 1024) {
        setQueue((current) => [
          ...current,
          {
            id,
            name: file.name,
            size: file.size,
            state: "error",
            message: `Larger than ${maxMb} MB`,
          },
        ]);
        continue;
      }
      setQueue((current) => [
        ...current,
        { id, name: file.name, size: file.size, state: "uploading" },
      ]);
      material.upload.mutate(
        { file, kind, note: noteText },
        {
          onSuccess: () => {
            setQueue((current) => current.filter((item) => item.id !== id));
          },
          onError: (error) => {
            setQueue((current) =>
              current.map((item) =>
                item.id === id
                  ? {
                      ...item,
                      state: "error",
                      message: error instanceof Error ? error.message : String(error),
                    }
                  : item,
              ),
            );
          },
        },
      );
    }
  };

  const bundle = () => {
    if (job.attachments.length === 0 && job.notes.length === 0) {
      toast.push("Nothing to bundle yet: add notes or files first", "info");
      return;
    }
    void onBundle();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="lg:col-span-2">
        <Card
          title="Attachments"
          actions={
            <Button size="sm" onClick={bundle}>
              <Package size={14} aria-hidden="true" /> Download bundle
            </Button>
          }
        >
          <div className="mb-3 grid gap-2 sm:grid-cols-[160px_1fr]">
            <Field label="Kind" htmlFor="attachment-kind">
              <Select
                id="attachment-kind"
                value={kind}
                onChange={(event) => setKind(event.target.value as AttachmentKind)}
              >
                {ATTACHMENT_KINDS.map((value) => (
                  <option key={value} value={value}>
                    {ATTACHMENT_LABELS[value]}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="File note" htmlFor="attachment-note">
              <Input
                id="attachment-note"
                placeholder="e.g. tailored for this posting"
                value={attachmentNote}
                onChange={(event) => setAttachmentNote(event.target.value)}
              />
            </Field>
          </div>
          <FileDrop
            onFiles={upload}
            hint={`Up to ${maxMb} MB per file. The kind and note above apply to every file dropped.`}
          />
          {queue.length > 0 ? (
            <ul className="mt-2 flex flex-col gap-1" aria-live="polite">
              {queue.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="min-w-0 truncate">{item.name}</span>
                  <span className={item.state === "error" ? "text-negative" : "text-fg-muted"}>
                    {item.state === "uploading" ? "uploading…" : item.message}
                  </span>
                  {item.state === "error" ? (
                    <button
                      type="button"
                      className="text-fg-muted underline"
                      onClick={() =>
                        setQueue((current) => current.filter((entry) => entry.id !== item.id))
                      }
                    >
                      dismiss
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {job.attachments.length === 0 ? (
            <p className="mt-3 text-sm text-fg-muted">No files attached yet.</p>
          ) : (
            <ul className="mt-3 divide-y divide-edge">
              {job.attachments.map((attachment) => (
                <AttachmentRow
                  key={attachment.id}
                  attachment={attachment}
                  jobId={job.job_id}
                  onPreview={() => setPreview(attachment)}
                />
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Form questions and answers">
        <form
          className="mb-3 flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!question.trim() || !answer.trim()) {
              return;
            }
            material.addNote.mutate(
              { kind: "qa", title: question.trim(), body: answer.trim() },
              {
                onSuccess: () => {
                  setQuestion("");
                  setAnswer("");
                },
              },
            );
          }}
        >
          <Input
            aria-label="Question"
            placeholder="Question asked by the form"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <Textarea
            aria-label="Answer"
            placeholder="Your answer (markdown)"
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            className="w-fit"
            disabled={material.addNote.isPending || !question.trim() || !answer.trim()}
          >
            Save answer
          </Button>
        </form>
        {questions.length === 0 ? (
          <p className="text-sm text-fg-muted">No answers recorded.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {questions.map((entry) => (
              <NoteItem key={entry.id} note={entry} jobId={job.job_id} />
            ))}
          </ul>
        )}
      </Card>

      <Card title="Notes">
        <form
          className="mb-3 flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!note.trim()) {
              return;
            }
            material.addNote.mutate(
              { kind: "note", body: note.trim() },
              { onSuccess: () => setNote("") },
            );
          }}
        >
          <Textarea
            aria-label="Note"
            placeholder="Anything worth remembering about this application (markdown)"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            className="w-fit"
            disabled={material.addNote.isPending || !note.trim()}
          >
            Add note
          </Button>
        </form>
        {notes.length === 0 ? (
          <p className="text-sm text-fg-muted">No notes yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {notes.map((entry) => (
              <NoteItem key={entry.id} note={entry} jobId={job.job_id} />
            ))}
          </ul>
        )}
      </Card>

      <Dialog
        open={preview !== null}
        title={preview?.filename ?? ""}
        onClose={() => setPreview(null)}
        wide
      >
        {preview ? (
          <AttachmentPreview key={preview.id} jobId={job.job_id} attachment={preview} />
        ) : null}
      </Dialog>
    </div>
  );
}
