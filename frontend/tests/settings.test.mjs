import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the source file; it has no React.
const settings = await import("../src/screens/settings/model.ts");

// An address agents reach that is not the default: another host and port.
const ORIGIN = "https://openings.example.test:18443/";

test("the clients: the plugin first, then Claude Code, Codex and JSON", () => {
  assert.deepEqual(
    settings.CLIENTS.map((client) => client.label),
    ["Claude Code plugin", "Claude Code", "Codex", "JSON"],
  );
});

test("the plugin installs from the marketplace", () => {
  assert.equal(
    settings.connectSnippet("plugin", ORIGIN),
    "/plugin marketplace add VincenzoImp/openings-job-search\n/plugin install openings@openings-job-search",
  );
});

test("claude mcp add names the address and a single-quoted header", () => {
  assert.equal(
    settings.connectSnippet("claude", ORIGIN),
    "claude mcp add --transport http openings https://openings.example.test:18443/mcp/ \\\n  --header 'Authorization: Bearer ${OPENINGS_TOKEN}'",
  );
});

test("Codex reads the token from its variable", () => {
  assert.equal(
    settings.connectSnippet("codex", "http://127.0.0.1:18080"),
    "codex mcp add openings --url http://127.0.0.1:18080/mcp/ \\\n  --bearer-token-env-var OPENINGS_TOKEN",
  );
});

test("any client: JSON with the address and the header", () => {
  assert.deepEqual(JSON.parse(settings.connectSnippet("json", ORIGIN)), {
    mcpServers: {
      openings: {
        type: "http",
        url: "https://openings.example.test:18443/mcp/",
        headers: { Authorization: "Bearer ${OPENINGS_TOKEN}" },
      },
    },
  });
});

test("the shell lines: the token, and the address the plugin needs", () => {
  assert.equal(
    settings.exportLines("http://127.0.0.1:8080/"),
    "export OPENINGS_TOKEN=op_…",
  );
  assert.equal(
    settings.exportLines(ORIGIN),
    "export OPENINGS_TOKEN=op_…\nexport OPENINGS_URL=https://openings.example.test:18443",
  );
  assert.equal(
    settings.exportLines("http://127.0.0.1:18080", "op_synthetic"),
    "export OPENINGS_TOKEN=op_synthetic\nexport OPENINGS_URL=http://127.0.0.1:18080",
  );
  assert.equal(
    settings.tokenLine("op_synthetic"),
    "export OPENINGS_TOKEN=op_synthetic",
  );
});

test("the first session: three prompts in order", () => {
  assert.deepEqual(
    settings.FIRST_SESSION.map((step) => step.prompt),
    [
      "Set up my Openings workspace from my CV",
      "Go through my new jobs",
      "Prepare CV and letter for my shortlist",
    ],
  );
});
