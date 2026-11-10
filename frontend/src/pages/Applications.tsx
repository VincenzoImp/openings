import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  calendarDate,
  formatTime,
  localToday,
  readinessLabels,
  requirementKinds,
  type Readiness,
  type Requirement,
  type RequirementKind,
  careerEntryLabel,
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
  type Consistency,
  type Document,
  type StaleInput,
  type Staleness,
  type Job,
  type ListResult,
  type Stage,
  type Template,
} from "../api";
import { FileManager } from "../files";
import {
  useEditorRecord,
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
  LazyDetails,
  outcomeLabel,
  outcomeLabels,
  stageLabels,
  Tabs,
  PendingResults,
} from "../ui";
const stages: Stage[] = ["draft", "applied", "interview", "offer", "closed"];
const priorityLabels: Record<number, string> = {
  1: "P1 · Highest",
  2: "P2 · High",
  3: "P3 · Normal",
  4: "P4 · Low",
  5: "P5 · Lowest",
};
/** Priority, deadline and blocking requirements, shown wherever an attempt is listed. */
function PlanTags({ application }: { application: Application }) {
  const today = localToday();
  const open = application.status === "draft";
  const overdue =
    open && !!application.deadline && application.deadline < today;
  const soon =
    open &&
    !!application.deadline &&
    !overdue &&
    application.deadline <= localToday(new Date(Date.now() + 7 * 86400000));
  const blocking = application.blocking_requirements || 0;
  if (!application.priority && !application.deadline && !blocking) return null;
  return (
    <span className="plan-tags">
      {!!application.priority && (
        <span
          className={`tag ${application.priority <= 2 ? "amber" : "neutral"}`}
          title={priorityLabels[application.priority]}
        >
          P{application.priority}
        </span>
      )}
      {application.deadline && (
        <span
          className={`tag ${overdue ? "danger" : soon ? "amber" : "neutral"}`}
        >
          <Icon name="clock" />
          {overdue ? "Overdue · " : "Due "}
          {calendarDate(application.deadline)}
        </span>
      )}
      {!!blocking && (
        <span className="tag danger">
          <Icon name="error" />
          {blocking} blocking requirement{blocking === 1 ? "" : "s"}
        </span>
      )}
    </span>
  );
}
function useApplicationProgress() {
  const { mutate, pending } = useWorkspace();
  const [closing, setClosing] = useState<Application | null>(null);
  const [outcome, setOutcome] = useState("");
  async function save(
    application: Application,
    status: Stage,
    result: string | null = null,
  ) {
    if (!confirmLeave()) return false;
    return mutate(
      () =>
        api(
          `/applications/${application.id}`,
          "PATCH",
          version(application, { status, outcome: result }),
        ),
      `Moved to ${stageLabels[status]}.`,
    );
  }
  async function move(application: Application, status: Stage) {
    if (application.status === status) return;
    if (status === "closed") {
      setOutcome("");
      setClosing(application);
    } else await save(application, status);
  }
  const dialog = closing && (
    <Dialog title="Close this application?" onClose={() => setClosing(null)}>
      <p className="modal-intro">
        Record the outcome of this application attempt.
      </p>
      <Field label="Outcome">
        <select
          value={outcome}
          onChange={(event) => setOutcome(event.target.value)}
        >
          <option value="">Choose an outcome</option>
          {Object.entries(outcomeLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <div className="actions form-actions">
        <Button onClick={() => setClosing(null)}>Keep application open</Button>
        <Button
          variant="primary"
          disabled={pending || !outcome}
          onClick={async () => {
            if (await save(closing, "closed", outcome)) setClosing(null);
          }}
        >
          Save outcome
        </Button>
      </div>
    </Dialog>
  );
  return { move, dialog };
}
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
    readiness: "",
    sort: "updated",
    offset: "0",
    view: (() => {
      try {
        return (
          localStorage.getItem("openings-application-view") ||
          (matchMedia("(max-width: 600px)").matches ? "list" : "board")
        );
      } catch {
        return matchMedia("(max-width: 600px)").matches ? "list" : "board";
      }
    })(),
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
  const updating = resource.loading || query !== filters.q;
  const filtered = !!(
    filters.q ||
    filters.status ||
    filters.outcome ||
    filters.readiness
  );
  const { pending } = useWorkspace();
  const progress = useApplicationProgress();
  const [dragged, setDragged] = useState<string | null>(null);
  async function move(id: string, status: Stage) {
    const app = resource.data.items.find((a) => a.id === id);
    if (app) await progress.move(app, status);
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
              onClick={() => {
                setFilters({ view });
                try {
                  localStorage.setItem("openings-application-view", view);
                } catch {}
              }}
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
          {Object.entries(outcomeLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter preparation readiness"
          value={filters.readiness}
          onChange={(e) =>
            setFilters({ readiness: e.target.value, offset: "0" })
          }
        >
          <option value="">Any readiness</option>
          {Object.entries(readinessLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
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
          <option value="deadline">Deadline (soonest)</option>
          <option value="priority">Priority (highest)</option>
        </select>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <PendingResults pending={updating} />
      <div className="stage-overview" aria-label="Application stage totals">
        {stages.map((stage) => (
          <Button
            key={stage}
            variant={filters.status === stage ? "selected" : ""}
            onClick={() =>
              setFilters({
                status: filters.status === stage ? "" : stage,
                offset: "0",
              })
            }
          >
            {stageLabels[stage]}{" "}
            <span>{resource.data.stage_counts?.[stage] ?? 0}</span>
          </Button>
        ))}
      </div>
      <div className="boardcaption">
        <span>{resource.data.total} application attempts</span>
        <span>
          {filters.view === "board"
            ? "Scroll across stages. Drag cards or use the move menu."
            : "Open an application to review documents and update progress."}
        </span>
      </div>
      {updating ? (
        <Loading />
      ) : !resource.data.items.length ? (
        <section className="card">
          <Empty
            title={
              filtered
                ? "No applications match your filters"
                : "Ready to prepare an application?"
            }
            action={
              filtered ? (
                <Button
                  onClick={() =>
                    setFilters({
                      q: "",
                      status: "",
                      outcome: "",
                      readiness: "",
                      offset: "0",
                    })
                  }
                >
                  Clear filters
                </Button>
              ) : (
                <a href="#shortlist" className="btn">
                  Review Shortlist
                </a>
              )
            }
          >
            {filtered
              ? "Try another search or clear the filters to see your applications."
              : "Choose a shortlisted job and start preparing its documents. Submission is recorded separately."}
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
              {(resource.data.stage_counts?.[stage] || 0) >
                resource.data.items.filter((a) => a.status === stage)
                  .length && (
                <button
                  className="textbutton stage-page-link"
                  onClick={() => setFilters({ status: stage, offset: "0" })}
                >
                  Showing{" "}
                  {resource.data.items.filter((a) => a.status === stage).length}{" "}
                  of {resource.data.stage_counts?.[stage]} · View stage
                </button>
              )}
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
                      <PlanTags application={app} />
                      {app.outcome && (
                        <span className="tag neutral outcome">
                          {outcomeLabel(app.outcome)}
                        </span>
                      )}
                      <Preparation application={app} />
                      <span className="application-next">
                        {app.status === "draft"
                          ? "Continue preparation"
                          : app.status === "closed"
                            ? "View outcome and documents"
                            : "Review documents and progress"}{" "}
                        <Icon name="arrow" />
                      </span>
                      <footer>
                        <span>
                          {!!app.documents_count && (
                            <>
                              <Icon name="file" />
                              {app.documents_count} saved revision
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
        <div className="card application-list">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Company / role</th>
                <th scope="col">Stage</th>
                <th scope="col">Plan</th>
                <th scope="col">Preparation</th>
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
                      <small>
                        {[app.job?.company, app.job?.location]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    </button>
                  </td>
                  <td data-label="Stage">
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
                  <td data-label="Plan">
                    <PlanTags application={app} />
                    {!app.priority &&
                      !app.deadline &&
                      !app.blocking_requirements && (
                        <span className="muted">Not set</span>
                      )}
                  </td>
                  <td data-label="Preparation">
                    <Preparation application={app} />
                  </td>
                  <td data-label="Outcome">{outcomeLabel(app.outcome)}</td>
                  <td data-label="Updated">{date(app.updated_at)}</td>
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
      {progress.dialog}
    </>
  );
}

function Preparation({ application }: { application: Application }) {
  const kinds: Record<string, string> = {
    resume: "CV",
    cover_letter: "Cover letter",
    answers: "Form answers",
    other: "Other",
  };
  return (
    <div className="preparation-summary" aria-label="Document preparation">
      {application.preparation?.length ? (
        application.preparation.map((item) => (
          <span
            key={item.kind}
            className={`preparation-item ${item.approved === item.revisions ? "approved" : ""}`}
          >
            {kinds[item.kind] || item.kind}:{" "}
            {item.approved === item.revisions
              ? "Approved PDF"
              : item.pdf < item.revisions
                ? ["resume", "cover_letter"].includes(item.kind)
                  ? "Needs PDF"
                  : "Content saved"
                : "PDF to review"}
            {item.revisions > 1
              ? ` (${item.approved}/${item.revisions} approved)`
              : ""}
          </span>
        ))
      ) : (
        <span>No documents yet</span>
      )}
      {!!application.stale_inputs?.length && (
        <span
          className="preparation-item stale"
          title={`Changed since the context was frozen: ${application.stale_inputs
            .map((input) => staleLabels[input])
            .join(", ")}`}
        >
          <Icon name="refresh" /> Built on older inputs
        </span>
      )}
    </div>
  );
}
const staleLabels: Record<StaleInput, string> = {
  profile: "Profile",
  instructions: "General guidance",
  template: "Template",
  knowledge: "Career entry",
  claim: "Claim",
};
const staleStates = {
  changed: "changed",
  deleted: "deleted",
  unapproved: "no longer approved",
};
function StalenessNotice({ application }: { application: Application }) {
  const report = useResource<Staleness | null>(
    application.stale_inputs?.length
      ? `/applications/${application.id}/staleness`
      : null,
    null,
  );
  if (!application.stale_inputs?.length) return null;
  const stale = report.data?.documents.filter(
    (item) => item.status === "stale",
  );
  return (
    <section className="stale-notice" aria-label="Built on older inputs">
      <h3>
        <Icon name="refresh" /> Built on older inputs
      </h3>
      <p>
        The current revisions were prepared from a frozen context. These inputs
        changed afterwards. Frozen contexts stay unchanged; to refresh, prepare
        a new context and save new revisions.
      </p>
      {report.error ? (
        <ErrorBox message={report.error} retry={report.reload} />
      ) : !report.data ? (
        <Loading />
      ) : (
        <>
          <ul>
            {report.data.changes.map((change) => (
              <li key={`${change.input}-${change.id ?? ""}`}>
                <strong>{staleLabels[change.input]}</strong>
                {change.label && change.id ? ` “${change.label}”` : ""}{" "}
                {staleStates[change.state]}
                {change.state === "changed" &&
                change.frozen_version !== null &&
                change.current_version !== null
                  ? ` (version ${change.frozen_version} → ${change.current_version})`
                  : ""}
              </li>
            ))}
          </ul>
          {!!stale?.length && (
            <p className="hint">
              Affected revisions:{" "}
              {stale
                .map((item) => item.title || kindLabels[item.kind] || item.kind)
                .join(", ")}
            </p>
          )}
        </>
      )}
    </section>
  );
}
const kindLabels: Record<string, string> = {
  resume: "CV",
  cover_letter: "Cover letter",
  answers: "Form answers",
  other: "Other",
};
function SourceCheck({ report }: { report: Consistency }) {
  if (report.status === "consistent")
    return (
      <p className="source-check ok">
        <Icon name="check" /> {report.reason}
      </p>
    );
  if (report.status === "not_checked")
    return <p className="source-check">{report.reason}</p>;
  return (
    <div className="source-check mismatch" role="status">
      <p>
        <Icon name="error" /> The saved content and the .tex source differ.{" "}
        {report.reason}
      </p>
      <ul>
        {report.mismatches.slice(0, 5).map((item) => (
          <li key={item.path}>
            <code>{item.path}</code> {item.text}
          </li>
        ))}
      </ul>
      <p className="hint">
        Save the matching content as a new revision or upload the matching
        source. Approve with differences only when they are intentional.
      </p>
    </div>
  );
}
function contextLabel(context: Json) {
  return [
    formatTime(String(context.created_at)),
    context.template_name || context.job_title,
    `${context.knowledge_count ?? 0} entries`,
    `${context.claim_count ?? 0} claims`,
    context.note_preview ? String(context.note_preview).slice(0, 60) : "",
    String(context.id).slice(0, 6),
  ]
    .filter(Boolean)
    .join(" · ");
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
                    {contextLabel(context)}
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
  const consistency = useResource<Consistency | null>(
    expanded ? `/documents/${summary.id}/consistency` : null,
    null,
  );
  const mismatch = consistency.data?.status === "mismatch";
  return (
    <article className="document-card">
      <header>
        <div>
          <span className="eyebrow">
            {(
              {
                resume: "CV",
                cover_letter: "Cover letter",
                answers: "Form answers",
                other: "Other",
              } as Record<string, string>
            )[document.kind] || document.kind}
          </span>
          <h3>{document.title || "Untitled document"}</h3>
          <p>
            Revision {document.revision_number || 1} ·{" "}
            {date(document.created_at)} ·{" "}
            {document.review_state === "approved"
              ? "Approved"
              : (document.file_count ?? document.files?.length ?? 0)
                ? "Awaiting review"
                : "Content saved · no files"}
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
              files={document.files}
              immutable
              preview
              readOnly={document.review_state === "approved"}
            />
            {consistency.data && <SourceCheck report={consistency.data} />}
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
                  variant={mismatch ? "danger" : "primary"}
                  icon="check"
                  disabled={
                    pending ||
                    detail.refreshing ||
                    !!detail.error ||
                    consistency.loading
                  }
                  onClick={() =>
                    mutate(
                      () =>
                        api(`/documents/${document.id}/review`, "POST", {
                          review_state: "approved",
                          expected_version: document.version,
                          allow_content_mismatch: mismatch,
                        }),
                      "Document approved.",
                    )
                  }
                >
                  {mismatch
                    ? "Approve with differences"
                    : "Approve this revision"}
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
  const progress = useApplicationProgress();
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
    if (app) await progress.move(app, status);
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
            priority: Number(form.get("priority")) || null,
            deadline: String(form.get("deadline") || "") || null,
            applied_at: form.get("applied_at")
              ? new Date(String(form.get("applied_at")) + "Z").toISOString()
              : null,
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
          <>
            <span className="smalltext muted">
              {app?.status === "draft"
                ? "Preparing — not submitted"
                : "Application progress is recorded manually."}
            </span>
            {app && (
              <Button className="small" onClick={() => setTab("posting")}>
                View posting
              </Button>
            )}
          </>
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
            <PlanTags application={app} />
            {!!app.blocking_requirements && (
              <div className="note requirement-alert" role="status">
                <Icon name="error" />
                <div>
                  <strong>
                    Blocking requirements need an owner decision before
                    documents are prepared or submitted.
                  </strong>
                  <ul>
                    {(app.requirements || [])
                      .filter((item) => item.blocking && !item.resolved)
                      .map((item) => (
                        <li key={item.id}>
                          {requirementKinds[item.kind] || item.kind}:{" "}
                          {item.text}
                        </li>
                      ))}
                  </ul>
                  <button
                    type="button"
                    className="textbutton"
                    onClick={() => setTab("requirements")}
                  >
                    Review requirements
                  </button>
                </div>
              </div>
            )}
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
                { id: "posting", label: "Posting" },
                {
                  id: "requirements",
                  label: "Requirements",
                  count: app.open_requirements || undefined,
                },
                { id: "answers", label: "Form answers" },
                { id: "history", label: "History" },
                { id: "details", label: "Details" },
              ]}
            />
            {tab === "posting" ? (
              <>
                <div className="posting">
                  {app.job?.posting ||
                    "The full posting is missing. Open the job from All jobs to add its text."}
                </div>
                {app.job?.url && (
                  <a
                    className="btn"
                    href={app.job.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Original posting <Icon name="external" />
                  </a>
                )}
              </>
            ) : tab === "documents" ? (
              <>
                {documents.error && (
                  <ErrorBox
                    message={documents.error}
                    retry={documents.reload}
                  />
                )}
                <details className="context-panel agent-preparation">
                  <summary>
                    Prepare with your agent · {contexts.data.total} saved
                    context{contexts.data.total === 1 ? "" : "s"}
                  </summary>
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
                            <strong>{contextLabel(context)}</strong>
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
                      <LazyDetails
                        className="context-files"
                        summary="Files in frozen contexts"
                      >
                        {contexts.data.items.map((context) => (
                          <section key={String(context.id)}>
                            <h3>{contextLabel(context)}</h3>
                            <FileManager
                              ownerType="context"
                              ownerId={String(context.id)}
                              immutable
                              readOnly
                            />
                          </section>
                        ))}
                      </LazyDetails>
                    </details>
                  )}
                </details>
                <Preparation application={app} />
                <StalenessNotice application={app} />
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
                <PendingResults
                  pending={
                    documents.loading || documentQuery !== documentFilters.doc_q
                  }
                />
                {documents.loading ||
                documentQuery !== documentFilters.doc_q ? (
                  <Loading />
                ) : documents.data.items.length ? (
                  documents.data.items.map((d) => (
                    <DocumentCard key={d.id} document={d} application={app} />
                  ))
                ) : (
                  <Empty
                    title={
                      documentFilters.doc_q ||
                      documentFilters.doc_kind ||
                      documentFilters.doc_review
                        ? "No documents match your filters"
                        : "Prepare your first document"
                    }
                    action={
                      documentFilters.doc_q ||
                      documentFilters.doc_kind ||
                      documentFilters.doc_review ? (
                        <Button
                          onClick={() =>
                            setDocumentFilters({
                              doc_q: "",
                              doc_kind: "",
                              doc_review: "",
                              doc_offset: "0",
                            })
                          }
                        >
                          Clear document filters
                        </Button>
                      ) : (
                        <Button onClick={() => setContextOpen(true)}>
                          Prepare with your agent
                        </Button>
                      )
                    }
                  >
                    Save a CV or cover letter, attach its files and review the
                    exact revision. Adding documents does not submit this
                    application.
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
            ) : tab === "requirements" ? (
              <RequirementsEditor
                key={`${app.id}-${app.version}`}
                application={app}
              />
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
              <form
                onSubmit={saveDetails}
                key={`${app.id}-${app.version}`}
                className="stack"
              >
                {app.status === "closed" && (
                  <Field label="Outcome">
                    <select
                      name="outcome"
                      defaultValue={app.outcome || "not_pursued"}
                    >
                      {Object.entries(outcomeLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>
                )}
                <div className="formgrid">
                  <Field
                    label="Priority"
                    hint="Orders preparation work. 1 is the highest."
                  >
                    <select
                      name="priority"
                      defaultValue={String(app.priority ?? "")}
                    >
                      <option value="">Not set</option>
                      {Object.entries(priorityLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field
                    label="Application deadline"
                    hint="The employer's closing date, if known."
                  >
                    <input
                      type="date"
                      name="deadline"
                      defaultValue={app.deadline || ""}
                    />
                  </Field>
                </div>
                <Field
                  label="Submission time (UTC)"
                  hint="Set a past submission time or leave blank to clear it. Moving to a submitted stage records the current time when no date is known."
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
      {progress.dialog}
      {app && contextOpen && (
        <ContextBuilder
          application={app}
          templatesResource={templates}
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
            files. The job and its other application attempts are kept. If this
            is its final attempt, a saved job returns to Shortlist. To stop
            preparation and keep documents, close as Not pursued instead.
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
function RequirementsEditor({ application }: { application: Application }) {
  const { mutate, pending } = useWorkspace();
  const [items, setItems] = useState<Requirement[]>(
    application.requirements || [],
  );
  const change = (index: number, patch: Partial<Requirement>) =>
    setItems((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    );
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await mutate(
      () =>
        api(
          `/applications/${application.id}`,
          "PATCH",
          version(application, {
            requirements: items.map((item) => ({
              ...item,
              text: item.text.trim(),
              note: item.note.trim(),
            })),
          }),
        ),
      "Requirements saved.",
    );
  }
  return (
    <form onSubmit={save} className="stack requirements-editor">
      <p className="hint">
        Record employer conditions from the posting or application form:
        authorship rules, attachments, references, format, language, eligibility
        and dates. An unresolved blocking requirement keeps this application not
        ready.
      </p>
      {!items.length && (
        <p className="muted">No employer requirements recorded.</p>
      )}
      {items.map((item, index) => (
        <fieldset
          key={item.id}
          className={`requirement-row ${item.blocking && !item.resolved ? "is-blocking" : ""} ${item.resolved ? "is-resolved" : ""}`}
        >
          <legend>
            {requirementKinds[item.kind] || item.kind}
            {item.blocking && !item.resolved
              ? " · blocking"
              : item.resolved
                ? " · resolved"
                : ""}
          </legend>
          <div className="requirement-head">
            <Field label="Kind">
              <select
                value={item.kind}
                onChange={(e) =>
                  change(index, { kind: e.target.value as RequirementKind })
                }
              >
                {Object.entries(requirementKinds).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <label className="checkline">
              <input
                type="checkbox"
                checked={item.blocking}
                onChange={(e) => change(index, { blocking: e.target.checked })}
              />
              Blocking
            </label>
            <label className="checkline">
              <input
                type="checkbox"
                checked={item.resolved}
                onChange={(e) => change(index, { resolved: e.target.checked })}
              />
              Resolved
            </label>
            <button
              type="button"
              className="iconbtn danger"
              data-dirty-control
              aria-label={`Remove requirement ${index + 1}`}
              onClick={() =>
                setItems((current) => current.filter((_, i) => i !== index))
              }
            >
              <Icon name="trash" />
            </button>
          </div>
          <Field label="Requirement">
            <textarea
              rows={2}
              required
              maxLength={2000}
              value={item.text}
              onChange={(e) => change(index, { text: e.target.value })}
            />
          </Field>
          <Field label="Resolution or open question">
            <input
              maxLength={2000}
              value={item.note}
              placeholder="Owner decision, supplied file or question to ask"
              onChange={(e) => change(index, { note: e.target.value })}
            />
          </Field>
        </fieldset>
      ))}
      <div className="actions form-actions">
        <Button
          type="button"
          icon="plus"
          data-dirty-control
          disabled={items.length >= 100}
          onClick={() =>
            setItems((current) => [
              ...current,
              {
                id: newId().replace(/-/g, "").slice(0, 12),
                kind: "other",
                text: "",
                blocking: false,
                resolved: false,
                note: "",
              },
            ])
          }
        >
          Add requirement
        </Button>
        <Button variant="primary" disabled={pending}>
          Save requirements
        </Button>
      </div>
    </form>
  );
}
function QuestionEditor({
  application: initial,
}: {
  application: Application;
}) {
  const application = useEditorRecord(initial, `/applications/${initial.id}`)!;
  const [editorRevision, setEditorRevision] = useState(0);
  const [editing, setEditing] = useState<
      import("../api").Question | "new" | null
    >(null),
    [kind, setKind] = useState("text");
  const { mutate, pending } = useWorkspace();
  const [answerError, setAnswerError] = useState("");
  const [removingQuestion, setRemovingQuestion] = useState<
    import("../api").Question | null
  >(null);
  const record = editing && editing !== "new" ? editing : null;
  useEffect(() => {
    const reload = (event: Event) => {
      const { path, record: latest } = (
        event as CustomEvent<{ path: string; record: Application }>
      ).detail;
      if (path !== `/applications/${initial.id}`) return;
      if (editing && editing !== "new") {
        const next = latest.questions.find(
          (question) => question.id === editing.id,
        );
        setEditing(next || null);
        if (next) setKind(next.type || "text");
      }
      setAnswerError("");
      setEditorRevision((value) => value + 1);
    };
    window.addEventListener("openings:record-reloaded", reload);
    return () => window.removeEventListener("openings:record-reloaded", reload);
  }, [initial.id, editing]);
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
    const clearAnswer = record && f.get("clear_answer") === "on";
    if (clearAnswer && record) delete answers[record.id];
    if (
      await mutate(async () => {
        try {
          await api(
            `/applications/${application.id}`,
            "PATCH",
            version(application, {
              questions,
              ...(clearAnswer ? { answers } : {}),
            }),
          );
        } catch (error) {
          if (
            error instanceof ApiError &&
            error.status === 422 &&
            error.code.startsWith("answer_")
          )
            setAnswerError(error.message);
          throw error;
        }
      }, "Question saved.")
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
            setAnswerError("");
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
                  setAnswerError("");
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
                onClick={() => setRemovingQuestion(q)}
              >
                <Icon name="trash" />
              </button>
            </div>
          ))}
        </details>
      )}
      {removingQuestion && (
        <Dialog
          title="Remove this question and its answer?"
          onClose={() => setRemovingQuestion(null)}
        >
          <p className="modal-intro">{removingQuestion.label}</p>
          <p>
            Its saved live answer will be permanently removed. Frozen contexts
            and document revisions keep their copies.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemovingQuestion(null)}>
              Keep question
            </Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                const answers = { ...application.answers };
                delete answers[removingQuestion.id];
                if (
                  await mutate(
                    () =>
                      api(
                        `/applications/${application.id}`,
                        "PATCH",
                        version(application, {
                          questions: application.questions.filter(
                            (q) => q.id !== removingQuestion.id,
                          ),
                          answers,
                        }),
                      ),
                    "Question removed.",
                  )
                )
                  setRemovingQuestion(null);
              }}
            >
              Remove question and answer
            </Button>
          </div>
        </Dialog>
      )}
      {editing && (
        <Dialog
          title={record ? "Edit form question." : "Add a form question."}
          onClose={() => setEditing(null)}
        >
          <form key={editorRevision} onSubmit={save}>
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
                Compatible saved answers are kept when you update this question.
              </p>
            )}
            {answerError && (
              <div className="note">
                <div>
                  <p>{answerError}</p>
                  <p>
                    Saved answer:{" "}
                    {JSON.stringify(
                      record ? application.answers[record.id] : null,
                    )}
                  </p>
                  <label className="checkline">
                    <input type="checkbox" name="clear_answer" />
                    Clear this incompatible answer when saving the question
                  </label>
                </div>
              </div>
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
  templatesResource,
  onClose,
}: {
  application: Application;
  templatesResource: ReturnType<typeof useResource<ListResult<Template>>>;
  onClose: () => void;
}) {
  const templates = templatesResource.data.items;
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
    [evidenceIds, setEvidenceIds] = useState<string[] | null>(null),
    [claimIds, setClaimIds] = useState<string[] | null>(null),
    [templateIds, setTemplateIds] = useState<string[]>([]);
  const chosenEvidence =
    evidenceIds ?? knowledge.data.items.slice(0, 500).map((k) => k.id);
  const availableClaims = claims.data.items.filter(
    (c) => !selectEvidence || chosenEvidence.includes(c.knowledge_id),
  );
  const chosenClaims = (
    claimIds ?? availableClaims.slice(0, 1000).map((c) => c.id)
  ).filter((id) => availableClaims.some((c) => c.id === id));
  return (
    <Dialog title="Prepare a frozen context." onClose={onClose}>
      <p className="modal-intro">
        Choose evidence and templates for your external agent. Saved snapshots
        retain the exact content and files from this moment.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (
            templatesResource.loading ||
            templatesResource.error ||
            knowledge.loading ||
            claims.loading ||
            knowledge.error ||
            claims.error
          )
            return;
          const form = new FormData(event.currentTarget);
          if (
            await mutate(async () => {
              const context = await api<Json>("/contexts", "POST", {
                application_id: application.id,
                template_ids: templateIds,
                ...(selectEvidence ? { knowledge_ids: chosenEvidence } : {}),
                ...(selectClaims ? { claim_ids: chosenClaims } : {}),
                note: form.get("note"),
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
        {templatesResource.loading && <Loading />}
        {templatesResource.error && (
          <ErrorBox
            message={templatesResource.error}
            retry={templatesResource.reload}
          />
        )}
        <ChoiceList
          label="Templates"
          limit={20}
          items={templates.map((t) => ({
            id: t.id,
            label: `${t.name} · ${t.kind === "resume" ? "CV" : "Cover letter"}`,
          }))}
          selected={templateIds}
          onChange={setTemplateIds}
          hint="Select up to 20 templates. Leave empty to use your defaults."
        />
        {!templatesResource.loading &&
          !templatesResource.error &&
          templates.length === 0 && (
            <p className="note">
              Add a template in Templates before preparing a context.
            </p>
          )}
        {knowledge.error && (
          <ErrorBox message={knowledge.error} retry={knowledge.reload} />
        )}
        {claims.error && (
          <ErrorBox message={claims.error} retry={claims.reload} />
        )}
        <label className="checkline">
          <input
            type="checkbox"
            checked={selectEvidence}
            onChange={(e) => setSelectEvidence(e.target.checked)}
          />
          Choose specific career entries
        </label>
        {selectEvidence && (
          <ChoiceList
            label="Career entries"
            limit={500}
            items={knowledge.data.items.map((k) => ({
              id: k.id,
              label: careerEntryLabel(k),
            }))}
            selected={chosenEvidence}
            onChange={(ids) => {
              setEvidenceIds(ids);
              if (selectClaims)
                setClaimIds(
                  chosenClaims.filter((id) =>
                    claims.data.items.some(
                      (c) => c.id === id && ids.includes(c.knowledge_id),
                    ),
                  ),
                );
            }}
            hint="Entries are initially selected, up to 500. Clear the selection to include none. Claims from excluded entries are excluded too."
          />
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
          <ChoiceList
            label="Approved claims"
            limit={1000}
            items={availableClaims.map((c) => ({
              id: c.id,
              label: `${c.knowledge_title || "Career entry"}${c.knowledge_organization ? ` · ${c.knowledge_organization}` : ""}: ${c.text_preview || c.text}`,
            }))}
            selected={chosenClaims}
            onChange={setClaimIds}
            hint="Only claims belonging to included entries are available. An empty selection deliberately includes no claims."
          />
        )}
        <Field label="Instructions for this snapshot">
          <textarea name="note" rows={4} />
        </Field>
        <div className="actions form-actions">
          <Button
            variant="primary"
            disabled={
              pending ||
              !templates.length ||
              templatesResource.loading ||
              !!templatesResource.error ||
              knowledge.loading ||
              claims.loading ||
              !!knowledge.error ||
              !!claims.error
            }
          >
            Save & download context
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
function ChoiceList({
  label,
  items,
  selected,
  onChange,
  hint,
  limit,
}: {
  label: string;
  items: { id: string; label: string }[];
  selected: string[];
  onChange: (ids: string[]) => void;
  hint: string;
  limit: number;
}) {
  const [query, setQuery] = useState("");
  const visible = items.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <fieldset className="selection-box">
      <legend>
        {label} · {selected.length} selected
      </legend>
      <p className="hint">{hint}</p>
      <input
        aria-label={`Find ${label.toLowerCase()} for context`}
        placeholder={`Find ${label.toLowerCase()}`}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="actions selection-actions">
        <Button
          type="button"
          data-dirty-control
          disabled={selected.length >= limit}
          onClick={() =>
            onChange(
              [
                ...new Set([...selected, ...visible.map((item) => item.id)]),
              ].slice(0, limit),
            )
          }
        >
          Select matching
        </Button>
        <Button
          type="button"
          data-dirty-control
          onClick={() =>
            onChange(
              selected.filter((id) => !visible.some((item) => item.id === id)),
            )
          }
        >
          Clear matching
        </Button>
      </div>
      <div className="choice-options">
        {visible.length ? (
          visible.map((item) => (
            <label className="checkline" key={item.id}>
              <input
                type="checkbox"
                checked={selected.includes(item.id)}
                disabled={
                  !selected.includes(item.id) && selected.length >= limit
                }
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...selected, item.id]
                      : selected.filter((id) => id !== item.id),
                  )
                }
              />
              {item.label}
            </label>
          ))
        ) : (
          <p className="hint">No matching {label.toLowerCase()}.</p>
        )}
      </div>
    </fieldset>
  );
}
