import { useState, type FormEvent } from "react";
import {
  api,
  date,
  jsonValue,
  version,
  type Application,
  type Job,
  type ListResult,
  type Note,
  type Triage,
} from "../api";
import {
  confirmLeave,
  useDebounce,
  useResource,
  useUrlFilters,
  useUrlState,
  useWorkspace,
} from "../state";
import { FileManager } from "../files";
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
  Score,
  Tabs,
} from "../ui";

const blankJobs: ListResult<Job> = { items: [], total: 0 };
export function AddJob({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    let created: Job | undefined;
    const ok = await mutate(async () => {
      created = await api<Job>("/jobs", "POST", {
        ...Object.fromEntries(f),
        metadata: jsonValue(f, "metadata"),
      });
    }, "Opportunity saved.");
    if (ok && created) {
      onClose();
      onCreated(created.id);
    }
  }
  return (
    <Dialog title="Add an opportunity." onClose={onClose}>
      <p className="modal-intro">Keep a job you found, however you found it.</p>
      <form onSubmit={submit}>
        <Field label="Job URL">
          <input
            name="url"
            type="url"
            placeholder="https://company.example/careers/role"
          />
        </Field>
        <div className="formgrid">
          <Field label="Role">
            <input name="title" placeholder="Backend Engineer" />
          </Field>
          <Field label="Company">
            <input name="company" placeholder="Company name" />
          </Field>
        </div>
        <Field label="Location">
          <input name="location" placeholder="City or region" />
        </Field>
        <AdvancedJson name="metadata" label="Job metadata" />
        <Field
          label="Posting text"
          hint="Add a URL or paste the posting. If a page cannot be read, you can complete its text later."
        >
          <textarea
            name="posting"
            rows={7}
            placeholder="Paste the full job posting…"
          />
        </Field>
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Add to inbox
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
export function JobsPage({
  onAdd,
  onOpen,
}: {
  onAdd: () => void;
  onOpen: (id: string) => void;
}) {
  const [filters, setFilters] = useUrlFilters({
    triage: "inbox",
    q: "",
    company: "",
    location: "",
    source: "",
    remote: "",
    job_type: "",
    score_min: "",
    score_max: "",
    score_state: "all",
    complete: "",
    created_since: "",
    created_until: "",
    sort: "newest",
    offset: "0",
  });
  const query = useDebounce(filters.q),
    offset = Number(filters.offset) || 0;
  const params = new URLSearchParams({ ...filters, q: query, limit: "50" });
  Object.entries(filters).forEach(([k, v]) => {
    if (!v) params.delete(k);
  });
  const resource = useResource<ListResult<Job>>(`/jobs?${params}`, blankJobs);
  const [selection, setSelection] = useState<Record<string, number>>({}),
    [forget, setForget] = useState(false);
  const { mutate, pending, notify } = useWorkspace();
  const selected = Object.keys(selection),
    change = (key: string, value: string) =>
      setFilters({ [key]: value, offset: "0" });
  const facets = resource.data.facets || {};
  async function bulk(action: string) {
    let result:
      | {
          succeeded?: number;
          failed?: number;
          items?: { error?: { message: string } }[];
        }
      | undefined;
    if (
      await mutate(async () => {
        result = await api("/jobs/bulk", "POST", {
          action,
          items: selected.map((id) => ({
            id,
            expected_version: selection[id],
          })),
        });
      }, "Selected opportunities updated.")
    ) {
      setSelection({});
      setForget(false);
      if (result?.failed)
        notify(
          `${result.succeeded || 0} completed; ${result.failed} failed. ${result.items?.find((item) => item.error)?.error?.message || "Refresh and retry."}`,
          true,
        );
    }
  }
  return (
    <>
      <Heading
        title="Your opportunities."
        description="A considered shortlist starts with a well-kept inbox."
      >
        <Button variant="primary" icon="plus" onClick={onAdd}>
          Add job
        </Button>
      </Heading>
      <Tabs
        label="Job triage"
        value={filters.triage}
        onChange={(value) => change("triage", value)}
        items={[
          { id: "inbox", label: "To review" },
          { id: "active", label: "All active" },
          { id: "saved", label: "Saved" },
          { id: "dismissed", label: "Dismissed" },
        ]}
      />
      <div className="toolbar">
        <div className="search">
          <Icon name="search" />
          <input
            aria-label="Search jobs"
            placeholder="Search jobs, companies or keywords"
            value={filters.q}
            onChange={(e) => change("q", e.target.value)}
          />
        </div>
        <select
          aria-label="Sort jobs"
          value={filters.sort}
          onChange={(e) => change("sort", e.target.value)}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="title">Role A–Z</option>
          <option value="score">Highest fit</option>
          <option value="company">Company A–Z</option>
        </select>
      </div>
      <details
        className="filter-panel"
        open={Object.entries(filters).some(
          ([k, v]) =>
            !["triage", "q", "sort", "offset", "score_state"].includes(k) &&
            !!v,
        )}
      >
        <summary>
          Filter opportunities{" "}
          <span className="muted">
            Location, source, work style, score & dates
          </span>
        </summary>
        <div className="filter-grid">
          {[
            ["company", "Company", "companies"],
            ["location", "Location", "locations"],
            ["source", "Source", "sources"],
            ["job_type", "Job type", "job_types"],
          ].map(([key, label, facet]) => (
            <Field label={label} key={key}>
              <input
                aria-label={label}
                list={`facet-${key}`}
                placeholder={`Any ${label.toLowerCase()}`}
                value={filters[key]}
                onChange={(e) => change(key, e.target.value)}
              />
              <datalist id={`facet-${key}`}>
                {(facets[facet] || []).map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
            </Field>
          ))}
          <Field label="Work style">
            <select
              value={filters.remote}
              onChange={(e) => change("remote", e.target.value)}
            >
              <option value="">Any work style</option>
              <option value="true">Remote</option>
              <option value="false">On site / hybrid</option>
            </select>
          </Field>
          <Field label="Posting completeness">
            <select
              value={filters.complete}
              onChange={(e) => change("complete", e.target.value)}
            >
              <option value="">All postings</option>
              <option value="true">Full posting saved</option>
              <option value="false">Needs posting text</option>
            </select>
          </Field>
          <Field label="Score freshness">
            <select
              value={filters.score_state}
              onChange={(e) => change("score_state", e.target.value)}
            >
              {["all", "current", "outdated", "unscored"].map((v) => (
                <option key={v} value={v}>
                  {v[0].toUpperCase() + v.slice(1)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Minimum fit score">
            <input
              type="number"
              min={0}
              max={100}
              value={filters.score_min}
              onChange={(e) => change("score_min", e.target.value)}
            />
          </Field>
          <Field label="Maximum fit score">
            <input
              type="number"
              min={0}
              max={100}
              value={filters.score_max}
              onChange={(e) => change("score_max", e.target.value)}
            />
          </Field>
          <Field label="Saved from">
            <input
              type="date"
              value={filters.created_since}
              onChange={(e) => change("created_since", e.target.value)}
            />
          </Field>
          <Field label="Saved through">
            <input
              type="date"
              value={filters.created_until}
              onChange={(e) => change("created_until", e.target.value)}
            />
          </Field>
          <Button
            className="small"
            onClick={() =>
              setFilters(
                Object.fromEntries(
                  Object.keys(filters)
                    .filter((k) => k !== "triage")
                    .map((k) => [
                      k,
                      k === "score_state"
                        ? "all"
                        : k === "sort"
                          ? "newest"
                          : k === "offset"
                            ? "0"
                            : "",
                    ]),
                ),
              )
            }
          >
            Clear filters
          </Button>
        </div>
      </details>
      {selected.length > 0 && (
        <div className="bulkbar" aria-label="Selected opportunities">
          <strong>{selected.length} selected</strong>
          <Button disabled={pending} onClick={() => bulk("saved")}>
            Save
          </Button>
          <Button disabled={pending} onClick={() => bulk("dismissed")}>
            Dismiss
          </Button>
          <Button disabled={pending} onClick={() => bulk("inbox")}>
            Restore
          </Button>
          <Button
            disabled={pending}
            icon="refresh"
            onClick={() => bulk("rescore")}
          >
            Rescore
          </Button>
          <Button variant="danger" onClick={() => setForget(true)}>
            Forget
          </Button>
          <button className="textbutton" onClick={() => setSelection({})}>
            Clear
          </button>
        </div>
      )}
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <section className="card joblist" aria-label="Opportunities">
        {!!resource.data.items.length && (
          <div className="selection-head">
            <label className="checkline">
              <input
                type="checkbox"
                aria-label="Select this page"
                checked={resource.data.items.every(
                  (j) => selection[j.id] !== undefined,
                )}
                onChange={(e) =>
                  setSelection((current) => {
                    const next = { ...current };
                    resource.data.items.forEach((j) => {
                      if (e.target.checked && Object.keys(next).length < 200)
                        next[j.id] = j.version;
                      else delete next[j.id];
                    });
                    return next;
                  })
                }
              />
              Select this page
            </label>
            <span className="muted smalltext">
              Up to 200 selected opportunities per action
            </span>
          </div>
        )}
        {resource.loading && !resource.data.items.length ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((job) => (
            <div className="jobrow" key={job.id}>
              <input
                className="row-select"
                type="checkbox"
                aria-label={`Select ${job.title}`}
                checked={selection[job.id] !== undefined}
                disabled={
                  selection[job.id] === undefined && selected.length >= 200
                }
                onChange={(e) =>
                  setSelection((current) => {
                    const next = { ...current };
                    if (e.target.checked) next[job.id] = job.version;
                    else delete next[job.id];
                    return next;
                  })
                }
              />
              <button className="jobmain" onClick={() => onOpen(job.id)}>
                <div>
                  <strong className="jobtitle">
                    {job.title || "Untitled opportunity"}
                  </strong>
                  <div className="jobmeta">
                    {job.company || "Unknown company"}
                    <span>·</span>
                    {job.source ||
                      String(
                        job.metadata.source ||
                          job.metadata.ats ||
                          "Saved posting",
                      )}
                    {job.job_type && (
                      <>
                        <span>·</span>
                        <span>
                          {job.job_type === "fulltime"
                            ? "Full time"
                            : job.job_type === "parttime"
                              ? "Part time"
                              : job.job_type}
                        </span>
                      </>
                    )}
                    <span className="mobile-job-location">
                      {job.location || "Location not specified"}
                    </span>
                    {job.complete === false && (
                      <span className="tag amber">Needs text</span>
                    )}
                  </div>
                </div>
              </button>
              <span className="location-col">
                {job.location || "Location not specified"}
                {job.is_remote &&
                  !job.location?.toLowerCase().includes("remote") && (
                    <small>Remote</small>
                  )}
                <time>{date(job.date_posted || job.created_at)}</time>
              </span>
              <Score score={job.score} outdated={job.score_outdated} />
              <button
                className="iconbtn"
                aria-label={`Open ${job.title}`}
                onClick={() => onOpen(job.id)}
              >
                <Icon name="arrow" />
              </button>
            </div>
          ))
        ) : (
          <Empty
            title="No opportunities in this view."
            action={
              <Button onClick={onAdd} icon="plus">
                Add a job
              </Button>
            }
          >
            Adjust your filters, add a posting, or save a search in Collection.
          </Empty>
        )}
      </section>
      <Pagination
        offset={offset}
        total={resource.data.total}
        limit={50}
        onChange={(value) => setFilters({ offset: String(value) })}
      />
      <p className="hint">
        Fit scores are indicative. Changes are checked against each selected
        record’s version.
      </p>
      {forget && (
        <Dialog
          title={`Forget ${selected.length} opportunities?`}
          onClose={() => setForget(false)}
        >
          <p className="modal-intro">
            Permanently remove selected jobs and their applications, notes and
            documents. They can appear as new jobs if collected again.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setForget(false)}>Keep jobs</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={() => bulk("forget")}
            >
              Forget selected jobs
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}

export function JobDrawer({
  id,
  onClose,
  onApplication,
}: {
  id: string;
  onClose: () => void;
  onApplication: (id: string) => void;
}) {
  const resource = useResource<Job | null>(`/jobs/${id}`, null),
    notes = useResource<ListResult<Note>>(`/jobs/${id}/notes`, {
      items: [],
      total: 0,
    });
  const { mutate, pending, notify } = useWorkspace();
  const [tab, setTab] = useUrlState("detail", "posting");
  const [editingNote, setEditingNote] = useState<Note | null>(null);
  const [scoringContext, setScoringContext] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [forget, setForget] = useState(false),
    [merging, setMerging] = useState(false);
  const job = resource.data;
  const applications = useResource<ListResult<Application>>(
    job && tab === "notes"
      ? `/applications?company=${encodeURIComponent(job.company)}&limit=200`
      : null,
    { items: [], total: 0 },
  );
  async function triage(value: Triage) {
    if (!confirmLeave()) return;
    if (job)
      await mutate(
        () =>
          api(`/jobs/${id}/triage`, "POST", version(job, { triage: value })),
        value === "dismissed" ? "Dismissed. History is kept." : "Job updated.",
      );
  }
  async function createApplication() {
    let app: Application | undefined;
    const ok = await mutate(async () => {
      app = await api<Application>("/applications", "POST", { job_id: id });
    }, "Application draft created.");
    if (ok && app) onApplication(app.id);
  }
  async function edit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!job) return;
    const form = new FormData(e.currentTarget);
    await mutate(
      () =>
        api(
          `/jobs/${id}`,
          "PATCH",
          version(job, {
            ...Object.fromEntries(form),
            metadata: jsonValue(form, "metadata"),
          }),
        ),
      "Job details saved.",
    );
  }
  async function addNote(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      values = new FormData(form),
      body = values.get("body"),
      application_id = values.get("application_id") || undefined;
    if (
      await mutate(
        () => api(`/jobs/${id}/notes`, "POST", { body, application_id }),
        "Note saved.",
      )
    )
      form.reset();
  }
  return (
    <>
      <Dialog
        drawer
        title={job?.title || "Opportunity"}
        onClose={onClose}
        footer={
          job && (
            <>
              <Button
                icon="trash"
                variant="subtle small danger"
                onClick={() => setForget(true)}
              >
                Forget
              </Button>
              <div className="actions">
                {job.triage === "dismissed" ? (
                  <Button onClick={() => triage("inbox")} disabled={pending}>
                    Restore to inbox
                  </Button>
                ) : (
                  <>
                    <Button
                      onClick={() => triage("dismissed")}
                      disabled={pending}
                    >
                      Dismiss
                    </Button>
                    <Button
                      icon="bookmark"
                      onClick={() => triage("saved")}
                      disabled={pending}
                    >
                      {job.triage === "saved" ? "Saved" : "Save job"}
                    </Button>
                    <Button
                      variant="primary"
                      onClick={createApplication}
                      disabled={pending}
                    >
                      Create application
                    </Button>
                  </>
                )}
              </div>
            </>
          )
        }
      >
        {resource.error ? (
          <ErrorBox message={resource.error} retry={resource.reload} />
        ) : !job ? (
          <Loading />
        ) : (
          <>
            <div className="jobmeta drawer-meta">
              <span>
                {job.company} · {job.location || "Location not specified"}
              </span>
            </div>
            <Tabs
              label="Opportunity details"
              items={[
                { id: "posting", label: "Posting" },
                { id: "notes", label: "Notes", count: notes.data.total },
                { id: "files", label: "Files" },
                { id: "edit", label: "Edit details" },
              ]}
              value={tab}
              onChange={setTab}
            />
            {tab === "posting" ? (
              <>
                <dl className="detailfacts">
                  <div>
                    <dt>Fit assessment</dt>
                    <dd>
                      <Score score={job.score} outdated={job.score_outdated} />
                    </dd>
                  </div>
                  <div>
                    <dt>Availability</dt>
                    <dd>{job.availability || "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Compensation</dt>
                    <dd>
                      {job.salary ||
                        String(job.metadata.salary || "Not specified")}
                    </dd>
                  </div>
                  <div>
                    <dt>Saved in workspace</dt>
                    <dd>{date(job.created_at)}</dd>
                  </div>
                </dl>
                {job.url && (
                  <a
                    className="btn small external-link"
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Icon name="external" />
                    Original posting
                  </a>
                )}
                <div className="actions form-actions">
                  <Button
                    icon="refresh"
                    disabled={pending || !job.posting}
                    onClick={() =>
                      mutate(
                        () =>
                          api("/scoring/rescore", "POST", {
                            job_ids: [id],
                            outdated_only: false,
                            limit: 1,
                          }),
                        "Fit assessment queued. Check Settings activity for progress.",
                      )
                    }
                  >
                    Update fit score
                  </Button>
                  <Button
                    onClick={() =>
                      api<Record<string, unknown>>(`/scoring/context/${id}`)
                        .then(setScoringContext)
                        .catch((e) => notify(e.message, true))
                    }
                  >
                    Inspect scoring context
                  </Button>
                  <Button onClick={() => setMerging(true)}>
                    Merge duplicate
                  </Button>
                </div>
                {!!job.postings?.length && (
                  <details className="provenance">
                    <summary>
                      Source provenance · {job.postings.length} postings
                    </summary>
                    {job.postings.map((p, i) => (
                      <article key={i}>
                        <strong>
                          {String(
                            p.source_name ||
                              p.source_id ||
                              p.provider ||
                              "Saved posting",
                          )}
                        </strong>
                        <p>{String(p.url || p.source_url || "")}</p>
                        <small>
                          {String(p.created_at || p.last_seen_at || "")}
                        </small>
                      </article>
                    ))}
                  </details>
                )}
                {job.posting ? (
                  <div className="posting">{job.posting}</div>
                ) : (
                  <div className="note">
                    <Icon name="info" />
                    <span>
                      The full posting is missing. Paste it under Edit details
                      to complete this record.
                    </span>
                  </div>
                )}
              </>
            ) : tab === "notes" ? (
              <>
                <div className="notes-list">
                  {notes.data.items.map((note) => (
                    <article className="note-entry" key={note.id}>
                      <p>{note.body || note.text}</p>
                      <div className="section-footer">
                        <time>{date(note.created_at)}</time>
                        <button
                          className="iconbtn"
                          aria-label="Edit note"
                          onClick={() =>
                            api<Note>(`/notes/${note.id}`)
                              .then(setEditingNote)
                              .catch((e) => notify(e.message, true))
                          }
                        >
                          <Icon name="edit" />
                        </button>
                        <button
                          className="iconbtn danger"
                          aria-label="Delete note"
                          disabled={pending}
                          onClick={() =>
                            mutate(
                              () => api(`/notes/${note.id}`, "DELETE"),
                              "Note removed.",
                            )
                          }
                        >
                          <Icon name="trash" />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
                <form onSubmit={addNote}>
                  <Field label="Your private note">
                    <textarea
                      name="body"
                      rows={5}
                      required
                      placeholder="What stands out? Questions to ask?"
                    />
                  </Field>
                  {applications.data.items.some((app) => app.job_id === id) && (
                    <Field label="Link to an application (optional)">
                      <select name="application_id">
                        <option value="">Job note</option>
                        {applications.data.items
                          .filter((app) => app.job_id === id)
                          .map((app) => (
                            <option key={app.id} value={app.id}>
                              {app.status} · {date(app.created_at)} ·{" "}
                              {app.id.slice(0, 8)}
                            </option>
                          ))}
                      </select>
                    </Field>
                  )}
                  <Button
                    variant="primary"
                    className="form-actions"
                    disabled={pending}
                  >
                    Add note
                  </Button>
                </form>
              </>
            ) : tab === "files" ? (
              <FileManager ownerType="job" ownerId={id} preview />
            ) : (
              <form onSubmit={edit} key={job.id}>
                <div className="stack">
                  <Field label="Role">
                    <input name="title" defaultValue={job.title} required />
                  </Field>
                  <Field label="Company">
                    <input name="company" defaultValue={job.company} />
                  </Field>
                  <Field label="Location">
                    <input name="location" defaultValue={job.location} />
                  </Field>
                  <Field label="Job URL">
                    <input name="url" type="url" defaultValue={job.url} />
                  </Field>
                  <Field label="Availability">
                    <select
                      name="availability"
                      defaultValue={job.availability || "unknown"}
                    >
                      <option value="unknown">Unknown</option>
                      <option value="open">Open</option>
                      <option value="closed">Closed</option>
                    </select>
                  </Field>
                  <AdvancedJson name="metadata" value={job.metadata} />
                  <Field label="Posting text">
                    <textarea
                      name="posting"
                      rows={13}
                      defaultValue={job.posting}
                    />
                  </Field>
                  <Button variant="primary" disabled={pending}>
                    Save details
                  </Button>
                </div>
              </form>
            )}
          </>
        )}
      </Dialog>
      {scoringContext && (
        <Dialog
          title="Scoring context."
          onClose={() => setScoringContext(null)}
        >
          <p className="modal-intro">
            The compact profile, job text and score levels used by the optional
            scorer.
          </p>
          <pre className="json-readout">
            {JSON.stringify(scoringContext, null, 2)}
          </pre>
        </Dialog>
      )}
      {editingNote && (
        <Dialog title="Edit your note." onClose={() => setEditingNote(null)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await mutate(
                  () =>
                    api(`/notes/${editingNote.id}`, "PATCH", {
                      body: new FormData(e.currentTarget).get("body"),
                      expected_version: editingNote.version,
                    }),
                  "Note updated.",
                )
              )
                setEditingNote(null);
            }}
          >
            <Field label="Note">
              <textarea
                name="body"
                required
                rows={6}
                defaultValue={editingNote.body}
              />
            </Field>
            <Button variant="primary" disabled={pending}>
              Save note
            </Button>
          </form>
        </Dialog>
      )}
      {merging && job && (
        <MergeJob
          job={job}
          onClose={() => setMerging(false)}
          onMerged={onClose}
        />
      )}
      {forget && (
        <Dialog title="Forget this job?" onClose={() => setForget(false)}>
          <p className="modal-intro">
            Permanently remove this opportunity, its applications, notes and
            documents. If collected again, it can appear as a new job.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setForget(false)}>Keep job</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () => api(`/jobs/${id}`, "DELETE"),
                    "Job and related records removed.",
                  )
                ) {
                  setForget(false);
                  onClose();
                }
              }}
            >
              Forget job
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function MergeJob({
  job,
  onClose,
  onMerged,
}: {
  job: Job;
  onClose: () => void;
  onMerged: () => void;
}) {
  const [query, setQuery] = useState(job.title),
    [selected, setSelected] = useState("");
  const candidates = useResource<ListResult<Job>>(
    `/jobs?limit=100&q=${encodeURIComponent(query)}`,
    blankJobs,
  );
  const { mutate, pending } = useWorkspace();
  const target = candidates.data.items.find((item) => item.id === selected);
  return (
    <Dialog title="Merge a verified duplicate." onClose={onClose}>
      <p className="modal-intro">
        Move this job's postings, notes and application history into the record
        you choose. The selected job remains in your workspace.
      </p>
      <Field label="Find the job to keep">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected("");
          }}
        />
      </Field>
      {candidates.error && (
        <ErrorBox message={candidates.error} retry={candidates.reload} />
      )}
      <Field label="Keep this job">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Choose a matching record</option>
          {candidates.data.items
            .filter((item) => item.id !== job.id)
            .map((item) => (
              <option value={item.id} key={item.id}>
                {item.company} · {item.title} · {date(item.created_at)}
              </option>
            ))}
        </select>
      </Field>
      <p className="hint">
        Only merge records you have checked. This removes the duplicate record.
      </p>
      <div className="actions form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="primary"
          disabled={pending || !target}
          onClick={async () => {
            if (
              target &&
              (await mutate(
                () =>
                  api(`/jobs/${job.id}/merge`, "POST", {
                    target_id: target.id,
                    expected_version: job.version,
                    target_version: target.version,
                  }),
                "Duplicate merged. History is kept in the selected job.",
              ))
            ) {
              onClose();
              onMerged();
            }
          }}
        >
          Merge into selected job
        </Button>
      </div>
    </Dialog>
  );
}
