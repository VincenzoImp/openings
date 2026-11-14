import { useState, type FormEvent } from "react";
import {
  api,
  fileSpec,
  sendUpload,
  uploadFile,
  type Application,
  type DocumentWithUploads,
  type Document,
  type Json,
} from "../../api";
import { Button, Dialog, Field, KeyValueEditor } from "../../design";
import { useWorkspace } from "../../state";
import { isSourceKind, kindLabels } from "./model";

/**
 * Save a document as a new revision. A CV or letter is its PDF, with an
 * optional .tex source it was built from and an optional note; form answers and
 * other kinds keep their text or fields. Earlier revisions never change.
 */
export function RevisionDialog({
  application,
  previous,
  kind: preset,
  onClose,
}: {
  application: Application;
  /** The revision this one replaces; none for a new document. */
  previous?: Document;
  /** The kind of a new document, chosen by the slot it is uploaded from. */
  kind?: string;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [kind, setKind] = useState(previous?.kind || preset || "cv");
  const sourceKind = isSourceKind(kind);
  const structured =
    !sourceKind && !!previous && typeof previous.content?.text !== "string";
  const [content, setContent] = useState<{
    value: Json;
    problem: string | null;
  }>({
    value: (previous?.content as Json) || {},
    problem: null,
  });
  const [source, setSource] = useState<File | null>(null);
  const [file, setFile] = useState<File | null>(null);
  // What a failed save already stored, so saving again only retries the rest.
  const [created, setCreated] = useState<string | null>(null);
  const [sourceSha, setSourceSha] = useState<string | null>(null);
  const [pdfDone, setPdfDone] = useState(false);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (structured && content.problem) return;
    const form = new FormData(event.currentTarget);
    const ok = await mutate(async () => {
      let id = created;
      let grants: DocumentWithUploads["uploads"];
      // The grant of a PDF built from a source names the source's hash only when
      // the browser could compute it; otherwise the PDF is reserved after the source.
      const sourceSpec = sourceKind && source ? await fileSpec(source) : null;
      if (!id) {
        const document = await api<DocumentWithUploads>("/documents", "POST", {
          application_id: application.id,
          previous_id: previous?.id || null,
          kind,
          title: String(form.get("title") || ""),
          note: String(form.get("note") || ""),
          ...(sourceKind
            ? {
                ...(file ? { pdf: await fileSpec(file) } : {}),
                ...(sourceSpec ? { source_file: sourceSpec } : {}),
              }
            : {
                content: structured
                  ? content.value
                  : { text: String(form.get("text") || "") },
              }),
        });
        id = document.id;
        grants = document.uploads;
        setCreated(id);
      }
      let built = sourceSha;
      if (sourceKind && source && !built) {
        built =
          (grants?.source
            ? await sendUpload(grants.source, source)
            : await uploadFile(source, "document", id)
          ).sha256 || null;
        setSourceSha(built);
      }
      if (file && !pdfDone) {
        if (grants?.pdf && (!source || sourceSpec?.sha256))
          await sendUpload(grants.pdf, file);
        else await uploadFile(file, "document", id, built);
        setPdfDone(true);
      }
    }, "Revision saved.");
    if (ok) onClose();
  }
  const locked = !!created;
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
            : "Store a CV, a letter or another document. Adding it does not submit the application."}
        </p>
        <div className="form-grid">
          <Field label="Kind">
            <select
              name="kind"
              value={kind}
              onChange={(event) => setKind(event.target.value)}
              disabled={!!previous || !!preset || locked}
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
              defaultValue={
                previous?.title || (preset ? kindLabels[preset] : "")
              }
              disabled={locked}
            />
          </Field>
        </div>
        {sourceKind ? (
          <>
            <Field
              label="PDF"
              hint="The document you send. The revision is complete once its PDF is stored."
            >
              <input
                type="file"
                accept=".pdf,application/pdf"
                required={!pdfDone}
                disabled={pdfDone}
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </Field>
            <Field
              label="Source (.tex)"
              hint="Optional: the source the PDF was built from. Its text is read from it; without one the text is read from the PDF."
            >
              <input
                type="file"
                accept=".tex,.ltx"
                disabled={!!sourceSha || pdfDone}
                onChange={(event) => setSource(event.target.files?.[0] || null)}
              />
            </Field>
          </>
        ) : structured ? (
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
              disabled={locked}
            />
          </Field>
        )}
        {!sourceKind && (
          <Field label="File" hint="Optional.">
            <input
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
          </Field>
        )}
        <Field label="Note" hint="Optional: what changed and why.">
          <textarea
            name="note"
            rows={2}
            maxLength={5000}
            defaultValue=""
            disabled={locked}
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
