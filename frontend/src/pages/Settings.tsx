import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  binary,
  copyText,
  type Json,
  date,
  formatTime,
  type BackgroundTask,
  type CollectionRun,
  type Source,
  type Job,
  version,
  type ListResult,
  type TokenKind,
  tokenKinds,
} from "../api";
import {
  useResource,
  useDebounce,
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
import { RunProgress, duration } from "./CollectionForms";
interface Token {
  id: string;
  name: string;
  kind: TokenKind;
  created_at: string;
  last_used_at?: string;
}
const tokenAccess: Record<TokenKind, string> = {
  agent:
    "Runs the job search. Cannot change your password, manage tokens, restore a backup or answer its own questions.",
  owner: "Full access, the same as your dashboard session.",
};
export default function SettingsPage({
  theme,
  onTheme,
  onLogout,
}: {
  theme: string;
  onTheme: () => void;
  onLogout: () => void;
}) {
  const [tab, setTab] = useUrlState("section", "agents");
  return (
    <>
      <Heading
        title="Settings"
        description="Manage agent access, collection and workspace backups."
      />
      <Tabs
        label="Settings sections"
        value={tab}
        onChange={setTab}
        items={[
          { id: "collection", label: "Collection" },
          { id: "agents", label: "Agent access" },
          { id: "activity", label: "Activity" },
          { id: "workspace", label: "Workspace" },
        ]}
      />
      <div className="settings-content">
        {tab === "collection" ? (
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
type SkillItem = { name: string; description: string; files: string[] };
const AGENT_GUIDE =
  "https://github.com/VincenzoImp/openings/blob/main/docs/user/agent-operated.md";
function clientSnippets(endpoint: string): Record<string, string> {
  return {
    "claude-code": `claude mcp add --transport http openings ${endpoint} \\\n  --header 'Authorization: Bearer \${OPENINGS_TOKEN}'`,
    codex: `# ~/.codex/config.toml\n[mcp_servers.openings]\nurl = "${endpoint}"\nbearer_token_env_var = "OPENINGS_TOKEN"`,
    json: JSON.stringify(
      {
        mcpServers: {
          openings: {
            type: "http",
            url: endpoint,
            headers: { Authorization: "Bearer ${OPENINGS_TOKEN}" },
          },
        },
      },
      null,
      2,
    ),
  };
}
function ClientSetup({ endpoint }: { endpoint: string }) {
  const { notify } = useWorkspace();
  const [client, setClient] = useState("claude-code");
  const snippet = clientSnippets(endpoint)[client];
  return (
    <>
      <Field
        label="Client configuration"
        hint="Keep the token in the OPENINGS_TOKEN environment variable, never in the file. Some clients write it as ${env:OPENINGS_TOKEN}."
      >
        <Tabs
          label="MCP client"
          value={client}
          onChange={setClient}
          items={[
            { id: "claude-code", label: "Claude Code" },
            { id: "codex", label: "Codex" },
            { id: "json", label: "Other (JSON)" },
          ]}
        />
        <pre className="snippet">
          <code>{snippet}</code>
        </pre>
        <div className="actions">
          <Button
            icon="copy"
            onClick={() =>
              copyText(snippet)
                .then(() => notify("Configuration copied."))
                .catch(() => notify("Select and copy the configuration."))
            }
          >
            Copy configuration
          </Button>
        </div>
      </Field>
      {[
        [
          "Connect your agent",
          "Create an agent access token below, set OPENINGS_TOKEN (and OPENINGS_URL for file transfers), and add the configuration above to your client.",
        ],
        [
          "Let it run the search",
          "The agent loads the workflow skills from this server, onboards your career, reviews new jobs and prepares a CV and letter for every shortlisted one.",
        ],
        [
          "Apply and record",
          "Open ready Drafts, apply on the employer's site and mark each one Applied or close it. The agent never submits for you.",
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
    </>
  );
}
function SkillsCard() {
  const skills = useResource<{ items: SkillItem[] }>("/skills", { items: [] });
  return (
    <section className="card sectioncard">
      <div className="sectiontitle">
        <div>
          <h2>Agent skills</h2>
          <p>
            Workflows this server ships for agents. Connected agents read them
            with <code>skills_list</code> and <code>skill_get</code>, or as MCP
            prompts. Start a new workspace with <code>setup-openings</code>.
          </p>
        </div>
      </div>
      {skills.error && (
        <ErrorBox message={skills.error} retry={skills.reload} />
      )}
      {skills.data.items.map((item) => (
        <div className="settingrow" key={item.name}>
          <div>
            <h3>{item.name}</h3>
            <p>{item.description}</p>
          </div>
        </div>
      ))}
      <div className="actions form-actions">
        <a
          className="textbutton smalltext"
          href={AGENT_GUIDE}
          target="_blank"
          rel="noreferrer"
        >
          Agent-operated job search guide
        </a>
      </div>
    </section>
  );
}
function AgentSettings() {
  const resource = useResource<ListResult<Token>>("/tokens", {
    items: [],
    total: 0,
  });
  const { mutate, pending, notify } = useWorkspace();
  const [token, setToken] = useState<string | null>(null);
  // An agent needs no owner authority, so that is the kind offered first.
  const [kind, setKind] = useState<TokenKind>("agent");
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await mutate(async () => {
      const result = await api<{ token: string }>("/tokens", "POST", {
        name: f.get("name"),
        kind,
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
            <h2>Connect an agent</h2>
            <p>
              Connect an external agent with the MCP endpoint and an access
              token.
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
        <div className="actions form-actions">
          <a
            className="btn small"
            href="/api/docs"
            target="_blank"
            rel="noreferrer"
          >
            API reference
          </a>
          <a
            className="textbutton smalltext"
            href="/api/v1/capabilities"
            target="_blank"
            rel="noreferrer"
          >
            Available operations
          </a>
        </div>
        <ClientSetup endpoint={endpoint} />
      </section>
      <SkillsCard />
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>Access tokens.</h2>
            <p>
              Separate tokens can be revoked without changing your password.
              Give an agent an <strong>Agent</strong> token; an{" "}
              <strong>Owner</strong> token has full access.
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
                <h3>
                  {item.name}{" "}
                  <span
                    className={`tag ${item.kind === "agent" ? "green" : "amber"}`}
                    title={tokenAccess[item.kind]}
                  >
                    {tokenKinds[item.kind]}
                  </span>
                </h3>
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
          <select
            aria-label="Token kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as TokenKind)}
          >
            <option value="agent">Agent token</option>
            <option value="owner">Owner token (full access)</option>
          </select>
          <Button variant="primary" disabled={pending}>
            Create token
          </Button>
        </form>
        <p className="hint token-kind-hint">{tokenAccess[kind]}</p>
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
    activity_view: "runs",
  });
  const taskView = filters.activity_view === "tasks";
  const [jobQuery, setJobQuery] = useState("");
  const sources = useResource<ListResult<Source>>(
    "/sources",
    { items: [], total: 0 },
    true,
  );
  const jobSearch = useDebounce(jobQuery);
  const jobs = useResource<ListResult<Job>>(
    taskView ? `/jobs?limit=100&q=${encodeURIComponent(jobSearch)}` : null,
    { items: [], total: 0 },
  );
  const params = new URLSearchParams({ limit: "30", offset: filters.offset });
  for (const key of [
    "state",
    "source_id",
    ...(taskView ? ["kind", "job_id"] : []),
  ])
    if (filters[key]) params.set(key, filters[key]);
  const resource = useResource<ListResult<BackgroundTask | CollectionRun>>(
    `${taskView ? "/tasks" : "/collection/runs"}?${params}`,
    { items: [], total: 0 },
  );
  const { mutate, pending } = useWorkspace();
  const [selected, setSelected] = useState<{ id: string; run: boolean } | null>(
    null,
  );
  const detail = useResource<BackgroundTask | CollectionRun | null>(
    selected
      ? `${selected.run ? "/collection/runs" : "/tasks"}/${selected.id}`
      : null,
    null,
  );
  const active = resource.data.items.some((item) =>
    ["queued", "running"].includes(item.state),
  );
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(resource.reload, 4000);
    return () => clearInterval(timer);
  }, [active]);
  const detailActive =
    detail.data && ["queued", "running"].includes(detail.data.state);
  useEffect(() => {
    if (!detailActive) return;
    const timer = setInterval(detail.reload, 4000);
    return () => clearInterval(timer);
  }, [detailActive, selected?.id]);
  return (
    <>
      <section className="card sectioncard">
        <div className="sectiontitle">
          <div>
            <h2>Activity</h2>
            <p>Follow collection runs and provider waits.</p>
          </div>
          <Button icon="refresh" onClick={resource.reload}>
            Refresh
          </Button>
        </div>
        <Tabs
          label="Activity views"
          value={taskView ? "tasks" : "runs"}
          onChange={(value) =>
            setFilters({
              activity_view: value,
              offset: "0",
              state: "",
              kind: "",
              job_id: "",
            })
          }
          items={[
            { id: "runs", label: "Collection runs" },
            { id: "tasks", label: "All tasks" },
          ]}
        />
        <div className="filter-grid activity-filters">
          <Field label="State">
            <select
              value={filters.state}
              onChange={(e) =>
                setFilters({ state: e.target.value, offset: "0" })
              }
            >
              <option value="">All states</option>
              {["queued", "running", "succeeded", "failed", "cancelled"].map(
                (value) => (
                  <option key={value} value={value}>
                    {value === "queued" ? "Queued / waiting" : value}
                  </option>
                ),
              )}
            </select>
          </Field>
          <Field label="Source">
            <select
              value={filters.source_id}
              onChange={(e) =>
                setFilters({ source_id: e.target.value, offset: "0" })
              }
            >
              <option value="">All sources</option>
              {filters.source_id &&
                !sources.data.items.some((s) => s.id === filters.source_id) && (
                  <option value={filters.source_id}>Selected source</option>
                )}
              {sources.data.items.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          {taskView && (
            <>
              <Field label="Task kind">
                <select
                  value={filters.kind}
                  onChange={(e) =>
                    setFilters({ kind: e.target.value, offset: "0" })
                  }
                >
                  <option value="">All kinds</option>
                  <option value="collect">Collection</option>
                </select>
              </Field>
              <Field label="Job">
                <input
                  type="search"
                  aria-label="Find a job for activity"
                  value={jobQuery}
                  placeholder="Find a job by title or company"
                  onChange={(e) => setJobQuery(e.target.value)}
                />
                <select
                  aria-label="Filter activity by job"
                  value={filters.job_id}
                  onChange={(e) =>
                    setFilters({ job_id: e.target.value, offset: "0" })
                  }
                >
                  <option value="">All jobs</option>
                  {filters.job_id &&
                    !jobs.data.items.some((j) => j.id === filters.job_id) && (
                      <option value={filters.job_id}>Selected job</option>
                    )}
                  {jobs.data.items.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title} · {j.company}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          )}
        </div>
        {resource.error && (
          <ErrorBox message={resource.error} retry={resource.reload} />
        )}
        <div className="task-list">
          {resource.loading ? (
            <Loading />
          ) : resource.data.items.length ? (
            resource.data.items.map((item) => {
              if (!taskView) {
                const run = item as CollectionRun;
                return (
                  <article className="task-entry" key={run.id}>
                    <div className="sectiontitle">
                      <div>
                        <button
                          className="table-link"
                          onClick={() => setSelected({ id: run.id, run: true })}
                        >
                          <h3>{run.source_name}</h3>
                        </button>
                        <p>
                          {formatTime(run.created_at)} ·{" "}
                          {run.task_ids?.length || run.tasks?.length || 0}{" "}
                          provider tasks
                        </p>
                      </div>
                      <span className="smalltext muted">
                        {duration(run.total_seconds)}
                      </span>
                    </div>
                    <RunProgress run={run} />
                    <div className="actions">
                      <Button
                        className="small"
                        onClick={() => setSelected({ id: run.id, run: true })}
                      >
                        Run details
                      </Button>
                      {["queued", "running"].includes(run.state) && (
                        <Button
                          className="small"
                          disabled={pending}
                          onClick={() =>
                            mutate(
                              () =>
                                api(
                                  `/collection/runs/${run.id}/cancel`,
                                  "POST",
                                ),
                              "Current run stopped.",
                            )
                          }
                        >
                          Stop run
                        </Button>
                      )}
                    </div>
                  </article>
                );
              }
              const task = item as BackgroundTask;
              return (
                <article className="task-entry" key={task.id}>
                  <div className="sectiontitle">
                    <div>
                      <button
                        className="table-link"
                        onClick={() => setSelected({ id: task.id, run: false })}
                      >
                        <h3>
                          {task.source_name || task.job_title || task.kind}
                        </h3>
                      </button>
                      <p>
                        {String(task.payload?.provider || "Collection")} ·{" "}
                        {formatTime(task.created_at)}
                      </p>
                    </div>
                    <TaskState task={task} />
                  </div>
                  <TaskSummary task={task} />
                  <TaskActions
                    task={task}
                    onDetails={() => setSelected({ id: task.id, run: false })}
                  />
                </article>
              );
            })
          ) : (
            <Empty title="No activity in this view.">
              Runs and tasks appear here when collection starts.
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
        <Dialog
          title={selected.run ? "Collection run" : "Task details"}
          onClose={() => setSelected(null)}
        >
          {detail.error ? (
            <ErrorBox message={detail.error} retry={detail.reload} />
          ) : detail.data ? (
            <>
              {selected.run ? (
                <>
                  <h3>{(detail.data as CollectionRun).source_name}</h3>
                  <RunProgress run={detail.data as CollectionRun} />
                  <p className="hint">
                    Each provider resumes its saved progress. Found and already
                    archived are observations; New counts unique archive
                    records.
                  </p>
                  {(detail.data as CollectionRun).tasks?.map((task) => (
                    <article className="task-entry" key={task.id}>
                      <div className="sectiontitle">
                        <h3>{String(task.payload?.provider || task.kind)}</h3>
                        <TaskState task={task} />
                      </div>
                      <TaskSummary task={task} />
                      <TaskActions task={task} />
                    </article>
                  ))}
                </>
              ) : (
                <>
                  <h3>
                    {(detail.data as BackgroundTask).source_name ||
                      (detail.data as BackgroundTask).job_title ||
                      (detail.data as BackgroundTask).kind}
                  </h3>
                  <TaskState task={detail.data as BackgroundTask} />
                  <TaskSummary task={detail.data as BackgroundTask} />
                  <TaskActions task={detail.data as BackgroundTask} />
                </>
              )}
              <details className="collection-advanced">
                <summary>Technical details and frozen settings</summary>
                <pre
                  className="json-readout"
                  tabIndex={0}
                  role="region"
                  aria-label="Technical details"
                >
                  {JSON.stringify(detail.data, null, 2)}
                </pre>
              </details>
            </>
          ) : (
            <Loading />
          )}
        </Dialog>
      )}
    </>
  );
}
function TaskState({ task }: { task: BackgroundTask }) {
  const waiting =
    task.state === "queued" &&
    !!task.next_run_at &&
    new Date(task.next_run_at).valueOf() > Date.now();
  return (
    <span
      className={`tag ${task.state === "failed" ? "amber" : task.state === "succeeded" ? "green" : "neutral"}`}
    >
      {waiting ? "Waiting" : task.state}
    </span>
  );
}
function TaskSummary({ task }: { task: BackgroundTask }) {
  const waiting = task.state === "queued",
    counts = task.result || {};
  return (
    <div className="task-summary">
      {task.error && (
        <p className={waiting ? "hint" : "source-error"}>{task.error}</p>
      )}
      {waiting && task.next_run_at && (
        <p className="smalltext muted">
          Next attempt {formatTime(task.next_run_at)}
        </p>
      )}
      <p className="smalltext muted">
        {[
          ["received", "Found"],
          ["created", "New"],
          ["existing", "Already archived"],
          ["invalid", "Invalid"],
          ["pending_descriptions", "Pending text"],
          ["unavailable_descriptions", "Text unavailable"],
        ]
          .filter(([key]) => typeof counts[key] === "number")
          .map(([key, label]) => `${label}: ${counts[key]}`)
          .join(" · ")}
      </p>
      {!!task.attempts && (
        <p className="smalltext muted">{task.attempts} attempts</p>
      )}
    </div>
  );
}
function TaskActions({
  task,
  onDetails,
}: {
  task: BackgroundTask;
  onDetails?: () => void;
}) {
  const { mutate, pending } = useWorkspace();
  return (
    <div className="actions">
      {onDetails && (
        <Button className="small" onClick={onDetails}>
          Details
        </Button>
      )}
      {["queued", "running"].includes(task.state) ? (
        <Button
          className="small"
          disabled={pending}
          onClick={() =>
            mutate(
              () => api(`/tasks/${task.id}/cancel`, "POST"),
              "Task stopped.",
            )
          }
        >
          Stop task
        </Button>
      ) : ["failed", "cancelled"].includes(task.state) ? (
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
  const workspace = useResource<Json>("/workspace", {});
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
          <div>
            <h2>Workspace.</h2>
            <p>
              {String(workspace.data.name || "Openings")}{" "}
              {workspace.data.version
                ? `${String(workspace.data.version)} · `
                : ""}
              Private, single owner workspace
            </p>
          </div>
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
            <p>Use a light or dark theme.</p>
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
        className="password-form"
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
        <div className="actions form-actions">
          <Button type="submit" variant="primary" disabled={pending}>
            Change password
          </Button>
        </div>
      </form>
      <div className="divider" />
      <p className="hint">Your job search workspace</p>
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
