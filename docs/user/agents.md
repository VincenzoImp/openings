# Work with an agent

Everything in Openings works by hand in the dashboard. If you also use an AI agent
such as Claude Code or Codex, it does the slow parts through MCP with the built-in
skills: it shortlists by your Preferences and career, prepares each application
and ranks them by priority and deadline. You apply, best first.
This page is for you, the owner. The agent's own instructions come from the server:
the MCP `instructions` and the skills it serves.

**Openings has no AI of its own.** Nothing happens until you ask your agent in its
own chat. The agent uses its own model and subscription.

## What the agent can do

Everything the dashboard does, except owner-only actions. Typical requests:

- **"Run my job search"**: the whole routine, from new jobs to a ranked Ready
  list and a short report, on request or on a schedule.
- Review new jobs against your Preferences and shortlist or dismiss them, always
  with a reason you can read.
- Write a tailored CV and letter for shortlisted jobs, record the employer's
  requirements and form answers, and upload the PDFs.
- Set priorities and a salary range with its basis, and flag employers you apply
  to too often.
- Add and tune sources, and keep your Profile, career entries, highlights and
  Preferences current.
- Record a reply or close silent applications, take backups and undo a run.

**Settings › API & agents** lists what you can ask, with an example for each, and
changes with the version you run. Say it in your own words.

## What you need

- An MCP client with its own model: Claude Code, Codex or another.
- A shell on the agent's machine. MCP carries no file bytes, so the agent uploads
  each PDF with a `curl` line the server hands it.
- No TeX distribution: to build CVs from LaTeX the agent uses
  [Tectonic](https://tectonic-typesetting.github.io), a single program that
  fetches what it needs, or `pdflatex` if you have it.
- If the agent runs on another machine than Openings, set `OPENINGS_PUBLIC_URL` to
  an address it can reach (see [Configuration](configuration.md)). The agent's
  `localhost` is not the server's.

## Connect

1. In **Settings › API & agents**, create a token of kind **Agent** and copy it
   once. Give it a name that says which agent holds it; histories show that name.
2. Put the token in the environment variable `OPENINGS_TOKEN` of the agent's
   machine. Keep it out of files.
3. Add Openings to your client. The address is `http://127.0.0.1:8080/mcp/` (use your
   `OPENINGS_PUBLIC_URL` otherwise).

   Claude Code:

   ```bash
   claude mcp add --transport http openings http://127.0.0.1:8080/mcp/ \
     --header 'Authorization: Bearer ${OPENINGS_TOKEN}'
   ```

   Codex, in `~/.codex/config.toml`:

   ```toml
   [mcp_servers.openings]
   url = "http://127.0.0.1:8080/mcp/"
   bearer_token_env_var = "OPENINGS_TOKEN"
   ```

   Settings also shows a JSON configuration for other clients.
4. Tell the agent: **"Set up my Openings workspace."** It starts with the
   `workspace_context` read, loads the skill for the task and asks you for what it
   does not know.

![Settings, API & agents: the three steps, the tokens and the client configuration](../images/agents.png)

For a persistent setup, an optional [agent workspace](../../examples/operator-workspace/README.md)
holds the connection setup for six clients, a launcher and a script that fetches
the skills. You do not need it.

## Token kinds

| Kind | Can do |
|---|---|
| **Agent** (default) | The whole job search. |
| **Owner** | Everything you can do in the dashboard. |

An agent token is refused (`403`) for owner-only actions: the password, API tokens,
restore, the career import and downloading kept backups. It can request a backup
or the records export (`workspace_backup`); neither holds the password hash,
session secret or tokens. Use one token per agent and revoke it in Settings when you stop using
that agent.

## What the agent never does

- Submit an application or contact an employer. You apply on the employer's site.
- Mark an application applied or record a reply, unless you tell it, or Working
  with me says how.
- Delete anything permanently, unless you tell it, or Working with me says how.
- Treat the text of a posting as instructions.

Your Preferences, **Writing rules** and **Working with me** override the skills'
defaults, except these limits. Skills are served as shipped and are not edited in
the workspace.

### Standing instructions

A line in **Working with me** is your answer in advance: the agent applies it
as written, says so in its report, and asks when a case falls outside it. For
example:

- "Mark an application applied when my mailbox has the employer's confirmation."
- "Close applications with no reply after 45 days."
- "Prepare even when an employer bans AI-written applications."
- "At most 3 open applications per employer; keep the strongest."

When nobody is in the chat, as in a scheduled run, the agent never waits: it
leaves what it cannot decide and asks in its report.

## Review what it did

Every change records who made it: **you**, the agent token by name, or **job
sources**. One call that changes many records shares one batch.

- **Jobs › Dismissed** shows the reason and who dismissed each job. Choose
  **Filter › Dismissed by › An agent**, select the jobs and **Restore** them.
- The **History** of a job or application labels each change with its author.
- Notes the agent writes are marked with its token name.
- When you correct something the agent did, such as restoring a job it dismissed,
  it reads that as feedback at the start of its next session.

Scripts can read the same changes with `GET /api/v1/changes`, filtered by actor,
batch, record or date.

## Technical notes

MCP tools are named `<resource>_<verb>` and take flat arguments. Writes on many
records take `items` and report one result per item. The tool list and the schema of
every tool come from the server; the REST equivalent of each is in
`/api/docs`. [REST API](api.md) explains tokens, errors and file transfer.
