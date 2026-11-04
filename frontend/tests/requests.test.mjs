import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/api.ts", import.meta.url),
  "utf8",
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
});
const { api, ApiError } = await import(
  "data:text/javascript;base64," + Buffer.from(outputText).toString("base64")
);
globalThis.window = { dispatchEvent() {} };
test("an aborted response body is rejected, never accepted as an empty list", async () => {
  const abort = new AbortController();
  globalThis.fetch = async () => ({
    status: 200,
    ok: true,
    json: async () => {
      abort.abort();
      throw new DOMException("Cancelled", "AbortError");
    },
  });
  await assert.rejects(api("/documents", "GET", undefined, abort.signal), {
    name: "AbortError",
  });
});
test("malformed successful JSON is an actionable error instead of typed empty data", async () => {
  globalThis.fetch = async () => ({
    status: 200,
    ok: true,
    json: async () => {
      throw new SyntaxError("Invalid JSON");
    },
  });
  await assert.rejects(
    api("/jobs"),
    (error) => error instanceof ApiError && error.code === "invalid_response",
  );
});
test("version conflicts retain their record path for editor-local recovery", async () => {
  globalThis.fetch = async () => ({
    status: 409,
    ok: false,
    json: async () => ({ error: { code: "conflict", message: "Changed." } }),
  });
  await assert.rejects(
    api("/jobs/example", "PATCH", {}),
    (error) => error.status === 409 && error.path === "/jobs/example",
  );
});
