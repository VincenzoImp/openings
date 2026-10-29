import { useState, type FormEvent } from "react";
import {
  api,
  date,
  download,
  newId,
  uploadFile,
  version,
  type Activity,
  type Application,
  type Document,
  type Job,
  type ListResult,
  type Stage,
  type Template,
} from "../api";
import { FileManager } from "../files";
import { useResource, useWorkspace } from "../state";
import {
  Avatar,
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Icon,
  Loading,
  stageLabels,
  Tabs,
} from "../ui";
const stages: Stage[] = ["draft", "applied", "interview", "offer", "closed"];
export function ApplicationsPage({ onOpen }: { onOpen: (id: string) => void }) {
  const [offset, setOffset] = useState(0);
  const resource = useResource<ListResult<Application>>(
    `/applications?limit=200&offset=${offset}`,
    { items: [], total: 0 },
  );
  const { mutate, pending } = useWorkspace();
  const [view, setView] = useState("board");
  async function move(id: string, status: Stage) {
    const app = resource.data.items.find((a) => a.id === id);
    if (app && app.status !== status)
      await mutate(
        () =>
          api(
            `/applications/${id}`,
            "PATCH",
            version(app, {
              status,
              outcome: status === "closed" ? "not_pursued" : null,
            }),
          ),
        `Moved to ${stageLabels[status]}.`,
      );
  }
  return (
    <>
      <Heading
        title="Keep the whole picture."
        description="Documents, conversations and decisions — each in its place."
      >
        <div className="segmented" aria-label="Application view">
          <Button
            variant={view === "board" ? "selected" : ""}
            icon="board"
            onClick={() => setView("board")}
          >
            Board
          </Button>
          <Button
            variant={view === "list" ? "selected" : ""}
            icon="list"
            onClick={() => setView("list")}
          >
            List
          </Button>
        </div>
      </Heading>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="boardcaption">
        <span>
          {resource.data.total} application attempts
          {resource.data.total > 200
            ? ` · Showing ${offset + 1}–${Math.min(offset + 200, resource.data.total)}`
            : ""}
        </span>
        <span>Move a card between stages, or open it to edit.</span>
      </div>
      {resource.loading && !resource.data.items.length ? (
        <Loading />
      ) : !resource.data.items.length ? (
        <section className="card">
          <Empty
            title="Make room for your next move."
            action={
              <Button onClick={() => (location.hash = "inbox")} icon="inbox">
                Browse opportunities
              </Button>
            }
          >
            Save a job in your inbox, then create an application to collect its
            documents and progress here.
          </Empty>
        </section>
      ) : view === "board" ? (
        <div className="kanban">
          {stages.map((stage) => (
            <section
              className="kanban-column"
              key={stage}
              aria-label={`${stageLabels[stage]} applications`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (!pending)
                  void move(e.dataTransfer.getData("text/plain"), stage);
              }}
            >
              <header className="kanban-head">
                <span>
                  <i className={`dot ${stage}`} />
                  {stageLabels[stage]}
                </span>
                <span>
                  {resource.data.items.filter((a) => a.status === stage).length}
                </span>
              </header>
              {resource.data.items
                .filter((a) => a.status === stage)
                .map((app) => (
                  <button
                    className="application-card"
                    key={app.id}
                    draggable={!pending}
                    onDragStart={(e) =>
                      e.dataTransfer.setData("text/plain", app.id)
                    }
                    onClick={() => onOpen(app.id)}
                  >
                    <div className="companyline">
                      <Avatar name={app.job?.company || "Company"} />
                      <span>{app.job?.company || "Company"}</span>
                    </div>
                    <strong>{app.job?.title || "Application"}</strong>
                    {app.outcome && (
                      <span className="tag neutral outcome">
                        {app.outcome === "accepted"
                          ? "Accepted"
                          : app.outcome === "rejected"
                            ? "Not selected"
                            : "Not pursued"}
                      </span>
                    )}
                    <footer>
                      <span>
                        <Icon name="file" /> Open workspace
                      </span>
                      <time>{date(app.updated_at || app.created_at)}</time>
                    </footer>
                  </button>
                ))}
            </section>
          ))}
        </div>
      ) : (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Company / role</th>
                <th scope="col">Stage</th>
                <th scope="col">Outcome</th>
                <th scope="col">Updated</th>
              </tr>
            </thead>
            <tbody>
              {resource.data.items.map((app) => (
                <tr key={app.id}>
                  <td>
                    <button
                      className="table-link"
                      onClick={() => onOpen(app.id)}
                    >
                      <strong>{app.job?.title || "Application"}</strong>
                      <small>{app.job?.company}</small>
                    </button>
                  </td>
                  <td>
                    <span className="status-label">
                      <i className={`dot ${app.status}`} />
                      {stageLabels[app.status]}
                    </span>
                  </td>
                  <td>{app.outcome?.replaceAll("_", " ") || "—"}</td>
                  <td>{date(app.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {resource.data.total > 200 && (
        <div className="actions form-actions">
          <Button
            disabled={offset === 0 || resource.loading}
            onClick={() => setOffset(Math.max(0, offset - 200))}
          >
            Previous
          </Button>
          <Button
            disabled={offset + 200 >= resource.data.total || resource.loading}
            onClick={() => setOffset(offset + 200)}
          >
            Next
          </Button>
        </div>
      )}
      <p className="hint">
        Creating or uploading documents does not mark an application as sent.
        Record the stage when it actually changes.
      </p>
    </>
  );
}
function DocumentEditor({
  application,
  previous,
  onClose,
}: {
  application: Application;
  previous?: Document;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [file, setFile] = useState<File | null>(null),
    [createdId, setCreatedId] = useState<string | null>(null);
  const structured = previous && typeof previous.content.text !== "string";
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const ok = await mutate(async () => {
      let id = createdId;
      if (!id) {
        const doc = await api<Document>("/documents", "POST", {
          application_id: application.id,
          context_id: previous?.context_id || null,
          previous_id: previous?.id || null,
          kind: previous?.kind || form.get("kind"),
          title: form.get("title"),
          content: structured
            ? JSON.parse(String(form.get("text")))
            : { text: form.get("text") },
        });
        id = doc.id;
        setCreatedId(id);
      }
      if (file) await uploadFile(file, "document", id);
    }, "Document revision saved.");
    if (ok) onClose();
  }
  return (
    <Dialog
      title={previous ? "Create a new revision." : "Add a document."}
      onClose={onClose}
    >
      <p className="modal-intro">
        Store externally prepared content, PDF and source files. Previous
        revisions stay unchanged.
      </p>
      <form onSubmit={submit}>
        <div className="formgrid">
          <Field label="Document type">
            <select
              name="kind"
              defaultValue={previous?.kind || "resume"}
              disabled={!!createdId || !!previous}
            >
              <option value="resume">CV</option>
              <option value="cover_letter">Cover letter</option>
              <option value="answers">Form answers</option>
              <option value="other">Other</option>
            </select>
          </Field>
          <Field label="Title">
            <input
              name="title"
              defaultValue={previous?.title || ""}
              placeholder="Application CV"
              required
              disabled={!!createdId}
            />
          </Field>
        </div>
        <Field
          label={structured ? "Structured content (JSON)" : "Content"}
          hint="Changing content creates a revision. A PDF is attached only when you upload it."
        >
          <textarea
            name="text"
            rows={9}
            defaultValue={
              structured
                ? JSON.stringify(previous.content, null, 2)
                : String(previous?.content.text || "")
            }
            disabled={!!createdId}
          />
        </Field>
        <Field label="PDF or source file (optional)">
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </Field>
        {createdId && (
          <p className="hint">
            The content revision is saved. You can retry its file upload.
          </p>
        )}
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Save revision
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
function DocumentCard({
  document,
  application,
}: {
  document: Document;
  application: Application;
}) {
  const { mutate, pending } = useWorkspace();
  const [expanded, setExpanded] = useState(false),
    [edit, setEdit] = useState(false);
  return (
    <article className="document-card">
      <header>
        <div>
          <span className="eyebrow">{document.kind.replaceAll("_", " ")}</span>
          <h3>{document.title || "Untitled document"}</h3>
          <p>
            {date(document.created_at)} ·{" "}
            {document.review_state === "approved"
              ? "Approved"
              : "Draft — ready for review"}
          </p>
        </div>
        <button
          className="iconbtn"
          aria-label={`${expanded ? "Hide" : "Show"} ${document.title}`}
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          <Icon name={expanded ? "close" : "file"} />
        </button>
      </header>
      {expanded && (
        <>
          <div className="document-text">
            {typeof document.content.text === "string" ? (
              document.content.text
            ) : (
              <pre>{JSON.stringify(document.content, null, 2)}</pre>
            )}
          </div>
          <FileManager
            ownerType="document"
            ownerId={document.id}
            immutable
            preview
            readOnly={document.review_state === "approved"}
          />
          <div className="actions form-actions">
            <Button icon="edit" onClick={() => setEdit(true)}>
              New revision
            </Button>
            {document.review_state !== "approved" && (
              <Button
                variant="primary"
                icon="check"
                disabled={pending}
                onClick={() =>
                  mutate(
                    () =>
                      api(`/documents/${document.id}/review`, "POST", {
                        review_state: "approved",
                        expected_review_state: document.review_state,
                      }),
                    "Document approved.",
                  )
                }
              >
                Approve this revision
              </Button>
            )}
          </div>
        </>
      )}
      {edit && (
        <DocumentEditor
          application={application}
          previous={document}
          onClose={() => setEdit(false)}
        />
      )}
    </article>
  );
}
export function ApplicationDrawer({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const resource = useResource<Application | null>(`/applications/${id}`, null),
    documents = useResource<ListResult<Document>>(
      `/documents?application_id=${id}`,
      { items: [], total: 0 },
      true,
    ),
    events = useResource<ListResult<Activity>>(`/applications/${id}/events`, {
      items: [],
      total: 0,
    }),
    templates = useResource<ListResult<Template>>(
      "/templates",
      {
        items: [],
        total: 0,
      },
      true,
    );
  const { mutate, pending } = useWorkspace();
  const [tab, setTab] = useState("documents"),
    [add, setAdd] = useState(false),
    [contextTemplate, setContextTemplate] = useState("");
  const app = resource.data;
  async function stage(status: Stage) {
    if (app)
      await mutate(
        () =>
          api(
            `/applications/${id}`,
            "PATCH",
            version(app, {
              status,
              outcome: status === "closed" ? "not_pursued" : null,
            }),
          ),
        "Application progress saved.",
      );
  }
  async function saveDetails(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!app) return;
    const form = new FormData(e.currentTarget);
    await mutate(
      () =>
        api(
          `/applications/${id}`,
          "PATCH",
          version(app, {
            note: form.get("note"),
            outcome: app.status === "closed" ? form.get("outcome") : null,
          }),
        ),
      "Application details saved.",
    );
  }
  async function saveAnswers(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!app) return;
    const form = new FormData(e.currentTarget),
      answers = Object.fromEntries(
        app.questions
          .map((q) => {
            const raw = String(form.get(q.id) || "");
            return [
              q.id,
              q.type === "boolean"
                ? raw === ""
                  ? ""
                  : raw === "true"
                : q.type === "number"
                  ? raw === ""
                    ? ""
                    : Number(raw)
                  : raw,
            ];
          })
          .filter(([, value]) => value !== ""),
      );
    await mutate(
      () => api(`/applications/${id}`, "PATCH", version(app, { answers })),
      "Draft answers saved.",
    );
  }
  async function exportContext() {
    await mutate(async () => {
      const result = await api<Record<string, unknown>>("/contexts", "POST", {
        application_id: id,
        template_id: contextTemplate || undefined,
        idempotency_key: newId(),
      });
      download("application-context.json", JSON.stringify(result, null, 2));
    }, "Frozen context exported for your agent.");
  }
  return (
    <>
      <Dialog
        drawer
        title={app?.job?.title || "Application workspace"}
        onClose={onClose}
        footer={
          <span className="smalltext muted">
            {app?.status === "draft"
              ? "Draft — not sent"
              : "Application progress is recorded manually."}
          </span>
        }
      >
        {resource.error ? (
          <ErrorBox message={resource.error} retry={resource.reload} />
        ) : !app ? (
          <Loading />
        ) : (
          <>
            <div className="jobmeta drawer-meta">
              <Avatar name={app.job?.company || "Company"} />
              {app.job?.company} ·{" "}
              {app.job?.location || "Location not specified"}
            </div>
            <div className="stage-control">
              <label htmlFor="application-stage">Stage</label>
              <select
                id="application-stage"
                aria-label="Application stage"
                disabled={pending}
                value={app.status}
                onChange={(e) => stage(e.target.value as Stage)}
              >
                {stages.map((s) => (
                  <option key={s} value={s}>
                    {stageLabels[s]}
                  </option>
                ))}
              </select>
            </div>
            <Tabs
              label="Application workspace"
              value={tab}
              onChange={setTab}
              items={[
                {
                  id: "documents",
                  label: "Documents",
                  count: documents.data.total,
                },
                { id: "answers", label: "Form answers" },
                { id: "history", label: "History" },
                { id: "details", label: "Details" },
              ]}
            />
            {tab === "documents" ? (
              <>
                {documents.error && (
                  <ErrorBox
                    message={documents.error}
                    retry={documents.reload}
                  />
                )}
                <section className="context-panel">
                  <h3>Your agent does the writing.</h3>
                  <p>
                    Export the job, your stored knowledge, template and
                    instructions as a frozen context. Upload PDF and sources
                    after external compilation.
                  </p>
                  <div className="actions">
                    <select
                      aria-label="Template for context"
                      value={contextTemplate}
                      onChange={(e) => setContextTemplate(e.target.value)}
                    >
                      <option value="">Default template</option>
                      {templates.data.items.map((t) => (
                        <option value={t.id} key={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      icon="download"
                      disabled={pending}
                      onClick={exportContext}
                    >
                      Export context
                    </Button>
                  </div>
                </section>
                <div className="sectiontitle">
                  <h3>Documents and revisions</h3>
                  <Button icon="plus" onClick={() => setAdd(true)}>
                    Add document
                  </Button>
                </div>
                {documents.data.items.length ? (
                  documents.data.items.map((d) => (
                    <DocumentCard key={d.id} document={d} application={app} />
                  ))
                ) : (
                  <Empty title="A clean starting point.">
                    Save a CV, cover letter or source file prepared by you or
                    your external agent.
                  </Empty>
                )}
              </>
            ) : tab === "answers" ? (
              <>
                <QuestionEditor application={app} />
                {app.questions.length ? (
                  <form
                    onSubmit={saveAnswers}
                    key={`answers-${app.version}`}
                    className="stack"
                  >
                    {app.questions.map((q) => (
                      <Field
                        label={q.label + (q.required ? " *" : "")}
                        key={q.id}
                        hint={
                          q.max_length
                            ? `Maximum ${q.max_length} characters`
                            : undefined
                        }
                      >
                        {q.options?.length ? (
                          <select
                            name={q.id}
                            defaultValue={String(app.answers[q.id] ?? "")}
                          >
                            <option value="">Select an answer</option>
                            {q.options.map((o) => (
                              <option key={o}>{o}</option>
                            ))}
                          </select>
                        ) : q.type === "boolean" ? (
                          <select
                            name={q.id}
                            defaultValue={
                              app.answers[q.id] === true
                                ? "true"
                                : app.answers[q.id] === false
                                  ? "false"
                                  : ""
                            }
                          >
                            <option value="">Select an answer</option>
                            <option value="true">Yes</option>
                            <option value="false">No</option>
                          </select>
                        ) : q.type === "number" ? (
                          <input
                            type="number"
                            name={q.id}
                            defaultValue={String(app.answers[q.id] ?? "")}
                          />
                        ) : (
                          <textarea
                            name={q.id}
                            rows={4}
                            defaultValue={String(app.answers[q.id] ?? "")}
                            maxLength={q.max_length}
                          />
                        )}
                      </Field>
                    ))}
                    <Button variant="primary" disabled={pending}>
                      Save answers
                    </Button>
                  </form>
                ) : (
                  <p className="hint">
                    Add the questions from the application form. Your agent can
                    prepare draft answers using the same context.
                  </p>
                )}
              </>
            ) : tab === "history" ? (
              <>
                {events.error && (
                  <ErrorBox message={events.error} retry={events.reload} />
                )}
                <div className="stack">
                  {events.data.items.map((e, i) => (
                    <article className="activity" key={e.id || i}>
                      <span className="activity-icon">
                        <Icon name="clock" />
                      </span>
                      <div>
                        <strong>
                          {e.message ||
                            e.title ||
                            (e.kind || e.type || "Updated").replaceAll(
                              "_",
                              " ",
                            )}
                        </strong>
                        <p>
                          {e.payload?.status ? String(e.payload.status) : ""}
                        </p>
                        <time>{date(e.created_at)}</time>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <form onSubmit={saveDetails} key={app.version} className="stack">
                {app.status === "closed" && (
                  <Field label="Outcome">
                    <select
                      name="outcome"
                      defaultValue={app.outcome || "not_pursued"}
                    >
                      <option value="accepted">Accepted</option>
                      <option value="rejected">Not selected</option>
                      <option value="not_pursued">Not pursued</option>
                    </select>
                  </Field>
                )}
                <Field
                  label="Application notes & writing guidance"
                  hint="Included in your agent's frozen application context."
                >
                  <textarea name="note" rows={9} defaultValue={app.note} />
                </Field>
                <Button variant="primary" disabled={pending}>
                  Save details
                </Button>
              </form>
            )}
          </>
        )}
      </Dialog>
      {app && add && (
        <DocumentEditor application={app} onClose={() => setAdd(false)} />
      )}
    </>
  );
}
function QuestionEditor({ application }: { application: Application }) {
  const [editing, setEditing] = useState<
      import("../api").Question | "new" | null
    >(null),
    [kind, setKind] = useState("text");
  const { mutate, pending } = useWorkspace();
  const record = editing && editing !== "new" ? editing : null;
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const question = {
      id: record?.id || newId(),
      label: String(f.get("label")),
      type: kind,
      required: f.get("required") === "on",
      options:
        kind === "choice"
          ? String(f.get("options") || "")
              .split("\n")
              .map((x) => x.trim())
              .filter(Boolean)
          : [],
      max_length: Number(f.get("max_length")) || undefined,
    };
    const questions = record
      ? application.questions.map((q) => (q.id === record.id ? question : q))
      : [...application.questions, question];
    const answers = { ...application.answers };
    if (record) delete answers[record.id];
    if (
      await mutate(
        () =>
          api(
            `/applications/${application.id}`,
            "PATCH",
            version(application, { questions, answers }),
          ),
        "Question saved.",
      )
    )
      setEditing(null);
  }
  return (
    <>
      <div className="sectiontitle">
        <h3>Application questions</h3>
        <Button
          icon="plus"
          onClick={() => {
            setKind("text");
            setEditing("new");
          }}
        >
          Add question
        </Button>
      </div>
      {application.questions.length > 0 && (
        <details className="manage-questions">
          <summary>Manage questions</summary>
          {application.questions.map((q) => (
            <div className="question-entry" key={q.id}>
              <span>{q.label}</span>
              <button
                className="iconbtn"
                aria-label={`Edit ${q.label}`}
                onClick={() => {
                  setKind(q.type || "text");
                  setEditing(q);
                }}
              >
                <Icon name="edit" />
              </button>
              <button
                className="iconbtn danger"
                aria-label={`Remove ${q.label}`}
                disabled={pending}
                onClick={() => {
                  const answers = { ...application.answers };
                  delete answers[q.id];
                  void mutate(
                    () =>
                      api(
                        `/applications/${application.id}`,
                        "PATCH",
                        version(application, {
                          questions: application.questions.filter(
                            (x) => x.id !== q.id,
                          ),
                          answers,
                        }),
                      ),
                    "Question removed.",
                  );
                }}
              >
                <Icon name="trash" />
              </button>
            </div>
          ))}
        </details>
      )}
      {editing && (
        <Dialog
          title={record ? "Edit form question." : "Add a form question."}
          onClose={() => setEditing(null)}
        >
          <form onSubmit={save}>
            <Field label="Question">
              <textarea
                name="label"
                required
                rows={3}
                defaultValue={record?.label}
              />
            </Field>
            <Field label="Answer type">
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="text">Text</option>
                <option value="choice">Select one option</option>
                <option value="boolean">Yes / no</option>
                <option value="number">Number</option>
              </select>
            </Field>
            {kind === "choice" && (
              <Field label="Options" hint="One permitted answer per line.">
                <textarea
                  name="options"
                  rows={4}
                  required
                  defaultValue={record?.options?.join("\n")}
                />
              </Field>
            )}
            {kind === "text" && (
              <Field label="Character limit (optional)">
                <input
                  type="number"
                  name="max_length"
                  min={1}
                  max={50000}
                  defaultValue={record?.max_length}
                />
              </Field>
            )}
            <label className="checkline">
              <input
                type="checkbox"
                name="required"
                defaultChecked={record?.required}
              />
              Answer is required
            </label>
            {record && (
              <p className="hint">
                Updating a question clears its draft answer so you can review it
                again.
              </p>
            )}
            <div className="actions form-actions">
              <Button variant="primary" disabled={pending}>
                Save question
              </Button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  );
}
