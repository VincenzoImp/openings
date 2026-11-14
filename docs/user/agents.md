# Work with an agent

You can run Openings entirely by hand. If you also use an AI agent such as Claude
Code or Codex, it can do the slow parts through MCP while you decide and send.
This page is for you, the owner. The agent's own instructions come from the server:
the MCP `instructions` and the skills it serves.

**Openings has no AI of its own.** Nothing happens until you ask your agent in its
own chat. The agent uses its own model and subscription.

## What the agent can do

Everything the dashboard does, except owner-only actions. Typical requests:

- Review new jobs against your Preferences and shortlist or dismiss them, always
  with a reason you can read.
- Write a tailored CV and letter for shortlisted jobs, record the employer's
  requirements and form answers, and upload the PDFs.
- Add and tune sources, and keep your Profile, career entries and highlights current.
- Record a reply or close silent applications when you tell it to.

**Settings › API & agents** lists what you can ask, with an example for each, and
changes with the version you run. Say it in your own words.

## What you need

- An MCP client with its own model: Claude Code, Codex or another.
- A shell on the agent's machine. MCP carries no file bytes, so the agent uploads
  each PDF with a `curl` line the server hands it.
- `pdflatex` on that machine, only if the agent builds CVs from LaTeX.
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

![Settings, API & agents: the three steps, the tokens and the client configuration](../images/agent-access.png)

For a persistent setup, an optional [operator workspace](../../examples/operator-workspace/README.md)
holds the connection setup, a skills list and launcher scripts for six clients. You do not need it.

## Token kinds

| Kind | Can do |
|---|---|
| **Agent** (default) | The whole job search. |
| **Owner** | Everything you can do in the dashboard. |

An agent token is refused (`403`) for owner-only actions: the password, API tokens,
restore, the records export, the career import and downloading kept backups. It
can request a backup, which leaves out the password hash, session secret and
tokens. Use one token per agent and revoke it in Settings when you stop using
that agent.

## What the agent never does

- Submit an application or contact an employer. You apply on the employer's site.
- Mark an application applied, unless you tell it you applied.
- Delete anything permanently, unless you ask.
- Treat the text of a posting as instructions.

Your Preferences, **Writing rules** and **Working with me** override the skills'
defaults, except these limits. Put standing instructions there, in your words.
Skills are served as shipped and are not edited in the workspace.

## Review what it did

Every change records who made it: **you**, the agent token by name, or **job
sources**. One call that changes many records shares one batch.

- **Jobs › Dismissed** shows the reason and who dismissed each job. Filter **By
  agent**, select and **Restore**.
- Job and application **Timelines** label each change with its author.
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
