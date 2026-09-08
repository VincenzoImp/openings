import { useState } from "react";
import { Download, Trash2 } from "lucide-react";

import { api } from "../../api/client";
import { ATTACHMENT_KINDS } from "../../api/types";
import type { AttachmentKind, JobDetail } from "../../api/types";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/EmptyState";
import { Field, Input, Select, Textarea } from "../../components/Field";
import { FileDrop } from "../../components/FileDrop";
import { MarkdownBody } from "../../components/MarkdownBody";
import { formatBytes, formatDateTime } from "../shared/format";
import { useJobMaterial } from "../shared/queries";

const KIND_LABELS: Record<AttachmentKind, string> = {
  cv: "CV",
  cover_letter: "Cover letter",
  form_answers: "Form answers",
  other: "Other",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

export function ApplicationTab({ job }: { job: JobDetail }) {
  const material = useJobMaterial(job.job_id);
  const [kind, setKind] = useState<AttachmentKind>("cv");
  const [attachmentNote, setAttachmentNote] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [note, setNote] = useState("");

  const questions = job.notes.filter((entry) => entry.kind === "qa");
  const notes = job.notes.filter((entry) => entry.kind === "note");

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title="Attachments">
        <div className="mb-3 grid gap-2 sm:grid-cols-[160px_1fr]">
          <Field label="Kind" htmlFor="attachment-kind">
            <Select
              id="attachment-kind"
              value={kind}
              onChange={(event) => setKind(event.target.value as AttachmentKind)}
            >
              {ATTACHMENT_KINDS.map((value) => (
                <option key={value} value={value}>
                  {KIND_LABELS[value]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Note" htmlFor="attachment-note">
            <Input
              id="attachment-note"
              placeholder="e.g. tailored for this posting"
              value={attachmentNote}
              onChange={(event) => setAttachmentNote(event.target.value)}
            />
          </Field>
        </div>
        <FileDrop
          disabled={material.upload.isPending}
          onFiles={(files) => {
            for (const file of files) {
              material.upload.mutate({ file, kind, note: attachmentNote.trim() || undefined });
            }
            setAttachmentNote("");
          }}
        />
        {job.attachments.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No files attached yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-slate-100">
            {job.attachments.map((attachment) => (
              <li key={attachment.id} className="flex items-center gap-3 py-2">
                <Badge tone="blue">{KIND_LABELS[attachment.kind]}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{attachment.filename}</div>
                  <div className="text-xs text-slate-500">
                    {formatBytes(attachment.size_bytes)} · {formatDateTime(attachment.created_at)}
                    {attachment.note ? ` · ${attachment.note}` : ""}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Download ${attachment.filename}`}
                  onClick={() => api.downloadAttachment(job.job_id, attachment)}
                >
                  <Download size={14} />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Delete ${attachment.filename}`}
                  onClick={() => material.deleteAttachment.mutate(attachment.id)}
                >
                  <Trash2 size={14} />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Form questions and answers">
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
            disabled={material.addNote.isPending}
          >
            Save answer
          </Button>
        </form>
        {questions.length === 0 ? (
          <EmptyState title="No answers recorded" />
        ) : (
          <ul className="flex flex-col gap-3">
            {questions.map((entry) => (
              <li key={entry.id} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold">{entry.title}</p>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Delete answer"
                    onClick={() => material.deleteNote.mutate(entry.id)}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
                <MarkdownBody text={entry.body} className="mt-1" />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Notes">
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
            disabled={material.addNote.isPending}
          >
            Add note
          </Button>
        </form>
        {notes.length === 0 ? (
          <EmptyState title="No notes yet" />
        ) : (
          <ul className="flex flex-col gap-3">
            {notes.map((entry) => (
              <li key={entry.id} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs text-slate-500">{formatDateTime(entry.created_at)}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Delete note"
                    onClick={() => material.deleteNote.mutate(entry.id)}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
                <MarkdownBody text={entry.body} />
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
