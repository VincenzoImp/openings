import { useState, type FormEvent } from "react";
import {
  api,
  uploadFile,
  type Application,
  type Document,
  type Json,
  type ListResult,
} from "../../api";
import { Button, Dialog, Field, KeyValueEditor } from "../../design";
import { dayTime } from "../../library/time";
import { useResource, useWorkspace } from "../../state";
import { kindLabels } from "./model";

const NONE = { items: [], total: 0 };

/**
 * Save a document as a new revision: its text (or, for a revision with
 * structured content, its fields as rows), an optional frozen copy it was
 * written from, and a PDF or source file. Earlier revisions never change.
 */
export function RevisionDialog({
  application,
  previous,
  onClose,
}: {
  application: Application;
  /** The revision this one replaces; none for a new document. */
  previous?: Document;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const structured = !!previous && typeof previous.content?.text !== "string";
  const [content, setContent] = useState<{
    value: Json;
    problem: string | null;
  }>({
    value: (previous?.content as Json) || {},
    problem: null,
  });
  const [file, setFile] = useState<File | null>(null);
  const [created, setCreated] = useState<string | null>(null);
  const contexts = useResource<ListResult<Json>>(
    previous
      ? null
      : `/contexts?application_id=${application.id}&summary=true&limit=50`,
    NONE,
  );
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (structured && content.problem) return;
    const form = new FormData(event.currentTarget);
    const ok = await mutate(async () => {
      let id = created;
      if (!id) {
        const document = await api<Document>("/documents", "POST", {
          application_id: application.id,
          context_id: previous?.context_id || form.get("context_id") || null,
          previous_id: previous?.id || null,
          kind: previous?.kind || form.get("kind"),
          title: String(form.get("title") || ""),
          content: structured
            ? content.value
            : { text: String(form.get("text") || "") },
        });
        id = document.id;
        setCreated(id);
      }
      if (file) await uploadFile(file, "document", id);
    }, "Revision saved.");
    if (ok) onClose();
  }
  return (
    <Dialog
      title={previous ? "Save a new revision" : "Add a document"}
      className="wide"
      onClose={onClose}
    >
      <form className="stack" onSubmit={save}>
        <p className="muted">
          {previous
            ? `It replaces revision ${previous.revision_number || 1}, which stays unchanged.`
            : "Store a document your agent prepared outside Openings. Adding it does not submit the application."}
        </p>
        <div className="form-grid">
          <Field label="Kind">
            <select
              name="kind"
              defaultValue={previous?.kind || "resume"}
              disabled={!!previous || !!created}
            >
              {Object.entries(kindLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Title">
            <input
              name="title"
              required
              maxLength={300}
              defaultValue={previous?.title}
              disabled={!!created}
            />
          </Field>
          {!previous && (
            <Field label="Written from" className="wide">
              <select name="context_id" defaultValue="" disabled={!!created}>
                <option value="">No frozen copy</option>
                {contexts.data.items.map((context) => (
                  <option key={String(context.id)} value={String(context.id)}>
                    {dayTime(String(context.created_at))}
                    {context.template_name ? ` · ${context.template_name}` : ""}
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>
        {structured ? (
          <fieldset className="field">
            <legend>Content</legend>
            <KeyValueEditor
              label="Content of the revision"
              value={content.value}
              onChange={(value, problem) => setContent({ value, problem })}
              addLabel="Add a field"
            />
          </fieldset>
        ) : (
          <Field label="Text" hint="Changing the text makes a new revision.">
            <textarea
              name="text"
              rows={8}
              defaultValue={
                typeof previous?.content?.text === "string"
                  ? previous.content.text
                  : ""
              }
              disabled={!!created}
            />
          </Field>
        )}
        <Field
          label="PDF or source file"
          hint="Optional. A PDF is shown on the review page."
        >
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </Field>
        {created && (
          <p className="caption">
            The revision is saved; saving again retries the file upload.
          </p>
        )}
        <div className="row">
          <Button
            variant="primary"
            disabled={pending || (structured && !!content.problem)}
          >
            Save the revision
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
