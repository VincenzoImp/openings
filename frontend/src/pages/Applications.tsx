import { useRef, useState, type FormEvent } from "react";
import {
  api,
  date,
  download,
  newId,
  jsonValue,
  type Json,
  type Claim,
  type Knowledge,
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
import {
  confirmLeave,
  useDebounce,
  useResource,
  useUrlFilters,
  useUrlState,
  useWorkspace,
} from "../state";
import {
  AdvancedJson,
  Pagination,
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
function StageMenu({
  application,
  pending,
  onMove,
}: {
  application: Application;
  pending: boolean;
  onMove: (id: string, stage: Stage) => void;
}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const id = `move-${application.id}`;
  return (
    <>
      <button
        type="button"
        ref={trigger}
        className="iconbtn stage-menu-trigger"
        popoverTarget={id}
        aria-label={`Move ${application.job?.title || "application"} to stage`}
        title="Move to stage"
        disabled={pending}
      >
        <Icon name="more" />
      </button>
      <div
        id={id}
        popover="auto"
        className="stage-menu-options"
        role="group"
        aria-label="Move to stage"
        onToggle={(event) => {
          const menu = event.currentTarget;
          if (!menu.matches(":popover-open") || !trigger.current) return;
          const anchor = trigger.current.getBoundingClientRect();
          const bounds = menu.getBoundingClientRect();
          menu.style.left = `${Math.max(8, Math.min(anchor.right - bounds.width, window.innerWidth - bounds.width - 8))}px`;
          menu.style.top = `${Math.max(8, Math.min(anchor.bottom + 4, window.innerHeight - bounds.height - 8))}px`;
        }}
      >
        <span>Move to</span>
        {stages.map((stage) => (
          <button
            type="button"
            key={stage}
            disabled={pending || stage === application.status}
            onClick={(event) => {
              event.currentTarget
                .closest<HTMLElement>("[popover]")
                ?.hidePopover();
              onMove(application.id, stage);
            }}
          >
            {stageLabels[stage]}
            {stage === application.status && <Icon name="check" />}
          </button>
        ))}
      </div>
    </>
  );
}
export function ApplicationsPage({ onOpen }: { onOpen: (id: string) => void }) {
  const [filters, setFilters] = useUrlFilters({
    q: "",
    status: "",
    outcome: "",
    sort: "updated",
    offset: "0",
    view: "board",
  });
  const query = useDebounce(filters.q),
    offset = Number(filters.offset) || 0,
    limit = 50;
  const params = new URLSearchParams({
    ...filters,
    q: query,
    limit: String(limit),
  });
  params.delete("view");
  Object.entries(filters).forEach(([key, value]) => {
    if (!value) params.delete(key);
  });
  const resource = useResource<ListResult<Application>>(
    `/applications?${params}`,
    { items: [], total: 0 },
  );
  const { mutate, pending } = useWorkspace();
  const [dragged, setDragged] = useState<string | null>(null);
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
        title="Applications"
        description="Track application attempts, documents and recorded progress."
      >
        <div className="segmented" aria-label="Application view">
          {["board", "list"].map((view) => (
            <Button
              key={view}
              variant={filters.view === view ? "selected" : ""}
              icon={view === "board" ? "board" : "list"}
              onClick={() => setFilters({ view })}
            >
              {view === "board" ? "Board" : "List"}
            </Button>
          ))}
        </div>
      </Heading>
      <div className="toolbar application-filters">
        <div className="search">
          <Icon name="search" />
          <input
            aria-label="Search applications"
            placeholder="Search company, role or notes"
            value={filters.q}
            onChange={(e) => setFilters({ q: e.target.value, offset: "0" })}
          />
        </div>
        <select
          aria-label="Filter application stage"
          value={filters.status}
          onChange={(e) => setFilters({ status: e.target.value, offset: "0" })}
        >
          <option value="">All stages</option>
          {stages.map((stage) => (
            <option key={stage} value={stage}>
              {stageLabels[stage]}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter application outcome"
          value={filters.outcome}
          onChange={(e) => setFilters({ outcome: e.target.value, offset: "0" })}
        >
          <option value="">All outcomes</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Not selected</option>
          <option value="not_pursued">Not pursued</option>
        </select>
        <select
          aria-label="Sort applications"
          value={filters.sort}
          onChange={(e) => setFilters({ sort: e.target.value, offset: "0" })}
        >
          <option value="updated">Recently updated</option>
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="company">Company A–Z</option>
          <option value="stage">Stage</option>
          <option value="applied">Submission date</option>
        </select>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="boardcaption">
        <span>{resource.data.total} application attempts</span>
        <span>Open a card. Drag between columns or use its move menu.</span>
      </div>
      {resource.loading && !resource.data.items.length ? (
        <Loading />
      ) : !resource.data.items.length ? (
        <section className="card">
          <Empty
            title="No applications in this view."
            action={
              <a href="#inbox" className="btn">
                Browse opportunities
              </a>
            }
          >
            Try another filter, or create an application from a job in your
            inbox.
          </Empty>
        </section>
      ) : filters.view === "board" ? (
        <div className={`kanban ${dragged ? "is-dragging" : ""}`}>
          {stages.map((stage) => (
            <section
              className="kanban-column"
              key={stage}
              aria-label={`${stageLabels[stage]} applications`}
              onDragOver={(e) => {
                if (dragged) {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                }
              }}
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
                  {resource.data.stage_counts?.[stage] ??
                    resource.data.items.filter((a) => a.status === stage)
                      .length}
                </span>
              </header>
              {resource.data.items
                .filter((a) => a.status === stage)
                .map((app) => (
                  <article
                    className={`application-card ${dragged === app.id ? "is-dragged" : ""}`}
                    key={app.id}
                    draggable={!pending}
                    onDragStart={(e) => {
                      e.dataTransfer.setData("text/plain", app.id);
                      e.dataTransfer.effectAllowed = "move";
                      setDragged(app.id);
                    }}
                    onDragEnd={() => setDragged(null)}
                  >
                    <button
                      className="application-open"
                      onClick={() => onOpen(app.id)}
                    >
                      <div className="companyline">
                        <span>{app.job?.company || "Company"}</span>
                      </div>
                      <strong title={app.job?.title}>
                        {app.job?.title || "Application"}
                      </strong>
                      <span className="application-location">
                        {app.job?.location || "Location not specified"}
                      </span>
                      {app.outcome && (
                        <span className="tag neutral outcome">
                          {app.outcome.replaceAll("_", " ")}
                        </span>
                      )}
                      <footer>
                        <span>
                          {!!app.documents_count && (
                            <>
                              <Icon name="file" />
                              {app.documents_count} document
                              {app.documents_count === 1 ? "" : "s"}
                            </>
                          )}
                        </span>
                        <time>{date(app.updated_at || app.created_at)}</time>
                      </footer>
                    </button>
                    <StageMenu
                      application={app}
                      pending={pending}
                      onMove={(id, stage) => void move(id, stage)}
                    />
                  </article>
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
                    <select
                      aria-label={`Stage for ${app.job?.title || "application"}`}
                      value={app.status}
                      disabled={pending}
                      onChange={(e) => move(app.id, e.target.value as Stage)}
                    >
                      {stages.map((s) => (
                        <option key={s} value={s}>
                          {stageLabels[s]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{app.outcome?.replaceAll("_", " ") || "—"}</td>
                  <td>{date(app.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination
        offset={offset}
        total={resource.data.total}
        limit={limit}
        onChange={(offset) => setFilters({ offset: String(offset) })}
      />
      <p className="hint">
        Column totals include every matching attempt across pages. Record stage
        changes when they happen.
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
  const { mutate, pending, refresh } = useWorkspace();
  const [file, setFile] = useState<File | null>(null),
    [createdId, setCreatedId] = useState<string | null>(null);
  const [documentText, setDocumentText] = useState(
    previous
      ? typeof previous.content.text === "string"
        ? previous.content.text
        : JSON.stringify(previous.content, null, 2)
      : "",
  );
  const [structured, setStructured] = useState(
    !!previous && typeof previous.content.text !== "string",
  );
  const [contextOffset, setContextOffset] = useState(0);
  const [selectedContext, setSelectedContext] = useState("");
  const [selectedContextLabel, setSelectedContextLabel] = useState("");
  const contexts = useResource<ListResult<Json>>(
    `/contexts?application_id=${application.id}&summary=true&limit=20&offset=${contextOffset}`,
    { items: [], total: 0 },
  );
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const ok = await mutate(async () => {
      let id = createdId;
      if (!id) {
        const doc = await api<Document>("/documents", "POST", {
          application_id: application.id,
          context_id: previous?.context_id || form.get("context_id") || null,
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
    if (ok) {
      refresh();
      onClose();
    }
  }
  return (
    <Dialog
      title={previous ? "Create a new revision." : "Add a document."}
      onClose={onClose}
    >
      <p className="modal-intro">
        Store externally prepared content, PDF and source files. Previous
        revisions stay unchanged.
        {previous?.revision_number
          ? ` Based on revision ${previous.revision_number}.`
          : ""}
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
        {!previous && (
          <section className="context-picker">
            <Field
              label="Frozen context"
              hint="Choose an optional frozen snapshot. Your selection is kept while you browse pages."
            >
              <select
                name="context_id"
                disabled={!!createdId}
                value={selectedContext}
                onChange={(e) => {
                  setSelectedContext(e.target.value);
                  setSelectedContextLabel(
                    e.target.selectedOptions[0]?.textContent || e.target.value,
                  );
                }}
              >
                <option value="">No frozen context</option>
                {selectedContext &&
                  !contexts.data.items.some(
                    (context) => context.id === selectedContext,
                  ) && (
                    <option value={selectedContext}>
                      {selectedContextLabel} · selected
                    </option>
                  )}
                {contexts.data.items.map((context) => (
                  <option key={String(context.id)} value={String(context.id)}>
                    {date(String(context.created_at))} ·{" "}
                    {String(context.id).slice(0, 8)}
                  </option>
                ))}
              </select>
            </Field>
            {contexts.error && (
              <ErrorBox message={contexts.error} retry={contexts.reload} />
            )}
            {contexts.data.total > 20 && (
              <Pagination
                label="Context chooser pages"
                offset={contextOffset}
                total={contexts.data.total}
                limit={20}
                onChange={setContextOffset}
              />
            )}
          </section>
        )}
        <label className="checkline">
          <input
            type="checkbox"
            checked={structured}
            onChange={(e) => {
              const next = e.target.checked;
              setDocumentText((value) => {
                if (next) return JSON.stringify({ text: value }, null, 2);
                try {
                  return String(JSON.parse(value).text || value);
                } catch {
                  return value;
                }
              });
              setStructured(next);
            }}
          />
          Use structured JSON content
        </label>
        <Field
          label={structured ? "Structured content (JSON)" : "Content"}
          hint="Changing content creates a revision. A PDF is attached only when you upload it."
        >
          <textarea
            key={String(structured)}
            name="text"
            rows={9}
            onChange={(e) => {
              setDocumentText(e.target.value);
              if (structured) {
                try {
                  const v = JSON.parse(e.target.value);
                  if (typeof v !== "object" || v === null || Array.isArray(v))
                    throw Error();
                  e.target.setCustomValidity("");
                } catch {
                  e.target.setCustomValidity("Enter a valid JSON object.");
                }
              }
            }}
            value={documentText}
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
  document: summary,
  application,
}: {
  document: Document;
  application: Application;
}) {
  const { mutate, pending } = useWorkspace();
  const [expanded, setExpanded] = useState(false),
    [edit, setEdit] = useState(false),
    [removing, setRemoving] = useState(false);
  const detail = useResource<Document | null>(
    expanded ? `/documents/${summary.id}` : null,
    null,
  );
  const document = detail.data || summary;
  return (
    <article className="document-card">
      <header>
        <div>
          <span className="eyebrow">{document.kind.replaceAll("_", " ")}</span>
          <h3>{document.title || "Untitled document"}</h3>
          <p>
            Revision {document.revision_number || 1} ·{" "}
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
      {expanded &&
        (detail.error ? (
          <ErrorBox message={detail.error} retry={detail.reload} />
        ) : detail.loading || !detail.data ? (
          <Loading />
        ) : (
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
              <Button
                icon="trash"
                variant="danger"
                onClick={() => setRemoving(true)}
              >
                Delete revision
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
        ))}
      {removing && (
        <Dialog
          title="Delete this document revision?"
          onClose={() => setRemoving(false)}
        >
          <p className="modal-intro">
            Remove this revision and its files. Other revisions and the
            application are kept.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(false)}>Keep revision</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={() =>
                mutate(
                  () => api(`/documents/${document.id}`, "DELETE"),
                  "Document revision removed.",
                )
              }
            >
              Delete revision
            </Button>
          </div>
        </Dialog>
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
  const [documentFilters, setDocumentFilters] = useUrlFilters({
    doc_q: "",
    doc_kind: "",
    doc_review: "",
    doc_offset: "0",
  });
  const documentQuery = useDebounce(documentFilters.doc_q);
  const resource = useResource<Application | null>(`/applications/${id}`, null),
    documents = useResource<ListResult<Document>>(
      `/documents?application_id=${id}&summary=true&limit=20&offset=${documentFilters.doc_offset}&q=${encodeURIComponent(documentQuery)}&kind=${documentFilters.doc_kind}${documentFilters.doc_review ? `&review_state=${documentFilters.doc_review}` : ""}`,
      { items: [], total: 0 },
    ),
    events = useResource<ListResult<Activity>>(`/applications/${id}/events`, {
      items: [],
      total: 0,
    }),
    templates = useResource<ListResult<Template>>(
      "/templates?summary=true",
      {
        items: [],
        total: 0,
      },
      true,
    );
  const { mutate, pending, notify } = useWorkspace();
  const [tab, setTab] = useUrlState("detail", "documents");
  const [add, setAdd] = useState(false),
    [contextOpen, setContextOpen] = useState(false),
    [removing, setRemoving] = useState(false);
  const [contextOffset, setContextOffset] = useUrlState("context_offset", "0");
  const contexts = useResource<ListResult<Json>>(
    `/contexts?application_id=${id}&summary=true&limit=20&offset=${Number(contextOffset) || 0}`,
    { items: [], total: 0 },
  );
  const app = resource.data;
  async function stage(status: Stage) {
    if (!confirmLeave()) return;
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
            ...(form.get("applied_at")
              ? {
                  applied_at: new Date(
                    String(form.get("applied_at")) + "Z",
                  ).toISOString(),
                }
              : {}),
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
      answers =
        form.get("structured_answers") === "on"
          ? jsonValue(form, "answers", {})
          : Object.fromEntries(
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
                  <h3>Prepare application documents</h3>
                  <p>
                    Export the job, your stored knowledge, template and
                    instructions as a frozen context. Upload PDF and sources
                    after external compilation.
                  </p>
                  <div className="actions">
                    <Button
                      icon="download"
                      disabled={pending}
                      onClick={() => setContextOpen(true)}
                    >
                      Prepare context
                    </Button>
                  </div>
                  {!!contexts.data.items.length && (
                    <details className="context-history">
                      <summary>Saved contexts · {contexts.data.total}</summary>
                      {contexts.data.items.map((context) => (
                        <div className="settingrow" key={String(context.id)}>
                          <div>
                            <strong>{date(String(context.created_at))}</strong>
                            <p>
                              Frozen snapshot · {String(context.id).slice(0, 8)}
                            </p>
                          </div>
                          <Button
                            className="small"
                            icon="download"
                            onClick={async () => {
                              try {
                                const data = await api<Json>(
                                  `/contexts/${context.id}`,
                                );
                                download(
                                  `context-${context.id}.json`,
                                  JSON.stringify(data, null, 2),
                                );
                              } catch (error) {
                                notify(
                                  error instanceof Error
                                    ? error.message
                                    : "Download failed.",
                                  true,
                                );
                              }
                            }}
                          >
                            Download
                          </Button>
                        </div>
                      ))}
                      <Pagination
                        label="Saved context pages"
                        offset={Number(contextOffset) || 0}
                        total={contexts.data.total}
                        limit={20}
                        onChange={(offset) => setContextOffset(String(offset))}
                      />
                      <details className="context-files">
                        <summary>Files in frozen contexts</summary>
                        {contexts.data.items.map((context) => (
                          <section key={String(context.id)}>
                            <h3>
                              {date(String(context.created_at))} ·{" "}
                              {String(context.id).slice(0, 8)}
                            </h3>
                            <FileManager
                              ownerType="context"
                              ownerId={String(context.id)}
                              immutable
                              readOnly
                            />
                          </section>
                        ))}
                      </details>
                    </details>
                  )}
                </section>
                <div className="sectiontitle">
                  <h3>Documents and revisions</h3>
                  <Button icon="plus" onClick={() => setAdd(true)}>
                    Add document
                  </Button>
                </div>
                <div className="document-filters">
                  <input
                    aria-label="Search documents"
                    placeholder="Search documents"
                    value={documentFilters.doc_q}
                    onChange={(e) =>
                      setDocumentFilters({
                        doc_q: e.target.value,
                        doc_offset: "0",
                      })
                    }
                  />
                  <select
                    aria-label="Document kind"
                    value={documentFilters.doc_kind}
                    onChange={(e) =>
                      setDocumentFilters({
                        doc_kind: e.target.value,
                        doc_offset: "0",
                      })
                    }
                  >
                    <option value="">All types</option>
                    <option value="resume">CV</option>
                    <option value="cover_letter">Cover letter</option>
                    <option value="answers">Form answers</option>
                    <option value="other">Other</option>
                  </select>
                  <select
                    aria-label="Document review state"
                    value={documentFilters.doc_review}
                    onChange={(e) =>
                      setDocumentFilters({
                        doc_review: e.target.value,
                        doc_offset: "0",
                      })
                    }
                  >
                    <option value="">All revisions</option>
                    <option value="draft">Draft</option>
                    <option value="approved">Approved</option>
                  </select>
                </div>
                {documents.data.items.length ? (
                  documents.data.items.map((d) => (
                    <DocumentCard key={d.id} document={d} application={app} />
                  ))
                ) : (
                  <Empty title="No documents in this view">
                    Save a CV, cover letter or source file prepared by you or
                    your external agent.
                  </Empty>
                )}
                <Pagination
                  offset={Number(documentFilters.doc_offset) || 0}
                  total={documents.data.total}
                  limit={20}
                  onChange={(offset) =>
                    setDocumentFilters({ doc_offset: String(offset) })
                  }
                />
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
                            step="any"
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
                    <label className="checkline">
                      <input type="checkbox" name="structured_answers" />
                      Use advanced structured answers below
                    </label>
                    <AdvancedJson
                      name="answers"
                      label="Structured answers"
                      value={app.answers}
                    />
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
                          {e.payload?.to
                            ? `${e.payload.from ? `${stageLabels[String(e.payload.from) as Stage] || String(e.payload.from)} → ` : ""}${stageLabels[String(e.payload.to) as Stage] || String(e.payload.to)}`
                            : e.payload?.status
                              ? String(e.payload.status)
                              : ""}
                        </p>
                        <time>{date(e.created_at)}</time>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <form onSubmit={saveDetails} key={app.id} className="stack">
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
                  label="Submission time (UTC)"
                  hint="Set this when recording a past submission. Stage changes record the current time by default."
                >
                  <input
                    type="datetime-local"
                    name="applied_at"
                    defaultValue={app.applied_at?.slice(0, 16) || ""}
                  />
                </Field>
                <Field
                  label="Application notes & writing guidance"
                  hint="Included in your agent's frozen application context."
                >
                  <textarea name="note" rows={9} defaultValue={app.note} />
                </Field>
                <Button variant="primary" disabled={pending}>
                  Save details
                </Button>
                <Button
                  type="button"
                  icon="trash"
                  variant="danger"
                  onClick={() => setRemoving(true)}
                >
                  Delete this application
                </Button>
              </form>
            )}
          </>
        )}
      </Dialog>
      {app && contextOpen && (
        <ContextBuilder
          application={app}
          templates={templates.data.items}
          onClose={() => setContextOpen(false)}
        />
      )}
      {app && removing && (
        <Dialog
          title="Delete this application attempt?"
          onClose={() => setRemoving(false)}
        >
          <p className="modal-intro">
            Remove this attempt, its history, frozen contexts, documents and
            files. The job and its other application attempts are kept.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(false)}>Keep application</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () =>
                      api(
                        `/applications/${id}?expected_version=${app.version}`,
                        "DELETE",
                      ),
                    "Application attempt deleted.",
                  )
                ) {
                  setRemoving(false);
                  onClose();
                }
              }}
            >
              Delete attempt
            </Button>
          </div>
        </Dialog>
      )}
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
function ContextBuilder({
  application,
  templates,
  onClose,
}: {
  application: Application;
  templates: Template[];
  onClose: () => void;
}) {
  const knowledge = useResource<ListResult<Knowledge>>(
      "/career/knowledge?summary=true",
      { items: [], total: 0 },
      true,
    ),
    claims = useResource<ListResult<Claim>>(
      "/career/claims?summary=true&approved=true",
      { items: [], total: 0 },
      true,
    );
  const { mutate, pending } = useWorkspace();
  const [selectEvidence, setSelectEvidence] = useState(false),
    [selectClaims, setSelectClaims] = useState(false),
    [query, setQuery] = useState("");
  return (
    <Dialog title="Prepare a frozen context." onClose={onClose}>
      <p className="modal-intro">
        Choose the evidence and templates your external agent should use. Saved
        snapshots retain the exact content and files from this moment.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            (selectEvidence && (knowledge.loading || knowledge.error)) ||
            (selectClaims && (claims.loading || claims.error))
          )
            return;
          const f = new FormData(e.currentTarget);
          if (
            await mutate(async () => {
              const context = await api<Json>("/contexts", "POST", {
                application_id: application.id,
                template_ids: f.getAll("templates"),
                ...(selectEvidence
                  ? { knowledge_ids: f.getAll("knowledge") }
                  : {}),
                ...(selectClaims ? { claim_ids: f.getAll("claims") } : {}),
                note: f.get("note"),
                idempotency_key: newId(),
              });
              download(
                `context-${context.id}.json`,
                JSON.stringify(context, null, 2),
              );
            }, "Frozen context saved and downloaded.")
          )
            onClose();
        }}
      >
        <fieldset className="selection-box">
          <legend>Templates</legend>
          <p className="hint">Leave empty to use your defaults.</p>
          {templates.map((t) => (
            <label className="checkline" key={t.id}>
              <input type="checkbox" name="templates" value={t.id} />
              {t.name} · {t.kind.replaceAll("_", " ")}
            </label>
          ))}
        </fieldset>
        <label className="checkline">
          <input
            type="checkbox"
            checked={selectEvidence}
            onChange={(e) => setSelectEvidence(e.target.checked)}
          />
          Choose specific career evidence
        </label>
        {selectEvidence && (
          <fieldset className="selection-box">
            <legend>Career evidence</legend>
            {knowledge.error ? (
              <ErrorBox message={knowledge.error} retry={knowledge.reload} />
            ) : knowledge.loading ? (
              <Loading />
            ) : null}
            <input
              aria-label="Find evidence for context"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find evidence"
            />
            {knowledge.data.items.map((k) => (
              <label
                className="checkline"
                style={{
                  display: k.title.toLowerCase().includes(query.toLowerCase())
                    ? undefined
                    : "none",
                }}
                key={k.id}
              >
                <input
                  type="checkbox"
                  name="knowledge"
                  value={k.id}
                  defaultChecked
                />
                {k.title}
              </label>
            ))}
          </fieldset>
        )}
        <label className="checkline">
          <input
            type="checkbox"
            checked={selectClaims}
            onChange={(e) => setSelectClaims(e.target.checked)}
          />
          Choose specific approved claims
        </label>
        {selectClaims && (
          <fieldset className="selection-box">
            <legend>Approved claims</legend>
            {claims.error ? (
              <ErrorBox message={claims.error} retry={claims.reload} />
            ) : claims.loading ? (
              <Loading />
            ) : null}
            {claims.data.items.map((c) => (
              <label className="checkline" key={c.id}>
                <input
                  type="checkbox"
                  name="claims"
                  value={c.id}
                  defaultChecked
                />
                {c.text_preview || c.text}
              </label>
            ))}
          </fieldset>
        )}
        <Field label="Instructions for this snapshot">
          <textarea name="note" rows={4} />
        </Field>
        <div className="actions form-actions">
          <Button
            variant="primary"
            disabled={
              pending ||
              (selectEvidence && (knowledge.loading || !!knowledge.error)) ||
              (selectClaims && (claims.loading || !!claims.error))
            }
          >
            Save & download context
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
