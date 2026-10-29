import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  binary,
  copyText,
  date,
  version,
  type ListResult,
  type Scoring,
} from "../api";
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
  Switch,
  Tabs,
} from "../ui";
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
  const [tab, setTab] = useState("scoring");
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
          { id: "agents", label: "Agent access" },
          { id: "activity", label: "Activity" },
          { id: "workspace", label: "Workspace" },
        ]}
      />
      <div className="reading-width">
        {tab === "scoring" ? (
          <ScoringSettings />
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
        className="card sectioncard"
        onSubmit={save}
        key={resource.data.version}
        id="scoring-form"
      >
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
            ["local", "Local service", "One optional CPU model on this host."],
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
    <>
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
      <section className="card sectioncard form-section">
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
    </>
  );
}
function TaskSettings() {
  const resource = useResource<ListResult<Task>>("/tasks?limit=50", {
    items: [],
    total: 0,
  });
  const { mutate, pending } = useWorkspace();
  const active = resource.data.items.some((t) =>
    ["queued", "running"].includes(t.status || t.state || ""),
  );
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(resource.reload, 4000);
    return () => clearInterval(timer);
  }, [active]);
  return (
    <section className="card sectioncard">
      <div className="sectiontitle">
        <div>
          <h2>Workspace activity.</h2>
          <p>
            Collection and scoring jobs, including useful failures and
            cancellation.
          </p>
        </div>
        <Button icon="refresh" onClick={resource.reload}>
          Refresh
        </Button>
      </div>
      {resource.error && (
        <ErrorBox message={resource.error} retry={resource.reload} />
      )}
      <div className="task-list">
        {resource.loading && !resource.data.items.length ? (
          <Loading />
        ) : resource.data.items.length ? (
          resource.data.items.map((task) => (
            <article className="task-entry" key={task.id}>
              <div className="sectiontitle">
                <div>
                  <h3>{task.kind.replaceAll("_", " ")}</h3>
                  <p>{date(task.created_at)}</p>
                </div>
                <span className={`tag ${task.error ? "amber" : "neutral"}`}>
                  {task.status || task.state}
                </span>
              </div>
              {task.error && <p className="source-error">{task.error}</p>}
              {task.result && (
                <p className="smalltext muted">
                  {Object.entries(task.result)
                    .filter(([, v]) => typeof v === "number")
                    .map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`)
                    .join(" · ")}
                </p>
              )}
              {["queued", "running"].includes(
                task.status || task.state || "",
              ) && (
                <Button
                  className="small"
                  disabled={pending}
                  onClick={() =>
                    mutate(
                      () => api(`/tasks/${task.id}/cancel`, "POST"),
                      "Task cancellation requested.",
                    )
                  }
                >
                  Cancel task
                </Button>
              )}
            </article>
          ))
        ) : (
          <Empty title="Quiet for now.">
            Collection and scoring activity appears here when you run a source
            or assessment.
          </Empty>
        )}
      </div>
    </section>
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
    <>
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
      {restore && <RestoreDialog onClose={() => setRestore(false)} />}
    </>
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
