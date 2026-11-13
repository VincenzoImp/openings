import { useState, type FormEvent } from "react";
import { api, version, type Template } from "../../api";
import { Button, Dialog, ErrorBanner, Field, Loading } from "../../design";
import { useResource, useWorkspace } from "../../state";

export const kindLabels = { cv: "CV", letter: "Letter" } as const;
const EXAMPLES = ["cv.tex", "letter.tex"];

function KindAndDefault({ template }: { template?: Template }) {
  return (
    <>
      <Field label="Document">
        <select name="kind" defaultValue={template?.kind}>
          <option value="cv">CV</option>
          <option value="letter">Letter</option>
        </select>
      </Field>
      <label className="toggle wide">
        <input
          name="is_default"
          type="checkbox"
          defaultChecked={template?.is_default}
        />
        <span>Use by default for this kind of document</span>
      </label>
    </>
  );
}

/** Add a template from pasted source or a .tex file. */
export function CreateTemplate({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [source, setSource] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    let record: Template | undefined;
    const ok = await mutate(async () => {
      record = await api<Template>("/templates", "POST", {
        name: form.get("name"),
        kind: form.get("kind"),
        tex: source,
        guidance: form.get("guidance"),
        rules: {},
        is_default: form.get("is_default") === "on",
      });
    }, "Template added.");
    if (ok && record) onCreated(record.id);
  }
  return (
    <Dialog title="Add a template" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <Field label="Name">
          <input name="name" required maxLength={200} />
        </Field>
        <KindAndDefault />
        <Field
          label="LaTeX source"
          hint="Your agent fills and compiles it on its own machine."
          className="wide"
        >
          <textarea
            className="code"
            required
            rows={8}
            spellCheck={false}
            value={source}
            onChange={(event) => setSource(event.target.value)}
          />
        </Field>
        <Field label="Or load a .tex file" className="wide">
          <input
            type="file"
            accept=".tex,.txt"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              if (file.size > 1_000_000)
                return notify("Use a source file smaller than 1 MB.", true);
              setSource(await file.text());
            }}
          />
        </Field>
        <p className="caption wide">
          Synthetic examples to start from:{" "}
          {EXAMPLES.map((name, index) => (
            <span key={name}>
              {index ? ", " : ""}
              <a href={`/api/v1/examples/${name}`} download={name}>
                {name}
              </a>
            </span>
          ))}
          .
        </p>
        <Field label="Guidance (optional)" className="wide">
          <textarea name="guidance" rows={3} />
        </Field>
        <div className="row wide">
          <Button variant="primary" disabled={pending}>
            Add template
          </Button>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Name, kind and default of a template. */
export function TemplateSettings({
  template,
  onClose,
}: {
  template: Template;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (
      await mutate(
        () =>
          api(
            `/templates/${template.id}`,
            "PATCH",
            version(template, {
              name: form.get("name"),
              kind: form.get("kind"),
              is_default: form.get("is_default") === "on",
            }),
          ),
        "Template saved.",
      )
    )
      onClose();
  }
  return (
    <Dialog title="Rename or change the template" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <Field label="Name">
          <input
            name="name"
            required
            maxLength={200}
            defaultValue={template.name}
          />
        </Field>
        <KindAndDefault template={template} />
        <div className="row wide">
          <Button variant="primary" disabled={pending}>
            Save template
          </Button>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
