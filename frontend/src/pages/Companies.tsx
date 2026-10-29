import { useState, type FormEvent } from "react";
import {
  api,
  date,
  version,
  type Json,
  type ListResult,
  type Source,
} from "../api";
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
  Switch,
} from "../ui";
interface Preview {
  kind: string;
  config: Record<string, string>;
  url: string;
  items: { title: string; company?: string; location?: string; url?: string }[];
  total: number;
}
export default function CompaniesPage() {
  const resource = useResource<ListResult<Source>>(
    "/sources",
    {
      items: [],
      total: 0,
    },
    true,
  );
  const { mutate, pending } = useWorkspace();
  const [editing, setEditing] = useState<Source | "new" | null>(null),
    [removing, setRemoving] = useState<Source | null>(null);
  return (
    <>
      <Heading
        title="Follow the teams you like."
        description="Collect opportunities directly from supported company boards and feeds."
      >
        <Button icon="refresh" onClick={resource.reload}>
          Refresh
        </Button>
        <Button variant="primary" icon="plus" onClick={() => setEditing("new")}>
          Add company
        </Button>
      </Heading>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="companygrid">
        {resource.loading ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((source) => (
            <article className="card companycard" key={source.id}>
              <div className="companyhead">
                <Avatar name={source.name} />
                <div>
                  <h3>{source.name}</h3>
                  <p>
                    {source.kind} · {source.config.board || "Feed"}
                  </p>
                </div>
                <Switch
                  label={`Enable ${source.name}`}
                  checked={source.enabled}
                  disabled={pending}
                  onChange={(enabled) =>
                    mutate(
                      () =>
                        api(
                          `/sources/${source.id}`,
                          "PATCH",
                          version(source, { enabled }),
                        ),
                      enabled
                        ? "Company source enabled."
                        : "Source paused. Stored jobs are kept.",
                    )
                  }
                />
              </div>
              <div className="companyfacts">
                <div>
                  <span>Collection</span>
                  <strong>{source.enabled ? "Enabled" : "Paused"}</strong>
                </div>
                <div>
                  <span>Schedule</span>
                  <strong>
                    {source.schedule.kind === "daily"
                      ? `Daily ${String(source.schedule.at || "07:00")}`
                      : `Every ${Number(source.schedule.minutes || 1440) / 60} hours`}
                  </strong>
                </div>
                <div>
                  <span>Last run</span>
                  <strong>{date(source.last_run_at)}</strong>
                </div>
              </div>
              {source.last_error && (
                <p className="source-error">
                  <Icon name="error" />
                  {source.last_error}
                </p>
              )}
              <div className="companyfoot">
                <Button
                  className="small"
                  onClick={() => setEditing(source)}
                  icon="edit"
                >
                  Configure
                </Button>
                <Button
                  className="small"
                  icon="play"
                  disabled={pending}
                  onClick={() =>
                    mutate(
                      () => api(`/sources/${source.id}/run`, "POST"),
                      "Collection queued. Check activity for progress.",
                    )
                  }
                >
                  Run now
                </Button>
                <button
                  className="iconbtn danger"
                  aria-label={`Remove ${source.name}`}
                  onClick={() => setRemoving(source)}
                >
                  <Icon name="trash" />
                </button>
              </div>
            </article>
          ))
        ) : (
          <section className="card full-grid">
            <Empty
              title="Keep an eye on the right teams."
              action={
                <Button icon="plus" onClick={() => setEditing("new")}>
                  Add your first company
                </Button>
              }
            >
              Paste a company career or ATS board URL, preview its
              opportunities, then choose when to collect them.
            </Empty>
          </section>
        )}
      </div>
      <div className="note form-section">
        <Icon name="info" />
        <span>
          Supported boards: Greenhouse, Lever, Ashby and RSS feeds. Pausing a
          source keeps its jobs, notes and application history.
        </span>
      </div>
      {editing && (
        <SourceEditor
          source={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}{" "}
      {removing && (
        <Dialog title="Remove this source?" onClose={() => setRemoving(null)}>
          <p className="modal-intro">
            Stop following {removing.name}. Existing jobs and applications
            remain in your workspace.
          </p>
          <div className="actions form-actions">
            <Button onClick={() => setRemoving(null)}>Keep source</Button>
            <Button
              variant="danger-fill"
              disabled={pending}
              onClick={async () => {
                if (
                  await mutate(
                    () => api(`/sources/${removing.id}`, "DELETE"),
                    "Source removed. Existing jobs are kept.",
                  )
                )
                  setRemoving(null);
              }}
            >
              Remove source
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
function SourceEditor({
  source,
  onClose,
}: {
  source?: Source;
  onClose: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  const [preview, setPreview] = useState<Preview | null>(null),
    [draft, setDraft] = useState<Json | null>(null);
  function values(form: HTMLFormElement): Json {
    const f = new FormData(form);
    return {
      name: f.get("name"),
      url: f.get("url"),
      kind: f.get("kind"),
      config: { ...source?.config, board: f.get("board") || undefined },
      enabled: f.get("enabled") === "on",
      filters: {
        titles: String(f.get("titles") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        locations: String(f.get("locations") || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
      },
      schedule: {
        kind: f.get("schedule_kind"),
        minutes: Number(f.get("minutes")) || 1440,
        at: f.get("at"),
        timezone: f.get("timezone"),
      },
    };
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = values(e.currentTarget);
    if (source) {
      if (
        await mutate(
          () => api(`/sources/${source.id}`, "PATCH", version(source, body)),
          "Source configuration saved.",
        )
      )
        onClose();
    } else
      await mutate(async () => {
        const result = await api<Preview>("/sources/preview", "POST", {
          url: body.url,
          kind: body.kind,
          config: body.config,
          name: body.name,
          filters: body.filters,
        });
        setPreview(result);
        setDraft({
          ...body,
          kind: result.kind,
          config: result.config,
          url: result.url,
        });
      }, "Source preview ready.");
  }
  async function create() {
    if (
      draft &&
      (await mutate(
        () => api("/sources", "POST", draft),
        "Company source added.",
      ))
    )
      onClose();
  }
  const filter = (name: string) =>
    Array.isArray(source?.filters[name])
      ? (source?.filters[name] as string[]).join(", ")
      : "";
  return (
    <Dialog
      title={
        source
          ? "Configure company collection."
          : preview
            ? "A look before you follow."
            : "Follow a company."
      }
      onClose={onClose}
    >
      {preview && !source ? (
        <>
          <p className="modal-intro">
            Found {preview.total} opportunities on this {preview.kind} board.
            Saving the source does not change existing jobs.
          </p>
          <div className="source-preview">
            {preview.items.slice(0, 8).map((job, i) => (
              <article key={i}>
                <strong>{job.title}</strong>
                <small>
                  {job.company} {job.location && `· ${job.location}`}
                </small>
              </article>
            ))}
            {!preview.items.length && (
              <p>
                No matching opportunities currently. You can still save this
                source for future collection.
              </p>
            )}
          </div>
          <div className="actions form-actions">
            <Button onClick={() => setPreview(null)}>Back</Button>
            <Button variant="primary" disabled={pending} onClick={create}>
              Save company
            </Button>
          </div>
        </>
      ) : (
        <form onSubmit={submit}>
          <Field label="Company name">
            <input
              name="name"
              defaultValue={source?.name}
              placeholder="Company name"
            />
          </Field>
          <Field
            label="Career / board URL"
            hint="Paste a supported ATS board or RSS feed URL."
          >
            <input
              name="url"
              type="url"
              required
              defaultValue={source?.url || ""}
              placeholder="https://jobs.lever.co/company"
            />
          </Field>
          <div className="formgrid">
            <Field label="Board type">
              <select name="kind" defaultValue={source?.kind || "auto"}>
                <option value="auto">Detect from URL</option>
                <option value="greenhouse">Greenhouse</option>
                <option value="lever">Lever</option>
                <option value="ashby">Ashby</option>
                <option value="rss">RSS feed</option>
              </select>
            </Field>
            <Field label="Board identifier (optional)">
              <input
                name="board"
                defaultValue={source?.config.board || ""}
                placeholder="company-slug"
              />
            </Field>
            <Field label="Role filters" hint="Optional comma-separated words.">
              <input
                name="titles"
                defaultValue={filter("titles")}
                placeholder="engineer, developer"
              />
            </Field>
            <Field
              label="Location filters"
              hint="Optional comma-separated locations."
            >
              <input
                name="locations"
                defaultValue={filter("locations")}
                placeholder="Zurich, remote"
              />
            </Field>
            <Field label="Schedule">
              <select
                name="schedule_kind"
                defaultValue={String(source?.schedule.kind || "daily")}
              >
                <option value="daily">At a daily time</option>
                <option value="interval">At an interval</option>
              </select>
            </Field>
            <Field label="Daily time">
              <input
                name="at"
                type="time"
                defaultValue={String(source?.schedule.at || "07:00")}
              />
            </Field>
            <Field label="Timezone">
              <input
                name="timezone"
                defaultValue={String(
                  source?.schedule.timezone ||
                    Intl.DateTimeFormat().resolvedOptions().timeZone ||
                    "UTC",
                )}
              />
            </Field>
            <Field label="Interval in minutes">
              <input
                name="minutes"
                type="number"
                min={15}
                max={43200}
                defaultValue={Number(source?.schedule.minutes || 1440)}
              />
            </Field>
          </div>
          <label className="checkline">
            <input
              name="enabled"
              type="checkbox"
              defaultChecked={source?.enabled || false}
            />
            Enable automatic collection
          </label>
          <div className="actions form-actions">
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" disabled={pending}>
              {source ? "Save source" : "Preview opportunities"}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
