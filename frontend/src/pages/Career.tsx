import { useState, type FormEvent } from "react";
import {
  api,
  careerDates,
  careerEntryLabel,
  jsonValue,
  knowledgeKinds,
  version,
  type CareerDates,
  type Claim,
  type KnowledgeKind,
  type Knowledge,
  type ListResult,
  type Profile,
} from "../api";
import { FileManager } from "../files";
import {
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
  const [tab, setTab] = useUrlState("section", "profile");
  return (
    <>
      <Heading
        title="Career"
        description="Store your profile, preferences, experience and reusable claims."
      />
      <Tabs
        label="Career sections"
        value={tab}
        onChange={setTab}
        items={[
          { id: "profile", label: "Profile & preferences" },
          { id: "knowledge", label: "Career entries" },
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
    body.links = jsonValue(f, "links", []);
    body.metadata = jsonValue(f, "metadata");
    await mutate(
      () => api("/career/profile", "PATCH", version(data, body)),
      "Profile saved. Relevant changes mark scores outdated without running inference.",
    );
  }
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} retry={reload} />;
  return (
    <form className="profile-layout" onSubmit={save} key={data.version}>
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>Profile and contact details</h2>
            <p>
              Contact information and a summary for your application documents.
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
          <div className="full">
            <ProfileLinks links={data.links} />
          </div>
          <div className="full">
            <AdvancedJson name="metadata" value={data.metadata} />
          </div>
          <Field label="Professional summary" className="full">
            <textarea name="summary" rows={5} defaultValue={data.summary} />
          </Field>
        </div>
      </section>
      <section className="card sectioncard form-section">
        <div className="sectiontitle">
          <div>
            <h2>Job preferences</h2>
            <p>
              These preferences guide optional fit scoring and application
              preparation.
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
          hint="A concise, factual overview for the optional scorer. Your external document agent can still read the career entries."
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
function ProfileLinks({ links }: { links: unknown[] }) {
  const [items, setItems] = useState<Record<string, unknown>[]>(
    links.map((item) =>
      typeof item === "string"
        ? { label: "Website", url: item }
        : (item as Record<string, unknown>),
    ),
  );
  return (
    <fieldset className="profile-links">
      <legend>Professional links</legend>
      <input
        type="hidden"
        name="links"
        value={JSON.stringify(items.filter((item) => item.url))}
      />
      {items.map((item, i) => (
        <div className="link-editor" key={i}>
          <input
            aria-label={`Link ${i + 1} label`}
            placeholder="LinkedIn, portfolio…"
            value={String(item.label || "")}
            onChange={(e) =>
              setItems((rows) =>
                rows.map((row, j) =>
                  j === i ? { ...row, label: e.target.value } : row,
                ),
              )
            }
          />
          <input
            aria-label={`Link ${i + 1} URL`}
            type="url"
            placeholder="https://…"
            value={String(item.url || "")}
            onChange={(e) =>
              setItems((rows) =>
                rows.map((row, j) =>
                  j === i ? { ...row, url: e.target.value } : row,
                ),
              )
            }
          />
          <button
            type="button"
            data-dirty-control="true"
            className="iconbtn danger"
            aria-label={`Remove link ${i + 1}`}
            onClick={() => setItems((rows) => rows.filter((_, j) => j !== i))}
          >
            <Icon name="close" />
          </button>
        </div>
      ))}
      <Button
        type="button"
        data-dirty-control="true"
        className="small"
        icon="plus"
        onClick={() => setItems((rows) => [...rows, { label: "", url: "" }])}
      >
        Add link
      </Button>
    </fieldset>
  );
}
function KnowledgePage() {
  const [filters, setFilters] = useUrlFilters({ q: "", kind: "", offset: "0" });
  const query = useDebounce(filters.q);
  const resource = useResource<ListResult<Knowledge>>(
    `/career/knowledge?summary=true&limit=30&offset=${filters.offset}&q=${encodeURIComponent(query)}&kind=${filters.kind}`,
    { items: [], total: 0 },
  );
  const { mutate, pending } = useWorkspace();
  const [creating, setCreating] = useState(false),
    [selected, setSelected] = useState<string | null>(null),
    [importing, setImporting] = useState(false),
    [removing, setRemoving] = useState<Knowledge | null>(null);
  return (
    <>
      <div className="sectiontitle">
        <div>
          <h2>Career entries</h2>
          <p>
            Organize your experience, education, projects and skills. Each entry
            can hold reusable claims.
          </p>
        </div>
        <div className="actions">
          <Button icon="upload" onClick={() => setImporting(true)}>
            Import
          </Button>
          <Button
            variant="primary"
            icon="plus"
            onClick={() => setCreating(true)}
          >
            Add entry
          </Button>
        </div>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="toolbar">
        <div className="search">
          <Icon name="search" />
          <input
            aria-label="Search career entries"
            placeholder="Search titles, organizations or descriptions"
            value={filters.q}
            onChange={(e) => setFilters({ q: e.target.value, offset: "0" })}
          />
        </div>
        <select
          aria-label="Entry type"
          value={filters.kind}
          onChange={(e) => setFilters({ kind: e.target.value, offset: "0" })}
        >
          <option value="">All types</option>
          {Object.entries(knowledgeKinds).map(([kind, label]) => (
            <option key={kind} value={kind}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="career-entry-list">
        {resource.loading ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((item) => (
            <article className="card career-entry-card" key={item.id}>
              <div className="career-entry-copy">
                <span className="eyebrow">{knowledgeKinds[item.kind]}</span>
                <h3>
                  <button
                    type="button"
                    className="career-entry-title"
                    aria-label={`Open ${careerEntryLabel(item)}`}
                    onClick={() => setSelected(item.id)}
                  >
                    {item.title}
                  </button>
                </h3>
                {item.organization && (
                  <p className="career-entry-organization">
                    {item.organization}
                  </p>
                )}
                {(item.narrative_preview?.trim() ||
                  item.claim_preview?.trim()) && (
                  <p className="career-entry-preview">
                    {!item.narrative_preview?.trim() && (
                      <span className="career-preview-label">Claim · </span>
                    )}
                    {item.narrative_preview?.trim() ||
                      item.claim_preview?.trim()}
                  </p>
                )}
              </div>
              <div className="career-entry-meta">
                {item.dates && (
                  <span className="career-entry-dates">
                    {careerDates(item.dates)}
                  </span>
                )}
                <small>
                  {item.claim_count ?? 0}{" "}
                  {(item.claim_count ?? 0) === 1 ? "claim" : "claims"}
                  {item.file_count
                    ? ` · ${item.file_count} ${item.file_count === 1 ? "file" : "files"}`
                    : ""}
                </small>
              </div>
              <div className="actions career-entry-actions">
                <button
                  type="button"
                  className="iconbtn"
                  aria-label={`Open details for ${careerEntryLabel(item)}`}
                  onClick={() => setSelected(item.id)}
                >
                  <Icon name="arrow" />
                </button>
                <button
                  type="button"
                  className="iconbtn danger"
                  aria-label={`Delete ${careerEntryLabel(item)}`}
                  onClick={() => setRemoving(item)}
                >
                  <Icon name="trash" />
                </button>
              </div>
            </article>
          ))
        ) : (
          <section className="card">
            <Empty
              title="No career entries in this view"
              action={
                <Button icon="plus" onClick={() => setCreating(true)}>
                  Add your first entry
                </Button>
              }
            >
              Add a title and any facts you know. Descriptions and claims can be
              added later.
            </Empty>
          </section>
        )}
      </div>
      <Pagination
        offset={Number(filters.offset) || 0}
        total={resource.data.total}
        onChange={(offset) => setFilters({ offset: String(offset) })}
      />
      {creating && (
        <KnowledgeEditor
          onClose={() => setCreating(false)}
          onSaved={(entry) => {
            setCreating(false);
            setSelected(entry.id);
          }}
        />
      )}
      {selected && (
        <KnowledgeDetail id={selected} onClose={() => setSelected(null)} />
      )}
      {importing && <KnowledgeImport onClose={() => setImporting(false)} />}
      {removing && (
        <Dialog
          title="Remove this career entry?"
          onClose={() => setRemoving(null)}
        >
          <p className="modal-intro">
            Remove {careerEntryLabel(removing)} and its claims from your current
            career record. Existing application snapshots retain the content
            they used.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(null)}>Keep entry</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () =>
                      api(
                        `/career/knowledge/${removing.id}?expected_version=${removing.version}`,
                        "DELETE",
                      ),
                    "Career entry removed.",
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
function KnowledgeDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const resource = useResource<Knowledge | null>(
    `/career/knowledge/${id}`,
    null,
  );
  const [editing, setEditing] = useState(false);
  const entry = resource.data;
  return (
    <Dialog drawer title={entry?.title || "Career entry"} onClose={onClose}>
      {resource.error ? (
        <ErrorBox message={resource.error} retry={resource.reload} />
      ) : resource.loading || !entry ? (
        <Loading />
      ) : (
        <>
          <div className="career-detail-header">
            <div>
              <span className="eyebrow">{knowledgeKinds[entry.kind]}</span>
              {entry.organization && (
                <p className="career-detail-organization">
                  {entry.organization}
                </p>
              )}
              {entry.dates && (
                <p className="muted">{careerDates(entry.dates)}</p>
              )}
            </div>
            <Button icon="edit" onClick={() => setEditing(true)}>
              Edit details
            </Button>
          </div>
          {!!entry.skills.length && (
            <div className="career-skill-tags" aria-label="Entry skills">
              {entry.skills.map((skill) => (
                <span className="tag neutral" key={skill}>
                  {skill}
                </span>
              ))}
            </div>
          )}
          {entry.narrative && (
            <section className="career-description">
              <h3>Description</h3>
              <p className="narrative">{entry.narrative}</p>
            </section>
          )}
          <EntryClaims entry={entry} />
          <LazyDetails className="evidence-files" summary="Supporting files">
            <FileManager ownerType="knowledge" ownerId={entry.id} />
          </LazyDetails>
        </>
      )}
      {editing && entry && (
        <KnowledgeEditor
          record={entry}
          onClose={() => setEditing(false)}
          onSaved={(saved) => {
            setEditing(false);
            resource.setData(saved);
            resource.reload();
          }}
        />
      )}
    </Dialog>
  );
}
const entryLabels: Partial<Record<KnowledgeKind, [string, string]>> = {
  experience: ["Job title", "Organization"],
  education: ["Qualification", "Institution"],
  award: ["Award", "Awarding organization"],
  publication: ["Publication title", "Venue"],
  project: ["Project title", "Organization"],
  course: ["Course title", "Provider"],
  skill: ["Group title", "Organization"],
  language: ["Language or group", "Organization"],
};
function KnowledgeEditor({
  record,
  onClose,
  onSaved,
}: {
  record?: Knowledge;
  onClose: () => void;
  onSaved: (record: Knowledge) => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [kind, setKind] = useState<KnowledgeKind>(record?.kind || "experience");
  const [mode, setMode] = useState<"none" | CareerDates["kind"]>(
    record?.dates?.kind || "none",
  );
  const [current, setCurrent] = useState(record?.dates?.current || false);
  const [start, setStart] = useState(dateParts(record?.dates?.start));
  const [end, setEnd] = useState(dateParts(record?.dates?.end));
  const labels = entryLabels[kind] || ["Title", "Organization"];
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const dates: CareerDates | null =
      mode === "none"
        ? null
        : {
            kind: mode,
            start: dateValue(start),
            end: mode === "period" && !current ? dateValue(end) : null,
            current: mode === "period" && current,
          };
    let result: Knowledge | undefined;
    const ok = await mutate(async () => {
      const body = {
        kind,
        title: f.get("title"),
        organization: f.get("organization"),
        narrative: f.get("narrative"),
        dates,
        skills: String(f.get("skills") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        ...(String(f.get("position") || "")
          ? { position: Number(f.get("position")) }
          : {}),
        metadata: jsonValue(f, "metadata", record?.metadata || {}),
      };
      const saved = await api<Knowledge>(
        record ? `/career/knowledge/${record.id}` : "/career/knowledge",
        record ? "PATCH" : "POST",
        record ? version(record, body) : body,
      );
      // The mutation clears the submitted form's dirty state before closing it.
      result = saved;
    }, "Career entry saved.");
    if (ok && result) onSaved(result);
  }
  return (
    <Dialog
      title={record ? "Edit career entry" : "Add career entry"}
      onClose={onClose}
    >
      <form onSubmit={save}>
        <Field label="Type">
          <select
            name="kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as KnowledgeKind)}
          >
            {Object.entries(knowledgeKinds).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={labels[0]}>
          <input
            name="title"
            required
            maxLength={300}
            defaultValue={record?.title}
          />
        </Field>
        <Field label={`${labels[1]} (optional)`}>
          <input
            name="organization"
            maxLength={300}
            defaultValue={record?.organization}
          />
        </Field>
        <fieldset className="career-date-fields">
          <legend>Dates</legend>
          <Field label="Date mode">
            <select
              name="date_mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as typeof mode)}
            >
              <option value="none">No date</option>
              <option value="single">Single date</option>
              <option value="period">Period</option>
            </select>
          </Field>
          {mode !== "none" && (
            <DatePart
              label={mode === "single" ? "" : "Start"}
              value={start}
              onChange={setStart}
            />
          )}
          {mode === "period" && (
            <>
              <label className="checkline">
                <input
                  name="current"
                  type="checkbox"
                  checked={current}
                  onChange={(e) => setCurrent(e.target.checked)}
                />
                Present
              </label>
              {!current && (
                <DatePart label="End" value={end} onChange={setEnd} />
              )}
            </>
          )}
        </fieldset>
        <Field
          label="Skills"
          hint="Separate skill tags with commas. They describe this entry."
        >
          <input name="skills" defaultValue={record?.skills.join(", ")} />
        </Field>
        <Field
          label="Description (optional)"
          hint="Add supporting facts and context when you are ready. Reusable CV wording belongs in claims."
        >
          <textarea
            name="narrative"
            rows={5}
            defaultValue={record?.narrative}
          />
        </Field>
        <Field
          label="Order"
          hint="Lower numbers appear first. Leave blank to append a new entry."
        >
          <input
            name="position"
            type="number"
            min={0}
            step={1}
            defaultValue={record?.position}
          />
        </Field>
        <AdvancedJson name="metadata" value={record?.metadata || {}} />
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Save entry
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
type DateParts = { year: string; month: string };
function dateParts(value?: string | null): DateParts {
  const [year = "", month = ""] = (value || "").split("-");
  return { year, month };
}
function dateValue(value: DateParts) {
  return value.year.padStart(4, "0") + (value.month ? `-${value.month}` : "");
}
function DatePart({
  label,
  value,
  onChange,
}: {
  label: string;
  value: DateParts;
  onChange: (value: DateParts) => void;
}) {
  return (
    <div className="career-date-parts">
      <Field label={label ? `${label} year` : "Year"}>
        <input
          type="number"
          name={`${label || "date"}_year`}
          required
          min={1}
          max={9999}
          step={1}
          inputMode="numeric"
          placeholder="2025"
          value={value.year}
          onChange={(e) => onChange({ ...value, year: e.target.value })}
        />
      </Field>
      <Field label={label ? `${label} month` : "Month"}>
        <select
          name={`${label || "date"}_month`}
          value={value.month}
          onChange={(e) => onChange({ ...value, month: e.target.value })}
        >
          <option value="">Year only</option>
          {[
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
          ].map((name, i) => (
            <option key={name} value={String(i + 1).padStart(2, "0")}>
              {name}
            </option>
          ))}
        </select>
      </Field>
    </div>
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
    <Dialog title="Import career entries" onClose={onClose}>
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
                <span className="tag neutral">
                  {entry.kind
                    ? knowledgeKinds[entry.kind] || entry.kind
                    : "Other"}
                </span>
                <h3>{entry.title}</h3>
                {entry.organization && <p>{entry.organization}</p>}
                {entry.dates && <small>{careerDates(entry.dates)}</small>}
                {entry.narrative && (
                  <p>
                    {entry.narrative.slice(0, 180)}
                    {entry.narrative.length > 180 ? "…" : ""}
                  </p>
                )}
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
  const [filters, setFilters] = useUrlFilters({
    q: "",
    approved: "",
    knowledge_id: "",
    offset: "0",
  });
  const query = useDebounce(filters.q);
  const resource = useResource<ListResult<Claim>>(
    `/career/claims?summary=true&limit=30&offset=${filters.offset}&q=${encodeURIComponent(query)}${filters.approved ? `&approved=${filters.approved}` : ""}${filters.knowledge_id ? `&knowledge_id=${filters.knowledge_id}` : ""}`,
    { items: [], total: 0 },
  );
  const knowledge = useResource<ListResult<Knowledge>>(
    "/career/knowledge?summary=true",
    { items: [], total: 0 },
    true,
  );
  const [editing, setEditing] = useState<Claim | "new" | null>(null);
  return (
    <>
      <div className="sectiontitle">
        <div>
          <h2>Reusable claims</h2>
          <p>
            Keep reusable wording linked to a career entry. Approve the content
            you want your agent to use.
          </p>
        </div>
        <Button
          variant="primary"
          icon="plus"
          disabled={
            knowledge.loading ||
            !!knowledge.error ||
            !knowledge.data.items.length
          }
          onClick={() => setEditing("new")}
        >
          Add claim
        </Button>
      </div>
      {knowledge.error && (
        <ErrorBox message={knowledge.error} retry={knowledge.reload} />
      )}
      <div className="toolbar">
        <div className="search">
          <Icon name="search" />
          <input
            aria-label="Search claims"
            placeholder="Search claims, titles or organizations"
            value={filters.q}
            onChange={(e) => setFilters({ q: e.target.value, offset: "0" })}
          />
        </div>
        <select
          aria-label="Claim approval"
          value={filters.approved}
          onChange={(e) =>
            setFilters({ approved: e.target.value, offset: "0" })
          }
        >
          <option value="">All claims</option>
          <option value="true">Approved</option>
          <option value="false">Draft</option>
        </select>
        <select
          aria-label="Entry filter"
          value={filters.knowledge_id}
          onChange={(e) =>
            setFilters({ knowledge_id: e.target.value, offset: "0" })
          }
        >
          <option value="">All entries</option>
          {knowledge.data.items.map((k) => (
            <option key={k.id} value={k.id}>
              {careerEntryLabel(k)}
            </option>
          ))}
        </select>
      </div>
      <ClaimList resource={resource} onEdit={setEditing} />
      <Pagination
        offset={Number(filters.offset) || 0}
        total={resource.data.total}
        onChange={(offset) => setFilters({ offset: String(offset) })}
      />
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
function EntryClaims({ entry }: { entry: Knowledge }) {
  const [offset, setOffset] = useState(0),
    [editing, setEditing] = useState<Claim | "new" | null>(null);
  const resource = useResource<ListResult<Claim>>(
    `/career/claims?knowledge_id=${entry.id}&limit=30&offset=${offset}`,
    { items: [], total: 0 },
  );
  return (
    <section className="career-entry-claims">
      <div className="sectiontitle">
        <div>
          <h3>
            Claims <span className="muted">({resource.data.total})</span>
          </h3>
          <p>Reusable wording for this entry.</p>
        </div>
        <Button icon="plus" onClick={() => setEditing("new")}>
          Add claim
        </Button>
      </div>
      <ClaimList resource={resource} onEdit={setEditing} entry={entry} />
      {resource.data.total > 30 && (
        <Pagination
          offset={offset}
          total={resource.data.total}
          onChange={setOffset}
        />
      )}
      {editing && (
        <ClaimEditor
          record={editing === "new" ? undefined : editing}
          knowledge={[entry]}
          fixedEntry={entry}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}
function ClaimList({
  resource,
  onEdit,
  entry,
}: {
  resource: ReturnType<typeof useResource<ListResult<Claim>>>;
  onEdit: (claim: Claim) => void;
  entry?: Knowledge;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [removing, setRemoving] = useState<Claim | null>(null);
  return (
    <>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <section
        className={`card career-claims-list ${entry ? "entry-scoped-claims" : ""}`}
      >
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
                  aria-label={`Approve claim: ${claim.text_preview || claim.text}`}
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
                <p>{claim.text_preview || claim.text}</p>
                {!entry && (
                  <small>
                    {[claim.knowledge_title, claim.knowledge_organization]
                      .filter(Boolean)
                      .join(" · ") || "Career entry"}
                  </small>
                )}
              </div>
              <span className={`tag ${claim.approved ? "green" : "neutral"}`}>
                {claim.approved ? "Approved" : "Draft"}
              </span>
              <div className="actions claim-actions">
                <button
                  type="button"
                  className="iconbtn"
                  aria-label="Edit claim"
                  onClick={() =>
                    api<Claim>(`/career/claims/${claim.id}`)
                      .then(onEdit)
                      .catch((e) => notify(e.message, true))
                  }
                >
                  <Icon name="edit" />
                </button>
                <button
                  type="button"
                  className="iconbtn danger"
                  aria-label="Delete claim"
                  disabled={pending}
                  onClick={() => setRemoving(claim)}
                >
                  <Icon name="trash" />
                </button>
              </div>
            </article>
          ))
        ) : (
          <Empty title="No claims in this view">
            {entry
              ? "Add a result, responsibility or skill list when you are ready."
              : "Add claims to your career entries, then review them here."}
          </Empty>
        )}
      </section>
      {removing && (
        <Dialog title="Remove this claim?" onClose={() => setRemoving(null)}>
          <p className="modal-intro">
            {removing.text_preview || removing.text}
          </p>
          <p className="hint">
            Existing application snapshots retain their copy.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(null)}>Keep claim</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () =>
                      api(
                        `/career/claims/${removing.id}?expected_version=${removing.version}`,
                        "DELETE",
                      ),
                    "Claim removed.",
                  )
                )
                  setRemoving(null);
              }}
            >
              Remove claim
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function ClaimEditor({
  record,
  knowledge,
  fixedEntry,
  onClose,
}: {
  record?: Claim;
  knowledge: Knowledge[];
  fixedEntry?: Knowledge;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (
      await mutate(() => {
        const body = {
          knowledge_id: f.get("knowledge_id"),
          text: f.get("text"),
          approved: f.get("approved") === "on",
          ...(String(f.get("position") || "")
            ? { position: Number(f.get("position")) }
            : {}),
          metadata: jsonValue(f, "metadata", record?.metadata || {}),
        };
        return api(
          record ? `/career/claims/${record.id}` : "/career/claims",
          record ? "PATCH" : "POST",
          record ? version(record, body) : body,
        );
      }, "Claim saved.")
    )
      onClose();
  }
  return (
    <Dialog
      title={record ? "Edit reusable claim" : "Add reusable claim"}
      onClose={onClose}
    >
      <form onSubmit={save}>
        {fixedEntry ? (
          <>
            <input type="hidden" name="knowledge_id" value={fixedEntry.id} />
            <p className="modal-intro">{careerEntryLabel(fixedEntry)}</p>
          </>
        ) : (
          <Field label="Career entry">
            <select
              name="knowledge_id"
              required
              defaultValue={record?.knowledge_id}
            >
              {knowledge.map((k) => (
                <option key={k.id} value={k.id}>
                  {careerEntryLabel(k)}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Claim">
          <textarea
            name="text"
            rows={6}
            required
            maxLength={5000}
            defaultValue={record?.text}
          />
        </Field>
        <Field
          label="Order"
          hint="Lower numbers appear first within the entry. Leave blank to append a new claim."
        >
          <input
            name="position"
            type="number"
            min={0}
            step={1}
            defaultValue={record?.position}
          />
        </Field>
        <label className="checkline">
          <input
            type="checkbox"
            name="approved"
            defaultChecked={record?.approved}
          />
          I have reviewed and approved this claim
        </label>
        <AdvancedJson name="metadata" value={record?.metadata || {}} />
        <div className="actions form-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={pending}>
            Save claim
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
