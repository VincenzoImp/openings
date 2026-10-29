import { useState, type FormEvent } from "react";
import {
  api,
  date,
  version,
  type Claim,
  type Knowledge,
  type ListResult,
  type Profile,
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
const blankProfile: Profile = {
  name: "",
  headline: "",
  location: "",
  email: "",
  phone: "",
  roles: "",
  preferences: "",
  summary: "",
  scoring_summary: "",
  links: [],
  metadata: {},
  version: 1,
};
export default function CareerPage() {
  const [tab, setTab] = useState("profile");
  return (
    <>
      <Heading
        title="Your experience, in full."
        description="A useful record of what you have done, what you know and what you want next."
      />
      <Tabs
        label="Career sections"
        value={tab}
        onChange={setTab}
        items={[
          { id: "profile", label: "Profile & preferences" },
          { id: "knowledge", label: "Career knowledge" },
          { id: "claims", label: "Reusable claims" },
        ]}
      />
      {tab === "profile" ? (
        <ProfileForm />
      ) : tab === "knowledge" ? (
        <KnowledgePage />
      ) : (
        <ClaimsPage />
      )}
    </>
  );
}
function ProfileForm() {
  const { data, loading, error, reload } = useResource<Profile>(
    "/career/profile",
    blankProfile,
  );
  const { mutate, pending } = useWorkspace();
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const fields = [
      "name",
      "headline",
      "location",
      "email",
      "phone",
      "roles",
      "preferences",
      "summary",
      "scoring_summary",
    ];
    const body: Record<string, unknown> = Object.fromEntries(
      fields.map((k) => [k, String(f.get(k) || "")]),
    );
    body.links = String(f.get("links") || "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
      .map(
        (url) =>
          data.links.find(
            (item) =>
              typeof item === "object" &&
              item !== null &&
              (item as { url?: string }).url === url,
          ) || { label: "Website", url },
      );
    await mutate(
      () => api("/career/profile", "PATCH", version(data, body)),
      "Profile saved. Relevant changes mark scores outdated without running inference.",
    );
  }
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} retry={reload} />;
  return (
    <form className="reading-width" onSubmit={save} key={data.version}>
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>The essentials.</h2>
            <p>
              Contact details and the professional story your agent can work
              from.
            </p>
          </div>
        </div>
        <div className="formgrid">
          <Field label="Full name">
            <input name="name" defaultValue={data.name} autoComplete="name" />
          </Field>
          <Field label="Professional headline">
            <input name="headline" defaultValue={data.headline} />
          </Field>
          <Field label="Location">
            <input name="location" defaultValue={data.location} />
          </Field>
          <Field label="Email">
            <input
              name="email"
              type="email"
              defaultValue={data.email}
              autoComplete="email"
            />
          </Field>
          <Field label="Phone">
            <input name="phone" defaultValue={data.phone} autoComplete="tel" />
          </Field>
          <Field label="Target roles">
            <input
              name="roles"
              defaultValue={data.roles}
              placeholder="Backend engineer, platform engineer"
            />
          </Field>
          <Field label="Links" className="full" hint="One full URL per line.">
            <textarea
              name="links"
              rows={3}
              defaultValue={data.links
                .map((item) =>
                  typeof item === "string"
                    ? item
                    : String((item as Record<string, unknown>).url || ""),
                )
                .filter(Boolean)
                .join("\n")}
            />
          </Field>
          <Field label="Professional summary" className="full">
            <textarea name="summary" rows={5} defaultValue={data.summary} />
          </Field>
        </div>
      </section>
      <section className="card sectioncard form-section">
        <div className="sectiontitle">
          <div>
            <h2>What you are looking for.</h2>
            <p>
              Preferences guide your search without replacing the full career
              record.
            </p>
          </div>
        </div>
        <Field label="Preferences">
          <textarea
            name="preferences"
            rows={5}
            defaultValue={data.preferences}
            placeholder="Locations, remote preferences, team interests, compensation…"
          />
        </Field>
        <Field
          label="Compact scoring profile"
          hint="A concise, factual overview for the optional scorer. Your external document agent can still read the detailed knowledge below."
        >
          <textarea
            name="scoring_summary"
            rows={5}
            defaultValue={data.scoring_summary}
          />
        </Field>
        <div className="section-footer">
          <span>Contact-only edits do not invalidate fit scores.</span>
          <Button variant="primary" disabled={pending}>
            Save profile
          </Button>
        </div>
      </section>
    </form>
  );
}
function KnowledgePage() {
  const resource = useResource<ListResult<Knowledge>>("/career/knowledge", {
    items: [],
    total: 0,
  });
  const { mutate, pending } = useWorkspace();
  const [editing, setEditing] = useState<Knowledge | "new" | null>(null),
    [importing, setImporting] = useState(false),
    [removing, setRemoving] = useState<Knowledge | null>(null);
  return (
    <>
      <div className="sectiontitle">
        <div>
          <h2>The detailed story.</h2>
          <p>
            Experiences, projects, courses and facts, with room for the context
            behind each claim.
          </p>
        </div>
        <div className="actions">
          <Button icon="upload" onClick={() => setImporting(true)}>
            Import
          </Button>
          <Button
            variant="primary"
            icon="plus"
            onClick={() => setEditing("new")}
          >
            Add knowledge
          </Button>
        </div>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="knowledge-grid">
        {resource.loading ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((item) => (
            <article className="card knowledge-card" key={item.id}>
              <div className="knowledge-head">
                <div>
                  <span className="eyebrow">{item.kind}</span>
                  <h3>{item.title}</h3>
                  <small className="muted">
                    {String(item.metadata.dates || date(item.updated_at))}
                  </small>
                </div>
                <div className="actions">
                  <button
                    className="iconbtn"
                    aria-label={`Edit ${item.title}`}
                    onClick={() => setEditing(item)}
                  >
                    <Icon name="edit" />
                  </button>
                  <button
                    className="iconbtn danger"
                    aria-label={`Delete ${item.title}`}
                    onClick={() => setRemoving(item)}
                  >
                    <Icon name="trash" />
                  </button>
                </div>
              </div>
              <p className="narrative">{item.narrative}</p>
              <details className="evidence-files">
                <summary>Supporting files</summary>
                <FileManager ownerType="knowledge" ownerId={item.id} />
              </details>
            </article>
          ))
        ) : (
          <section className="card">
            <Empty
              title="Your experience deserves more than a bullet."
              action={
                <Button icon="plus" onClick={() => setEditing("new")}>
                  Add your first experience
                </Button>
              }
            >
              Record projects, responsibilities, decisions and outcomes. Your
              agent can turn this context into relevant application wording.
            </Empty>
          </section>
        )}
      </div>
      {editing && (
        <KnowledgeEditor
          record={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}{" "}
      {importing && <KnowledgeImport onClose={() => setImporting(false)} />}{" "}
      {removing && (
        <Dialog
          title="Remove this knowledge entry?"
          onClose={() => setRemoving(null)}
        >
          <p className="modal-intro">
            Remove {removing.title} from your current career record. Existing
            application snapshots retain the evidence they used.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(null)}>Keep entry</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () => api(`/career/knowledge/${removing.id}`, "DELETE"),
                    "Knowledge entry removed.",
                  )
                )
                  setRemoving(null);
              }}
            >
              Remove entry
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function KnowledgeEditor({
  record,
  onClose,
}: {
  record?: Knowledge;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      kind: f.get("kind"),
      title: f.get("title"),
      narrative: f.get("narrative"),
      metadata: {
        ...record?.metadata,
        dates: f.get("dates"),
        skills: String(f.get("skills") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
      },
    };
    if (
      await mutate(
        () =>
          api(
            record ? `/career/knowledge/${record.id}` : "/career/knowledge",
            record ? "PATCH" : "POST",
            record ? version(record, body) : body,
          ),
        "Career knowledge saved.",
      )
    )
      onClose();
  }
  return (
    <Dialog
      title={record ? "Edit career knowledge." : "Add career knowledge."}
      onClose={onClose}
    >
      <form onSubmit={save}>
        <div className="formgrid">
          <Field label="Type">
            <select name="kind" defaultValue={record?.kind || "experience"}>
              <option value="experience">Experience</option>
              <option value="project">Project</option>
              <option value="course">Course</option>
              <option value="fact">Fact</option>
            </select>
          </Field>
          <Field label="Dates">
            <input
              name="dates"
              defaultValue={String(record?.metadata.dates || "")}
              placeholder="2021 – present"
            />
          </Field>
        </div>
        <Field label="Title / organization">
          <input name="title" required defaultValue={record?.title} />
        </Field>
        <Field
          label="Detailed evidence"
          hint="Describe what you did, decisions, results and useful context. Keep claims factual."
        >
          <textarea
            name="narrative"
            rows={10}
            required
            defaultValue={record?.narrative}
          />
        </Field>
        <Field label="Skills" hint="Separate with commas.">
          <input
            name="skills"
            defaultValue={
              Array.isArray(record?.metadata.skills)
                ? record?.metadata.skills.join(", ")
                : ""
            }
          />
        </Field>
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Save knowledge
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
interface ImportPreview {
  knowledge: Partial<Knowledge>[];
  profile?: Record<string, unknown>;
  expected_profile_version?: number;
  warnings: string[];
}
function KnowledgeImport({ onClose }: { onClose: () => void }) {
  const { mutate, pending, notify } = useWorkspace();
  const [raw, setRaw] = useState(""),
    [preview, setPreview] = useState<ImportPreview | null>(null);
  async function inspect() {
    await mutate(
      async () =>
        setPreview(
          await api<ImportPreview>("/career/import/preview", "POST", {
            text: raw,
          }),
        ),
      "Import preview ready.",
    );
  }
  async function apply() {
    if (!preview) return;
    if (
      await mutate(
        () =>
          api("/career/import", "POST", {
            knowledge: preview.knowledge,
            profile: preview.profile,
            expected_profile_version: preview.expected_profile_version,
          }),
        "Career information imported.",
      )
    )
      onClose();
  }
  return (
    <Dialog title="Import career knowledge." onClose={onClose}>
      <p className="modal-intro">
        Preview text, Markdown or JSON before adding it. Profile fields are
        changed only after you confirm the preview.
      </p>
      {!preview ? (
        <>
          <Field label="Text or JSON">
            <textarea
              rows={12}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              placeholder='[{"kind":"project","title":"Example project","narrative":"What you built and learned…"}]'
            />
          </Field>
          <Field label="Or select a text / JSON file">
            <input
              type="file"
              accept=".txt,.md,.json"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  if (file.size > 2_000_000) {
                    notify("Use a text file below 2 MB.", true);
                    return;
                  }
                  setRaw(await file.text());
                }
              }}
            />
          </Field>
          <Button
            variant="primary"
            disabled={pending || !raw.trim()}
            onClick={inspect}
          >
            Preview import
          </Button>
        </>
      ) : (
        <>
          {preview.warnings?.map((warning, i) => (
            <div className="note" key={i}>
              <Icon name="info" />
              <span>{warning}</span>
            </div>
          ))}
          {preview.profile && (
            <section className="import-profile">
              <h3>Profile fields to update</h3>
              <dl>
                {Object.entries(preview.profile).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>
                      {typeof value === "string"
                        ? value
                        : JSON.stringify(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          <div className="import-preview">
            {preview.knowledge.map((entry, i) => (
              <article key={i}>
                <span className="tag neutral">{entry.kind}</span>
                <h3>{entry.title}</h3>
                <p>
                  {entry.narrative?.slice(0, 180)}
                  {(entry.narrative?.length || 0) > 180 ? "…" : ""}
                </p>
              </article>
            ))}
          </div>
          <div className="actions form-actions">
            <Button onClick={() => setPreview(null)}>Back</Button>
            <Button variant="primary" disabled={pending} onClick={apply}>
              Confirm import
            </Button>
          </div>
        </>
      )}
    </Dialog>
  );
}
function ClaimsPage() {
  const resource = useResource<ListResult<Claim>>("/career/claims", {
      items: [],
      total: 0,
    }),
    knowledge = useResource<ListResult<Knowledge>>("/career/knowledge", {
      items: [],
      total: 0,
    });
  const { mutate, pending } = useWorkspace();
  const [editing, setEditing] = useState<Claim | "new" | null>(null);
  return (
    <>
      <div className="sectiontitle">
        <div>
          <h2>Useful statements, grounded in evidence.</h2>
          <p>
            Approved claims are available for your agent to reuse. New wording
            can still come from detailed knowledge.
          </p>
        </div>
        <Button
          variant="primary"
          icon="plus"
          onClick={() => setEditing("new")}
          disabled={!knowledge.data.items.length}
        >
          Add claim
        </Button>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <section className="card">
        {resource.loading ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((claim) => (
            <article className="claimrow" key={claim.id}>
              <label className="claim-approval">
                <input
                  type="checkbox"
                  checked={claim.approved}
                  disabled={pending}
                  aria-label={`Approve claim: ${claim.text}`}
                  onChange={(e) =>
                    mutate(
                      () =>
                        api(
                          `/career/claims/${claim.id}`,
                          "PATCH",
                          version(claim, { approved: e.target.checked }),
                        ),
                      e.target.checked
                        ? "Claim approved."
                        : "Claim marked as draft.",
                    )
                  }
                />
              </label>
              <div className="claimcopy">
                <p>{claim.text}</p>
                <small>
                  {knowledge.data.items.find((k) => k.id === claim.knowledge_id)
                    ?.title || "Linked career evidence"}
                </small>
              </div>
              <span className={`tag ${claim.approved ? "green" : "neutral"}`}>
                {claim.approved ? "Approved" : "Draft"}
              </span>
              <button
                className="iconbtn"
                aria-label="Edit claim"
                onClick={() => setEditing(claim)}
              >
                <Icon name="edit" />
              </button>
              <button
                className="iconbtn danger"
                aria-label="Delete claim"
                disabled={pending}
                onClick={() =>
                  mutate(
                    () => api(`/career/claims/${claim.id}`, "DELETE"),
                    "Claim removed.",
                  )
                }
              >
                <Icon name="trash" />
              </button>
            </article>
          ))
        ) : (
          <Empty title="Build a useful set of claims.">
            Add detailed career knowledge first, then collect concise statements
            you may want to reuse.
          </Empty>
        )}
      </section>
      {editing && (
        <ClaimEditor
          record={editing === "new" ? undefined : editing}
          knowledge={knowledge.data.items}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}
function ClaimEditor({
  record,
  knowledge,
  onClose,
}: {
  record?: Claim;
  knowledge: Knowledge[];
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget),
      body = {
        knowledge_id: f.get("knowledge_id"),
        text: f.get("text"),
        approved: f.get("approved") === "on",
      };
    if (
      await mutate(
        () =>
          api(
            record ? `/career/claims/${record.id}` : "/career/claims",
            record ? "PATCH" : "POST",
            record ? version(record, body) : body,
          ),
        "Claim saved.",
      )
    )
      onClose();
  }
  return (
    <Dialog
      title={record ? "Edit a reusable claim." : "Add a reusable claim."}
      onClose={onClose}
    >
      <form onSubmit={save}>
        <Field label="Supporting knowledge">
          <select
            name="knowledge_id"
            required
            defaultValue={record?.knowledge_id}
          >
            {knowledge.map((k) => (
              <option key={k.id} value={k.id}>
                {k.title}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Claim">
          <textarea name="text" rows={6} required defaultValue={record?.text} />
        </Field>
        <label className="checkline">
          <input
            type="checkbox"
            name="approved"
            defaultChecked={record?.approved}
          />
          I have reviewed and approved this claim
        </label>
        <div className="actions form-actions">
          <Button variant="primary" disabled={pending}>
            Save claim
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
