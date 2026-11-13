import { useState } from "react";
import { copyText } from "../../api";
import { Button, SegmentedControl } from "../../design";
import { useWorkspace } from "../../state";

const GUIDE =
  "https://github.com/VincenzoImp/openings/blob/main/docs/user/agent-operated.md";

function snippets(endpoint: string): Record<string, string> {
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

/** The addresses and the client configuration an agent connects with. */
export function Connect({ origin }: { origin: string }) {
  const { notify } = useWorkspace();
  const [client, setClient] = useState("claude-code");
  const endpoint = `${origin}/mcp`;
  const snippet = snippets(endpoint)[client];
  const copy = (value: string, what: string) =>
    copyText(value)
      .then(() => notify(`${what} copied.`))
      .catch(() => notify(`Select and copy the ${what.toLowerCase()}.`));
  return (
    <section className="card" aria-labelledby="connect-title">
      <header>
        <h2 id="connect-title" className="grow">
          Connect an agent
        </h2>
        <Button
          size="sm"
          icon="copy"
          onClick={() => copy(snippet, "Configuration")}
        >
          Copy
        </Button>
      </header>
      <div className="body stack">
        <p>
          Add this to your agent's MCP configuration. Keep the token in the
          OPENINGS_TOKEN environment variable, never in the file; set
          OPENINGS_URL as well for file transfers.
        </p>
        <SegmentedControl
          label="MCP client"
          value={client}
          onChange={setClient}
          options={[
            { id: "claude-code", label: "Claude Code" },
            { id: "codex", label: "Codex" },
            { id: "json", label: "Other (JSON)" },
          ]}
        />
        <pre className="code" tabIndex={0} aria-label="MCP configuration">
          {snippet}
        </pre>
        <dl className="dl">
          <dt>MCP</dt>
          <dd className="mono">
            {endpoint}{" "}
            <button
              type="button"
              className="link"
              onClick={() => copy(endpoint, "MCP address")}
            >
              Copy
              <span className="sr"> the MCP address</span>
            </button>
          </dd>
          <dt>REST</dt>
          <dd className="mono">{origin}/api</dd>
        </dl>
        <p className="caption">
          The skills your agent needs are served by the workspace and match its
          version; see the Skills tab. The agent loads them, onboards your
          career, reviews new jobs and prepares a CV and letter for each
          shortlisted one. You apply on the employer's site and mark the
          application Applied: the agent never submits for you.
        </p>
        <div className="row">
          <a
            className="btn sm"
            href="/api/docs"
            target="_blank"
            rel="noreferrer"
          >
            API reference
          </a>
          <a
            className="btn sm quiet"
            href="/api/v1/capabilities"
            target="_blank"
            rel="noreferrer"
          >
            Available operations
          </a>
          <a
            className="btn sm quiet"
            href={GUIDE}
            target="_blank"
            rel="noreferrer"
          >
            Agent-operated job search guide
          </a>
        </div>
      </div>
    </section>
  );
}
