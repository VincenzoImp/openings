import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  version,
  type Instructions,
  type ListResult,
  type Template,
} from "../api";
import { FileManager } from "../files";
import { useResource, useWorkspace } from "../state";
import {
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Icon,
  Loading,
  Tabs,
} from "../ui";
export default function TemplatesPage() {
  const resource = useResource<ListResult<Template>>(
      "/templates",
      {
        items: [],
        total: 0,
      },
      true,
    ),
    instructions = useResource<Instructions>("/instructions", {
      general: "",
      version: 1,
    });
  const { mutate, pending } = useWorkspace();
  const [selected, setSelected] = useState<string | null>(null),
    [tab, setTab] = useState("instructions"),
    [creating, setCreating] = useState(false),
    [removing, setRemoving] = useState(false);
  const template =
    resource.data.items.find((t) => t.id === selected) ||
    resource.data.items[0];
  useEffect(() => {
    if (template) setSelected(template.id);
  }, [template?.id]);
  async function saveInstructions(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await mutate(
      () =>
        api(
          "/instructions",
          "PATCH",
          version(instructions.data, { general: f.get("general") }),
        ),
      "General document instructions saved.",
    );
  }
  async function saveTemplate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!template) return;
    const f = new FormData(e.currentTarget),
      body = {
        name: f.get("name"),
        is_default: f.get("is_default") === "on",
        ...(tab === "source"
          ? { tex: f.get("tex") }
          : {
              guidance: f.get("guidance"),
              rules: {
                ...template.rules,
                max_bullet_chars:
                  Number(f.get("max_bullet_chars")) || undefined,
                max_pages: Number(f.get("max_pages")) || undefined,
                max_bullets: Number(f.get("max_bullets")) || undefined,
              },
            }),
      };
    await mutate(
      () => api(`/templates/${template.id}`, "PATCH", version(template, body)),
      "Template saved. Existing application contexts are unchanged.",
    );
  }
  return (
    <>
      <Heading
        title="A good starting point."
        description="Your templates and writing guidance, ready for you and your agent."
      >
        <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
          Add template
        </Button>
      </Heading>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <section className="card sectioncard global-instructions">
        <div className="sectiontitle">
          <div>
            <h2>General writing instructions.</h2>
            <p>
              Stored once, included in every new application context alongside
              template-specific guidance.
            </p>
          </div>
        </div>
        {instructions.error ? (
          <ErrorBox message={instructions.error} retry={instructions.reload} />
        ) : instructions.loading ? (
          <Loading />
        ) : (
          <form onSubmit={saveInstructions} key={instructions.data.version}>
            <Field label="General document guidance">
              <textarea
                name="general"
                rows={4}
                defaultValue={instructions.data.general}
                placeholder="Keep wording factual and specific. Prefer concise, evidence-backed claims…"
              />
            </Field>
            <div className="section-footer">
              <span>These instructions are read by your external agent.</span>
              <Button disabled={pending}>Save instructions</Button>
            </div>
          </form>
        )}
      </section>
      {resource.loading ? (
        <Loading />
      ) : !template ? (
        <section className="card form-section">
          <Empty
            title="Bring your own template."
            action={
              <Button icon="plus" onClick={() => setCreating(true)}>
                Add a LaTeX template
              </Button>
            }
          >
            Store a CV or cover-letter template with its assets and guidance.
            Compilation happens on your agent's machine.
          </Empty>
        </section>
      ) : (
        <div className="templates-layout form-section">
          <aside className="template-list" aria-label="Saved templates">
            {resource.data.items.map((item) => (
              <button
                key={item.id}
                className={`template-option ${template.id === item.id ? "active" : ""}`}
                onClick={() => setSelected(item.id)}
              >
                <div className="template-banner">
                  <span className="mini-page">
                    <span />
                    <span />
                    <span />
                    <span />
                  </span>
                </div>
                <strong>{item.name}</strong>
                <small>
                  {item.kind === "resume" ? "CV" : "Cover letter"} · LaTeX ·
                  version {item.version}
                </small>
                {item.is_default && <span className="tag green">Default</span>}
              </button>
            ))}
          </aside>
          <section className="card sectioncard">
            <div className="sectiontitle">
              <div>
                <h2>{template.name}</h2>
                <p>
                  {template.kind === "resume" ? "CV" : "Cover letter"} template
                  package
                </p>
              </div>
              <button
                className="iconbtn danger"
                aria-label="Delete template"
                onClick={() => setRemoving(true)}
              >
                <Icon name="trash" />
              </button>
            </div>
            <Tabs
              label="Template sections"
              value={tab}
              onChange={setTab}
              items={[
                { id: "instructions", label: "Guidance & rules" },
                { id: "source", label: "LaTeX source" },
                { id: "assets", label: "Files & preview" },
              ]}
            />
            {tab === "assets" ? (
              <>
                <p className="hint">
                  Attach fonts, images and other template assets. An optional
                  PDF preview must be compiled externally and uploaded.
                </p>
                <FileManager
                  ownerType="template"
                  ownerId={template.id}
                  preview
                />
              </>
            ) : (
              <form
                onSubmit={saveTemplate}
                key={`${template.id}-${template.version}-${tab}`}
              >
                <Field label="Template name">
                  <input name="name" defaultValue={template.name} required />
                </Field>
                {tab === "source" ? (
                  <Field
                    label="LaTeX source"
                    hint="The server stores this source. Your external agent fills and compiles it."
                  >
                    <textarea
                      className="source-editor"
                      name="tex"
                      rows={18}
                      spellCheck={false}
                      defaultValue={template.tex}
                    />
                  </Field>
                ) : (
                  <>
                    <Field
                      label="Additional template guidance"
                      hint="Appended to the general writing instructions for this template."
                    >
                      <textarea
                        name="guidance"
                        rows={5}
                        defaultValue={template.guidance}
                      />
                    </Field>
                    <div className="formgrid">
                      <Field label="Maximum bullet characters">
                        <input
                          name="max_bullet_chars"
                          type="number"
                          min={1}
                          max={5000}
                          defaultValue={template.rules.max_bullet_chars || ""}
                        />
                      </Field>
                      <Field label="Target maximum pages">
                        <input
                          name="max_pages"
                          type="number"
                          min={1}
                          max={20}
                          defaultValue={template.rules.max_pages || ""}
                        />
                      </Field>
                      <Field label="Maximum bullets per section">
                        <input
                          name="max_bullets"
                          type="number"
                          min={1}
                          max={100}
                          defaultValue={template.rules.max_bullets || ""}
                        />
                      </Field>
                    </div>
                  </>
                )}
                <label className="checkline">
                  <input
                    name="is_default"
                    type="checkbox"
                    defaultChecked={template.is_default}
                  />
                  Use as the default{" "}
                  {template.kind === "resume" ? "CV" : "cover-letter"} template
                </label>
                <div className="section-footer">
                  <span>
                    Prepared application snapshots keep their original version.
                  </span>
                  <Button variant="primary" disabled={pending}>
                    Save template
                  </Button>
                </div>
              </form>
            )}
          </section>
        </div>
      )}
      {creating && (
        <CreateTemplate
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setSelected(id);
            setCreating(false);
          }}
        />
      )}
      {removing && template && (
        <Dialog
          title="Remove this template?"
          onClose={() => setRemoving(false)}
        >
          <p className="modal-intro">
            Remove {template.name} from your current templates. Existing
            application contexts retain their frozen template and assets.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(false)}>Keep template</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () =>
                      api(
                        `/templates/${template.id}?expected_version=${template.version}`,
                        "DELETE",
                      ),
                    "Template removed.",
                  )
                ) {
                  setRemoving(false);
                  setSelected(null);
                }
              }}
            >
              Remove template
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function CreateTemplate({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [source, setSource] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    let record: Template | undefined;
    const ok = await mutate(async () => {
      record = await api<Template>("/templates", "POST", {
        name: f.get("name"),
        kind: f.get("kind"),
        tex: source,
        guidance: f.get("guidance"),
        rules: {},
        is_default: f.get("is_default") === "on",
      });
    }, "Template added.");
    if (ok && record) onCreated(record.id);
  }
  return (
    <Dialog title="Add your template." onClose={onClose}>
      <form onSubmit={submit}>
        <div className="formgrid">
          <Field label="Name">
            <input name="name" required placeholder="My editorial CV" />
          </Field>
          <Field label="Document type">
            <select name="kind">
              <option value="resume">CV</option>
              <option value="cover_letter">Cover letter</option>
            </select>
          </Field>
        </div>
        <Field label="LaTeX source">
          <textarea
            className="source-editor"
            required
            rows={9}
            spellCheck={false}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Paste your LaTeX template…"
          />
        </Field>
        <Field label="Or load a .tex file">
          <input
            type="file"
            accept=".tex,.txt"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) {
                if (file.size > 1_000_000) {
                  notify("Use a source file smaller than 1 MB.", true);
                  return;
                }
                setSource(await file.text());
              }
            }}
          />
        </Field>
        <Field label="Additional guidance (optional)">
          <textarea name="guidance" rows={3} />
        </Field>
        <label className="checkline">
          <input name="is_default" type="checkbox" />
          Use as default for this document type
        </label>
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Add template
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
