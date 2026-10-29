import { useState, type FormEvent } from "react";
import {
  api,
  date,
  version,
  type Application,
  type Job,
  type ListResult,
  type Note,
  type Triage,
} from "../api";
import { useResource, useWorkspace } from "../state";
import { FileManager } from "../files";
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
      created = await api<Job>("/jobs", "POST", Object.fromEntries(f));
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
  const [triage, setTriage] = useState<Triage>("inbox"),
    [query, setQuery] = useState(""),
    [company, setCompany] = useState(""),
    [sort, setSort] = useState("newest"),
    [offset, setOffset] = useState(0);
  const params = new URLSearchParams({
    triage,
    q: query,
    company,
    sort,
    limit: "50",
    offset: String(offset),
  });
  const resource = useResource<ListResult<Job>>(`/jobs?${params}`, blankJobs);
  const change = (fn: () => void) => {
    fn();
    setOffset(0);
  };
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
        value={triage}
        onChange={(id) => change(() => setTriage(id as Triage))}
        items={[
          { id: "inbox", label: "To review" },
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
            value={query}
            onChange={(e) => change(() => setQuery(e.target.value))}
          />
        </div>
        <input
          className="company-filter"
          aria-label="Filter by company"
          placeholder="Company"
          value={company}
          onChange={(e) => change(() => setCompany(e.target.value))}
        />
        <select
          aria-label="Sort jobs"
          value={sort}
          onChange={(e) => change(() => setSort(e.target.value))}
        >
          <option value="newest">Newest first</option>
          <option value="score">Highest fit</option>
          <option value="company">Company A–Z</option>
        </select>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <section className="card joblist" aria-label="Opportunities">
        {resource.loading && resource.data.items.length === 0 ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((job) => (
            <div className="jobrow" key={job.id}>
              <button className="jobmain" onClick={() => onOpen(job.id)}>
                <Avatar name={job.company} />
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
                    {!job.posting && (
                      <span className="tag amber">Needs text</span>
                    )}
                  </div>
                </div>
              </button>
              <span className="location-col">
                {job.location || "Location not specified"}
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
            title={
              query || company
                ? "No matching opportunities."
                : triage === "dismissed"
                  ? "Nothing set aside."
                  : "Room for your next opportunity."
            }
            action={
              triage === "inbox" && !query && !company ? (
                <Button icon="plus" onClick={onAdd}>
                  Add a job
                </Button>
              ) : undefined
            }
          >
            {query || company
              ? "Try a different search or company."
              : triage === "dismissed"
                ? "Dismissed jobs keep their history and can be restored here."
                : "Add an offer you found, or follow companies to collect their open roles."}
          </Empty>
        )}
      </section>
      <div className="list-footer">
        <span>
          {resource.data.total}{" "}
          {resource.data.total === 1 ? "opportunity" : "opportunities"}
        </span>
        <div className="actions">
          {offset > 0 && (
            <Button
              className="small"
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous
            </Button>
          )}
          {offset + 50 < resource.data.total && (
            <Button className="small" onClick={() => setOffset(offset + 50)}>
              Next
            </Button>
          )}
          <span>Scores are indicative</span>
        </div>
      </div>
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
  const { mutate, pending } = useWorkspace();
  const [tab, setTab] = useState("posting"),
    [forget, setForget] = useState(false),
    [merging, setMerging] = useState(false);
  const job = resource.data;
  async function triage(value: Triage) {
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
      () => api(`/jobs/${id}`, "PATCH", version(job, Object.fromEntries(form))),
      "Job details saved.",
    );
  }
  async function addNote(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      body = new FormData(form).get("body");
    if (
      await mutate(
        () => api(`/jobs/${id}/notes`, "POST", { body }),
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
              <Avatar name={job.company} />
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
                  <Button onClick={() => setMerging(true)}>
                    Merge duplicate
                  </Button>
                </div>
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
              <form onSubmit={edit} key={job.version}>
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
