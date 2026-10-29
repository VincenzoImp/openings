import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  binary,
  copyText,
  type Json,
  date,
  version,
  type ListResult,
  type Scoring,
} from "../api";
import {
  useResource,
  useUrlFilters,
  useUrlState,
  useWorkspace,
} from "../state";
import {
  Pagination,
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Icon,
  Loading,
  Switch,
  Tabs,
} from "../ui";
import { ProviderSettings } from "./Companies";
const blankScoring: Scoring = {
  enabled: false,
  mode: "local",
  provider: "laya",
  base_url: "http://scorer:8000",
  model: "english",
  rubric: "",
  max_len: 2048,
  timeout_seconds: 120,
  periodic_rescore: { enabled: false, minutes: 1440, batch_size: 50 },
  version: 1,
};
interface Token {
  id: string;
  name: string;
  created_at: string;
  last_used_at?: string;
}
interface Task {
  id: string;
  kind: string;
  status?: string;
  state?: string;
  created_at: string;
  updated_at?: string;
  error?: string;
  result?: Record<string, unknown>;
}
export default function SettingsPage({
  theme,
  onTheme,
  onLogout,
}: {
  theme: string;
  onTheme: () => void;
  onLogout: () => void;
}) {
  const [tab, setTab] = useUrlState("section", "scoring");
  return (
    <>
      <Heading
        title="Make it work for you."
        description="A small set of controls, with deliberate defaults."
      />
      <Tabs
        label="Settings sections"
        value={tab}
        onChange={setTab}
        items={[
          { id: "scoring", label: "AI scoring" },
          { id: "collection", label: "Collection" },
          { id: "agents", label: "Agent access" },
          { id: "activity", label: "Activity" },
          { id: "workspace", label: "Workspace" },
        ]}
      />
      <div className="settings-content">
        {tab === "scoring" ? (
          <ScoringSettings />
        ) : tab === "collection" ? (
          <ProviderSettings />
        ) : tab === "agents" ? (
          <AgentSettings />
        ) : tab === "activity" ? (
          <TaskSettings />
        ) : (
          <WorkspaceSettings
            theme={theme}
            onTheme={onTheme}
            onLogout={onLogout}
          />
        )}
      </div>
    </>
  );
}
function ScoringSettings() {
  const resource = useResource<Scoring>("/scoring", blankScoring);
  const { mutate, pending, notify } = useWorkspace();
  const [enabled, setEnabled] = useState(false),
    [mode, setMode] = useState("local"),
    [periodic, setPeriodic] = useState(false),
    [testing, setTesting] = useState<string | null>(null),
    [rescore, setRescore] = useState(false);
  useEffect(() => {
    setEnabled(resource.data.enabled);
    setMode(resource.data.mode);
    setPeriodic(resource.data.periodic_rescore.enabled);
  }, [resource.data]);
  function values(form: HTMLFormElement) {
    const f = new FormData(form);
    const body: Record<string, unknown> = {
      enabled,
      mode,
      provider: f.get("provider"),
      base_url: f.get("base_url"),
      model: f.get("model"),
      rubric: f.get("rubric"),
      criteria: String(f.get("criteria") || "")
        .split("\n")
        .map((value) => value.trim())
        .filter(Boolean),
      max_len: Number(f.get("max_len")) || 2048,
      timeout_seconds: Number(f.get("timeout_seconds")) || 120,
      periodic_rescore: {
        enabled: periodic,
        minutes:
          Number(
            f.get("periodic_minutes") ?? resource.data.periodic_rescore.minutes,
          ) || 1440,
        batch_size:
          Number(
            f.get("batch_size") ?? resource.data.periodic_rescore.batch_size,
          ) || 50,
      },
    };
    if (f.get("api_key")) body.api_key = f.get("api_key");
    if (f.get("clear_key") === "on") body.api_key = "";
    return body;
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await mutate(
      () =>
        api(
          "/scoring",
          "PATCH",
          version(resource.data, values(e.currentTarget)),
        ),
      "Scoring settings saved. Existing scores may be marked outdated; no bulk rescoring started.",
    );
  }
  async function test(form: HTMLFormElement | null) {
    if (!form) return;
    try {
      setTesting("Testing the endpoint…");
      const result = await api<Record<string, unknown>>(
        "/scoring/test",
        "POST",
        values(form),
      );
      setTesting(
        `Connected. ${String(result.model || result.message || "The endpoint returned a valid score.")}`,
      );
    } catch (e) {
      setTesting(null);
      notify(e instanceof Error ? e.message : "Connection failed.", true);
    }
  }
  if (resource.loading) return <Loading />;
  if (resource.error)
    return <ErrorBox message={resource.error} retry={resource.reload} />;
  return (
    <>
      <form
        className="settings-grid scoring-layout"
        onSubmit={save}
        key={resource.data.version}
        id="scoring-form"
      >
        <section className="card sectioncard">
          <div className="settingrow">
            <div>
              <h3>Enable AI scoring</h3>
              <p>
                Assess complete opportunities against your stored profile and
                preferences.
              </p>
            </div>
            <Switch
              label="Enable AI scoring"
              checked={enabled}
              onChange={setEnabled}
            />
          </div>
          <div className="radio-cards">
            {[
              [
                "local",
                "Local service",
                "One optional CPU model on this host.",
              ],
              [
                "remote",
                "Remote service",
                "A compatible service on another machine.",
              ],
            ].map(([id, title, description]) => (
              <label className="radio-card" key={id}>
                <input
                  type="radio"
                  name="mode"
                  checked={mode === id}
                  onChange={() => setMode(id)}
                />
                <span>
                  <strong>{title}</strong>
                  <small>{description}</small>
                </span>
              </label>
            ))}
          </div>
          <div className="formgrid">
            <Field label="Service URL">
              <input
                name="base_url"
                type="url"
                defaultValue={resource.data.base_url}
                required
              />
            </Field>
            <Field label="Served model">
              <input name="model" defaultValue={resource.data.model} required />
            </Field>
            <Field label="Protocol profile">
              <select name="provider" defaultValue={resource.data.provider}>
                <option value="laya">Laya</option>
                <option value="systemone">Jev / System One compatible</option>
              </select>
            </Field>
            <Field label="Maximum context tokens">
              <input
                name="max_len"
                type="number"
                min={256}
                max={8192}
                defaultValue={resource.data.max_len}
              />
            </Field>
            <Field
              label="API key (optional)"
              hint={
                resource.data.api_key_set
                  ? "A key is stored. Leave empty to keep it."
                  : "Required only if your endpoint asks for one."
              }
            >
              <input
                name="api_key"
                type="password"
                autoComplete="new-password"
                placeholder={resource.data.api_key_set ? "••••••••" : ""}
              />
            </Field>
            <Field label="Request timeout (seconds)">
              <input
                name="timeout_seconds"
                type="number"
                min={5}
                max={600}
                defaultValue={resource.data.timeout_seconds}
              />
            </Field>
          </div>
          {resource.data.api_key_set && (
            <label className="checkline">
              <input name="clear_key" type="checkbox" />
              Remove the stored API key
            </label>
          )}
        </section>
        <section className="card sectioncard">
          <h2 className="section-heading">Define a useful fit assessment.</h2>
          <Field
            label="Score levels"
            hint="One description per line, from lowest to highest fit. Use 2–10 levels."
          >
            <textarea
              name="criteria"
              rows={6}
              required
              defaultValue={(resource.data.criteria || []).join("\n")}
            />
          </Field>
          <Field
            label="Assessment instructions"
            hint="Used only for fit scoring, separately from your document-writing guidance."
          >
            <textarea
              name="rubric"
              rows={7}
              defaultValue={resource.data.rubric}
            />
          </Field>
          <div className="actions form-actions">
            <Button
              type="button"
              icon="play"
              disabled={pending}
              onClick={(e) => test(e.currentTarget.form)}
            >
              Test connection
            </Button>
            {testing && <span className="smalltext">{testing}</span>}
          </div>
          <div className="divider" />
          <div className="settingrow">
            <div>
              <h3>Periodically update outdated scores</h3>
              <p>
                Off by default. Editing a profile never starts a bulk rescore.
              </p>
            </div>
            <Switch
              label="Periodic rescoring"
              checked={periodic}
              onChange={setPeriodic}
            />
          </div>
          {periodic && (
            <div className="formgrid">
              <Field label="Check every (minutes)">
                <input
                  name="periodic_minutes"
                  type="number"
                  min={60}
                  max={43200}
                  defaultValue={resource.data.periodic_rescore.minutes}
                />
              </Field>
              <Field label="Maximum jobs per batch">
                <input
                  name="batch_size"
                  type="number"
                  min={1}
                  max={200}
                  defaultValue={resource.data.periodic_rescore.batch_size}
                />
              </Field>
            </div>
          )}
          <div className="section-footer">
            <span>
              Scoring is indicative. Turning it off keeps stored scores.
            </span>
            <Button variant="primary" disabled={pending}>
              Save scoring settings
            </Button>
          </div>
        </section>
      </form>
      <div className="card sectioncard form-section">
        <div className="sectiontitle">
          <div>
            <h2>Update scores deliberately.</h2>
            <p>
              Queue a bounded batch of outdated jobs. This never generates
              application documents.
            </p>
          </div>
        </div>
        <Button
          icon="refresh"
          disabled={!resource.data.enabled || pending}
          onClick={() => setRescore(true)}
        >
          Update outdated scores
        </Button>
      </div>
      {rescore && (
        <Dialog
          title="Update outdated scores?"
          onClose={() => setRescore(false)}
        >
          <p className="modal-intro">
            Only non-dismissed jobs with outdated assessments will be queued.
            Existing scores remain until a replacement succeeds.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const limit = Number(new FormData(e.currentTarget).get("limit"));
              if (
                await mutate(
                  () =>
                    api("/scoring/rescore", "POST", {
                      outdated_only: true,
                      limit,
                      job_ids: [],
                    }),
                  "Rescoring queued.",
                )
              )
                setRescore(false);
            }}
          >
            <Field label="Maximum jobs in this batch">
              <input
                name="limit"
                type="number"
                defaultValue={50}
                min={1}
                max={200}
              />
            </Field>
            <div className="actions form-actions">
              <Button variant="primary" disabled={pending}>
                Queue rescoring
              </Button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  );
}
function AgentSettings() {
  const resource = useResource<ListResult<Token>>("/tokens", {
    items: [],
    total: 0,
  });
  const { mutate, pending, notify } = useWorkspace();
  const [token, setToken] = useState<string | null>(null);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await mutate(async () => {
      const result = await api<{ token: string }>("/tokens", "POST", {
        name: f.get("name"),
      });
      setToken(result.token);
    }, "Access token created. Save it before closing this view.");
  }
  const endpoint = `${location.origin}/mcp`;
  return (
    <div className="settings-grid">
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>Your agent, your tools.</h2>
            <p>
              The workspace keeps context. Your external agent writes and
              compiles.
            </p>
          </div>
        </div>
        <Field label="MCP endpoint">
          <span className="endpoint">
            {endpoint}
            <button
              type="button"
              className="iconbtn"
              aria-label="Copy MCP endpoint"
              onClick={() =>
                copyText(endpoint)
                  .then(() => notify("MCP endpoint copied."))
                  .catch(() => notify("Copy the endpoint shown above."))
              }
            >
              <Icon name="copy" />
            </button>
          </span>
        </Field>
        {[
          [
            "Connect your assistant",
            "Configure this HTTP MCP endpoint in Codex, Claude Code or another MCP client using an access token.",
          ],
          [
            "Read the right context",
            "Your agent reads career evidence, the posting, templates and stored instructions through the same service as this dashboard.",
          ],
          [
            "Prepare externally, review here",
            "The agent compiles on its machine and uploads PDF, sources and answers. Review them before recording an application as sent.",
          ],
        ].map(([title, body], i) => (
          <div className="step" key={title}>
            <span className="stepnum">{i + 1}</span>
            <div>
              <strong>{title}</strong>
              <p>{body}</p>
            </div>
          </div>
        ))}
      </section>
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>Access tokens.</h2>
            <p>
              Separate tokens can be revoked without changing your password.
            </p>
          </div>
        </div>
        {resource.error && (
          <ErrorBox message={resource.error} retry={resource.reload} />
        )}
        <div className="token-list">
          {resource.data.items.map((item) => (
            <div className="settingrow" key={item.id}>
              <div>
                <h3>{item.name}</h3>
                <p>
                  Created {date(item.created_at)} · Last used{" "}
                  {date(item.last_used_at)}
                </p>
              </div>
              <Button
                variant="danger small"
                disabled={pending}
                onClick={() =>
                  mutate(
                    () => api(`/tokens/${item.id}`, "DELETE"),
                    "Access token revoked.",
                  )
                }
              >
                Revoke
              </Button>
            </div>
          ))}
        </div>
        <form className="actions token-form" onSubmit={create}>
          <input
            name="name"
            aria-label="Token name"
            placeholder="My coding assistant"
            required
          />
          <Button variant="primary" disabled={pending}>
            Create token
          </Button>
        </form>
        {token && (
          <div className="new-token" role="status">
            <strong>Save this token now. It will only be shown once.</strong>
            <code>{token}</code>
            <div className="actions">
              <Button
                icon="copy"
                onClick={() =>
                  copyText(token)
                    .then(() => notify("Token copied."))
                    .catch(() => notify("Select and copy the token manually."))
                }
              >
                Copy token
              </Button>
              <Button onClick={() => setToken(null)}>I have saved it</Button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
function TaskSettings() {
  const [filters, setFilters] = useUrlFilters({
    state: "",
    kind: "",
    source_id: "",
    job_id: "",
    offset: "0",
  });
  const params = new URLSearchParams({ ...filters, limit: "30" });
  Object.entries(filters).forEach(([key, value]) => {
    if (!value) params.delete(key);
  });
  const resource = useResource<
    ListResult<Task & { source_name?: string; job_title?: string }>
  >(`/tasks?${params}`, { items: [], total: 0 });
  const { mutate, pending } = useWorkspace();
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useResource<Json | null>(
    selected ? `/tasks/${selected}` : null,
    null,
  );
  const active = resource.data.items.some((t) =>
    ["queued", "running"].includes(t.status || t.state || ""),
  );
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(resource.reload, 4000);
    return () => clearInterval(timer);
  }, [active]);
  return (
    <>
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>Workspace activity.</h2>
            <p>
              Inspect collection and scoring work, including failures and retry
              eligibility.
            </p>
          </div>
          <Button icon="refresh" onClick={resource.reload}>
            Refresh
          </Button>
        </div>
        <div className="filter-grid">
          <Field label="Task state">
            <select
              value={filters.state}
              onChange={(e) =>
                setFilters({ state: e.target.value, offset: "0" })
              }
            >
              <option value="">All states</option>
              {["queued", "running", "succeeded", "failed", "cancelled"].map(
                (value) => (
                  <option key={value}>{value}</option>
                ),
              )}
            </select>
          </Field>
          <Field label="Task kind">
            <select
              value={filters.kind}
              onChange={(e) =>
                setFilters({ kind: e.target.value, offset: "0" })
              }
            >
              <option value="">All kinds</option>
              <option value="collect">Collection</option>
              <option value="score">Scoring</option>
            </select>
          </Field>
          <Field label="Source ID">
            <input
              value={filters.source_id}
              onChange={(e) =>
                setFilters({ source_id: e.target.value, offset: "0" })
              }
              placeholder="Any source"
            />
          </Field>
          <Field label="Job ID">
            <input
              value={filters.job_id}
              onChange={(e) =>
                setFilters({ job_id: e.target.value, offset: "0" })
              }
              placeholder="Any job"
            />
          </Field>
        </div>
        {resource.error && (
          <ErrorBox message={resource.error} retry={resource.reload} />
        )}
        <div className="task-list">
          {resource.loading ? (
            <Loading />
          ) : resource.data.items.length ? (
            resource.data.items.map((task) => (
              <article className="task-entry" key={task.id}>
                <div className="sectiontitle">
                  <div>
                    <button
                      className="table-link"
                      onClick={() => setSelected(task.id)}
                    >
                      <h3>
                        {task.source_name ||
                          task.job_title ||
                          task.kind.replaceAll("_", " ")}
                      </h3>
                    </button>
                    <p>
                      {task.kind} · {date(task.created_at)}
                    </p>
                  </div>
                  <span className={`tag ${task.error ? "amber" : "neutral"}`}>
                    {task.status || task.state}
                  </span>
                </div>
                {task.error && <p className="source-error">{task.error}</p>}
                <div className="actions">
                  <Button
                    className="small"
                    onClick={() => setSelected(task.id)}
                  >
                    Details
                  </Button>
                  {["queued", "running"].includes(
                    task.status || task.state || "",
                  ) ? (
                    <Button
                      className="small"
                      disabled={pending}
                      onClick={() =>
                        mutate(
                          () => api(`/tasks/${task.id}/cancel`, "POST"),
                          "Cancellation requested.",
                        )
                      }
                    >
                      Cancel task
                    </Button>
                  ) : ["failed", "cancelled"].includes(
                      task.status || task.state || "",
                    ) ? (
                    <Button
                      className="small"
                      icon="refresh"
                      disabled={pending}
                      onClick={() =>
                        mutate(
                          () => api(`/tasks/${task.id}/retry`, "POST"),
                          "Task retry queued.",
                        )
                      }
                    >
                      Retry
                    </Button>
                  ) : null}
                </div>
              </article>
            ))
          ) : (
            <Empty title="No activity in this view.">
              Collection and scoring runs appear here with their results.
            </Empty>
          )}
        </div>
        <Pagination
          offset={Number(filters.offset) || 0}
          total={resource.data.total}
          onChange={(offset) => setFilters({ offset: String(offset) })}
        />
      </section>
      {selected && (
        <Dialog title="Task details." onClose={() => setSelected(null)}>
          {detail.error ? (
            <ErrorBox message={detail.error} retry={detail.reload} />
          ) : detail.data ? (
            <pre className="json-readout">
              {JSON.stringify(detail.data, null, 2)}
            </pre>
          ) : (
            <Loading />
          )}
        </Dialog>
      )}
    </>
  );
}
function WorkspaceSettings({
  theme,
  onTheme,
  onLogout,
}: {
  theme: string;
  onTheme: () => void;
  onLogout: () => void;
}) {
  const { mutate, pending, notify } = useWorkspace();
  const [restore, setRestore] = useState(false);
  async function backup() {
    await mutate(async () => {
      const response = await binary("/backup", "GET");
      if (!response.ok) throw Error("The backup could not be created.");
      const blob = await response.blob(),
        url = URL.createObjectURL(blob),
        a = document.createElement("a");
      a.href = url;
      a.download = `openings-${new Date().toISOString().slice(0, 10)}.sqlite`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, "Consistent SQLite backup downloaded.");
  }
  return (
    <div className="settings-grid">
      <section className="card sectioncard">
        <div className="sectiontitle">
          <h2>Workspace.</h2>
        </div>
        <div className="settingrow">
          <div>
            <h3>Interface language</h3>
            <p>English. Your content can use any language.</p>
          </div>
          <span className="tag neutral">English</span>
        </div>
        <div className="settingrow">
          <div>
            <h3>Appearance</h3>
            <p>Comfortable contrast and quiet surfaces.</p>
          </div>
          <Button icon={theme === "light" ? "moon" : "sun"} onClick={onTheme}>
            {theme === "light" ? "Dark mode" : "Light mode"}
          </Button>
        </div>
        <div className="settingrow">
          <div>
            <h3>Portable backup</h3>
            <p>One SQLite file includes your data and document bytes.</p>
          </div>
          <Button icon="download" onClick={backup} disabled={pending}>
            Download backup
          </Button>
        </div>
        <div className="settingrow">
          <div>
            <h3>Export records</h3>
            <p>Download a portable JSON archive of workspace records.</p>
          </div>
          <Button
            icon="download"
            disabled={pending}
            onClick={() =>
              mutate(async () => {
                const response = await binary("/export", "GET");
                const url = URL.createObjectURL(await response.blob());
                const a = document.createElement("a");
                a.href = url;
                a.download = "openings-records.json";
                a.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
              }, "Records exported.")
            }
          >
            Export records
          </Button>
        </div>
        <div className="settingrow">
          <div>
            <h3>Restore a backup</h3>
            <p>Replace this workspace with a validated Openings backup.</p>
          </div>
          <Button icon="upload" onClick={() => setRestore(true)}>
            Restore
          </Button>
        </div>
        <div className="settingrow">
          <div>
            <h3>Sign out</h3>
            <p>End this browser session.</p>
          </div>
          <Button icon="logout" onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </section>
      <PasswordSettings />
      {restore && <RestoreDialog onClose={() => setRestore(false)} />}
    </div>
  );
}
function RestoreDialog({ onClose }: { onClose: () => void }) {
  const { mutate, pending } = useWorkspace();
  const [file, setFile] = useState<File | null>(null),
    [confirmation, setConfirmation] = useState("");
  return (
    <Dialog title="Restore this workspace?" onClose={onClose}>
      <p className="modal-intro">
        The selected backup will replace current workspace data. Download a
        backup first if you want to keep the current state. This installation's
        owner password and access tokens are preserved.
      </p>
      <Field label="SQLite backup">
        <input
          type="file"
          accept=".sqlite,.sqlite3,.db"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </Field>
      <Field label="Type RESTORE to confirm">
        <input
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          autoComplete="off"
        />
      </Field>
      <div className="actions form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="danger-fill"
          disabled={pending || !file || confirmation !== "RESTORE"}
          onClick={async () => {
            if (!file) return;
            const ok = await mutate(async () => {
              await binary("/backup/restore", "POST", file, {
                "Content-Type": "application/vnd.sqlite3",
              });
            }, "Workspace restored.");
            if (ok) location.reload();
          }}
        >
          Restore backup
        </Button>
      </div>
    </Dialog>
  );
}

function PasswordSettings() {
  const { mutate, pending, notify } = useWorkspace();
  return (
    <section className="card sectioncard">
      <div className="sectiontitle">
        <div>
          <h2>Owner access.</h2>
          <p>
            Change the owner password. API access tokens keep working; browser
            sessions must sign in again.
          </p>
        </div>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          if (f.get("password") !== f.get("confirm")) {
            notify("The passwords do not match.", true);
            return;
          }
          if (
            await mutate(
              () =>
                api("/auth/password", "POST", { password: f.get("password") }),
              "Password changed. Sign in with your new password.",
            )
          )
            window.dispatchEvent(new Event("openings:unauthorized"));
        }}
      >
        <Field label="New password">
          <input
            name="password"
            type="password"
            minLength={10}
            required
            autoComplete="new-password"
          />
        </Field>
        <Field label="Confirm new password">
          <input
            name="confirm"
            type="password"
            minLength={10}
            required
            autoComplete="new-password"
          />
        </Field>
        <Button variant="primary" disabled={pending}>
          Change password
        </Button>
      </form>
      <div className="divider" />
      <p className="hint">Openings 0.5.0 · Your job search workspace</p>
      <p className="hint">
        <a
          className="textbutton"
          href="/api/v1/capabilities"
          target="_blank"
          rel="noreferrer"
        >
          Service capabilities & interface coverage <Icon name="external" />
        </a>
      </p>
    </section>
  );
}
