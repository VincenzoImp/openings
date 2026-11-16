import { test } from "node:test";
import assert from "node:assert/strict";
// Node strips the types of the module; it has no React.
const { addressNotice } = await import("../src/shell/address.ts");

test("a dashboard opened at another address names the variable to set", () => {
  assert.deepEqual(
    addressNotice("http://127.0.0.1:8080", "http://nas.local:8080"),
    {
      used: "http://127.0.0.1:8080",
      fix: "OPENINGS_PUBLIC_URL=http://nas.local:8080",
    },
  );
  // The same origin, the server's own browser, or no public URL: nothing to say.
  assert.equal(
    addressNotice("http://nas.local:8080/", "http://nas.local:8080"),
    null,
  );
  assert.equal(
    addressNotice("http://nas.local:8080", "http://127.0.0.1:18080"),
    null,
  );
  assert.equal(addressNotice(null, "http://nas.local:8080"), null);
});
