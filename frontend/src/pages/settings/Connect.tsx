import { useState } from "react";
import { copyText } from "../../api";
import { CodeBlock, SegmentedControl } from "../../design";
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
        <CodeBlock
          label="MCP configuration"
          copyLabel="Copy the MCP configuration"
          onCopy={() => copy(snippet, "Configuration")}
        >
          {snippet}
        </CodeBlock>
        <dl className="dl">
          <dt>MCP</dt>
          <dd>
            <CodeBlock
              inline
              label="MCP address"
              copyLabel="Copy the MCP address"
              onCopy={() => copy(endpoint, "MCP address")}
            >
              {endpoint}
            </CodeBlock>
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
